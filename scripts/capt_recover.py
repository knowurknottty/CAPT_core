#!/usr/bin/env python3
"""Operator-initiated CAPT Node recovery, existing identities only.

A local TTY confirmation is NOT cryptographic human-presence attestation.
No new node/pairing, ledger, provider keys, or HumanApproval is ever created.
"""
from __future__ import annotations
import argparse
import fcntl
import json
import os
import socket
import stat
import struct
import subprocess
import sys
import time
from pathlib import Path

HOME = Path.home()
NODE = HOME / "capt-node-assembled/scripts/capt-node"

def invoke(argv, timeout=15):
    return subprocess.run([str(x) for x in argv], capture_output=True,
                          text=True, timeout=timeout, check=False)

def is_live(path):
    s=socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(0.6)
    try:
        s.connect(path)
        return True
    except OSError:
        return False
    finally:
        s.close()

def node_health(config):
    if not config.is_file() or not NODE.is_file():
        raise RuntimeError("canonical Node config/wrapper missing")
    p=invoke([NODE,"status","--config",config])
    if p.returncode:
        raise RuntimeError("Node status API refused")
    data=json.loads(p.stdout)
    ep=data.get("endpoint","")
    if not ep.startswith("unix:///"):
        raise RuntimeError("unexpected Node socket endpoint")
    return ep[7:], is_live(ep[7:])

def existing_controllers(config):
    p=invoke([NODE,"controllers","--config",config])
    if p.returncode:
        raise RuntimeError("cannot read registered controller IDs")
    found=[]
    for item in json.loads(p.stdout):
        name=item.get("controllerId")
        if not isinstance(name,str) or "/" in name or name in {"",".",".."}:
            continue
        cap=config.parent / (name+".capability.json")
        if not cap.exists():
            continue
        info=cap.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise RuntimeError(f"unsafe capability file metadata: {name}")
        found.append((name,cap))
    return found

def local_runtime(state):
    token_file=state/"runtime.token"
    sock_file=state/"runtime.sock"
    if not token_file.exists() and not sock_file.exists():
        return {"profile":state.name,"state":"not_installed"}
    try:
        metadata=token_file.lstat()
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid() or metadata.st_mode & 0o077:
            return {"profile":state.name,"state":"unsafe_token_metadata"}
        fd=os.open(token_file,os.O_RDONLY | getattr(os,"O_NOFOLLOW",0))
        try:
            token=os.read(fd,4096).decode().strip()
        finally:
            os.close(fd)
        if not token:
            # The authenticated exchange below is the health check.
            # A bare socket probe creates an unauthenticated audit rejection.
            return {"profile":state.name,"state":"unreachable_or_empty_token"}
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as s:
            s.settimeout(3)
            s.connect(str(sock_file))
            def xchg(request):
                payload=json.dumps(request,separators=(",",":")).encode()
                s.sendall(struct.pack(">I",len(payload))+payload)
                def exact(length):
                    result=bytearray()
                    while len(result)<length:
                        piece=s.recv(length-len(result))
                        if not piece: raise OSError("EOF")
                        result.extend(piece)
                    return bytes(result)
                n=struct.unpack(">I",exact(4))[0]
                if n>1048576: raise ValueError("unbounded response")
                return json.loads(exact(n))
            if xchg({"token":token}).get("ok") is not True:
                return {"profile":state.name,"state":"auth_refused"}
            if xchg({"op":"identity"}).get("ok") is not True:
                return {"profile":state.name,"state":"identity_refused"}
        return {"profile":state.name,"state":"authenticated"}
    except (OSError,ValueError,UnicodeError):
        return {"profile":state.name,"state":"ipc_failure"}

def main():
    p=argparse.ArgumentParser()
    mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--status",action="store_true")
    mode.add_argument("--recover",action="store_true")
    p.add_argument("--config",type=Path,default=HOME/".capt-node/node.json")
    p.add_argument("--expires-minutes",type=int,default=240)
    opts=p.parse_args()
    if not 15<=opts.expires_minutes<=1440:
        p.error("expires-minutes must be 15..1440")
    if os.geteuid()==0:
        print("REFUSED: cannot run as root",file=sys.stderr)
        return 2
    if opts.recover:
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            print("REFUSED: requires physical operator terminal, not background agent",file=sys.stderr)
            return 2
        if input("Renew ONLY existing controllers? Type REFRESH: ")!="REFRESH":
            return 2
    config=opts.config.expanduser().resolve()
    # --status is truly read-only: do not create a lockfile just to inspect.
    fd=None
    if opts.recover:
        lock=config.parent/".capt-refresh.lock"
        fd=os.open(lock,os.O_CREAT|os.O_RDWR,0o600)
        try:
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            print("BLOCKED: another recovery is active",file=sys.stderr)
            return 2
    try:
        socket_path,live=node_health(config)
        result={"node": "ready" if live else "unreachable",
                "config":str(config),"renewals":[]}
        if opts.recover and not live:
            logs=config.parent/"logs"
            logs.mkdir(parents=True,exist_ok=True,mode=0o700)
            with (logs/"node-serve.log").open("ab") as logfile:
                subprocess.Popen([str(NODE),"serve","--config",str(config)],
                                 stdin=subprocess.DEVNULL,stdout=logfile,stderr=logfile,
                                 start_new_session=True,close_fds=True)
            for _ in range(30):
                if is_live(socket_path):
                    live=True
                    break
                time.sleep(0.2)
            result["node"]="ready" if live else "start_failed"
        controllers=existing_controllers(config)
        result["existingCapabilityControllers"]=[n for n,_ in controllers]
        if opts.recover and live:
            for name,cap in controllers:
                attempt=invoke([NODE,"mcp-authorize","--config",config,
                                "--controller-id",name,"--capability-file",cap,
                                "--expires-minutes",opts.expires_minutes],timeout=30)
                result["renewals"].append({"controller":name,
                       "state":"renewed" if attempt.returncode==0 else "refused"})
        result["runtimeProfiles"]=[local_runtime(HOME/x)
                  for x in (".capt",".capt-inversion-labs")]
        result["desktopClients"]="must_reconnect_per_client"
        result["remoteOAuth"]="not_renewable_via_local_Node"
        result["presence"]="local_tty_is_not_hardware_attestation"
        print(json.dumps(result,indent=2,sort_keys=True))
        problems=result["node"]!="ready" or any(
            v["state"] not in {"authenticated","not_installed"} for v in result["runtimeProfiles"]
        ) or any(v["state"]!="renewed" for v in result["renewals"])
        return 1 if problems else 0
    except (OSError,RuntimeError,ValueError,subprocess.TimeoutExpired) as err:
        print(json.dumps({"state":"blocked","errorType":type(err).__name__}))
        return 2
    finally:
        if fd is not None:
            fcntl.flock(fd,fcntl.LOCK_UN)
            os.close(fd)

if __name__=="__main__":
    raise SystemExit(main())
