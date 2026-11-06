"""Isolated fake Keychain: NEVER read or mutate a live user's secret."""
import base64
import concurrent.futures
import threading
from types import SimpleNamespace

import pytest

from capt_runtime import state_security as ss


def _cp(code, text=""):
    return SimpleNamespace(returncode=code, stdout=text, stderr="")


def _fixture_store(monkeypatch):
    store={}
    history=[]
    lock=threading.Lock()
    monkeypatch.setattr(ss.sys,"platform","darwin")
    monkeypatch.setattr(ss.shutil,"which",lambda name:"/usr/bin/security")
    def security_call(args, **kwargs):
        assert kwargs.get("capture_output") is True
        assert kwargs.get("timeout")==5
        assert args[0]=="security"
        with lock:
            if args[1]=="find-generic-password":
                history.append(tuple(args))
                return _cp(0,store["key"]) if "key" in store else _cp(44)
            # The add arrives as an interactive command on stdin, never in argv.
            assert list(args)==["security","-i"], args
            line=kwargs["input"]
            assert line.endswith("\n") and line.count("\n")==1
            words=line.split()
            history.append(tuple(["security",*words]))
            assert words[0]=="add-generic-password"
            assert "-U" not in words
            if "key" in store:
                return _cp(45)
            store["key"]=words[words.index("-w")+1]
            store.setdefault("argv",[]).append(tuple(args))
            return _cp(0)
    monkeypatch.setattr(ss.subprocess,"run",security_call)
    return store,history


def test_create_once_then_read_same_key_without_update(monkeypatch):
    store,history=_fixture_store(monkeypatch)
    seen_argv=[]
    inner=ss.subprocess.run
    monkeypatch.setattr(ss.subprocess,"run",lambda args,**kw:(seen_argv.append(list(args)),inner(args,**kw))[1])
    a=ss._keychain_key()
    b=ss._keychain_key()
    assert a==b==base64.b64decode(store["key"])
    assert len([x for x in history if x[1]=="add-generic-password"])==1
    assert len(a)==32
    # The key never appears in any process argv (the process table is readable by
    # every same-uid process, which before R0.4 included the remotely driven Node).
    assert all(store["key"] not in arg for argv in seen_argv for arg in argv)


def test_two_concurrent_fresh_processes_resolve_same_winner(monkeypatch):
    store,history=_fixture_store(monkeypatch)
    barrier=threading.Barrier(2)
    real_run=ss.subprocess.run
    def race(args,**kwargs):
        if args[1]=="-i":
            barrier.wait(timeout=3)
        return real_run(args,**kwargs)
    monkeypatch.setattr(ss.subprocess,"run",race)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        a,b=list(executor.map(lambda _:ss._keychain_key(),range(2)))
    assert a==b==base64.b64decode(store["key"])
    assert len([x for x in history if x[1]=="add-generic-password"])==2
    assert all("-U" not in x for x in history)


@pytest.mark.parametrize("error_status",[1,36,55,100])
def test_keychain_errors_fail_closed_not_reinitialize(monkeypatch,error_status):
    calls=[]
    monkeypatch.setattr(ss.sys,"platform","darwin")
    monkeypatch.setattr(ss.shutil,"which",lambda _: "/usr/bin/security")
    def bad(args,**kwargs):
        calls.append(args)
        return _cp(error_status,"")
    monkeypatch.setattr(ss.subprocess,"run",bad)
    with pytest.raises(ss.AtRestProtectionError, match="LOOKUP_FAILED"):
        ss._keychain_key()
    assert len(calls)==1


def test_successful_find_with_empty_data_fails_closed(monkeypatch):
    monkeypatch.setattr(ss.sys,"platform","darwin")
    monkeypatch.setattr(ss.shutil,"which",lambda _: "/usr/bin/security")
    monkeypatch.setattr(ss.subprocess,"run",lambda *args,**kw:_cp(0,""))
    with pytest.raises(ss.AtRestProtectionError,match="STATE_KEY_INVALID_LENGTH"):
        ss._keychain_key()


def test_missing_key_and_failed_creation_does_not_fallback(monkeypatch):
    monkeypatch.setattr(ss.sys,"platform","darwin")
    monkeypatch.setattr(ss.shutil,"which",lambda _: "/usr/bin/security")
    calls=[_cp(44),_cp(1),_cp(44)]
    monkeypatch.setattr(ss.subprocess,"run",lambda *args,**kw:calls.pop(0))
    with pytest.raises(ss.AtRestProtectionError,match="CREATE_FAILED"):
        ss._keychain_key()


def test_later_keychain_swap_detected_before_writes(monkeypatch):
    monkeypatch.setattr(ss.sys,"platform","darwin")
    monkeypatch.setattr(ss.shutil,"which",lambda _: "/usr/bin/security")
    replacement=base64.b64encode(b"y"*32).decode()
    calls=[_cp(44),_cp(0),_cp(0,replacement)]
    monkeypatch.setattr(ss.subprocess,"run",lambda *args,**kw:calls.pop(0))
    with pytest.raises(ss.AtRestProtectionError,match="CHANGED_DURING_INIT"):
        ss._keychain_key()


