"""Machine-checkable M0-A invariants (spec §18, mission items 1-10).

Each entry is a structured assertion the conformance suite evaluates. Keeping
them as data (not prose) means the verification report can show, per invariant,
the exact test that exercised it and its result.
"""

from __future__ import annotations

from typing import List, Dict

INVARIANTS: List[Dict[str, str]] = [
    {
        "id": "I1",
        "statement": "Contracts derive from one neutral schema source (JSON Schema).",
        "evidence": "contracts/schema/*.schema.json; generate.py emits both bindings.",
        "test": "test_contracts::test_schema_is_single_source",
    },
    {
        "id": "I2",
        "statement": "TS and Python bindings are generated reproducibly.",
        "evidence": "check_drift.py; two-generation byte diff.",
        "test": "test_contracts::test_generation_reproducible",
    },
    {
        "id": "I3",
        "statement": "Governance, cognition, execution, verification, claim authority are structurally distinct.",
        "evidence": "authority.py deny-by-default matrix; aggregate OWNED_FIELDS disjoint.",
        "test": "test_authority::test_plane_separation",
    },
    {
        "id": "I4",
        "statement": "Mission/Task/Capability/DriverRun/Claim have explicit aggregate ownership.",
        "evidence": "aggregates/*.py OWNED_FIELDS; ownership-disjoint test.",
        "test": "test_aggregates::test_ownership_disjoint",
    },
    {
        "id": "I5",
        "statement": "Consequential state transitions are committed transactionally.",
        "evidence": "store.commit_command single transaction; crash leaves no partial state.",
        "test": "test_ledger::test_atomic_commit",
    },
    {
        "id": "I6",
        "statement": "Durable events are recorded only after valid state transitions.",
        "evidence": "event persisted inside same transaction as state; dispatch post-commit.",
        "test": "test_ledger::test_event_after_state",
    },
    {
        "id": "I7",
        "statement": "Capability grants and leases are scope-bound and auditable.",
        "evidence": "capability.py scope_contains; reservation/consumption records.",
        "test": "test_capability::test_scope_bound",
    },
    {
        "id": "I8",
        "statement": "Runtime state can be checkpointed, restarted, and replayed.",
        "evidence": "checkpoint.py + replay.py; two-process proof.",
        "test": "test_replay::test_two_process_restart",
    },
    {
        "id": "I9",
        "statement": "Replay does not duplicate state transitions.",
        "evidence": "replay reducer skips version<=current; duplicate command idempotent.",
        "test": "test_replay::test_no_duplicate_state",
    },
    {
        "id": "I10",
        "statement": "No implementation or test status is claimed without evidence.",
        "evidence": "this report; every claim cites a command + exit code.",
        "test": "test_contracts::test_invariants_documented",
    },
]


def by_id(inv_id: str) -> Dict[str, str]:
    for inv in INVARIANTS:
        if inv["id"] == inv_id:
            return inv
    raise KeyError(inv_id)
