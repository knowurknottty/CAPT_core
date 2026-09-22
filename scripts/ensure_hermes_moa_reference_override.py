#!/usr/bin/env python3
"""CAPT-managed conformance gate for Hermes paid MoA reference routing.

Hermes may update independently of CAPT. This tool detects whether the current
Hermes source still honors auxiliary.moa_reference.allow_paid and can reapply the
narrow compatibility patch without weakening free_only for other auxiliary tasks.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

PATCH_MARKER = "def _allow_paid_openrouter_for_task(task: Optional[str]) -> bool:"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_is_patched(text: str) -> bool:
    return (
        PATCH_MARKER in text
        and "allow_paid=allow_paid" in text
        and "_describe_openrouter_unavailable(model=req.model, allow_paid=allow_paid)"
        in text
    )


def patch_source(text: str) -> str:
    if source_is_patched(text):
        return text

    old = """def _try_openrouter(explicit_api_key: Optional[Union[str, Callable[[], str]]] = None, model: str = None) -> Tuple[Optional[OpenAI], Optional[str]]:
    free_only, cfg_model = _aux_openrouter_settings()
    or_model = model or cfg_model
    if free_only and not _is_free_model(or_model):
"""
    new = """def _try_openrouter(
    explicit_api_key: Optional[Union[str, Callable[[], str]]] = None,
    model: str = None,
    *,
    allow_paid: bool = False,
) -> Tuple[Optional[OpenAI], Optional[str]]:
    free_only, cfg_model = _aux_openrouter_settings()
    or_model = model or cfg_model
    if free_only and not allow_paid and not _is_free_model(or_model):
"""
    if old not in text:
        raise RuntimeError("unsupported Hermes _try_openrouter shape")
    text = text.replace(old, new, 1)


    old = """def _describe_openrouter_unavailable(model: str = None) -> str:
    \"\"\"Return the policy or credential reason OpenRouter was unavailable.\"\"\"
    free_only, cfg_model = _aux_openrouter_settings()
    or_model = model or cfg_model
    if free_only and not _is_free_model(or_model):
"""
    new = """def _describe_openrouter_unavailable(model: str = None, *, allow_paid: bool = False) -> str:
    \"\"\"Return the policy or credential reason OpenRouter was unavailable.\"\"\"
    free_only, cfg_model = _aux_openrouter_settings()
    or_model = model or cfg_model
    if free_only and not allow_paid and not _is_free_model(or_model):
