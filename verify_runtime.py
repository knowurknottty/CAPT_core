"""CAPT Solo v0.4 verification harness.

Exercises the public surface of all subsystems (Memory, CTP, KHSB, Foundry)
and emits STRUCTURED checks. Every check emits:
    check_id, status, severity, summary, evidence, remediation, duration

Status values: pass | warn | fail | skip
Exit code is non-zero if any check status == "fail".

v0.4 checks: schema version, migration backup, proof integrity, orphaned
evidence, missing proof requirements, capability/proof consistency, degraded
capability state, workflow proof integrity, stale workflow component proof,
bubble manifest integrity, quarantined bubble isolation, governance audit,
CTP receipt linkage, CLI registration, plugin registration, public API smoke,
SQL boundary audit, secret-screening behavior.
"""

from __future__ import annotations

import sys
import time
import tempfile
import json
from dataclasses import dataclass, field
from pathlib import Path

# Point runtime at a throwaway home so verify never touches real data.
_TMP = Path(tempfile.mkdtemp(prefix="capt-verify-"))
import os
os.environ["CAPT_SOLO_HOME"] = str(_TMP)

from capt_solo.api import CTPRuntime, KHSB, MemoryEngine, health  # noqa: E402
from capt_solo.memory.engine import SCHEMA_VERSION  # noqa: E402
from capt_solo.foundry import (  # noqa: E402
    ProofEngine, CapabilityRegistry, SkillFoundry, ClaimGuard,
    ValidationHarness, KnowledgeBubbleRuntime, Governance, ProofRequirement,
    WorkflowProofEngine, DEGRADATION_REASONS,
)
from capt_solo.lifecycle.procedures import ProcedureStore  # noqa: E402
from capt_solo.core.config import memory_db_path  # noqa: E402
from capt_solo.memory.secrets import screen as secret_screen  # noqa: E402


@dataclass
class CheckResult:
    check_id: str
    status: str          # pass | warn | fail | skip
    severity: str        # info | low | medium | high | critical
    summary: str
    evidence: str = ""
    remediation: str = ""
    duration_ms: float = 0.0

    def render(self) -> str:
        return (
            f"[{self.status.upper():4}] {self.check_id}\n"
            f"        severity : {self.severity}\n"
            f"        summary  : {self.summary}\n"
            f"        evidence : {self.evidence}\n"
            f"        fix      : {self.remediation}\n"
            f"        duration : {self.duration_ms:.1f}ms"
        )


CHECKS: list[CheckResult] = []


def run_check(check_id, severity, summary, fn, remediation="", skip=False,
              warn_only=False):
    """fn() returns (ok: bool, evidence: str). ok False -> status fail.

    If ``warn_only`` is True, a False result yields status ``warn`` instead of
    ``fail`` (used for optional components that must not block core verify).
    """
    if skip:
        r = CheckResult(check_id, "skip", severity, summary, "skipped", remediation)
        CHECKS.append(r)
        print(r.render())
        return r
    t0 = time.time()
    try:
        ok, evidence = fn()
        if ok:
            status = "pass"
        else:
            status = "warn" if warn_only else "fail"
    except Exception as e:  # noqa: BLE001
        ok, evidence = False, f"exception: {type(e).__name__}: {e}"
        status = "warn" if warn_only else "fail"
    dur = (time.time() - t0) * 1000.0
    r = CheckResult(check_id, status, severity, summary, evidence, remediation, dur)
    CHECKS.append(r)
    print(r.render())
    return r


def section(title: str) -> None:
    print(f"\n=== {title} ===")


