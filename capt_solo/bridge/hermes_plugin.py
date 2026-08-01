"""Hermes plugin registration for the CAPT Bootstrap Bridge.

Registers the ``llm_execution`` middleware that performs the actual provider
authority transfer. Registration is *inert*: until a bridge boot succeeds, the
middleware passes every call straight through to Hermes
(``HERMES_BEFORE_BRIDGE``), so merely installing the plugin changes nothing.

Hermes contract (verified in ``hermes_cli/plugins.py``):
``register(context)`` is called with a ``PluginContext`` exposing
``register_middleware(kind, callback)``. ``llm_execution`` is in
``VALID_MIDDLEWARE`` so registration is warning-free.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

MIDDLEWARE_KIND = "llm_execution"


def register(context: Any) -> None:
    """Entry point invoked by Hermes' plugin loader."""
    from capt_solo.bridge.hermes_middleware import llm_execution_middleware

    register_middleware = getattr(context, "register_middleware", None)
    if not callable(register_middleware):
        logger.warning(
            "CAPT bridge: host does not expose register_middleware; "
            "provider authority transfer is NOT available"
        )
        return
    register_middleware(MIDDLEWARE_KIND, llm_execution_middleware)
    logger.info(
        "CAPT bridge: registered %s middleware (inert until a validated bridge boot)",
        MIDDLEWARE_KIND,
    )
