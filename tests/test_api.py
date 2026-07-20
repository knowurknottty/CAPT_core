"""Tests for the public API aggregator and core config."""

import os
from pathlib import Path

import pytest

from capt_solo import api
from capt_solo.core import config
from capt_solo.core.errors import (
    BusError, CaptSoloError, ConfigurationError, IdempotencyError,
    IntegrityError, MemoryError_, TransactionError,
)


def test_api_exports_public_symbols():
    for name in ["MemoryEngine", "Memory", "SearchAdapter", "SearchHit",
                 "CTPRuntime", "Receipt", "KHSB", "Message",
                 "health", "home_dir", "data_dir", "memory_db_path",
                 "ctp_journal_dir", "khsb_dir", "backup_dir"]:
        assert hasattr(api, name), name


def test_api_health(isolated_home):
    h = api.health()
    assert h["status"] == "ok"
    assert h["memory_integrity"] is True
    assert h["ctp_integrity"] is True


def test_config_paths(isolated_home):
    assert config.home_dir() == isolated_home
    assert config.data_dir() == isolated_home / "data"
    assert config.memory_db_path() == isolated_home / "data" / "memory.db"
    assert config.ctp_journal_dir() == isolated_home / "data" / "ctp"
    assert config.khsb_dir() == isolated_home / "data" / "khsb"
    assert config.backup_dir() == isolated_home / "backups"


def test_config_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("CAPT_SOLO_HOME", str(tmp_path / "custom"))
    config.ensure_dirs()
    assert config.home_dir() == (tmp_path / "custom")


def test_config_ensure_dirs(isolated_home):
    config.ensure_dirs()
    for d in (config.data_dir(), config.ctp_journal_dir(),
              config.khsb_dir(), config.backup_dir()):
        assert d.is_dir()


def test_error_hierarchy():
    assert issubclass(MemoryError_, CaptSoloError)
    assert issubclass(TransactionError, CaptSoloError)
    assert issubclass(IdempotencyError, TransactionError)
    assert issubclass(BusError, CaptSoloError)
    assert issubclass(IntegrityError, CaptSoloError)
    assert issubclass(ConfigurationError, CaptSoloError)
