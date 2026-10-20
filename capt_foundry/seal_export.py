"""SEAL Research Asset Export (ADR-0130).

The stable data boundary between the Foundry (producer) and Project SEAL
(consumer). SEAL consumes entities, aliases, and corpus manifests without
importing Foundry internals or depending on Foundry table layout.

Hard boundary rules, enforced here and asserted by tests:

  - The Foundry does NOT import SEAL. The dependency is one-directional.
  - The envelope contains NO case, ruleset, candidate, prompt, submission,
    reviewer, or model-run field. Those are SEAL-owned concepts; emitting them
    would make the Foundry a SEAL task author, which ADR-0130 forbids.
  - Evidence identifiers are exported as REFERENCES with an explicit
    ``verification_owner`` marker. The Foundry never asserts that evidence is
    verified — only the runtime can, via ``record_verification``.
  - Export is read-only and performs no network access and no submission.
"""

from __future__ import annotations

from typing import Any

from capt_foundry.canonical import FOUNDRY_SCHEMA_VERSION, digest, utc_now
from capt_foundry.corpus import CorpusRegistry
from capt_foundry.entities import AliasRegistry, EntityRegistry
from capt_foundry.errors import ValidationError

SEAL_EXPORT_FORMAT = "seal.research_asset_export"
SEAL_EXPORT_FORMAT_VERSION = "1.0.0"

# Concepts SEAL owns. The Foundry must never emit them (ADR-0130).
FORBIDDEN_KEYS = frozenset(
    {
        "case", "cases", "seal_case", "sealcase", "case_id",
        "ruleset", "rulesets", "ruleset_id", "ruleset_binding",
        "candidate", "candidates", "candidate_portfolio",
        "prompt", "prompts", "prompt_preflight", "generated_prompt",
        "submission", "submit", "submitted", "external_submission",
        "reviewer", "reviewers", "review_outcome", "reviewer_outcome",
        "model_run", "model_runs", "adjudication", "final_answer",
        "research_debt", "uniqueness_proof",
    }
)


def _scan_forbidden(node: Any, path: str = "$") -> list[str]:
    """Recursively find SEAL-owned keys. Used by export AND by tests."""
    found: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                found.append(f"{path}.{key}")
            found.extend(_scan_forbidden(value, f"{path}.{key}"))
    elif isinstance(node, list):
        for i, item in enumerate(node):
            found.extend(_scan_forbidden(item, f"{path}[{i}]"))
    return found


class SealAssetExporter:
    """Produces the SEAL-facing envelope. Read-only."""

    def __init__(
        self,
        entities: EntityRegistry,
        aliases: AliasRegistry,
        corpora: CorpusRegistry,
        clock=utc_now,
    ) -> None:
        self.entities = entities
        self.aliases = aliases
        self.corpora = corpora
        self._clock = clock

    def export(
        self,
        *,
        entity_ids: list[str] | None = None,
        corpus_ids: list[str] | None = None,
        exported_at: str | None = None,
    ) -> dict[str, Any]:
        """Build a deterministic, versioned envelope for SEAL.

        ``entity_ids``/``corpus_ids`` omitted means "everything registered".
        """
        ents = (
            [self.entities.require(e) for e in sorted(set(entity_ids))]
            if entity_ids is not None
            else self.entities.all()
        )
        corps = (
            [self.corpora.require(c) for c in sorted(set(corpus_ids))]
            if corpus_ids is not None
            else [
                dict(r)
                for r in self.corpora.store.conn.execute(
                    "SELECT * FROM corpora ORDER BY corpus_id"
                ).fetchall()
            ]
        )

        entity_out: list[dict[str, Any]] = []
        for row in ents:
            aliases = self.aliases.aliases_for(row["entity_id"])
            entity_out.append(
                {
                    "entity_id": row["entity_id"],
                    "entity_type": row["entity_type"],
                    "canonical_name": row["canonical_name"],
                    "normalized_name": row["normalized_name"],
                    "description": row["description"],
                    "status": row["status"],
                    "superseded_by": row["superseded_by"],
                    "attributes": row["attributes"],
                    "record_digest": row["record_digest"],
                    "aliases": [
                        {
                            "alias": a["alias"],
                            "normalized_alias": a["normalized_alias"],
                            "alias_kind": a["alias_kind"],
                            "confidence": a["confidence"],
                            "evidence_refs": a["evidence_ids"],
                        }
                        for a in aliases
                    ],
                    "evidence_refs": row["evidence_ids"],
                    "provenance": {
                        "registered_by": row["registered_by"],
                        "registered_at": row["registered_at"],
                    },
                }
            )

        corpus_out: list[dict[str, Any]] = []
        for row in corps:
            corpus_out.append(
                {
                    "corpus_id": row["corpus_id"],
                    "name": row["name"],
                    "root_label": row["root_label"],
                    "description": row["description"],
                    "manifest_digest": row["manifest_digest"],
                    "document_count": row["document_count"],
                    "freshness": row["status"],
                    "last_validated_at": row["last_validated_at"],
                    "documents": [
                        {
                            "document_id": d["document_id"],
                            "relative_path": d["relative_path"],
                            "content_digest": d["content_digest"],
                            "byte_size": d["byte_size"],
                            "media_type": d["media_type"],
                            "locator": d["locator"],
                        }
                        for d in self.corpora.documents(row["corpus_id"])
                    ],
                    "provenance": {
                        "registered_by": row["registered_by"],
                        "registered_at": row["registered_at"],
                    },
                }
            )

        body = {
            "format": SEAL_EXPORT_FORMAT,
            "format_version": SEAL_EXPORT_FORMAT_VERSION,
            "foundry_schema_version": FOUNDRY_SCHEMA_VERSION,
            "producer": "capt_foundry",
            "entities": entity_out,
            "corpora": corpus_out,
            "boundary": {
                "evidence_owner": "capt_runtime",
                "verification_owner": "capt_runtime",
                "provenance_owner": "capt_solo.memory/capt_solo.foundry.proof",
                "ledger_owner": "capt_runtime.store",
                "governance_owner": "capt_runtime.authority",
                "case_owner": "project_seal",
                "note": (
                    "evidence_refs are identifiers into runtime-owned evidence. "
                    "The Foundry asserts no verification status."
                ),
            },
        }

        leaks = _scan_forbidden(body)
        if leaks:
            raise ValidationError(
                "seal_export",
                [f"SEAL-owned key emitted by Foundry: {k}" for k in leaks],
            )

        body["content_digest"] = digest(body)
        body["exported_at"] = exported_at or self._clock()
        return body

    @staticmethod
    def verify(envelope: dict[str, Any]) -> dict[str, Any]:
        """Recompute the content digest of an envelope (round-trip integrity)."""
        body = {k: v for k, v in envelope.items() if k not in ("content_digest", "exported_at")}
        recomputed = digest(body)
        return {
            "matches": recomputed == envelope.get("content_digest"),
            "stored": envelope.get("content_digest"),
            "recomputed": recomputed,
        }
