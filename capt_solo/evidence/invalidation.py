"""Invalidation Event Model — first-class invalidators with scoped rules.

An invalidation explains: what changed, which evidence was affected, why, what
remains current, and what verification is now required. Invalidation is SCOPED:
a docs change does not invalidate DSP tests unless an explicit dependency exists.
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

from .core import EvidenceRecord, EvidenceStatus


class InvalidationReason(str, Enum):
    HEAD_CHANGED = "head_changed"
    WORKING_TREE_PATH_CHANGED = "working_tree_path_changed"
    DEPENDENCY_LOCKFILE_CHANGED = "dependency_lockfile_changed"
    RUNTIME_TOOLCHAIN_CHANGED = "runtime_toolchain_changed"
    ENVIRONMENT_IDENTITY_CHANGED = "environment_identity_changed"
    CONFIGURATION_CHANGED = "configuration_changed"
    GENERATED_ARTIFACT_CHANGED = "generated_artifact_changed"
    VERIFICATION_COMMAND_CHANGED = "verification_command_changed"
    VERIFICATION_SCOPE_EXPANDED = "verification_scope_expanded"
    SOURCE_EVIDENCE_DELETED = "source_evidence_deleted"
    SOURCE_EVIDENCE_CONTRADICTED = "source_evidence_contradicted"
    POLICY_CHANGED = "policy_changed"
    USER_REQUESTED_FRESH = "user_requested_fresh"
    EVIDENCE_TTL_EXPIRED = "evidence_ttl_expired"
    PROJECT_NAMESPACE_CHANGED = "project_namespace_changed"
    BRANCH_CHANGED = "branch_changed"
    REPOSITORY_IDENTITY_CHANGED = "repository_identity_changed"
    EVIDENCE_SUPERSEDED = "evidence_superseded"
    SUPPORTING_EVIDENCE_INVALID = "supporting_evidence_invalid"


class InvalidationScope(str, Enum):
    LOCAL = "local"            # only the directly-affected evidence
    TRANSITIVE = "transitive"  # evidence that depends on the changed evidence
    PARTIAL = "partial"        # some scopes affected, others current
    FULL = "full"              # everything in the project/repo


@dataclass
class InvalidationEvent:
    event_id: str
    reason: str
    changed_paths: List[str] = field(default_factory=list)
    affected_evidence_ids: List[str] = field(default_factory=list)
    unaffected_evidence_ids: List[str] = field(default_factory=list)
    invalidation_scope: str = InvalidationScope.LOCAL.value
    required_verification: List[str] = field(default_factory=list)
    detail: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict:
        return self.__dict__


@dataclass
class InvalidationRule:
    """Maps a reason + changed paths to which evidence classes/scopes it hits."""
    reason: str
    # evidence classes this invalidator affects (empty = all)
    affects_evidence_classes: List[str] = field(default_factory=list)
    # evidence scopes this invalidator affects (empty = all)
    affects_scopes: List[str] = field(default_factory=list)
    # invalidation scope to apply
    invalidation_scope: str = InvalidationScope.LOCAL.value
    # verification scopes required when triggered
    required_verification: List[str] = field(default_factory=list)
    # path globs that, if changed, trigger this rule (empty = any path)
    path_globs: List[str] = field(default_factory=list)


# Default rule table. Scoped: docs change hits only docs evidence; lockfile hits
# build/runtime broadly; HEAD hits everything.
DEFAULT_RULES: List[InvalidationRule] = [
    InvalidationRule(InvalidationReason.HEAD_CHANGED.value,
                    affects_evidence_classes=[], affects_scopes=[],
                    invalidation_scope=InvalidationScope.FULL.value,
                    required_verification=["full"]),
    InvalidationRule(InvalidationReason.BRANCH_CHANGED.value,
                    affects_evidence_classes=[], affects_scopes=[],
                    invalidation_scope=InvalidationScope.FULL.value,
                    required_verification=["full"]),
    InvalidationRule(InvalidationReason.REPOSITORY_IDENTITY_CHANGED.value,
                    affects_evidence_classes=[], affects_scopes=[],
                    invalidation_scope=InvalidationScope.FULL.value,
                    required_verification=["full"]),
    InvalidationRule(InvalidationReason.DEPENDENCY_LOCKFILE_CHANGED.value,
                    affects_evidence_classes=[], affects_scopes=[],
                    invalidation_scope=InvalidationScope.FULL.value,
                    required_verification=["full"]),
    InvalidationRule(InvalidationReason.RUNTIME_TOOLCHAIN_CHANGED.value,
                    affects_evidence_classes=[], affects_scopes=[],
                    invalidation_scope=InvalidationScope.FULL.value,
                    required_verification=["full"]),
    InvalidationRule(InvalidationReason.ENVIRONMENT_IDENTITY_CHANGED.value,
                    affects_evidence_classes=[], affects_scopes=[],
                    invalidation_scope=InvalidationScope.FULL.value,
                    required_verification=["full"]),
    InvalidationRule(InvalidationReason.POLICY_CHANGED.value,
                    affects_evidence_classes=[], affects_scopes=[],
                    invalidation_scope=InvalidationScope.FULL.value,
                    required_verification=["full"]),
    InvalidationRule(InvalidationReason.VERIFICATION_COMMAND_CHANGED.value,
                    affects_evidence_classes=[], affects_scopes=[],
                    invalidation_scope=InvalidationScope.LOCAL.value,
                    required_verification=["targeted"]),
    InvalidationRule(InvalidationReason.VERIFICATION_SCOPE_EXPANDED.value,
                    affects_evidence_classes=[], affects_scopes=[],
                    invalidation_scope=InvalidationScope.PARTIAL.value,
                    required_verification=["targeted"]),
    InvalidationRule(InvalidationReason.GENERATED_ARTIFACT_CHANGED.value,
                    affects_evidence_classes=[], affects_scopes=[],
                    invalidation_scope=InvalidationScope.LOCAL.value,
                    required_verification=["targeted"],
                    path_globs=["dist/*", "build/*", "*.whl", "*.egg-info/*"]),
    InvalidationRule(InvalidationReason.WORKING_TREE_PATH_CHANGED.value,
                    affects_evidence_classes=[], affects_scopes=[],
                    invalidation_scope=InvalidationScope.LOCAL.value,
                    required_verification=["targeted"]),
    InvalidationRule(InvalidationReason.USER_REQUESTED_FRESH.value,
                    affects_evidence_classes=[], affects_scopes=[],
                    invalidation_scope=InvalidationScope.FULL.value,
                    required_verification=["full"]),
    InvalidationRule(InvalidationReason.EVIDENCE_SUPERSEDED.value,
                    affects_evidence_classes=[], affects_scopes=[],
                    invalidation_scope=InvalidationScope.LOCAL.value,
                    required_verification=[]),
    InvalidationRule(InvalidationReason.SOURCE_EVIDENCE_DELETED.value,
                    affects_evidence_classes=[], affects_scopes=[],
                    invalidation_scope=InvalidationScope.TRANSITIVE.value,
                    required_verification=["targeted"]),
    InvalidationRule(InvalidationReason.SUPPORTING_EVIDENCE_INVALID.value,
                    affects_evidence_classes=[], affects_scopes=[],
                    invalidation_scope=InvalidationScope.TRANSITIVE.value,
                    required_verification=["targeted"]),
    InvalidationRule(InvalidationReason.SOURCE_EVIDENCE_CONTRADICTED.value,
                    affects_evidence_classes=[], affects_scopes=[],
                    invalidation_scope=InvalidationScope.TRANSITIVE.value,
                    required_verification=["targeted"]),
]


def _match_glob(rel: str, glob: str) -> bool:
    import fnmatch
    g = glob.lstrip("./")
    if fnmatch.fnmatch(rel, g):
        return True
    if "**" in g:
        prefix = g.split("**")[0].rstrip("/")
        return rel.startswith(prefix) or ("/" + prefix + "/") in ("/" + rel)
    return False


def scan_invalidation(reason: str, changed_paths: List[str],
                      evidence: List[EvidenceRecord],
                      rules: Optional[List[InvalidationRule]] = None) -> InvalidationEvent:
    """Produce a scoped invalidation event for a reason + changed paths.

    Determines which evidence records are affected (by class/scope/path match)
    and which remain current. Does NOT mutate evidence (caller applies status).
    """
    rules = rules or DEFAULT_RULES
    rule = next((r for r in rules if r.reason == reason), None)
    if rule is None:
        rule = InvalidationRule(reason, invalidation_scope=InvalidationScope.LOCAL.value,
                                required_verification=["targeted"])
    # Reasons that are global invalidators (affect all evidence unless class/scope
    # filter excludes). Path-based reasons are scoped to overlapping source paths.
    PATH_BASED_REASONS = {
        InvalidationReason.WORKING_TREE_PATH_CHANGED.value,
        InvalidationReason.GENERATED_ARTIFACT_CHANGED.value,
    }
    rels = [p.replace("\\", "/") for p in changed_paths]

    def paths_overlap(rec: EvidenceRecord) -> bool:
        sp = [s.replace("\\", "/") for s in rec.source.source_paths]
        if not sp:
            return False  # cannot prove relevance; do not over-invalidate
        return any(_match_glob(r, g) for r in rels for g in sp)

    affected = []
    unaffected = []
    for rec in evidence:
        hit = False
        if rule.affects_evidence_classes and rec.evidence_class not in rule.affects_evidence_classes:
            hit = False
        elif rule.affects_scopes and rec.scope not in rule.affects_scopes:
            hit = False
        elif reason in PATH_BASED_REASONS:
            hit = paths_overlap(rec)
        else:
            # global invalidator (HEAD, lockfile, env, policy, user, etc.)
            hit = True
        # path_globs on the rule further restrict (e.g. generated artifact globs)
        if hit and rule.path_globs:
            if not any(_match_glob(r, g) for r in rels for g in rule.path_globs):
                hit = False
        if hit:
            affected.append(rec.record_id)
        else:
            unaffected.append(rec.record_id)
    # For FULL scope, everything is affected.
    if rule.invalidation_scope == InvalidationScope.FULL.value:
        affected = [r.record_id for r in evidence]
        unaffected = []
    ev_hash = hashlib.sha256(
        (reason + "|" + "|".join(sorted(rels))).encode()).hexdigest()[:12]
    return InvalidationEvent(
        event_id=f"inv-{ev_hash}",
        reason=reason, changed_paths=rels,
        affected_evidence_ids=affected, unaffected_evidence_ids=unaffected,
        invalidation_scope=rule.invalidation_scope,
        required_verification=rule.required_verification,
        detail=f"reason={reason}; {len(affected)} affected, {len(unaffected)} current",
    )


@dataclass
class InvalidationDecision:
    action: str   # INVALIDATE | PARTIAL | KEEP_CURRENT
    event: InvalidationEvent
    reason: str = ""


class InvalidationGraph:
    """Lightweight index of invalidation events keyed by evidence id.

    Supports: which events touched an evidence record, and transitive closure
    (evidence depending on invalidated evidence is also invalidated).
    """

    def __init__(self) -> None:
        self._by_evidence: Dict[str, List[InvalidationEvent]] = {}
        self._events: List[InvalidationEvent] = []

    def record(self, event: InvalidationEvent) -> None:
        self._events.append(event)
        for eid in event.affected_evidence_ids:
            self._by_evidence.setdefault(eid, []).append(event)

    def events_for(self, evidence_id: str) -> List[InvalidationEvent]:
        return self._by_evidence.get(evidence_id, [])

    def transitive_invalidations(self, direct_ids: List[str],
                                 dependency_map: Dict[str, List[str]]) -> List[str]:
        """Given directly-invalidated ids and a dependency map (id -> depends_on),
        return the full set including transitively-affected evidence."""
        seen = set(direct_ids)
        stack = list(direct_ids)
        while stack:
            cur = stack.pop()
            for dependent, deps in dependency_map.items():
                if cur in deps and dependent not in seen:
                    seen.add(dependent)
                    stack.append(dependent)
        return list(seen)
