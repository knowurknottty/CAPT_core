"""CAPT Solo v0.1 — local-first cognitive runtime for individual developers.

Public surface is intentionally small and stable. Everything under
``capt_solo.*`` that is not re-exported from :mod:`capt_solo.api` is an
implementation detail and may change between minor versions.

Future capabilities (distributed KHSB, remote memory stores, multi-agent
federation, bioCAPT integration) are reserved as extension points only and
are NOT implemented in v0.1.
"""

__version__ = "0.1.0"
__all__ = ["__version__"]
