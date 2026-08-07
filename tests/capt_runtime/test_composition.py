from pathlib import Path

from capt_runtime.composition import create_runtime


def test_composition_owns_one_shared_runtime_service(tmp_path: Path) -> None:
    runtime = create_runtime(str(tmp_path / "ledger.db"))
    try:
        command = runtime.command_service("operator", "session")
        assert command.store is runtime.store
        assert command.svc is runtime.service
        assert command.memory_engine is runtime.memory_engine
    finally:
        runtime.close()


def test_openharness_host_uses_composition_registry_once(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "README.md").write_text("# target\n")
    runtime = create_runtime(str(tmp_path / "ledger.db"))
    try:
        first = runtime.openharness_host(
            target_repo=str(target), staging_root=str(tmp_path / "staging-a")
        )
        second = runtime.openharness_host(
            target_repo=str(target), staging_root=str(tmp_path / "staging-b")
        )
        assert first.registry is runtime.registry
        assert second.registry is runtime.registry
        assert runtime.registry.list_drivers() == ["openharness"]
        assert first.memory_engine is runtime.memory_engine
    finally:
        runtime.close()
