"""Separate-process restart proof for test_replay::test_two_process_restart.

Run as a module so it executes in a process distinct from the test runner.
It opens the same on-disk store, performs a full replay and a checkpoint+tail
replay, and prints a JSON line proving they are equivalent.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "contracts" / "generated" / "python"))

from capt_runtime.checkpoint import create_checkpoint  # noqa: E402
from capt_runtime.replay import (  # noqa: E402
    checkpoint_replay,
    full_replay,
    replay_equivalent,
)
from capt_runtime.store import EventStore  # noqa: E402


def main(db_path: str) -> int:
    store = EventStore(db_path)
    full = full_replay(store)
    manifest = create_checkpoint(store, "cp-restart", "2026-08-02T00:09:00Z",
                                  "sha256:" + "0" * 64)
    partial = checkpoint_replay(store, manifest)
    store.close()

    equivalent = replay_equivalent(full, partial)
    print(
        json.dumps(
            {
                "equivalent": equivalent,
                "full_applied": full.applied,
                "replay_applied": partial.applied,
                "full_digest": full.digest(),
                "replay_digest": partial.digest(),
            }
        )
    )
    return 0 if equivalent else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
