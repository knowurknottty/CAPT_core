"""Credential-shape pattern registry for CAPT redaction layers.

Donor cherry-pick provenance (CAPT donor convergence R1)
--------------------------------------------------------
Upstream donor : gitleaks/gitleaks (https://github.com/gitleaks/gitleaks)
Frozen SHA     : b58d3f102cf3a2c84cb7f923d05c25c9b1aed84b
License        : MIT, Copyright (c) 2019 Zachary Rice (upstream LICENSE at the
                 frozen SHA; MIT text retained below).
Derived from   : config/gitleaks.toml at the frozen SHA. This module adapts a
                 curated subset of upstream rule regexes (rule ids recorded
                 per pattern below); it is NOT a wholesale copy of upstream
                 configuration. Regexes were calibrated for CAPT's local-first
                 evidence redaction (low false-positive rate on digests,
                 manifests and prose).

    MIT License
    Copyright (c) 2019 Zachary Rice

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
    SOFTWARE.

CAPT-native additions (not present in the upstream subset): ``openrouter_api_key``
(``sk-or-v1-``) because OpenRouter is a first-class CAPT provider, and the generic
``openai_style_key`` family (``sk-...``) which subsumes Anthropic ``sk-ant-`` and
OpenAI project/service keys.

Scope and honesty
-----------------
This registry detects credential SHAPES so they can be redacted from exports,
projections and logs. It is high-precision, NOT exhaustive; a clean scan never
proves the absence of secrets. It is stdlib-only, purely local, and grants no
authority, mints no evidence, and bypasses no CAPT boundary.
"""

from __future__ import annotations

import re
from typing import List, Tuple

# (label, upstream_rule_id_or_"capt-native", compiled pattern)
CREDENTIAL_PATTERNS: Tuple[Tuple[str, str, re.Pattern], ...] = (
    # Order matters: multi-line / longest specific shapes first.
    (
        "private_key",
        "private-key",
        re.compile(
            r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?"
            r"PRIVATE KEY(?: BLOCK)?-----",
            re.IGNORECASE,
        ),
    ),
    (
        "aws_access_key",
        "aws-access-token",
        # Covers AKIA (long-lived), ASIA (STS/temporary) and A3T/ABIA/ACCA
        # prefixes. CAPT keeps the broader [0-9A-Z] charset used by CAPT's
        # pre-existing AKIA pattern instead of upstream's base32 subset.
        re.compile(r"(?:A3T[A-Z0-9]|AKIA|ASIA|ABIA|ACCA)[0-9A-Z]{16}"),
    ),
    (
        "github_pat",
        "github-pat",
        re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    ),
    (
        "github_fine_grained_pat",
        "github-fine-grained-pat",
        re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    ),
    (
        "gitlab_pat",
        "gitlab-pat",
        re.compile(r"glpat-[A-Za-z0-9_\-]{20}"),
    ),
    (
        "huggingface_token",
        "huggingface-access-token",
        re.compile(r"hf_[A-Za-z0-9]{34}", re.IGNORECASE),
    ),
    (
        "npm_token",
        "npm-access-token",
        re.compile(r"npm_[A-Za-z0-9]{36}", re.IGNORECASE),
    ),
    (
        "linear_api_key",
        "linear-api-key",
        re.compile(r"lin_api_[A-Za-z0-9]{40}"),
    ),
    (
        "google_api_key",
        "gcp-api-key",
        re.compile(r"AIza[0-9A-Za-z_\-]{35}"),
    ),
    (
        "stripe_key",
        "stripe-api-key",
        re.compile(r"(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{16,}"),
    ),
    (
        "slack_token",
        "slack-api-token",
        re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}"),
    ),
    (
        "slack_webhook",
        "slack-webhook",
        re.compile(r"hooks\.slack\.com/services/[A-Za-z0-9_]+/[A-Za-z0-9_]+/[A-Za-z0-9]+"),
    ),
    (
        "openrouter_api_key",
        "capt-native",
        re.compile(r"sk-or-v1-[A-Za-z0-9_\-]{20,}"),
    ),
    (
        "openai_style_key",
        "capt-native (subsumes anthropic-api-key, openai-api-key)",
        # sk-ant-api03-..., sk-proj-..., sk-svcacct-..., sk-or-v1-..., etc.
        # Word-bounded so prose such as "desk-" or "usk-" does not match.
        re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}"),
    ),
    (
        "jwt",
        "jwt",
        re.compile(r"eyJ[A-Za-z0-9_\-]{8,}\.eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{10,}"),
    ),
)


def find_credential_shapes(text: str) -> List[str]:
    """Return sorted unique labels of credential shapes found in ``text``.

    Purely local inspection; never raises on non-str input coercion is the
    caller's responsibility (str expected).
    """
    hits = {label for label, _rule, pat in CREDENTIAL_PATTERNS if pat.search(text)}
    return sorted(hits)


def redact_credential_shapes(text: str, marker: str = "[REDACTED_KEY]") -> str:
    """Replace every registered credential shape in ``text`` with ``marker``.

    The full match is replaced (no prefix is retained); callers that want an
    audit prefix must derive it before calling, never after.
    """
    out = text
    for _label, _rule, pat in CREDENTIAL_PATTERNS:
        out = pat.sub(marker, out)
    return out
