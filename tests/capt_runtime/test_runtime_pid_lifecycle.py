"""CAPT RuntimeService PID metadata must follow launchd restarts exactly."""
import os
import stat

from desktop.capt_runtime_service import (
    _runtime_pid_path,
    _publish_runtime_pid,
    _clear_runtime_pid_if_owned,
)


def test_atomic_pid_replaces_stale_advertisement(tmp_path):
    sock=tmp_path/"runtime.sock"
    pidfile=_runtime_pid_path(sock)
    pidfile.write_text("100\n")
    assert _publish_runtime_pid(sock,pid=200)==pidfile
    assert pidfile.read_text()=="200\n"
    assert stat.S_IMODE(pidfile.stat().st_mode)==0o600
    assert not list(tmp_path.glob(".runtime-pid-*"))


def test_cleanup_never_erases_newer_successor(tmp_path):
    sock=tmp_path/"runtime.sock"
    _publish_runtime_pid(sock,pid=100)
    _publish_runtime_pid(sock,pid=101)
    assert not _clear_runtime_pid_if_owned(sock,pid=100)
    assert _runtime_pid_path(sock).read_text().strip()=="101"
    assert _clear_runtime_pid_if_owned(sock,pid=101)
    assert not _runtime_pid_path(sock).exists()


def test_symlink_is_replaced_not_followed(tmp_path):
    target=tmp_path/"external.txt"
    target.write_text("DO NOT TOUCH")
    sock=tmp_path/"runtime.sock"
    pidfile=_runtime_pid_path(sock)
    pidfile.symlink_to(target)
    _publish_runtime_pid(sock,pid=300)
    assert not pidfile.is_symlink()
    assert pidfile.read_text()=="300\n"
    assert target.read_text()=="DO NOT TOUCH"


def test_symlink_cleanup_refused(tmp_path):
    target=tmp_path/"target"
    target.write_text("404\n")
    sock=tmp_path/"runtime.sock"
    _runtime_pid_path(sock).symlink_to(target)
    assert not _clear_runtime_pid_if_owned(sock,pid=404)
    assert target.read_text()=="404\n"


def test_invalid_pids_do_not_replace_existing_metadata(tmp_path):
    import pytest
    sock=tmp_path/"runtime.sock"
    _publish_runtime_pid(sock,pid=500)
    for pid in (0,-1,"500",True):
        with pytest.raises(ValueError,match="RUNTIME_PID_INVALID"):
            _publish_runtime_pid(sock,pid=pid)
    assert _runtime_pid_path(sock).read_text()=="500\n"


def test_missing_pid_metadata_cleanup_is_safe(tmp_path):
    sock=tmp_path/"service.sock"
    assert not _clear_runtime_pid_if_owned(sock,pid=123)
