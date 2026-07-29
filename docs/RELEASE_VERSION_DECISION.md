# Release Version Decision

## Decision

The release candidate is `0.5.0` (unreleased; do not create a tag in this
workflow).

## Evidence

`CAPT_CANON.md` defines semantic versioning as `MAJOR.MINOR.PATCH` and states
that a MINOR release is a backward-compatible public addition. ContextPack v1
adds a packaged, documented public exchange contract without changing an
existing public signature or persisted-schema migration path. The prior current
metadata was `0.4.2`; therefore `0.5.0` is the semver-consistent successor.

## Authoritative locations updated

- `pyproject.toml`
- `capt_solo/__init__.py`
- `capt_solo/plugin/plugin.json`
- `capt_solo/foundry/bubble.py`
- `README.md`
- `CHANGELOG.md`

## Tag plan

After final clean-SHA verification and explicit owner authorization, create a
local `v0.5.0` tag against that verified commit. This gate neither creates nor
publishes a tag.