"""
    if old not in text:
        raise RuntimeError("unsupported Hermes unavailable-description shape")
    text = text.replace(old, new, 1)

    anchor = "def _warn_paid_lane_once(model: str) -> None:\n"
    helper = """def _allow_paid_openrouter_for_task(task: Optional[str]) -> bool:
    \"\"\"Allow paid OpenRouter only for explicitly opted-in MoA reference calls.\"\"\"
    if task != \"moa_reference\":
        return False
    try:
        from hermes_cli.config import cfg_get, load_config_readonly
        cfg = load_config_readonly()
        return bool(cfg_get(cfg, \"auxiliary\", \"moa_reference\", \"allow_paid\", default=False))
    except Exception:
        return False


"""
    if anchor not in text:
        raise RuntimeError("unsupported Hermes paid-lane helper shape")
    text = text.replace(anchor, helper + anchor, 1)


    resolver_call = "    client, default = _try_openrouter(explicit_api_key=req.explicit_api_key, model=req.model)\n"
    if resolver_call not in text:
        raise RuntimeError("unsupported Hermes OpenRouter resolver call shape")
    replacement = (
        "    allow_paid = _allow_paid_openrouter_for_task(req.task)\n"
        "    client, default = _try_openrouter(\n"
        "        explicit_api_key=req.explicit_api_key,\n"
        "        model=req.model,\n"
        "        allow_paid=allow_paid,\n"
        "    )\n"
    )
    text = text.replace(resolver_call, replacement, 1)

    unavailable_call = "_describe_openrouter_unavailable(model=req.model)"
    if unavailable_call not in text:
        raise RuntimeError("unsupported Hermes OpenRouter unavailable call shape")
    text = text.replace(
        unavailable_call,
        "_describe_openrouter_unavailable(model=req.model, allow_paid=allow_paid)",
        1,
    )

    if not source_is_patched(text):
        raise RuntimeError("Hermes patch verification failed")
    compile(text, "auxiliary_client.py", "exec")
    return text


def config_has_opt_in(text: str) -> bool:
    lines = text.splitlines()
    in_aux = False
    in_moa = False
    aux_indent = moa_indent = None
    for line in lines:
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if stripped == "auxiliary:":
            in_aux, aux_indent = True, indent
            in_moa = False
            continue
        if in_aux and stripped and indent <= int(aux_indent or 0):
            in_aux = False
            in_moa = False
        if in_aux and stripped == "moa_reference:":
            in_moa, moa_indent = True, indent
            continue
        if in_moa and stripped and indent <= int(moa_indent or 0):
            in_moa = False
        if in_moa and stripped.lower() == "allow_paid: true":
            return True
    return False


def patch_config(text: str) -> str:
    if config_has_opt_in(text):
        return text
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip() == "moa_reference:" and line.startswith("  "):
            indent = " " * (len(line) - len(line.lstrip()) + 2)
            lines.insert(index + 1, f"{indent}allow_paid: true")
            result = "\n".join(lines) + ("\n" if text.endswith("\n") else "")
            if config_has_opt_in(result):
                return result
    raise RuntimeError("auxiliary.moa_reference block not found in Hermes config")


def inspect(hermes_root: Path, config_path: Path) -> dict[str, object]:
    source = hermes_root / "agent" / "auxiliary_client.py"
    source_bytes = source.read_bytes()
    source_text = source_bytes.decode()
    config_text = config_path.read_text()
    patched = source_is_patched(source_text)
    opted_in = config_has_opt_in(config_text)
    return {
        "source": str(source),
        "sourceSha256": sha256_bytes(source_bytes),
        "sourcePatchPresent": patched,
        "config": str(config_path),
        "configOptIn": opted_in,
        "conformant": patched and opted_in,
    }


def apply(hermes_root: Path, config_path: Path, backup_root: Path) -> dict[str, object]:
    source = hermes_root / "agent" / "auxiliary_client.py"
    before = source.read_bytes()
    config_before = config_path.read_bytes()

    patched_source = patch_source(before.decode()).encode()
    patched_config = patch_config(config_before.decode()).encode()

    backup_root.mkdir(parents=True, exist_ok=True)
    source_backup = backup_root / f"auxiliary_client.{sha256_bytes(before)[:16]}.bak"
    config_backup = backup_root / f"config.{sha256_bytes(config_before)[:16]}.bak"
    if not source_backup.exists():
        shutil.copy2(source, source_backup)
    if not config_backup.exists():
        shutil.copy2(config_path, config_backup)


    source.write_bytes(patched_source)
    config_path.write_bytes(patched_config)

    result = inspect(hermes_root, config_path)
    result["sourceBeforeSha256"] = sha256_bytes(before)
    result["sourceAfterSha256"] = sha256_bytes(patched_source)
    result["backupRoot"] = str(backup_root)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--hermes-root",
        type=Path,
        default=Path.home() / ".hermes" / "hermes-agent",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path.home() / ".hermes" / "config.yaml",
    )
    parser.add_argument(
        "--backup-root",
        type=Path,
        default=Path.home() / ".capt" / "hermes-compat" / "backups",
    )
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    state = (
        apply(args.hermes_root, args.config, args.backup_root)
        if args.apply
        else inspect(args.hermes_root, args.config)
    )
    print(json.dumps(state, indent=2, sort_keys=True))
    return 0 if state["conformant"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
