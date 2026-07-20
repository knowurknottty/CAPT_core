"""Memory Engine implementation.

Storage is SQLite (single file, human-readable via ``.dump`` / JSON export).
The schema is versioned (``schema_version`` table) so backward-compatible
migrations can be applied automatically on open.

Public API (stable across v0.1.x):
    - store(content, *, namespace, tags, provenance, confidence, metadata)
    - get(memory_id)
    - update(memory_id, **fields)
    - delete(memory_id)
    - search(query, *, limit, namespace, tags)
    - list(*, namespace, tags, limit)
    - export_json(path)
    - import_json(path, *, merge)
    - backup(path=None) -> path
    - restore(path)
    - integrity_check() -> bool
    - set_search_adapter(adapter)

Extension point: vector search is added later by supplying a
:class:`SearchAdapter` implementation; the public methods above are unchanged.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from capt_solo.core.config import backup_dir, memory_db_path
from capt_solo.core.errors import IntegrityError, MemoryError_
from capt_solo.memory.search import SearchAdapter, default_adapter

SCHEMA_VERSION = 4  # v0.4 adds foundry: capabilities, proof, skills, bubbles, governance


@dataclass
class Memory:
    """Public representation of a stored memory record."""

    memory_id: str
    content: str
    namespace: str
    tags: List[str]
    provenance: str
    confidence: float
    metadata: Dict[str, Any]
    created_at: float
    updated_at: float
    tier: str = "durable"
    lifecycle_state: str = "active"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "content": self.content,
            "namespace": self.namespace,
            "tags": self.tags,
            "provenance": self.provenance,
            "confidence": self.confidence,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "tier": self.tier,
            "lifecycle_state": self.lifecycle_state,
        }


def _now() -> float:
    return time.time()


class MemoryEngine:
    """Local-first memory store backed by SQLite."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._db_path = Path(db_path) if db_path else memory_db_path()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._adapter: SearchAdapter = default_adapter()
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()
        self._rebuild_index()

    # ----- schema / migrations ------------------------------------------
    # Dev-only escape hatch. NEVER enabled in normal operation or verification.
    ALLOW_MIGRATION_WITHOUT_BACKUP = False

    def _backup_before_migration(self, from_version: int) -> Dict[str, Any]:
        """Create a verified pre-migration backup of the persistent database.

        This is a SAFETY GATE, not a convenience. On a persistent DB the
        backup must succeed and validate before any schema mutation is
        applied. If it fails, the migration is aborted.

        Uses SQLite's online ``backup`` API so WAL state is captured
        correctly (a raw file copy can miss un-checkpointed WAL pages).

        Returns a receipt dict. Raises ``MigrationBackupError`` on failure
        unless ``ALLOW_MIGRATION_WITHOUT_BACKUP`` is explicitly enabled
        (development only, emits a severe warning).
        """
        receipt: Dict[str, Any] = {
            "source_version": from_version,
            "target_version": SCHEMA_VERSION,
            "backup_path": None,
            "timestamp": time.time(),
            "success": False,
            "integrity_check": None,
            "error": None,
        }
        # In-memory databases have no filesystem to back up.
        if str(self._db_path) in (":memory:", "") or not self._db_path.exists():
            if str(self._db_path) in (":memory:", ""):
                receipt["error"] = "in-memory database: no filesystem backup possible"
                receipt["success"] = True  # nothing to back up; explicit, documented
                return receipt
            # file path configured but file missing: nothing to back up yet
            receipt["error"] = "source database does not exist; nothing to back up"
            receipt["success"] = True
            return receipt

        backup_dir = self._db_path.parent.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        dest = backup_dir / f"capt_solo.v{from_version}.{stamp}.db"
        # guarantee uniqueness even within the same second
        n = 0
        while dest.exists():
            n += 1
            dest = backup_dir / f"capt_solo.v{from_version}.{stamp}.{n}.db"

        try:
            # Open a SEPARATE connection to the same DB file for the backup so
            # the engine's own connection transaction state cannot deadlock
            # SQLite's online backup (which requires the source not be mid-txn).
            srcconn = sqlite3.connect(str(self._db_path))
            try:
                bconn = sqlite3.connect(str(dest))
                try:
                    srcconn.backup(bconn)
                finally:
                    bconn.close()
            finally:
                srcconn.close()
            # verify the backup opens and passes integrity_check
            vconn = sqlite3.connect(str(dest))
            try:
                rows = vconn.execute("PRAGMA integrity_check").fetchall()
                ok = all(r[0] == "ok" for r in rows)
                receipt["integrity_check"] = "ok" if ok else "corrupt"
                if not ok:
                    raise RuntimeError(f"backup integrity_check failed: {rows}")
            finally:
                vconn.close()
            receipt["backup_path"] = str(dest)
            receipt["success"] = True
            return receipt
        except Exception as e:  # pragma: no cover - defensive
            receipt["error"] = f"{type(e).__name__}: {e}"
            if self.ALLOW_MIGRATION_WITHOUT_BACKUP:
                import sys
                print("[SEVERE WARNING] Migration proceeded WITHOUT a verified "
                      "backup (ALLOW_MIGRATION_WITHOUT_BACKUP=True). Data loss "
                      "risk.", file=sys.stderr)
                receipt["success"] = True
                return receipt
            from capt_solo.core.errors import MigrationBackupError
            raise MigrationBackupError(
                f"pre-migration backup failed for {self._db_path}: {e}") from e

    def _init_schema(self) -> None:
        cur = self._conn.cursor()
        cur.execute(
            "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)"
        )
        cur.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
        row = cur.fetchone()
        current = row["version"] if row else 0
        if current == 0:
            self._create_v1()
            cur.execute("INSERT INTO schema_version (version) VALUES (1)")
            current = 1
            self._conn.commit()  # persist v1 before any backup/migration
        # back up before any forward migration (idempotent: only if upgrading)
        if current < SCHEMA_VERSION:
            self._backup_before_migration(current)
        # apply forward migrations transactionally
        self._migrate(current)
        self._conn.commit()

    def _create_v1(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS memories (
                memory_id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                namespace TEXT NOT NULL DEFAULT 'default',
                provenance TEXT NOT NULL DEFAULT 'unknown',
                confidence REAL NOT NULL DEFAULT 1.0,
                metadata TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                tier TEXT NOT NULL DEFAULT 'durable',
                lifecycle_state TEXT NOT NULL DEFAULT 'active'
            );
            CREATE TABLE IF NOT EXISTS tags (
                memory_id TEXT NOT NULL,
                tag TEXT NOT NULL,
                PRIMARY KEY (memory_id, tag),
                FOREIGN KEY (memory_id) REFERENCES memories(memory_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_mem_namespace ON memories(namespace);
            CREATE INDEX IF NOT EXISTS idx_mem_updated ON memories(updated_at);
            CREATE INDEX IF NOT EXISTS idx_mem_tier ON memories(tier);
            CREATE INDEX IF NOT EXISTS idx_mem_lifecycle ON memories(lifecycle_state);
            CREATE INDEX IF NOT EXISTS idx_tags_tag ON tags(tag);
            """
        )

    def _create_v2(self) -> None:
        """CSG graph + conflict/context tables (v0.2)."""
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS memory_nodes (
                memory_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL DEFAULT 'fact',
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS memory_edges (
                edge_id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                target TEXT NOT NULL,
                edge_type TEXT NOT NULL,
                weight REAL NOT NULL DEFAULT 1.0,
                confidence REAL NOT NULL DEFAULT 1.0,
                provenance TEXT NOT NULL DEFAULT 'unknown',
                created_at REAL NOT NULL,
                ctp_tx_id TEXT,
                FOREIGN KEY (source) REFERENCES memory_nodes(memory_id) ON DELETE CASCADE,
                FOREIGN KEY (target) REFERENCES memory_nodes(memory_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_edges_source ON memory_edges(source);
            CREATE INDEX IF NOT EXISTS idx_edges_target ON memory_edges(target);
            CREATE INDEX IF NOT EXISTS idx_edges_type ON memory_edges(edge_type);

            CREATE TABLE IF NOT EXISTS memory_aliases (
                alias TEXT NOT NULL,
                memory_id TEXT NOT NULL,
                created_at REAL NOT NULL,
                PRIMARY KEY (alias, memory_id)
            );
            CREATE TABLE IF NOT EXISTS memory_conflicts (
                conflict_id TEXT PRIMARY KEY,
                memory_a TEXT NOT NULL,
                memory_b TEXT NOT NULL,
                reason TEXT,
                resolved INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL,
                ctp_tx_id TEXT
            );
            CREATE TABLE IF NOT EXISTS context_builds (
                build_id TEXT PRIMARY KEY,
                query TEXT,
                namespace TEXT,
                created_at REAL NOT NULL,
                item_count INTEGER NOT NULL DEFAULT 0,
                trace_id TEXT
            );
            CREATE TABLE IF NOT EXISTS context_build_items (
                build_id TEXT NOT NULL,
                memory_id TEXT NOT NULL,
                selected INTEGER NOT NULL DEFAULT 1,
                score REAL,
                PRIMARY KEY (build_id, memory_id)
            );
            """
        )

    def _create_v3(self) -> None:
        """Adaptive lifecycle, sessions, procedures, prospective, feedback (v0.3)."""
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS memory_lifecycle_transitions (
                transition_id TEXT PRIMARY KEY,
                memory_id TEXT NOT NULL,
                previous_state TEXT NOT NULL,
                new_state TEXT NOT NULL,
                reason TEXT,
                actor TEXT NOT NULL DEFAULT 'unknown',
                evidence TEXT,
                ctp_tx_id TEXT,
                config_snapshot TEXT,
                trace_id TEXT,
                created_at REAL NOT NULL,
                FOREIGN KEY (memory_id) REFERENCES memories(memory_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_lc_memory ON memory_lifecycle_transitions(memory_id);

            CREATE TABLE IF NOT EXISTS memory_retention_policies (
                namespace TEXT NOT NULL,
                retention_class TEXT NOT NULL DEFAULT 'project',
                decay_rate REAL NOT NULL DEFAULT 0.0,
                PRIMARY KEY (namespace)
            );

            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                project_namespace TEXT NOT NULL,
                objective TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                start_time REAL NOT NULL,
                last_checkpoint REAL,
                active_task TEXT,
                completed_work TEXT,
                files_touched TEXT,
                decisions TEXT,
                failures TEXT,
                hypotheses TEXT,
                ctp_transactions TEXT,
                pending_actions TEXT,
                blockers TEXT,
                unresolved_questions TEXT,
                context_build_ref TEXT,
                restart_packet TEXT,
                close_outcome TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_sess_ns ON sessions(project_namespace);
            CREATE INDEX IF NOT EXISTS idx_sess_status ON sessions(status);

            CREATE TABLE IF NOT EXISTS session_checkpoints (
                checkpoint_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                objective TEXT,
                progress TEXT,
                latest_verified_result TEXT,
                current_hypothesis TEXT,
                pending_transaction TEXT,
                unresolved_failure TEXT,
                files_in_scope TEXT,
                next_action TEXT,
                safety_warning TEXT,
                restart_context TEXT,
                created_at REAL NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_cp_session ON session_checkpoints(session_id);

            CREATE TABLE IF NOT EXISTS session_events (
                event_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload TEXT,
                created_at REAL NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS session_consolidations (
                consolidation_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                reviewable_result TEXT,
                applied INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS procedures (
                procedure_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                trigger TEXT,
                purpose TEXT,
                preconditions TEXT,
                inputs TEXT,
                steps TEXT,
                expected_outputs TEXT,
                verification TEXT,
                failure_modes TEXT,
                recovery_steps TEXT,
                evidence_refs TEXT,
                artifact_refs TEXT,
                version INTEGER NOT NULL DEFAULT 1,
                success_count INTEGER NOT NULL DEFAULT 0,
                failure_count INTEGER NOT NULL DEFAULT 0,
                last_verified_at REAL,
                trust_state TEXT NOT NULL DEFAULT 'candidate',
                lifecycle_state TEXT NOT NULL DEFAULT 'candidate',
                namespace TEXT NOT NULL DEFAULT 'default',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_proc_ns ON procedures(namespace);
            CREATE INDEX IF NOT EXISTS idx_proc_name ON procedures(name);

            CREATE TABLE IF NOT EXISTS procedure_versions (
                procedure_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                name TEXT NOT NULL,
                trigger TEXT,
                purpose TEXT,
                preconditions TEXT,
                inputs TEXT,
                steps TEXT,
                expected_outputs TEXT,
                verification TEXT,
                failure_modes TEXT,
                recovery_steps TEXT,
                evidence_refs TEXT,
                artifact_refs TEXT,
                created_at REAL NOT NULL,
                PRIMARY KEY (procedure_id, version),
                FOREIGN KEY (procedure_id) REFERENCES procedures(procedure_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS procedure_runs (
                run_id TEXT PRIMARY KEY,
                procedure_id TEXT NOT NULL,
                version_used INTEGER NOT NULL,
                inputs TEXT,
                outcome TEXT NOT NULL,
                verification_result TEXT,
                failure_reason TEXT,
                ctp_ref TEXT,
                session_ref TEXT,
                created_at REAL NOT NULL,
                FOREIGN KEY (procedure_id) REFERENCES procedures(procedure_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_run_proc ON procedure_runs(procedure_id);

            CREATE TABLE IF NOT EXISTS prospective_memories (
                intent_id TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                kind TEXT NOT NULL DEFAULT 'task',
                status TEXT NOT NULL DEFAULT 'pending',
                priority TEXT NOT NULL DEFAULT 'normal',
                namespace TEXT NOT NULL DEFAULT 'default',
                source_session TEXT,
                source_memory TEXT,
                prerequisites TEXT,
                blocking_conditions TEXT,
                target_condition TEXT,
                due_date REAL,
                retry_after TEXT,
                evidence TEXT,
                ctp_refs TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                resolved_at REAL
            );
            CREATE INDEX IF NOT EXISTS idx_prosp_ns ON prospective_memories(namespace);
            CREATE INDEX IF NOT EXISTS idx_prosp_status ON prospective_memories(status);

            CREATE TABLE IF NOT EXISTS retrieval_feedback (
                feedback_id TEXT PRIMARY KEY,
                memory_id TEXT,
                context_build_id TEXT,
                session_id TEXT,
                query TEXT,
                feedback_kind TEXT NOT NULL,
                reason TEXT,
                actor TEXT NOT NULL DEFAULT 'unknown',
                trace_id TEXT,
                created_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_fb_memory ON retrieval_feedback(memory_id);

            CREATE TABLE IF NOT EXISTS retrieval_adaptation (
                namespace TEXT NOT NULL,
                key TEXT NOT NULL,
                value REAL NOT NULL,
                updated_at REAL NOT NULL,
                PRIMARY KEY (namespace, key)
            );

            CREATE TABLE IF NOT EXISTS semantic_index_metadata (
                adapter_name TEXT PRIMARY KEY,
                model_identity TEXT,
                model_version TEXT,
                dimensions INTEGER,
                built_at REAL NOT NULL,
                source_version INTEGER NOT NULL
            );
            """
        )

    def _create_v4(self) -> None:
        """v0.4 foundry tables: proof engine, capability registry, skill
        foundry, knowledge bubbles, governance audit.

        Created explicitly via migration (not lazily) so schema state is
        deterministic and verifiable. Idempotent via CREATE IF NOT EXISTS.
        """
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS proof_evidence (
                evidence_id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                producer TEXT NOT NULL,
                timestamp REAL NOT NULL,
                hash TEXT NOT NULL,
                provenance TEXT NOT NULL,
                trust REAL NOT NULL DEFAULT 1.0,
                expiration REAL NOT NULL,
                scope TEXT NOT NULL DEFAULT 'default',
                artifacts TEXT NOT NULL DEFAULT '[]',
                payload TEXT NOT NULL DEFAULT '{}',
                ctp_tx_id TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_proof_scope ON proof_evidence(scope);
            CREATE INDEX IF NOT EXISTS idx_proof_type ON proof_evidence(type);
            CREATE INDEX IF NOT EXISTS idx_proof_hash ON proof_evidence(hash);

            CREATE TABLE IF NOT EXISTS proof_requirements (
                scope TEXT NOT NULL,
                type TEXT NOT NULL,
                min_count INTEGER NOT NULL DEFAULT 1,
                min_trust REAL NOT NULL DEFAULT 0.0,
                PRIMARY KEY (scope, type)
            );

            CREATE TABLE IF NOT EXISTS capabilities (
                identifier TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                provider TEXT NOT NULL,
                required_environment TEXT NOT NULL DEFAULT '',
                required_tools TEXT NOT NULL DEFAULT '[]',
                permissions TEXT NOT NULL DEFAULT '[]',
                dependencies TEXT NOT NULL DEFAULT '[]',
                supported_versions TEXT NOT NULL DEFAULT '[]',
                trust REAL NOT NULL DEFAULT 0.0,
                lifecycle TEXT NOT NULL DEFAULT 'candidate',
                evidence TEXT NOT NULL DEFAULT '[]',
                last_verification REAL NOT NULL DEFAULT 0.0,
                degradation_state TEXT NOT NULL DEFAULT 'none',
                compatibility_matrix TEXT NOT NULL DEFAULT '{}',
                creation_metadata TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_cap_lifecycle ON capabilities(lifecycle);

            CREATE TABLE IF NOT EXISTS skills (
                skill_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                version TEXT NOT NULL,
                compatibility TEXT NOT NULL DEFAULT '',
                trigger TEXT NOT NULL DEFAULT '',
                purpose TEXT NOT NULL DEFAULT '',
                prerequisites TEXT NOT NULL DEFAULT '',
                required_tools TEXT NOT NULL DEFAULT '[]',
                permissions TEXT NOT NULL DEFAULT '[]',
                workflow TEXT NOT NULL DEFAULT '[]',
                expected_outputs TEXT NOT NULL DEFAULT '',
                rollback_strategy TEXT NOT NULL DEFAULT '',
                failure_modes TEXT NOT NULL DEFAULT '',
                recovery_strategy TEXT NOT NULL DEFAULT '',
                verification_requirements TEXT NOT NULL DEFAULT '[]',
                supporting_evidence TEXT NOT NULL DEFAULT '[]',
                trust_state TEXT NOT NULL DEFAULT 'candidate',
                lifecycle_state TEXT NOT NULL DEFAULT 'candidate',
                creation_metadata TEXT NOT NULL DEFAULT '{}',
                ctp_refs TEXT NOT NULL DEFAULT '[]',
                source_procedure TEXT NOT NULL DEFAULT '',
                content_hash TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_skill_lifecycle ON skills(lifecycle_state);
            CREATE INDEX IF NOT EXISTS idx_skill_name ON skills(name);

            CREATE TABLE IF NOT EXISTS skill_candidates (
                candidate_id TEXT PRIMARY KEY,
                source_procedure TEXT NOT NULL,
                skill_id TEXT,
                status TEXT NOT NULL DEFAULT 'candidate',
                notes TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS composite_workflows (
                workflow_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                definition TEXT NOT NULL,
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS workflow_proofs (
                workflow_id TEXT PRIMARY KEY,
                version TEXT NOT NULL,
                definition TEXT NOT NULL,
                lifecycle_state TEXT NOT NULL DEFAULT 'candidate',
                verifier TEXT NOT NULL DEFAULT '',
                governance_ref TEXT NOT NULL DEFAULT '',
                ctp_receipt TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_wf_lifecycle ON workflow_proofs(lifecycle_state);

            CREATE TABLE IF NOT EXISTS knowledge_bubbles (
                bubble_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                lifecycle_state TEXT NOT NULL DEFAULT 'imported',
                definition TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                validation_report TEXT,
                imported_at REAL NOT NULL,
                installed_at REAL,
                approved_by TEXT,
                ctp_tx_id TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_bubble_lifecycle ON knowledge_bubbles(lifecycle_state);

            CREATE TABLE IF NOT EXISTS governance_audit (
                audit_id TEXT PRIMARY KEY,
                action TEXT NOT NULL,
                actor TEXT NOT NULL,
                ctp_tx_id TEXT,
                target TEXT NOT NULL,
                reason TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                timestamp REAL NOT NULL,
                rollback_ref TEXT
            );

            CREATE TABLE IF NOT EXISTS capability_degradations (
                capability TEXT NOT NULL,
                reason TEXT NOT NULL,
                record TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_deg_cap ON capability_degradations(capability);
            """
        )

    def _migrate(self, current: int) -> None:
        """Apply forward migrations. Each step is idempotent and guarded.

        v1 -> v2: add CSG graph tables + conflict/context tables.
        v2 -> v3: add tier/lifecycle_state columns to memories (ALTER,
        backward-compatible defaults), then create the v0.3 tables.
        v3 -> v4: create the v0.4 foundry tables (proof, capabilities,
        skills, bubbles, governance) via explicit migration.
        """
        if current < 2:
            self._create_v2()
            self._conn.execute("INSERT INTO schema_version (version) VALUES (2)")
            self._conn.execute(
                "INSERT OR IGNORE INTO memory_nodes (memory_id, kind, created_at) "
                "SELECT memory_id, 'fact', created_at FROM memories"
            )
        if current < 3:
            # backward-compatible column additions for existing rows
            for col, dflt in (("tier", "'durable'"), ("lifecycle_state", "'active'")):
                try:
                    self._conn.execute(
                        f"ALTER TABLE memories ADD COLUMN {col} TEXT NOT NULL DEFAULT {dflt}"
                    )
                except sqlite3.OperationalError:
                    # column already exists (idempotent re-run)
                    pass
            self._create_v3()
            self._conn.execute("INSERT INTO schema_version (version) VALUES (3)")
            # seed lifecycle_state for any memories lacking one
            self._conn.execute(
                "UPDATE memories SET lifecycle_state='active' WHERE lifecycle_state IS NULL OR lifecycle_state=''"
            )
            self._conn.execute(
                "UPDATE memories SET tier='durable' WHERE tier IS NULL OR tier=''"
            )
        if current < 4:
            self._create_v4()
            self._conn.execute("INSERT INTO schema_version (version) VALUES (4)")

    # ----- index ---------------------------------------------------------
    def set_search_adapter(self, adapter: SearchAdapter) -> None:
        self._adapter = adapter
        self._rebuild_index()

    def _rebuild_index(self) -> None:
        self._adapter.clear()
        for m in self._iter_all():
            self._adapter.index(m.memory_id, m.content, self._meta_for(m))

    def _meta_for(self, m: Memory) -> Dict[str, Any]:
        return {"tags": m.tags, "namespace": m.namespace, "metadata": m.metadata}

    def _iter_all(self) -> List[Memory]:
        rows = self._conn.execute("SELECT * FROM memories").fetchall()
        out = []
        for r in rows:
            tags = [t["tag"] for t in self._conn.execute(
                "SELECT tag FROM tags WHERE memory_id=?", (r["memory_id"],))]
            out.append(self._row_to_memory(r, tags))
        return out

    # ----- public API ----------------------------------------------------
    def store(
        self,
        content: str,
        *,
        namespace: str = "default",
        tags: Optional[List[str]] = None,
        provenance: str = "unknown",
        confidence: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
        tier: str = "durable",
        lifecycle_state: str = "active",
    ) -> Memory:
        if not content:
            raise MemoryError_("content must be non-empty")
        if not (0.0 <= confidence <= 1.0):
            raise MemoryError_("confidence must be between 0.0 and 1.0")
        mid = uuid.uuid4().hex
        now = _now()
        tags = tags or []
        meta = metadata or {}
        cur = self._conn.cursor()
        cur.execute(
            """INSERT INTO memories
               (memory_id, content, namespace, provenance, confidence, metadata,
                created_at, updated_at, tier, lifecycle_state)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (mid, content, namespace, provenance, confidence, json.dumps(meta),
             now, now, tier, lifecycle_state),
        )
        for t in tags:
            cur.execute("INSERT OR IGNORE INTO tags (memory_id, tag) VALUES (?,?)", (mid, t))
        self._conn.commit()
        mem = self.get(mid)
        assert mem is not None
        self._adapter.index(mid, content, self._meta_for(mem))
        return mem

    def get(self, memory_id: str) -> Optional[Memory]:
        row = self._conn.execute(
            "SELECT * FROM memories WHERE memory_id=?", (memory_id,)).fetchone()
        if not row:
            return None
        tags = [t["tag"] for t in self._conn.execute(
            "SELECT tag FROM tags WHERE memory_id=?", (memory_id,))]
        return self._row_to_memory(row, tags)

    def update(
        self,
        memory_id: str,
        *,
        content: Optional[str] = None,
        namespace: Optional[str] = None,
        tags: Optional[List[str]] = None,
        provenance: Optional[str] = None,
        confidence: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tier: Optional[str] = None,
        lifecycle_state: Optional[str] = None,
    ) -> Memory:
        existing = self.get(memory_id)
        if existing is None:
            raise MemoryError_(f"memory_id not found: {memory_id}")
        now = _now()
        fields = []
        params: List[Any] = []
        if content is not None:
            fields.append("content=?")
            params.append(content)
        if namespace is not None:
            fields.append("namespace=?")
            params.append(namespace)
        if provenance is not None:
            fields.append("provenance=?")
            params.append(provenance)
        if confidence is not None:
            if not (0.0 <= confidence <= 1.0):
                raise MemoryError_("confidence must be between 0.0 and 1.0")
            fields.append("confidence=?")
            params.append(confidence)
        if tier is not None:
            fields.append("tier=?")
            params.append(tier)
        if lifecycle_state is not None:
            fields.append("lifecycle_state=?")
            params.append(lifecycle_state)
        if metadata is not None:
            fields.append("metadata=?")
            params.append(json.dumps(metadata))
        if fields:
            fields.append("updated_at=?")
            params.append(now)
            params.append(memory_id)
            self._conn.execute(
                f"UPDATE memories SET {', '.join(fields)} WHERE memory_id=?",
                params,
            )
        if tags is not None:
            self._conn.execute("DELETE FROM tags WHERE memory_id=?", (memory_id,))
            for t in tags:
                self._conn.execute(
                    "INSERT OR IGNORE INTO tags (memory_id, tag) VALUES (?,?)", (memory_id, t))
        self._conn.commit()
        mem = self.get(memory_id)
        assert mem is not None
        self._adapter.index(memory_id, mem.content, self._meta_for(mem))
        return mem

    def delete(self, memory_id: str) -> bool:
        if self.get(memory_id) is None:
            return False
        self._conn.execute("DELETE FROM memories WHERE memory_id=?", (memory_id,))
        self._conn.commit()
        self._adapter.remove(memory_id)
        return True

    # ----- v0.2 internal helpers (used by pipeline/context) ------------
    def _store_raw(
        self, content: str, *, namespace: str = "default",
        tags: Optional[List[str]] = None, provenance: str = "unknown",
        confidence: float = 1.0, metadata: Optional[Dict[str, Any]] = None,
        tier: str = "durable", lifecycle_state: str = "active",
    ) -> "Memory":
        """Insert without re-validation (pipeline already validated)."""
        mid = uuid.uuid4().hex
        now = _now()
        tags = tags or []
        meta = metadata or {}
        cur = self._conn.cursor()
        cur.execute(
            """INSERT INTO memories
               (memory_id, content, namespace, provenance, confidence, metadata,
                created_at, updated_at, tier, lifecycle_state)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (mid, content, namespace, provenance, confidence, json.dumps(meta),
             now, now, tier, lifecycle_state),
        )
        for t in tags:
            cur.execute("INSERT OR IGNORE INTO tags (memory_id, tag) VALUES (?,?)", (mid, t))
        mem = self.get(mid)
        assert mem is not None
        return mem

    def _iter_all_for_context(
        self, *, namespace: Optional[str] = None,
        tags: Optional[List[str]] = None,
        kinds: Optional[List[str]] = None,
    ) -> List["Memory"]:
        """Return all memories (optionally filtered) for context building."""
        rows = self._conn.execute("SELECT * FROM memories").fetchall()
        out = []
        for r in rows:
            tags_r = [t["tag"] for t in self._conn.execute(
                "SELECT tag FROM tags WHERE memory_id=?", (r["memory_id"],))]
            m = self._row_to_memory(r, tags_r)
            if namespace and m.namespace != namespace:
                continue
            if tags and not set(tags).issubset(set(m.tags)):
                continue
            if kinds:
                kind = str((m.metadata or {}).get("kind", "fact"))
                if kind not in kinds:
                    continue
            out.append(m)
        return out

    # ----- v0.2 public: deduplication / conflict / CSG -----------------
    def find_duplicates(self, content: str, *, namespace: str = "default",
                       tags: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Return duplicate candidates for ``content`` against existing memories."""
        from capt_solo.memory.deduplicate import find_duplicates as _fd
        existing = [m.to_dict() for m in self._iter_all()]
        res = _fd(content, namespace, tuple(tags or []), existing)
        return res.value["matches"]

    def add_relation(
        self, source: str, target: str, edge_type: str, *,
        weight: float = 1.0, confidence: float = 1.0,
        provenance: str = "unknown", ctp_tx_id: Optional[str] = None,
    ) -> str:
        """Add a CSG edge between two memories. Returns edge_id."""
        from capt_solo.memory.csg import CSG
        csg = CSG(self._conn)
        return csg.add_edge(source, target, edge_type, weight=weight,
                           confidence=confidence, provenance=provenance,
                           ctp_tx_id=ctp_tx_id)

    def remove_relation(self, edge_id: str) -> bool:
        from capt_solo.memory.csg import CSG
        return CSG(self._conn).remove_edge(edge_id)

    def get_neighbors(self, memory_id: str):
        from capt_solo.memory.csg import CSG
        return CSG(self._conn).get_neighbors(memory_id)

    def find_path(self, source: str, target: str, max_depth: int = 6):
        from capt_solo.memory.csg import CSG
        return CSG(self._conn).find_path(source, target, max_depth)

    def detect_conflicts(self, memory_id: str) -> List[Dict[str, Any]]:
        """Return explicit UNRESOLVED conflicts touching this memory.

        Reads from ``memory_conflicts`` (not the CSG edge table) so that a
        resolved conflict no longer surfaces here.
        """
        rows = self._conn.execute(
            "SELECT * FROM memory_conflicts WHERE resolved=0 AND (memory_a=? OR memory_b=?)",
            (memory_id, memory_id)).fetchall()
        out = []
        for r in rows:
            other = r["memory_b"] if r["memory_a"] == memory_id else r["memory_a"]
            out.append({"conflict_id": r["conflict_id"], "with": other,
                        "reason": r["reason"], "type": "contradicts"})
        return out

    def record_conflict(self, a: str, b: str, *,
                       reason: Optional[str] = None,
                       ctp_tx_id: Optional[str] = None) -> str:
        """Record an explicit conflict between two memories (coexists until resolved)."""
        cid = uuid.uuid4().hex
        self._conn.execute(
            """INSERT INTO memory_conflicts
               (conflict_id, memory_a, memory_b, reason, resolved, created_at, ctp_tx_id)
               VALUES (?,?,?,?,0,?,?)""",
            (cid, a, b, reason, _now(), ctp_tx_id))
        self._conn.commit()
        # also add a CSG contradiction edge for graph traversal
        self.add_relation(a, b, "contradicts", provenance="conflict_review",
                          ctp_tx_id=ctp_tx_id)
        return cid

    def resolve_conflict(self, conflict_id: str) -> bool:
        cur = self._conn.execute(
            "UPDATE memory_conflicts SET resolved=1 WHERE conflict_id=?", (conflict_id,))
        self._conn.commit()
        return cur.rowcount > 0

    def list_conflicts(self, *, unresolved_only: bool = True) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM memory_conflicts"
        if unresolved_only:
            sql += " WHERE resolved=0"
        rows = self._conn.execute(sql).fetchall()
        return [dict(r) for r in rows]

    def mark_superseded(self, memory_id: str, *, by: Optional[str] = None,
                        ctp_tx_id: Optional[str] = None) -> bool:
        """Mark a memory as superseded (penalized in selection, not deleted)."""
        mem = self.get(memory_id)
        if mem is None:
            return False
        meta = dict(mem.metadata)
        meta["status"] = "superseded"
        if by:
            meta["superseded_by"] = by
        self.update(memory_id, metadata=meta)
        if by:
            self.add_relation(by, memory_id, "supersedes",
                              provenance="supersede", ctp_tx_id=ctp_tx_id)
        return True

    def merge(self, source_id: str, target_id: str, *,
              ctp_tx_id: Optional[str] = None) -> bool:
        """Explicit merge: alias source -> target, keep target, mark source superseded.

        Recoverable: the alias is recorded and the source is retained (not
        hard-deleted) so it can be restored from backup or transaction history.
        """
        src = self.get(source_id)
        tgt = self.get(target_id)
        if src is None or tgt is None:
            return False
        now = _now()
        self._conn.execute(
            "INSERT OR IGNORE INTO memory_aliases (alias, memory_id, created_at) VALUES (?,?,?)",
            (source_id, target_id, now))
        # add duplicates edge in CSG
        self.add_relation(source_id, target_id, "duplicates",
                          provenance="merge", ctp_tx_id=ctp_tx_id)
        self.mark_superseded(source_id, by=target_id, ctp_tx_id=ctp_tx_id)
        return True

    def add_alias(self, alias: str, memory_id: str) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO memory_aliases (alias, memory_id, created_at) VALUES (?,?,?)",
            (alias, memory_id, _now()))
        self._conn.commit()

    def resolve_alias(self, alias: str) -> Optional[str]:
        row = self._conn.execute(
            "SELECT memory_id FROM memory_aliases WHERE alias=?", (alias,)).fetchone()
        return row["memory_id"] if row else None

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        namespace: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> List[Memory]:
        hits = self._adapter.search(query, limit=limit * 4)
        out = []
        for h in hits:
            m = self.get(h.memory_id)
            if m is None:
                continue
            if namespace and m.namespace != namespace:
                continue
            if tags and not set(tags).issubset(set(m.tags)):
                continue
            out.append(m)
            if len(out) >= limit:
                break
        return out

    def list(
        self,
        *,
        namespace: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
    ) -> List[Memory]:
        sql = "SELECT memory_id FROM memories"
        where = []
        params: List[Any] = []
        if namespace:
            where.append("namespace=?")
            params.append(namespace)
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        ids = [r["memory_id"] for r in self._conn.execute(sql, params)]
        out = []
        for mid in ids:
            m = self.get(mid)
            if m is None:
                continue
            if tags and not set(tags).issubset(set(m.tags)):
                continue
            out.append(m)
        return out

    # ----- export / import / backup -------------------------------------
    def export_json(self, path: Optional[Path] = None) -> Path:
        target = Path(path) if path else (backup_dir() / f"memory_export_{int(_now())}.json")
        target.parent.mkdir(parents=True, exist_ok=True)
        mem_rows = self._conn.execute(
            "SELECT memory_id, content, namespace, provenance, confidence, "
            "metadata, created_at, updated_at, tier, lifecycle_state FROM memories"
        ).fetchall()
        memories = []
        for r in mem_rows:
            memories.append({
                "memory_id": r["memory_id"],
                "content": r["content"],
                "namespace": r["namespace"],
                "provenance": r["provenance"],
                "confidence": r["confidence"],
                "metadata": json.loads(r["metadata"]),
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
                "tier": r["tier"],
                "lifecycle_state": r["lifecycle_state"],
                "tags": [t["tag"] for t in self._conn.execute(
                    "SELECT tag FROM tags WHERE memory_id=?", (r["memory_id"],))],
            })
        data = {
            "format": "capt-solo-memory",
            "version": SCHEMA_VERSION,
            "exported_at": _now(),
            "memories": memories,
            "edges": [dict(r) for r in self._conn.execute(
                "SELECT edge_id, source, target, edge_type, weight, confidence, "
                "provenance, created_at, ctp_tx_id FROM memory_edges").fetchall()],
            "conflicts": [dict(r) for r in self._conn.execute(
                "SELECT * FROM memory_conflicts").fetchall()],
            "aliases": [dict(r) for r in self._conn.execute(
                "SELECT * FROM memory_aliases").fetchall()],
            # v0.3 lifecycle / session / procedure / prospective / feedback data
            "lifecycle_transitions": [dict(r) for r in self._conn.execute(
                "SELECT * FROM memory_lifecycle_transitions").fetchall()],
            "retention_policies": [dict(r) for r in self._conn.execute(
                "SELECT * FROM memory_retention_policies").fetchall()],
            "sessions": [dict(r) for r in self._conn.execute(
                "SELECT * FROM sessions").fetchall()],
            "session_checkpoints": [dict(r) for r in self._conn.execute(
                "SELECT * FROM session_checkpoints").fetchall()],
            "session_events": [dict(r) for r in self._conn.execute(
                "SELECT * FROM session_events").fetchall()],
            "session_consolidations": [dict(r) for r in self._conn.execute(
                "SELECT * FROM session_consolidations").fetchall()],
            "procedures": [dict(r) for r in self._conn.execute(
                "SELECT * FROM procedures").fetchall()],
            "procedure_versions": [dict(r) for r in self._conn.execute(
                "SELECT * FROM procedure_versions").fetchall()],
            "procedure_runs": [dict(r) for r in self._conn.execute(
                "SELECT * FROM procedure_runs").fetchall()],
            "prospective_memories": [dict(r) for r in self._conn.execute(
                "SELECT * FROM prospective_memories").fetchall()],
            "retrieval_feedback": [dict(r) for r in self._conn.execute(
                "SELECT * FROM retrieval_feedback").fetchall()],
            "retrieval_adaptation": [dict(r) for r in self._conn.execute(
                "SELECT * FROM retrieval_adaptation").fetchall()],
        }
        target.write_text(json.dumps(data, indent=2))
        return target

    def import_json(self, path: Path, *, merge: bool = True) -> int:
        p = Path(path)
        if not p.exists():
            raise MemoryError_(f"import file not found: {p}")
        data = json.loads(p.read_text())
        if data.get("format") != "capt-solo-memory":
            raise MemoryError_("not a CAPT Solo memory export")
        count = 0
        for rec in data.get("memories", []):
            existing = self.get(rec["memory_id"])
            if existing and merge:
                if rec.get("updated_at", 0) >= existing.updated_at:
                    self._upsert(rec)
                    count += 1
            elif not existing:
                self._upsert(rec)
                count += 1
        # seed graph nodes for any memories lacking one (idempotent) BEFORE edges
        self._conn.execute(
            "INSERT OR IGNORE INTO memory_nodes (memory_id, kind, created_at) "
            "SELECT memory_id, 'fact', updated_at FROM memories "
            "WHERE memory_id NOT IN (SELECT memory_id FROM memory_nodes)")
        # restore graph edges (idempotent INSERT OR IGNORE)
        for e in data.get("edges", []):
            self._conn.execute(
                """INSERT OR IGNORE INTO memory_edges
                   (edge_id, source, target, edge_type, weight, confidence,
                    provenance, created_at, ctp_tx_id)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (e["edge_id"], e["source"], e["target"], e["edge_type"],
                 e.get("weight", 1.0), e.get("confidence", 1.0),
                 e.get("provenance", "unknown"), e.get("created_at", _now()),
                 e.get("ctp_tx_id")))
        for c in data.get("conflicts", []):
            self._conn.execute(
                """INSERT OR IGNORE INTO memory_conflicts
                   (conflict_id, memory_a, memory_b, reason, resolved, created_at, ctp_tx_id)
                   VALUES (?,?,?,?,?,?,?)""",
                (c["conflict_id"], c["memory_a"], c["memory_b"], c.get("reason"),
                 c.get("resolved", 0), c.get("created_at", _now()), c.get("ctp_tx_id")))
        for a in data.get("aliases", []):
            self._conn.execute(
                "INSERT OR IGNORE INTO memory_aliases (alias, memory_id, created_at) VALUES (?,?,?)",
                (a["alias"], a["memory_id"], a.get("created_at", _now())))
        # v0.3 tables (idempotent INSERT OR IGNORE)
        for t in data.get("lifecycle_transitions", []):
            self._conn.execute(
                """INSERT OR IGNORE INTO memory_lifecycle_transitions
                   (transition_id, memory_id, previous_state, new_state, reason,
                    actor, evidence, ctp_tx_id, config_snapshot, trace_id, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (t["transition_id"], t["memory_id"], t["previous_state"], t["new_state"],
                 t.get("reason"), t.get("actor"), t.get("evidence"), t.get("ctp_tx_id"),
                 t.get("config_snapshot"), t.get("trace_id"), t.get("created_at")))
        for rp in data.get("retention_policies", []):
            self._conn.execute(
                "INSERT OR IGNORE INTO memory_retention_policies "
                "(namespace, retention_class, decay_rate) VALUES (?,?,?)",
                (rp["namespace"], rp["retention_class"], rp.get("decay_rate", 0.0)))
        for s in data.get("sessions", []):
            self._conn.execute(
                """INSERT OR IGNORE INTO sessions
                   (session_id, project_namespace, objective, status, start_time,
                    last_checkpoint, created_at, updated_at, active_task,
                    completed_work, files_touched, decisions, failures, hypotheses,
                    ctp_transactions, pending_actions, blockers, unresolved_questions,
                    close_outcome)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (s["session_id"], s["project_namespace"], s.get("objective", ""),
                 s.get("status", "active"), s.get("start_time"), s.get("last_checkpoint"),
                 s.get("created_at"), s.get("updated_at"), s.get("active_task"),
                 s.get("completed_work"), s.get("files_touched"), s.get("decisions"),
                 s.get("failures"), s.get("hypotheses"), s.get("ctp_transactions"),
                 s.get("pending_actions"), s.get("blockers"), s.get("unresolved_questions"),
                 s.get("close_outcome")))
        for cp in data.get("session_checkpoints", []):
            self._conn.execute(
                """INSERT OR IGNORE INTO session_checkpoints
                   (checkpoint_id, session_id, version, objective, progress,
                    latest_verified_result, current_hypothesis, pending_transaction,
                    unresolved_failure, files_in_scope, next_action, safety_warning,
                    restart_context, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (cp["checkpoint_id"], cp["session_id"], cp["version"], cp.get("objective", ""),
                 cp.get("progress", ""), cp.get("latest_verified_result", ""),
                 cp.get("current_hypothesis", ""), cp.get("pending_transaction", ""),
                 cp.get("unresolved_failure", ""), cp.get("files_in_scope", "[]"),
                 cp.get("next_action", ""), cp.get("safety_warning", ""),
                 cp.get("restart_context", ""), cp.get("created_at")))
        for ev in data.get("session_events", []):
            self._conn.execute(
                "INSERT OR IGNORE INTO session_events "
                "(event_id, session_id, event_type, payload, created_at) VALUES (?,?,?,?,?)",
                (ev["event_id"], ev["session_id"], ev["event_type"], ev.get("payload", "{}"),
                 ev.get("created_at")))
        for sc in data.get("session_consolidations", []):
            self._conn.execute(
                """INSERT OR IGNORE INTO session_consolidations
                   (consolidation_id, session_id, reviewable_result, applied, created_at)
                   VALUES (?,?,?,?,?)""",
                (sc["consolidation_id"], sc["session_id"], sc.get("reviewable_result", "{}"),
                 sc.get("applied", 0), sc.get("created_at")))
        for pr in data.get("procedures", []):
            self._conn.execute(
                """INSERT OR IGNORE INTO procedures
                   (procedure_id, name, trigger, purpose, preconditions, inputs,
                    steps, expected_outputs, verification, failure_modes,
                    recovery_steps, evidence_refs, artifact_refs, version,
                    success_count, failure_count, last_verified_at, trust_state,
                    lifecycle_state, namespace, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (pr["procedure_id"], pr["name"], pr.get("trigger", ""), pr.get("purpose", ""),
                 pr.get("preconditions", ""), pr.get("inputs", ""), pr.get("steps", ""),
                 pr.get("expected_outputs", ""), pr.get("verification", ""),
                 pr.get("failure_modes", ""), pr.get("recovery_steps", ""),
                 pr.get("evidence_refs", "[]"), pr.get("artifact_refs", "[]"),
                 pr.get("version", 1), pr.get("success_count", 0), pr.get("failure_count", 0),
                 pr.get("last_verified_at"), pr.get("trust_state", "candidate"),
                 pr.get("lifecycle_state", "candidate"), pr.get("namespace", "default"),
                 pr.get("created_at"), pr.get("updated_at")))
        for pv in data.get("procedure_versions", []):
            self._conn.execute(
                """INSERT OR IGNORE INTO procedure_versions
                   (procedure_id, version, name, trigger, purpose, preconditions,
                    inputs, steps, expected_outputs, verification, failure_modes,
                    recovery_steps, evidence_refs, artifact_refs, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (pv["procedure_id"], pv["version"], pv.get("name", ""), pv.get("trigger", ""),
                 pv.get("purpose", ""), pv.get("preconditions", ""), pv.get("inputs", ""),
                 pv.get("steps", ""), pv.get("expected_outputs", ""), pv.get("verification", ""),
                 pv.get("failure_modes", ""), pv.get("recovery_steps", ""),
                 pv.get("evidence_refs", "[]"), pv.get("artifact_refs", "[]"), pv.get("created_at")))
        for run in data.get("procedure_runs", []):
            self._conn.execute(
                """INSERT OR IGNORE INTO procedure_runs
                   (run_id, procedure_id, version_used, inputs, outcome,
                    verification_result, failure_reason, ctp_ref, session_ref, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (run["run_id"], run["procedure_id"], run.get("version_used"),
                 run.get("inputs", ""), run.get("outcome", ""), run.get("verification_result", ""),
                 run.get("failure_reason", ""), run.get("ctp_ref"), run.get("session_ref"),
                 run.get("created_at")))
        for pm in data.get("prospective_memories", []):
            self._conn.execute(
                """INSERT OR IGNORE INTO prospective_memories
                   (intent_id, description, kind, status, priority, namespace,
                    source_session, source_memory, prerequisites, blocking_conditions,
                    target_condition, due_date, retry_after, evidence, ctp_refs,
                    created_at, updated_at, resolved_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (pm["intent_id"], pm["description"], pm.get("kind", "task"), pm.get("status", "pending"),
                 pm.get("priority", "normal"), pm.get("namespace", "default"), pm.get("source_session"),
                 pm.get("source_memory"), pm.get("prerequisites", "[]"), pm.get("blocking_conditions", "[]"),
                 pm.get("target_condition", ""), pm.get("due_date"), pm.get("retry_after", ""),
                 pm.get("evidence", ""), pm.get("ctp_refs", "[]"), pm.get("created_at"),
                 pm.get("updated_at"), pm.get("resolved_at")))
        for fb in data.get("retrieval_feedback", []):
            self._conn.execute(
                """INSERT OR IGNORE INTO retrieval_feedback
                   (feedback_id, memory_id, context_build_id, session_id, query,
                    feedback_kind, reason, actor, trace_id, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (fb["feedback_id"], fb.get("memory_id"), fb.get("context_build_id"),
                 fb.get("session_id"), fb.get("query", ""), fb.get("feedback_kind"),
                 fb.get("reason", ""), fb.get("actor", "unknown"), fb.get("trace_id"),
                 fb.get("created_at")))
        for ra in data.get("retrieval_adaptation", []):
            self._conn.execute(
                "INSERT OR IGNORE INTO retrieval_adaptation "
                "(namespace, key, value, updated_at) VALUES (?,?,?,?)",
                (ra["namespace"], ra["key"], ra.get("value", 0.0), ra.get("updated_at")))
        self._conn.commit()
        self._rebuild_index()
        return count

    def _upsert(self, rec: Dict[str, Any]) -> None:
        mid = rec["memory_id"]
        cur = self._conn.cursor()
        cur.execute(
            """INSERT OR REPLACE INTO memories
               (memory_id, content, namespace, provenance, confidence, metadata,
                created_at, updated_at, tier, lifecycle_state)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (mid, rec["content"], rec.get("namespace", "default"),
             rec.get("provenance", "unknown"), rec.get("confidence", 1.0),
             json.dumps(rec.get("metadata", {})), rec.get("created_at", _now()),
             rec.get("updated_at", _now()), rec.get("tier", "durable"),
             rec.get("lifecycle_state", "active")),
        )
        cur.execute("DELETE FROM tags WHERE memory_id=?", (mid,))
        for t in rec.get("tags", []):
            cur.execute("INSERT OR IGNORE INTO tags (memory_id, tag) VALUES (?,?)", (mid, t))
        self._conn.commit()

    def backup(self, path: Optional[Path] = None) -> Path:
        target = Path(path) if path else (backup_dir() / f"memory_backup_{int(_now())}.db")
        target.parent.mkdir(parents=True, exist_ok=True)
        self._conn.commit()
        # Ensure all WAL content is folded into the main db file before copy
        # so the backup is self-contained and restorable on its own.
        self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        shutil.copyfile(self._db_path, target)
        return target

    def restore(self, path: Path) -> None:
        p = Path(path)
        if not p.exists():
            raise MemoryError_(f"backup not found: {p}")
        self._conn.close()
        shutil.copyfile(p, self._db_path)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()  # ensure schema_version + tables exist after restore
        self._rebuild_index()

    def integrity_check(self) -> bool:
        try:
            rows = self._conn.execute("PRAGMA integrity_check").fetchall()
            ok = all(r[0] == "ok" for r in rows)
            if not ok:
                return False
            # cross-check tag referential integrity
            orphan = self._conn.execute(
                "SELECT COUNT(*) AS c FROM tags t LEFT JOIN memories m "
                "ON t.memory_id=m.memory_id WHERE m.memory_id IS NULL").fetchone()
            return orphan["c"] == 0
        except sqlite3.Error as e:  # pragma: no cover
            raise IntegrityError(f"integrity check failed: {e}")

    def close(self) -> None:
        self._conn.commit()
        self._conn.close()

    # ----- helpers -------------------------------------------------------
    @staticmethod
    def _row_to_memory(row: sqlite3.Row, tags: List[str]) -> Memory:
        return Memory(
            memory_id=row["memory_id"],
            content=row["content"],
            namespace=row["namespace"],
            tags=tags,
            provenance=row["provenance"],
            confidence=row["confidence"],
            metadata=json.loads(row["metadata"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            tier=row["tier"] if "tier" in row.keys() else "durable",
            lifecycle_state=row["lifecycle_state"] if "lifecycle_state" in row.keys() else "active",
        )
