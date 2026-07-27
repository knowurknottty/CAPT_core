# CANONICAL ARCHITECTURE — Workspace Entrypoint

This root file is the discoverable entrypoint required by the CAPT Universal
Workspace contract. It is **not** a duplicate of the canonical architecture.

The full canonical architecture — layer index, canonical homes, release targets,
and per-subsystem decomposition — lives at:

    docs/CANONICAL_ARCHITECTURE.md

For the per-subsystem ownership, maturity evidence, and owner-decision gates,
see:

    docs/CANONICAL_OWNERSHIP_MATRIX.md

The machine-readable subsystem registry (single source of truth for structural
constraints) is:

    architecture/registry.yaml

Validate it with `python3 architecture/validate_registry.py` or
`capt architecture validate`.
