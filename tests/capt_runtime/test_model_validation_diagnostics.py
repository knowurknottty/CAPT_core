"""CAPT model validation receipts disclose only stable internal codes."""
from __future__ import annotations

import pytest

from capt_runtime.diagnostic_receipts import safe_model_validation_code


@pytest.mark.parametrize(
    "reason",
    [
        "MODEL_TASK_OBJECTIVE_OR_TARGET_MISSING",
        "MODEL_VISIBLE_PROMPT_TITLE_TOO_LONG",
        "PROVIDER_OR_MODEL_UNAVAILABLE",
        "PROVIDER_CREDENTIAL_UNAVAILABLE",
        "REASONING_EFFORT_REQUIRES_PROVIDER",
        "MODEL_EXECUTION_SECONDS_OUT_OF_RANGE",
        "MODEL_PROMPT_APPROVAL_RECEIPT_REQUIRED",
    ],
)
def test_internal_preflight_code_is_preserved(reason):
    assert safe_model_validation_code(ValueError(reason)) == reason


@pytest.mark.parametrize(
    "exception",
    [
        ValueError("Bearer API_KEY_example"),
        ValueError("PROVIDER_CREDENTIAL_UNAVAILABLE:/Users/private"),
        ValueError("PROVIDER_CREDENTIAL_UNAVAILABLE\nsecret"),
        ValueError("unsupported filesystem path /Users/secret"),
        RuntimeError("PROVIDER_CREDENTIAL_UNAVAILABLE"),
        KeyError("PROVIDER_CREDENTIAL_UNAVAILABLE"),
    ],
)
def test_untrusted_exception_is_redacted(exception):
    assert safe_model_validation_code(exception) in {
        "MODEL_VALUE_ERROR_REDACTED",
        "MODEL_FAILURE_DETAILS_REDACTED",
    }
