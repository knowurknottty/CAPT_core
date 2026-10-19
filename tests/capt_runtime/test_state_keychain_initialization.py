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
            history.append(tuple(args))
            if args[1]=="find-generic-password":
                return _cp(0,store["key"]) if "key" in store else _cp(44)
            assert args[1]=="add-generic-password"
            assert "-U" not in args
            if "key" in store:
                return _cp(45)
            store["key"]=args[args.index("-w")+1]
            return _cp(0)
    monkeypatch.setattr(ss.subprocess,"run",security_call)
    return store,history


def test_create_once_then_read_same_key_without_update(monkeypatch):
    store,history=_fixture_store(monkeypatch)
    a=ss._keychain_key()
    b=ss._keychain_key()
    assert a==b==base64.b64decode(store["key"])
    assert len([x for x in history if x[1]=="add-generic-password"])==1
    assert len(a)==32


def test_two_concurrent_fresh_processes_resolve_same_winner(monkeypatch):
    store,history=_fixture_store(monkeypatch)
    barrier=threading.Barrier(2)
    real_run=ss.subprocess.run
    def race(args,**kwargs):
        if args[1]=="add-generic-password":
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