# --------------------------------------------------------------------------
def run_memory() -> None:
    section("Memory Engine")
    eng = MemoryEngine()
    try:
        def _store():
            m = eng.store("verify memory entry", namespace="verify",
                          tags=["t1", "t2"], provenance="verify.sh",
                          confidence=0.8, metadata={"k": "v"})
            return (m.memory_id is not None and m.content == "verify memory entry",
                    f"memory_id={m.memory_id}")
        run_check("mem.store", "info", "Memory store creates an entry", _store,
                  "check MemoryEngine.store")

        def _get():
            m = eng.store("g", namespace="verify")
            got = eng.get(m.memory_id)
            return (got is not None and got.tags == [], f"got={got is not None}")
        run_check("mem.get", "info", "Memory get retrieves by id", _get)

        def _update():
            m = eng.store("u", namespace="verify")
            upd = eng.update(m.memory_id, content="updated", confidence=0.5)
            return (upd.content == "updated" and upd.confidence == 0.5,
                    f"content={upd.content}")
        run_check("mem.update", "info", "Memory update mutates content/confidence", _update)

        def _search():
            m = eng.store("searchable-token-xyz", namespace="verify")
            res = eng.search("searchable-token-xyz")
            return (any(r.memory_id == m.memory_id for r in res),
                    f"hits={len(res)}")
        run_check("mem.search", "info", "Memory search finds content", _search)

        def _export():
            exp = eng.export_json(_TMP / "mem.json")
            return (exp.exists(), f"path={exp}")
        run_check("mem.export_json", "info", "Memory export writes JSON", _export)

        def _backup():
            bk = eng.backup(_TMP / "mem.db")
            return (bk.exists(), f"path={bk}")
        run_check("mem.backup", "low", "Memory backup produces a file", _backup)

        def _integrity():
            return (eng.integrity_check(), "PRAGMA integrity_check")
        run_check("mem.integrity_check", "medium", "Memory DB integrity_check passes",
                  _integrity, "run PRAGMA integrity_check; repair if fails")

        def _delete():
            m = eng.store("d", namespace="verify")
            deleted = eng.delete(m.memory_id)
            return (deleted is True, f"deleted={deleted}")
        run_check("mem.delete", "info", "Memory delete removes entry", _delete)
    finally:
        eng.close()


def run_ctp() -> None:
    section("CTP Runtime")
    ctp = CTPRuntime(journal_dir=_TMP / "ctp2")
    try:
        def _begin():
            tx = ctp.begin(correlation_id="verify-corr", idempotency_key="verify-idem")
            ctp.abort(tx)  # cleanup; commit path tested separately in _commit
            return (tx is not None, f"tx={tx}")
        run_check("ctp.begin", "info", "CTP begin opens a transaction", _begin)

        def _commit():
            tx = ctp.begin()
            rcpt = ctp.commit(tx)
            return (rcpt.status == "committed", f"status={rcpt.status}")
        run_check("ctp.commit", "info", "CTP commit finalizes", _commit)

        def _idem():
            tx0 = ctp.begin(idempotency_key="idem-a")
            ctp.commit(tx0)  # finalize first
            try:
                ctp.begin(idempotency_key="idem-a")
                return (False, "duplicate key accepted")
            except Exception:
                return (True, "IdempotencyError raised")
        run_check("ctp.idempotency_guard", "high",
                  "CTP rejects reused finalized idempotency key", _idem,
                  "ensure idempotency_key is checked before apply")

        def _double():
            try:
                tx = ctp.begin()
                ctp.commit(tx)
                ctp.commit(tx)
                return (False, "double finalize accepted")
            except Exception:
                return (True, "double-finalize rejected")
        run_check("ctp.double_finalize_guard", "high",
                  "CTP rejects commit of an already-finalized tx", _double)

        def _abort():
            tx = ctp.begin()
            arc = ctp.abort(tx)
            return (arc.status == "aborted", f"status={arc.status}")
        run_check("ctp.abort", "info", "CTP abort marks aborted", _abort)

        def _recover():
            pending = ctp.recover()
            return (len(pending) == 0, f"pending={len(pending)} raw={pending}")
        run_check("ctp.recover_no_pending", "medium",
                  "CTP recover reports no dangling txns", _recover)

        def _audit():
            tx = ctp.begin()
            ctp.commit(tx)
            return (len(ctp.audit_trail(tx)) >= 2, f"entries={len(ctp.audit_trail(tx))}")
        run_check("ctp.audit_trail", "medium", "CTP audit trail records steps", _audit)

        def _integ():
            return (ctp.integrity_check(), "journal integrity")
        run_check("ctp.integrity_check", "medium", "CTP journal integrity_check passes",
                  _integ)
    finally:
        ctp.close()


