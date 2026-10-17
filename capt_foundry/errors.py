"""Foundry error hierarchy.

Distinct from ``capt_runtime.errors``: a Foundry failure is a curation or
identity failure, never an authority or state-transition failure. The Foundry
does not raise ``AuthorityViolation`` because it grants no authority (ADR-0130).
"""

from __future__ import annotations

from typing import List


class FoundryError(Exception):
    """Base class for every Foundry failure."""


class ValidationError(FoundryError):
    """A record violated its own contract."""

    def __init__(self, subject: str, problems: List[str]) -> None:
        self.subject = subject
        self.problems = list(problems)
        super().__init__("%s: %s" % (subject, "; ".join(problems)))


class DuplicateIdentity(FoundryError):
    """Registration would create a second identity for an existing id."""


class UnknownEntity(FoundryError):
    """A reference names an entity that was never registered."""


class AmbiguousAlias(FoundryError):
    """An alias resolves to more than one entity.

    The Foundry refuses to guess. Ambiguity is returned to the caller as an
    error carrying every candidate, so a human can disambiguate.
    """

    def __init__(self, alias: str, candidates: List[str]) -> None:
        self.alias = alias
        self.candidates = sorted(candidates)
        super().__init__(
            "alias %r is ambiguous across entities: %s"
            % (alias, ", ".join(self.candidates))
        )


class DanglingReference(FoundryError):
    """An asset references an entity or document that does not exist."""


class PathEscape(FoundryError):
    """A path left its declared root, or traversed a symlink out of it."""