def test_threaded_state_key_initialization_does_not_generate_many_keys(monkeypatch):
    monkeypatch.delenv("CAPT_STATE_KEY_B64",raising=False)
    monkeypatch.setattr(ss,"_KEY_CACHE",None)
    count=[0]
    lock=threading.Lock()
    def generate():
        with lock:
            count[0]+=1
        return b"a"*32
    monkeypatch.setattr(ss,"_keychain_key",generate)
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
        values=list(executor.map(lambda _:ss.state_key(),range(50)))
    assert len(set(values))==1
    assert count[0]==1


def test_timeout_raises_stable_code_without_command_line(monkeypatch, caplog):
    """A TimeoutExpired carries the full command; it must not escape into logs."""
    import logging
    import subprocess
    import traceback
    caplog.set_level(logging.DEBUG)
    monkeypatch.setattr(ss.sys,"platform","darwin")
    monkeypatch.setattr(ss.shutil,"which",lambda _: "/usr/bin/security")
    secret=base64.b64encode(b"s"*32).decode()
    calls=[]
    def run(args,**kw):
        calls.append(args)
        if len(calls)==1:
            return _cp(44)
        raise subprocess.TimeoutExpired(cmd=[*args, kw.get("input","")], timeout=5)
    monkeypatch.setattr(ss.subprocess,"run",run)
    monkeypatch.setattr(ss.os,"urandom",lambda n: b"s"*n)
    with pytest.raises(ss.AtRestProtectionError) as exc:
        ss._keychain_key()
    assert str(exc.value)=="STATE_KEYCHAIN_TIMEOUT"
    assert exc.value.__cause__ is None and exc.value.__suppress_context__ is True
    rendered="".join(traceback.format_exception(exc.value))
    logging.getLogger("capt").exception("keychain failure", exc_info=exc.value)
    assert secret not in rendered and secret not in caplog.text and "-w" not in rendered


def test_missing_security_binary_fails_closed(monkeypatch):
    monkeypatch.setattr(ss.sys,"platform","darwin")
    monkeypatch.setattr(ss.shutil,"which",lambda _: "/usr/bin/security")
    def gone(*a,**k):
        raise FileNotFoundError("security")
    monkeypatch.setattr(ss.subprocess,"run",gone)
    with pytest.raises(ss.AtRestProtectionError,match="STATE_KEYCHAIN_UNAVAILABLE"):
        ss._keychain_key()


def test_no_plaintext_fallback_or_rotation_when_keychain_is_present(monkeypatch, tmp_path):
    """Keychain errors never fall back to ~/.capt/keys, and an existing key is never replaced."""
    monkeypatch.delenv("CAPT_STATE_KEY_B64",raising=False)
    monkeypatch.setattr(ss,"_KEY_CACHE",None)
    monkeypatch.setattr(ss.Path,"home",lambda: tmp_path)
    monkeypatch.setattr(ss.sys,"platform","darwin")
    monkeypatch.setattr(ss.shutil,"which",lambda _: "/usr/bin/security")
    monkeypatch.setattr(ss.subprocess,"run",lambda *a,**k:_cp(36))
    with pytest.raises(ss.AtRestProtectionError):
        ss.state_key()
    assert not (tmp_path/".capt").exists()
    store,history=_fixture_store(monkeypatch)
    store["key"]=base64.b64encode(b"k"*32).decode()
    assert ss.state_key()==b"k"*32
    assert not any(x[1]=="add-generic-password" for x in history)


@pytest.mark.skipif(not (__import__("sys").platform=="darwin" and __import__("os").environ.get("CAPT_KEYCHAIN_LIVE_PROBE")=="1"),
                    reason="real Keychain probe: macOS with CAPT_KEYCHAIN_LIVE_PROBE=1 (uses a disposable keychain)")
def test_real_security_cli_disposable_keychain(tmp_path, monkeypatch):
    """Against the real `security` CLI and a throwaway keychain file: create-once, readback,
    duplicate refusal (exit 45) and no key in argv. Never touches the login keychain."""
    import os
    import secrets
    import subprocess
    keychain=str(tmp_path/"capt-probe.keychain-db")
    password=secrets.token_hex(16)
    before=subprocess.run(["security","list-keychains","-d","user"],capture_output=True,text=True).stdout
    subprocess.run(["security","create-keychain","-p",password,keychain],check=True,capture_output=True)
    try:
        subprocess.run(["security","unlock-keychain","-p",password,keychain],check=True,capture_output=True)
        seen=[]
        real=subprocess.run
        monkeypatch.setattr(ss.subprocess,"run",lambda args,**kw:(seen.append(list(args)),real(args,**kw))[1])
        first=ss._keychain_key(keychain)
        second=ss._keychain_key(keychain)
        assert first==second and len(first)==32
        encoded=base64.b64encode(first).decode()
        assert all(encoded not in a for argv in seen for a in argv)
        dup=real(["security","-i"],input=f"add-generic-password -s {ss._KEYCHAIN_SERVICE} -a {ss._KEYCHAIN_ACCOUNT} -w {base64.b64encode(os.urandom(32)).decode()} {keychain}\n",
                 capture_output=True,text=True,timeout=5)
        assert dup.returncode==45
        assert ss._keychain_key(keychain)==first  # never rotated
    finally:
        subprocess.run(["security","delete-keychain",keychain],capture_output=True)
        after=subprocess.run(["security","list-keychains","-d","user"],capture_output=True,text=True).stdout
        assert after==before
