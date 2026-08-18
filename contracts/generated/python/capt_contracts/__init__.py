# DO NOT EDIT. This file is GENERATED from contracts/schema/.
#
# generator:      contracts/tools/generate.py
# regenerate:     python3 contracts/tools/generate.py
# drift check:    python3 contracts/tools/check_drift.py
# schema version: 1.0.0
# source digest:  sha256:2d6c348b36a87e6f509459dc0ca2a6a0b1443dd12b5cceb09d2c6ca27e812362
#
# The JSON Schema source is normative (ADR-0101). Edits made here are
# erased on the next generation and will fail the CI drift check.

"""Generated CAPT contract bindings (Python)."""

from .types import *  # noqa: F401,F403
from .types import CONTRACT_SCHEMA_VERSION, RUNTIME_VERSION  # noqa: F401
from .validate import (  # noqa: F401
    ValidationFailure,
    is_valid,
    known_types,
    require_valid,
    validate,
)
from .spec import SPEC, SPEC_JSON  # noqa: F401