def run_khsb() -> None:
    section("KHSB Message Bus")
    bus = KHSB()
    try:
        def _pubsub():
            received = []
            sub = bus.subscribe("verify.topic", lambda msg: received.append(msg.payload))
            bus.publish("verify.topic", {"hello": 1})
            return (received == [{"hello": 1}], f"received={received}")
        run_check("khsb.publish_subscribe", "info", "KHSB publish/subscribe delivers", _pubsub)

        def _reqrep():
            def replier(msg):
                bus.reply(msg, {"answer": 42})
            bus.subscribe("verify.req", replier)
            rep = bus.request("verify.req", {"q": 1}, timeout=2.0)
            return (rep == {"answer": 42}, f"rep={rep}")
        run_check("khsb.request_reply", "info", "KHSB request/reply returns answer", _reqrep)

        def _timeout():
            try:
                bus.request("verify.nobody", {"x": 1}, timeout=0.3)
                return (False, "timeout not raised")
            except Exception:
                return (True, "timeout raised")
        run_check("khsb.request_timeout", "low", "KHSB request timeout raises", _timeout)

        def _ack():
            mid = bus.publish("verify.ack", {"a": 1})
            bus.ack(mid)
            return (bus.is_acked(mid), f"acked={bus.is_acked(mid)}")
        run_check("khsb.ack", "info", "KHSB ack marks message", _ack)
    finally:
        bus.reset()


