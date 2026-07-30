"""CAPT Solo v0.4.1 — optional components.

Components are isolated capabilities that run as local child processes. They
never embed into CAPT memory, CTP, or KHSB internals. Failure of a component
degrades ONLY that component's capability.
"""

from capt_solo.components.anti_token_extraction import (
    AntiTokenExtractionComponent,
    ATEManifest,
    ComponentUnavailable,
    UnsafeConfiguration,
    COMPONENT_ID,
    UPSTREAM_REPO,
    PINNED_COMMIT,
    load_manifest,
    save_manifest,
    purge_legacy_cache,
    bootstrap_anti_token_extraction,
)

__all__ = [
    "AntiTokenExtractionComponent",
    "ATEManifest",
    "ComponentUnavailable",
    "UnsafeConfiguration",
    "COMPONENT_ID",
    "UPSTREAM_REPO",
    "PINNED_COMMIT",
    "load_manifest",
    "save_manifest",
    "purge_legacy_cache",
    "bootstrap_anti_token_extraction",
]
