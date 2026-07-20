"""Shared pytest fixtures for CAPT Solo tests.

Each test gets an isolated runtime home so no test touches real user data and
tests never interfere with one another.
"""

import pytest
from pathlib import Path
import tempfile
import os

from capt_solo.core.config import reset_paths_for_test


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path):
    reset_paths_for_test(tmp_path / "home")
    yield tmp_path / "home"


@pytest.fixture
def mem_engine(isolated_home):
    from capt_solo.memory.engine import MemoryEngine
    eng = MemoryEngine()
    yield eng
    eng.close()


@pytest.fixture
def ctp_runtime(isolated_home):
    from capt_solo.ctp.journal import CTPRuntime
    rt = CTPRuntime()
    yield rt
    rt.close()


@pytest.fixture
def bus(isolated_home):
    from capt_solo.khsb.bus import KHSB
    b = KHSB()
    yield b
    b.reset()


@pytest.fixture
def lifecycle_manager(isolated_home):
    from capt_solo.memory.engine import MemoryEngine
    from capt_solo.lifecycle.manager import LifecycleManager
    from capt_solo.khsb.bus import KHSB
    from capt_solo.ctp.journal import CTPRuntime
    eng = MemoryEngine()
    mgr = LifecycleManager(eng, bus=KHSB(), ctp=CTPRuntime())
    yield mgr
    eng.close()