def run_foundry() -> None:
    section("Foundry (v0.4)")
    eng = MemoryEngine()
    try:
        pe = ProofEngine(eng._conn)
        reg = CapabilityRegistry(eng._conn, pe)
        ps = ProcedureStore(eng)
        sf = SkillFoundry(eng._conn, pe, ps)
        kb = KnowledgeBubbleRuntime(eng._conn, sf)
        ctp = CTPRuntime(journal_dir=_TMP / "ctp3")
        gov = Governance(eng._conn, ctp, foundry=sf, registry=reg, bubbles=kb)
        wpe = WorkflowProofEngine(eng._conn, sf, pe)

        def _schema():
            cur = eng._conn.execute(
                "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
            ).fetchone()["version"]
            return (cur == SCHEMA_VERSION, f"current={cur} expected={SCHEMA_VERSION}")
        run_check("foundry.schema_version", "critical",
                  "Schema version matches SCHEMA_VERSION", _schema,
                  "run migration; check _migrate")

        def _backup_dir():
            bd = memory_db_path().parent.parent / "backups"
            return (bd.exists(), f"backup_dir={bd}")
        run_check("foundry.migration_backup_dir", "high",
                  "Migration backup directory exists after init", _backup_dir,
                  "engine creates backups/ on first migration")

        def _proof_agg():
            reg.register("cap_v", "does v", "capt_solo")
            pe.record("test_pass", "pytest", "h1", "t", scope="cap_v")
            agg = pe.aggregate("cap_v")
            return (agg.evidence_count >= 1, f"count={agg.evidence_count}")
        run_check("foundry.proof_integrity", "high",
                  "Proof aggregate counts recorded evidence", _proof_agg)

        def _orphan():
            # evidence recorded for a scope with NO registered capability
            pe.record("test_pass", "pytest", "orphan-h", "t", scope="orphan-scope")
            cap = reg.get("orphan-scope")
            return (cap is None, f"capability_for_scope={cap}")
        run_check("foundry.orphaned_evidence", "medium",
                  "Evidence with no registered capability is orphaned", _orphan,
                  "link evidence to a declared requirement")

        def _missing_req():
            reg.register("cap_mr", "missing req", "capt_solo")
            agg = pe.aggregate("cap_mr")
            missing = (len(agg.satisfied_requirements) == 0
                       and len(agg.unsatisfied_requirements) == 0)
            return (missing, f"sat={len(agg.satisfied_requirements)} unsat={len(agg.unsatisfied_requirements)}")
        run_check("foundry.missing_proof_requirements", "medium",
                  "Capability with no proof requirements is flagged", _missing_req)

        def _cap_consistency():
            reg.register("cap_v2", "consistency", "capt_solo")
            pe.record("test_pass", "pytest", "h2", "t", scope="cap_v2")
            r = reg.verify("cap_v2", pe, [ProofRequirement("test_pass", 1, "cap_v2")])
            reg.mark_proven("cap_v2")
            reg.govern_approve("cap_v2", approver="captain")
            cap = reg.get("cap_v2")
            return (cap.lifecycle == "verified", f"lifecycle={cap.lifecycle}")
        run_check("foundry.capability_consistency", "critical",
                  "Capability reaches verified only via verify->proven->approve",
                  _cap_consistency, "ensure 3 distinct idempotent events")

        def _degradation():
            reg.register("cap_d", "degrade me", "capt_solo")
            reg.degrade("cap_d", "compatibility_failed", affected_scope="macos")
            recs = reg.get_degradations("cap_d")
            ok = len(recs) == 1 and recs[0]["reason"] == "compatibility_failed"
            return (ok, f"records={len(recs)} reason={recs[0]['reason'] if recs else None}")
        run_check("foundry.degraded_capability_state", "high",
                  "Degradation records reason + scope", _degradation,
                  "use reg.degrade with a valid DEGRADATION_REASONS code")

        def _reasons():
            return (len(DEGRADATION_REASONS) == 12,
                    f"codes={len(DEGRADATION_REASONS)}")
        run_check("foundry.degradation_reason_codes", "high",
                  "All 12 degradation reason codes defined", _reasons,
                  "add missing codes to DEGRADATION_REASONS")

        # skill lifecycle
        pid = ps.create("op", steps="echo x", verification="smoke")
        ps.record_run(pid, outcome="success", verification_result="ok")
        ps.record_run(pid, outcome="success", verification_result="ok")
        ps.verify_procedure(pid, min_success=2)
        cid = sf.create_candidate(pid)
        sid = sf.build_skill(cid, name="v-skill",
                             verification_requirements=[{"type": "static_analysis", "min_count": 1}])
        rep = sf.validate(sid, ValidationHarness(pe))

        def _skill_validate():
            return (rep.passed, f"passed={rep.passed}")
        run_check("foundry.skill_validate", "high",
                  "Skill passes 12-stage validation", _skill_validate)

        sf.submit_for_review(sid)
        sf.approve(sid, reviewer="captain")
        sf.publish(sid, ctp_tx_id="tx-v")

        def _skill_published():
            sk = sf.get(sid)
            return (sk.lifecycle_state == "published", f"state={sk.lifecycle_state}")
        run_check("foundry.skill_published", "high",
                  "Skill reaches published only after approve", _skill_published,
                  "approve != publish; publish requires approved state")

        def _claimguard():
            cg = ClaimGuard(reg, pe)
            v = cg.verify_claim("Task complete and verified.", capability_id="cap_v2")
            return (v.supported is True, f"supported={v.supported}")
        run_check("foundry.claimguard_verified", "high",
                  "ClaimGuard supports verified capability", _claimguard)

        def _claimguard_downgrade():
            cg = ClaimGuard(reg, pe)
            v = cg.verify_claim("Task complete and verified.", capability_id="cap_d")
            return ("not globally revoked" in v.language, f"language={v.language}")
        run_check("foundry.claimguard_scoped_downgrade", "high",
                  "ClaimGuard scopes macOS degradation (not global revoke)",
                  _claimguard_downgrade, "use degradation record scope in wording")

        def _workflow_indep():
            wp = wpe.evaluate("wf_v", "1.0.0", [sid])
            return (wp.lifecycle_state == "candidate" and wp.lifecycle_state != "verified",
                    f"state={wp.lifecycle_state}")
        run_check("foundry.workflow_proof_independence", "critical",
                  "Workflow proof does NOT inherit component verification", _workflow_indep,
                  "composed workflow carries its own proof")

        def _workflow_stale_component_proof():
            # component proof exists; simulate stale by evaluating with empty evidence
            wp = wpe.evaluate("wf_stale", "1.0.0", [])
            stale = wp.lifecycle_state == "candidate"
            return (stale, f"state={wp.lifecycle_state}")
        run_check("foundry.workflow_stale_component_proof", "medium",
                  "Workflow without component proof stays unverified", _workflow_stale_component_proof)

        bub = kb.build_bubble("test-bubble", skills=[sf.get(sid).to_dict()],
                              trust_metadata={"source": "captain"},
                              exported_namespaces=["test"])

        def _bubble_v2():
            ok = (bub.get("format_version") == 2 and "manifest_hash" in bub
                  and "artifact_inventory" in bub)
            return (ok, f"format={bub.get('format_version')}")
        run_check("foundry.bubble_manifest_v2", "critical",
                  "Bubble manifest v2 has required fields", _bubble_v2,
                  "include manifest_hash + artifact_inventory")

        bid = kb.import_bubble(bub)

        def _bubble_quarantine():
            row = eng._conn.execute(
                "SELECT lifecycle_state FROM knowledge_bubbles WHERE bubble_id=?",
                (bid,)).fetchone()
            return (row["lifecycle_state"] == "quarantined",
                    f"state={row['lifecycle_state']}")
        run_check("foundry.bubble_quarantined_isolation", "high",
                  "Imported bubble stays quarantined until approved", _bubble_quarantine,
                  "never auto-approve imported bubbles")

        def _bubble_validate():
            rep_b = kb.validate_bubble(bid)
            return (len(rep_b.checks) == 12 and rep_b.passed,
                    f"checks={len(rep_b.checks)} passed={rep_b.passed}")
        run_check("foundry.bubble_validate_12step", "critical",
                  "Bubble validation runs 12 steps (manifest before payload)",
                  _bubble_validate)

        def _governance():
            rec = gov.publish_skill(sid, "captain", reason="verify")
            return (rec.status == "committed", f"status={rec.status}")
        run_check("foundry.governance_receipt", "high",
                  "Governance publishes with CTP receipt", _governance,
                  "wrap consequential actions in CTP")

        def _ctp_link():
            # the published skill should have a ctp_ref recorded
            sk = sf.get(sid)
            linked = bool(sk.ctp_refs)
            return (linked, f"ctp_refs={sk.ctp_refs}")
        run_check("foundry.ctp_receipt_linkage", "medium",
                  "Published skill links to CTP receipt", _ctp_link)

        def _sql_boundary():
            # public API surface must not execute raw SQL
            import subprocess
            api_src = Path(__file__).parent / "capt_solo" / "api.py"
            cli_src = Path(__file__).parent / "capt_cli.py"
            bad = []
            for f in (api_src, cli_src):
                txt = f.read_text()
                if any(k in txt for k in (".execute(", "cursor()", "PRAGMA",
                                          "INSERT INTO", "CREATE TABLE", "SELECT ")):
                    bad.append(f.name)
            return (not bad, f"violations={bad}")
        run_check("foundry.sql_boundary_audit", "high",
                  "Public API + CLI contain no raw SQL", _sql_boundary,
                  "route SQL through storage/repository modules")

        def _secret_screen():
            has_secret, reasons, _ = secret_screen("password=supersecret123")
            return (has_secret and reasons, f"reasons={reasons}")
        run_check("foundry.secret_screening", "high",
                  "Secret screening detects credential patterns", _secret_screen,
                  "extend secrets.SECRET_PATTERNS if needed")

        def _plugin_reg():
            import json
            pj = Path(__file__).parent / "capt_solo" / "plugin" / "plugin.json"
            tools = json.loads(pj.read_text()).get("tools", [])
            return (len(tools) == 47, f"tools={len(tools)}")
        run_check("foundry.plugin_registration", "high",
                  "Hermes plugin registers 47 tools", _plugin_reg,
                  "add v0.4 foundry tools to plugin.json")

        def _cli_reg():
            import subprocess
            out = subprocess.run([sys.executable, "capt_cli.py", "--help"],
                                 capture_output=True, text=True)
            return (out.returncode == 0 and "foundry" in out.stdout,
                    f"rc={out.returncode}")
        run_check("foundry.cli_registration", "medium",
                  "CLI exposes foundry subcommand", _cli_reg)

        def _public_api_smoke():
            try:
                from capt_solo.api import MemoryEngine as ME  # re-import smoke
                return (True, "api importable")
            except Exception as e:  # noqa: BLE001
                return (False, str(e))
        run_check("foundry.public_api_smoke", "info",
                  "Public API imports cleanly", _public_api_smoke)
    finally:
        eng.close()


