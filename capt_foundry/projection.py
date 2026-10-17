"""Obsidian projection (ADR-0130).

Renders curated assets as human-readable Markdown so a human can actually review
what was curated. The projection is DERIVED and READ-ONLY with respect to
canonical state: registries and the runtime ledger remain the source of truth,
exactly as OneNote is a projection in the SEAL workflow. Deleting the vault loses
nothing.

Write-path safety, because this is the only component that writes outside the
database:
  - every write is confined to a caller-declared vault root;
  - path traversal and symlinks fail closed;
  - filenames are sanitized, so a hostile entity name cannot escape or overwrite;
  - nothing is ever deleted;
  - regeneration is idempotent — identical input yields identical bytes.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

from capt_foundry.errors import PathEscape, ValidationError

_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}
_MAX_STEM = 120


def sanitize_filename(name: str) -> str:
    """Reduce an arbitrary title to a safe single path segment.

    Strips separators and control characters, collapses whitespace, refuses
    reserved device names, bounds the length, and never returns an empty or
    dot-only stem.
    """
    text = unicodedata.normalize("NFKC", name)
    text = _UNSAFE.sub("-", text)
    text = " ".join(text.split())
    text = text.strip(" .")
    if not text:
        text = "untitled"
    if text.lower() in _RESERVED or text.lower().split(".")[0] in _RESERVED:
        text = "_" + text
    if len(text) > _MAX_STEM:
        text = text[:_MAX_STEM].rstrip(" .")
    return text


def _safe_target(root: Path, filename: str) -> Path:
    """Resolve ``filename`` directly under ``root``, refusing every escape."""
    if Path(filename).is_absolute() or len(Path(filename).parts) != 1:
        raise PathEscape(f"projection filename must be a single segment: {filename!r}")
    root_resolved = root.resolve()
    target = (root_resolved / filename).resolve()
    try:
        target.relative_to(root_resolved)
    except ValueError:
        raise PathEscape(f"{filename!r} escapes vault root {root_resolved}")
    if target.is_symlink() or (root_resolved / filename).is_symlink():
        raise PathEscape(f"refusing to write through symlink at {target}")
    return target


def _fm_escape(value: Any) -> str:
    """Quote a YAML front-matter scalar safely.

    Control characters — newline above all — must be escaped, not just quotes:
    a raw newline terminates the scalar and lets a hostile value inject its own
    front-matter key. Escaping is applied to the whole C0 range plus DEL.
    """
    text = "" if value is None else str(value)
    text = text.replace("\\", "\\\\").replace('"', '\\"')
    out = []
    for ch in text:
        if ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif ord(ch) < 0x20 or ord(ch) == 0x7F:
            out.append(f"\\u{ord(ch):04x}")
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


class ObsidianProjection:
    """Renders curated assets to a vault directory."""

    def __init__(self, vault_root: str | Path, subdir: str = "CAPT Foundry") -> None:
        root = Path(vault_root)
        if not root.exists():
            raise ValidationError("ObsidianProjection", [f"vault root does not exist: {root}"])
        if not root.is_dir():
            raise ValidationError("ObsidianProjection", ["vault root is not a directory"])
        if root.is_symlink():
            raise PathEscape(f"vault root is a symlink: {root}")
        self.vault_root = root.resolve()
        clean = sanitize_filename(subdir)
        self.target_dir = _safe_target(self.vault_root, clean)
        self.target_dir.mkdir(parents=True, exist_ok=True)

    # -- rendering (pure) --------------------------------------------------

    def render_asset(self, manifest: dict[str, Any]) -> str:
        """Deterministic Markdown for one published asset. No I/O."""
        payload = manifest.get("foundry_payload") or {}
        entities: list[dict[str, Any]] = payload.get("entities", [])
        corpora: list[dict[str, Any]] = payload.get("corpora", [])
        prov = manifest.get("provenance") or {}

        lines: list[str] = [
            "---",
            "capt_asset_id: {}".format(_fm_escape(payload.get("asset_id", manifest.get("bubble_id")))),
            "capt_asset_version: {}".format(_fm_escape(payload.get("asset_version"))),
            "capt_format: {}".format(_fm_escape(payload.get("format"))),
            "capt_format_version: {}".format(_fm_escape(payload.get("format_version"))),
            "capt_manifest_hash: {}".format(_fm_escape(manifest.get("manifest_hash"))),
            "capt_payload_digest: {}".format(_fm_escape(manifest.get("foundry_payload_digest"))),
            "capt_published_by: {}".format(_fm_escape(prov.get("published_by"))),
            "capt_published_at: {}".format(_fm_escape(prov.get("published_at"))),
            "capt_projection: derived-read-only",
            "---",
            "",
            "# %s" % (payload.get("name") or manifest.get("name") or "Untitled asset"),
            "",
            "> Derived projection of a CAPT Foundry asset. Canonical state lives in",
            "> the Foundry registries and the CAPT runtime ledger. Edits here are not",
            "> read back and will be overwritten on regeneration.",
            "",
        ]
        if payload.get("summary"):
            lines += [str(payload["summary"]), ""]

        lines += ["## Entities", ""]
        if not entities:
            lines += ["_None._", ""]
        for ent in entities:
            lines.append("### {}".format(ent.get("canonical_name", ent.get("entity_id"))))
            lines.append("")
            lines.append("- **Entity ID:** `{}`".format(ent.get("entity_id")))
            lines.append("- **Type:** {}".format(ent.get("entity_type")))
            lines.append("- **Status:** {}".format(ent.get("status")))
            if ent.get("superseded_by"):
                lines.append("- **Superseded by:** `{}`".format(ent["superseded_by"]))
            if ent.get("description"):
                lines.append("- **Description:** {}".format(ent["description"]))
            lines.append("- **Record digest:** `{}`".format(ent.get("record_digest")))
            eprov = ent.get("provenance") or {}
            lines.append(
                "- **Registered:** {} by `{}`".format(eprov.get("registered_at"), eprov.get("registered_by"))
            )
            aliases = ent.get("aliases") or []
            if aliases:
                lines += ["", "| Alias | Kind | Confidence | Evidence |", "|---|---|---|---|"]
                for a in aliases:
                    ev = ", ".join(f"`{e}`" for e in (a.get("evidence_ids") or [])) or "—"
                    lines.append(
                        "| {} | {} | {} | {} |".format(a.get("alias"), a.get("alias_kind"), a.get("confidence"), ev)
                    )
            ev_ids = ent.get("evidence_ids") or []
            if ev_ids:
                lines += ["", "**Evidence references:** " + ", ".join(f"`{e}`" for e in ev_ids)]
            lines.append("")

        lines += ["## Corpora", ""]
        if not corpora:
            lines += ["_None._", ""]
        for c in corpora:
            lines.append("### {}".format(c.get("name", c.get("corpus_id"))))
            lines.append("")
            lines.append("- **Corpus ID:** `{}`".format(c.get("corpus_id")))
            lines.append("- **Root label:** {}".format(c.get("root_label")))
            lines.append("- **Documents:** {}".format(c.get("document_count")))
            lines.append("- **Manifest digest:** `{}`".format(c.get("manifest_digest")))
            lines.append("- **Freshness:** {}".format(c.get("status")))
            lines.append("- **Last validated:** {}".format(c.get("last_validated_at")))
            docs = c.get("documents") or []
            if docs:
                lines += ["", "| Document | Path | Size | Content digest |", "|---|---|---|---|"]
                for d in docs:
                    lines.append(
                        "| `{}` | {} | {} | `{}` |".format(
                            d.get("document_id"),
                            d.get("relative_path"),
                            d.get("byte_size"),
                            d.get("content_digest"),
                        )
                    )
            lines.append("")

        refs = payload.get("evidence_refs") or []
        lines += ["## Evidence references", ""]
        lines += (
            ["_None._", ""]
            if not refs
            else [f"- `{r}`" for r in refs] + [""]
        )
        lines += [
            "---",
            "",
            "_Evidence bodies and verification verdicts are owned by the CAPT runtime",
            "(ADR-0130). The identifiers above are references, not proof._",
            "",
        ]
        return "\n".join(lines)

    # -- writing -----------------------------------------------------------

    def project_asset(self, manifest: dict[str, Any], filename: str | None = None) -> Path:
        """Write one asset note. Idempotent; never deletes."""
        payload = manifest.get("foundry_payload") or {}
        stem = filename or sanitize_filename(
            str(payload.get("name") or manifest.get("name") or payload.get("asset_id") or "asset")
        )
        if not stem.endswith(".md"):
            stem += ".md"
        target = _safe_target(self.target_dir, stem)
        content = self.render_asset(manifest)
        if target.exists() and target.read_text(encoding="utf-8") == content:
            return target  # byte-identical: no write, no mtime churn
        target.write_text(content, encoding="utf-8")
        return target

    def project_index(self, manifests: list[dict[str, Any]]) -> Path:
        """Write a stable index note listing every projected asset."""
        rows = []
        for m in sorted(
            manifests,
            key=lambda x: str((x.get("foundry_payload") or {}).get("asset_id") or ""),
        ):
            p = m.get("foundry_payload") or {}
            rows.append(
                "| [[{}]] | `{}` | {} | `{}` |".format(
                    sanitize_filename(str(p.get("name") or "asset")),
                    p.get("asset_id"),
                    p.get("asset_version"),
                    m.get("manifest_hash"),
                )
            )
        lines = [
            "---",
            "capt_projection: derived-read-only",
            f"capt_asset_count: {len(manifests)}",
            "---",
            "",
            "# CAPT Foundry — curated assets",
            "",
            "| Asset | ID | Version | Manifest hash |",
            "|---|---|---|---|",
        ]
        lines += rows if rows else ["| _none_ | | | |"]
        lines.append("")
        content = "\n".join(lines)
        target = _safe_target(self.target_dir, "CAPT Foundry Index.md")
        if target.exists() and target.read_text(encoding="utf-8") == content:
            return target
        target.write_text(content, encoding="utf-8")
        return target
