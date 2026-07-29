#!/usr/bin/env python3
"""Installed-artifact smoke checks for the v0.5 adoption profiles.

This script is intentionally outside the package. Release verification runs it
with the Python interpreter from a clean wheel or sdist environment so imports
cannot silently fall back to the source checkout.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import tempfile
import urllib.request
from pathlib import Path


def _deny_network(*_args, **_kwargs):
    raise AssertionError("network access attempted during installed-artifact smoke")


def _git(repo: Path, *args: str) -> None:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        timeout=20,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())


def _contextpack_smoke():
    from capt_solo.contextpack import (
        Mission,
        MissionIntent,
        RecordRef,
        TokenBudget,
        build_context_pack,
        canonical_json,
        render_handoff,
        validate_context_pack,
    )

    fact = "The verification fixture contains subject version one."
    pack = build_context_pack(
        Mission("profile-smoke", "verify installed artifact", ("validation passes",)),
        MissionIntent(
            "preserve evidence",
            "high",
            ("local only",),
            "artifact is inspectable",
            ("no network",),
        ),
        (),
        invariants=(RecordRef("inv-1", "sha256:inv", "invariant", {"content": "No network."}),),
        evidence=(RecordRef("ev-1", "sha256:ev", "test", {"content": fact}),),
        memory=(),
        receipts=(),
        rendered_context=f"No network. {fact}",
        token_budget=TokenBudget(256, 0, 256, 16, 240, "chars/4", "chars_div_4", "heuristic_estimated"),
        evaluation_clock="2026-07-29T00:00:00Z",
        confidence=1.0,
        assumption_review_status="reviewed_none_found",
        protected_fact_review_status="reviewed",
    )
    validation = validate_context_pack(pack)
    if validation.status != "PASS":
        raise AssertionError(validation.to_dict())
    restored = type(pack).from_dict(json.loads(canonical_json(pack.to_dict())))
    if restored.digest != pack.digest:
        raise AssertionError("ContextPack digest changed during round trip")
    handoff = render_handoff(pack)
    return {
        "digest": pack.digest,
        "validation": validation.status,
        "handoff_digest": handoff.pack_digest,
    }


def run(state_root: Path) -> dict:
    os.environ["CAPT_SOLO_HOME"] = str(state_root / "runtime")

    original_socket = socket.socket
    original_create_connection = socket.create_connection
    original_urlopen = urllib.request.urlopen
    socket.socket = _deny_network
    socket.create_connection = _deny_network
    urllib.request.urlopen = _deny_network
    try:
        import capt_solo
        import capt_solo.api
        import capt_solo.contextpack
        import capt_solo.ctp
        import capt_solo.evidence
        import capt_solo.foundry
        import capt_solo.khsb
        import capt_solo.memory
        import capt_solo.ontology
        import capt_solo.plugin
        import capt_solo.verification
        import capt_solo.workspace

        from capt_solo.evidence import (
            EvidenceClaim,
            EvidenceClass,
            EvidenceRecord,
            EvidenceSource,
            EvidenceStatus,
        )
        from capt_solo.verification import (
            VerificationScope,
            build_vsi,
            diff_vsi,
            vsi_equivalent,
        )
        from capt_solo.ctp import CTPRuntime

        evidence = EvidenceRecord(
            record_id="profile-evidence-1",
            claim=EvidenceClaim("claim-1", "installed artifact imports"),
            evidence_class=EvidenceClass.RUNTIME_OBSERVATION.value,
            source=EvidenceSource("runtime", "tools/profile_smoke.py"),
            status=EvidenceStatus.CURRENT.value,
            confidence=1.0,
            created_at="2026-07-29T00:00:00+00:00",
        )
        evidence_round_trip = EvidenceRecord.from_dict(evidence.to_dict())
        if evidence_round_trip.to_dict() != evidence.to_dict():
            raise AssertionError("EvidenceRecord serialization changed content")

        subject = state_root / "subject"
        subject.mkdir(parents=True)
        _git(subject, "init", "-q")
        _git(subject, "config", "user.email", "release-fixture@example.invalid")
        _git(subject, "config", "user.name", "CAPT Release Fixture")
        artifact = subject / "result.txt"
        artifact.write_text("version one\n", encoding="utf-8")
        _git(subject, "add", "result.txt")
        _git(subject, "commit", "-q", "-m", "fixture")
        first_vsi = build_vsi(str(subject), VerificationScope.FULL, "profile-smoke")
        same_vsi = build_vsi(str(subject), VerificationScope.FULL, "profile-smoke")
        if not vsi_equivalent(first_vsi, same_vsi):
            raise AssertionError("equivalent subject state produced different VSI")
        artifact.write_text("version two\n", encoding="utf-8")
        changed_vsi = build_vsi(str(subject), VerificationScope.FULL, "profile-smoke")
        changes = diff_vsi(first_vsi, changed_vsi)
        if vsi_equivalent(first_vsi, changed_vsi) or not changes:
            raise AssertionError("subject change did not invalidate VSI applicability")

        ctp_dir = state_root / "ctp"
        with CTPRuntime(journal_dir=ctp_dir) as ctp:
            tx_id = ctp.begin(
                correlation_id="profile-smoke",
                idempotency_key="profile-smoke-v1",
                meta={"subject": "result.txt"},
            )
            ctp.validate(tx_id, {"ok": True})
            receipt = ctp.commit(tx_id)
            if receipt.status != "committed" or not ctp.integrity_check():
                raise AssertionError("CTP receipt or integrity verification failed")

        context_result = _contextpack_smoke()
        health = capt_solo.api.health()
        if health.get("status") != "ok":
            raise AssertionError(health)

        module_origins = {
            name: str(module.__file__)
            for name, module in {
                "capt_solo": capt_solo,
                "evidence": capt_solo.evidence,
                "verification": capt_solo.verification,
                "contextpack": capt_solo.contextpack,
                "ctp": capt_solo.ctp,
                "workspace": capt_solo.workspace,
            }.items()
        }
        return {
            "ok": True,
            "profiles": {
                "evidence": {"record_id": evidence.record_id, "serialized": True},
                "verification": {
                    "initial_head": first_vsi.head_commit,
                    "equivalent_reuse": True,
                    "changed_applicability": True,
                    "diff_reasons": changes,
                },
                "context": context_result,
                "transaction": {
                    "tx_id": receipt.tx_id,
                    "status": receipt.status,
                    "integrity": True,
                },
                "workspace": {"imported": True, "persistence": "none"},
                "full_runtime": {"health": health["status"]},
            },
            "network": "blocked and unused",
            "state_root": str(state_root),
            "module_origins": module_origins,
        }
    finally:
        socket.socket = original_socket
        socket.create_connection = original_create_connection
        urllib.request.urlopen = original_urlopen


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-root", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.state_root is None:
        with tempfile.TemporaryDirectory(prefix="capt-profile-smoke-") as tmp:
            result = run(Path(tmp))
    else:
        args.state_root.mkdir(parents=True, exist_ok=True)
        result = run(args.state_root.resolve())
    print(json.dumps(result, indent=2, sort_keys=True) if args.json else result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
