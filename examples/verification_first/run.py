#!/usr/bin/env python3
"""Five-minute, local-only CAPT verification walkthrough.

The example deliberately changes the subject after a successful verification
to demonstrate that evidence applicability is bounded to the verified state.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import urllib.request
from dataclasses import asdict
from pathlib import Path


FIXED_TIME = "2026-07-29T00:00:00+00:00"


def _write_json(path: Path, value) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def _git(repo: Path, *args: str) -> str:
    environment = os.environ.copy()
    environment.update({
        "GIT_AUTHOR_DATE": "2026-07-29T00:00:00+00:00",
        "GIT_COMMITTER_DATE": "2026-07-29T00:00:00+00:00",
    })
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
        timeout=20,
    )
    return result.stdout.strip()


def _deny_network(*_args, **_kwargs):
    raise AssertionError("the verification-first tutorial attempted network I/O")


def _verify_report(report: Path) -> dict:
    text = report.read_text(encoding="utf-8")
    expected = ("Release gate: PASS", "Evidence count: 3")
    missing = [line for line in expected if line not in text]
    return {
        "command": "inspect report.md for the two declared release facts",
        "status": "PASS" if not missing else "FAIL",
        "expected": list(expected),
        "missing": missing,
    }


def run(output: Path) -> dict:
    from capt_solo.contextpack import (
        Mission,
        MissionIntent,
        RecordRef,
        TokenBudget,
        build_context_pack,
        render_handoff,
        validate_context_pack,
    )
    from capt_solo.ctp import CTPRuntime
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

    output.mkdir(parents=True, exist_ok=False)
    os.environ["CAPT_SOLO_HOME"] = str(output / "runtime")
    subject = output / "subject"
    subject.mkdir()
    _git(subject, "init", "-q")
    _git(subject, "config", "user.email", "tutorial@example.invalid")
    _git(subject, "config", "user.name", "CAPT Tutorial")

    report = subject / "report.md"
    report.write_text(
        "# AI-generated release summary\n\n"
        "Release gate: PASS\n"
        "Evidence count: 3\n",
        encoding="utf-8",
    )
    _git(subject, "add", "report.md")
    _git(subject, "commit", "-q", "-m", "record generated report")

    first_result = _verify_report(report)
    first_vsi = build_vsi(
        str(subject),
        VerificationScope.FULL,
        first_result["command"],
    )
    same_vsi = build_vsi(
        str(subject),
        VerificationScope.FULL,
        first_result["command"],
    )
    reuse_allowed = vsi_equivalent(first_vsi, same_vsi)
    verification_id = "verification-release-report-v1"
    evidence = EvidenceRecord(
        record_id="evidence-release-report-v1",
        claim=EvidenceClaim(
            "claim-release-report-v1",
            "report.md contains the two inspected release facts",
            claim_type="acceptance",
            confidence_class="verified",
        ),
        evidence_class=EvidenceClass.VERIFICATION.value,
        source=EvidenceSource(
            "test",
            first_result["command"],
            repository=str(subject),
            branch=first_vsi.active_branch,
            head_commit=first_vsi.head_commit,
            working_tree_state=first_vsi.working_tree_status,
            source_paths=["report.md"],
            environment_identity=first_vsi.runtime_identity,
        ),
        status=EvidenceStatus.CURRENT.value,
        confidence=1.0,
        verification_record_id=verification_id,
        verification_scope=VerificationScope.FULL.value,
        summary="The claim passed against the recorded Verified State Identity.",
        created_at=FIXED_TIME,
    )

    with CTPRuntime(journal_dir=output / "ctp") as runtime:
        tx_id = runtime.begin(
            correlation_id="verification-first-tutorial",
            idempotency_key="verification-first-tutorial-v1",
            meta={
                "claim_id": evidence.claim.claim_id,
                "verification_record_id": verification_id,
            },
        )
        runtime.validate(tx_id, {"ok": first_result["status"] == "PASS"})
        receipt = runtime.commit(tx_id)
        integrity = runtime.integrity_check()

    pack = build_context_pack(
        Mission(
            "verification-first-tutorial",
            "decide whether the generated release claim is supported",
            ("claim is tied to inspectable evidence",),
        ),
        MissionIntent(
            "preserve the user's ability to inspect and reject the claim",
            "high",
            ("local files only",),
            "all facts link to evidence or a receipt",
            ("no network", "no hidden state"),
        ),
        (),
        invariants=(
            RecordRef(
                "invariant-local-only",
                "sha256:local-only",
                "invariant",
                {"content": "No network access is allowed."},
            ),
        ),
        evidence=(
            RecordRef(
                evidence.record_id,
                f"sha256:{first_vsi.scope_file_hashes['report.md']}",
                "verification",
                {"content": evidence.claim.statement},
            ),
        ),
        memory=(),
        receipts=(
            RecordRef(
                receipt.tx_id,
                f"ctp:{receipt.tx_id}",
                "receipt",
                {"content": f"CTP transaction {receipt.status}."},
            ),
        ),
        rendered_context=(
            "No network access is allowed. "
            f"{evidence.claim.statement} "
            f"CTP transaction {receipt.status}."
        ),
        token_budget=TokenBudget(
            512,
            0,
            512,
            48,
            464,
            "chars/4",
            "chars_div_4",
            "heuristic_estimated",
        ),
        evaluation_clock="2026-07-29T00:00:00Z",
        confidence=1.0,
        assumption_review_status="reviewed_none_found",
        protected_fact_review_status="reviewed",
    )
    pack_validation = validate_context_pack(pack)
    handoff = render_handoff(pack)

    _write_json(output / "evidence.json", evidence.to_dict())
    _write_json(output / "verification-before.json", {
        "record_id": verification_id,
        "status": first_result["status"],
        "vsi": asdict(first_vsi),
        "reuse_on_equivalent_state": reuse_allowed,
    })
    _write_json(output / "receipt.json", {
        **receipt.to_dict(),
        "journal_integrity": integrity,
    })
    _write_json(output / "context-pack.json", pack.to_dict())
    _write_json(output / "handoff.json", handoff.to_dict())

    # Now make the generated claim false. The prior evidence stays inspectable
    # but is no longer applicable to the changed state.
    report.write_text(
        "# AI-generated release summary\n\n"
        "Release gate: PASS\n"
        "Evidence count: 2\n",
        encoding="utf-8",
    )
    changed_result = _verify_report(report)
    changed_vsi = build_vsi(
        str(subject),
        VerificationScope.FULL,
        first_result["command"],
    )
    differences = diff_vsi(first_vsi, changed_vsi)
    still_equivalent = vsi_equivalent(first_vsi, changed_vsi)
    applicability = {
        "prior_evidence_status": evidence.status,
        "prior_evidence_applicable": still_equivalent,
        "decision": (
            "REUSE_CURRENT_EVIDENCE"
            if still_equivalent
            else "RUN_TARGETED_VERIFICATION"
        ),
        "changed_verification_status": changed_result["status"],
        "diff_reasons": differences,
    }
    _write_json(output / "verification-after.json", {
        "status": changed_result["status"],
        "vsi": asdict(changed_vsi),
        "result": changed_result,
    })
    _write_json(output / "applicability.json", applicability)

    import capt_solo.contextpack
    import capt_solo.evidence
    import capt_solo.verification

    summary = {
        "ok": (
            first_result["status"] == "PASS"
            and reuse_allowed
            and receipt.status == "committed"
            and integrity
            and pack_validation.status == "PASS"
            and changed_result["status"] == "FAIL"
            and not still_equivalent
        ),
        "before": first_result["status"],
        "equivalent_state_reuse": reuse_allowed,
        "receipt": receipt.status,
        "context_pack": pack_validation.status,
        "after_mutation": changed_result["status"],
        "prior_evidence_applicable_after_mutation": still_equivalent,
        "next_decision": applicability["decision"],
        "network": "blocked and unused",
        "outputs": sorted(path.name for path in output.glob("*.json")),
        "module_origins": {
            "contextpack": str(capt_solo.contextpack.__file__),
            "evidence": str(capt_solo.evidence.__file__),
            "verification": str(capt_solo.verification.__file__),
        },
    }
    _write_json(output / "summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    original_socket = socket.socket
    original_connection = socket.create_connection
    original_urlopen = urllib.request.urlopen
    socket.socket = _deny_network
    socket.create_connection = _deny_network
    urllib.request.urlopen = _deny_network
    try:
        result = run(args.output.resolve())
    finally:
        socket.socket = original_socket
        socket.create_connection = original_connection
        urllib.request.urlopen = original_urlopen
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