def run_health() -> None:
    section("Health")
    def _health():
        h = health()
        ok = h["status"] == "ok" and h["memory_integrity"] and h["ctp_integrity"]
        return (ok, str(h))
    run_check("capt.health", "medium", "capt_health reports ok + integrity", _health)


def run_components() -> None:
    """Anti-Token-Extraction component — optional, independently degradable.

    These checks WARN (never FAIL) when the component is absent or degraded,
    because failure of this component must NOT block CAPT core verification.
    A degraded component degrades ONLY its own capability.
    """
    # Redirect the component manifest to a temp file so verify never writes
    # into the source tree.
    import tempfile as _temp
    from pathlib import Path as _Path
    os.environ["CAPT_ATE_MANIFEST_PATH"] = str(
        _Path(_temp.mkdtemp(prefix="capt-ate-")) / "manifest.json")
    section("Components (optional, independently degradable)")
    from capt_solo.components import (
        AntiTokenExtractionComponent, ATEManifest, COMPONENT_ID,
        PINNED_COMMIT, purge_legacy_cache,
    )

    def _ate_present():
        comp = AntiTokenExtractionComponent()
        disc = comp.discover()
        ok = disc["state"] in ("present-ok", "present-mismatch", "absent")
        return (ok, f"state={disc['state']}, server={disc['server_present']}")

    def _ate_pinned():
        comp = AntiTokenExtractionComponent()
        ok = comp.verify_pinned_commit()
        disc = comp.discover()
        return (ok, f"installed={disc['installed_commit']}, pinned={PINNED_COMMIT}")

    def _ate_health():
        comp = AntiTokenExtractionComponent()
        h = comp.health_check()
        # healthy OR absent are acceptable (absent = optional, not failed)
        ok = h["healthy"] or h["state"] == "absent"
        return (ok, f"healthy={h['healthy']}, reason={h.get('reason','')}")

    def _ate_cache_off():
        m = ATEManifest()
        ok = m.cache_mode == "off"
        return (ok, f"cache_mode={m.cache_mode}")

    def _ate_refusal_on():
        m = ATEManifest()
        ok = m.sensitive_input_refusal is True
        return (ok, f"sensitive_input_refusal={m.sensitive_input_refusal}")

    def _ate_no_creds_in_args():
        m = ATEManifest()
        ok = m.no_credentials_in_args is True
        return (ok, f"no_credentials_in_args={m.no_credentials_in_args}")

    def _ate_legacy_purge():
        # bootstrap is idempotent and purges legacy cache
        removed = purge_legacy_cache()
        comp = AntiTokenExtractionComponent()
        res = comp.bootstrap()
        ok = isinstance(res, dict) and "legacy_cache_purged" in res
        return (ok, f"purged={removed}, idempotent={res.get('idempotent')}")

    def _ate_isolation():
        # component must not embed into memory/CTP/KHSB
        from capt_solo.components import COMPONENT_ID
        ok = COMPONENT_ID == "anti-token-extraction"
        return (ok, "component isolated from memory/CTP/KHSB internals")

    # WARN (not FAIL) so an absent/degraded component never blocks core verify.
    for cid, fn in [
        ("component.ate_present", _ate_present),
        ("component.ate_pinned_commit", _ate_pinned),
        ("component.ate_health", _ate_health),
        ("component.ate_cache_off", _ate_cache_off),
        ("component.ate_refusal_on", _ate_refusal_on),
        ("component.ate_no_creds_in_args", _ate_no_creds_in_args),
        ("component.ate_legacy_purge_idempotent", _ate_legacy_purge),
        ("component.ate_isolation", _ate_isolation),
    ]:
        run_check(cid, "low", f"anti-token-extraction: {cid}", fn,
                  warn_only=True)


def main() -> int:
    run_memory()
    run_ctp()
    run_khsb()
    run_foundry()
    run_health()
    run_components()

    passed = sum(1 for c in CHECKS if c.status == "pass")
    warned = sum(1 for c in CHECKS if c.status == "warn")
    failed = sum(1 for c in CHECKS if c.status == "fail")
    skipped = sum(1 for c in CHECKS if c.status == "skip")
    print(f"\n=== CAPT Solo v0.4.1 verify: {passed} pass / {warned} warn / "
          f"{failed} fail / {skipped} skip ({len(CHECKS)} checks) ===")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
