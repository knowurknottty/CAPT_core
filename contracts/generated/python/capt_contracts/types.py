# DO NOT EDIT. This file is GENERATED from contracts/schema/.
#
# generator:      contracts/tools/generate.py
# regenerate:     python3 contracts/tools/generate.py
# drift check:    python3 contracts/tools/check_drift.py
# schema version: 1.0.0
# source digest:  sha256:6f678ba0f511575039b56f09a82ced6bf5623818f4e5dc408e3199d02587033b
#
# The JSON Schema source is normative (ADR-0101). Edits made here are
# erased on the next generation and will fail the CI drift check.

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union

try:  # Python 3.8+
    from typing import Literal
except ImportError:  # pragma: no cover
    from typing_extensions import Literal  # type: ignore

CONTRACT_SCHEMA_VERSION = "1.0.0"
RUNTIME_VERSION = "0.1.0"


@dataclass(frozen=True)
class Capability(object):
    """Definition of what an operation permits."""

    capabilityId: Identifier
    consequential: bool
    name: str
    operations: List[str]
    schemaVersion: SchemaVersion
    dependsOn: List[Identifier] = field(default_factory=list)


@dataclass(frozen=True)
class CapabilityConsumptionRecord(object):
    """CapabilityConsumptionRecord"""

    consumptionId: Identifier
    finalizedAt: Timestamp
    leaseId: Identifier
    outcome: ConsumptionOutcome
    reservationId: Identifier
    schemaVersion: SchemaVersion
    sideEffectIdentity: Optional[str] = None


@dataclass(frozen=True)
class CapabilityGrant(object):
    """Scoped, conditioned, versioned authorization. policyDecisionId and policyBundleDigest are REQUIRED: authority cannot exist without a recorded decision (ledger Finding I)."""

    capabilityId: Identifier
    conditions: List[GrantCondition]
    grantId: Identifier
    issuedAt: Timestamp
    issuedBy: ActorRef
    operations: List[str]
    policyBundleDigest: Digest
    policyDecisionId: Identifier
    schemaVersion: SchemaVersion
    scope: ResourceScope
    subject: ActorRef
    validFrom: Timestamp
    validUntil: Timestamp
    maxUses: Optional[int] = None


@dataclass(frozen=True)
class CapabilityLease(object):
    """Binds a grant to mission + task + execution context. A lease may only NARROW its parent grant (ADR-0107)."""

    activatedAt: Timestamp
    executionContextId: Identifier
    grantId: Identifier
    leaseId: Identifier
    missionId: Identifier
    operations: List[str]
    schemaVersion: SchemaVersion
    scope: ResourceScope
    taskId: Identifier
    validFrom: Timestamp
    validUntil: Timestamp
    maxUses: Optional[int] = None


@dataclass(frozen=True)
class CapabilityRequirement(object):
    """CapabilityRequirement"""

    capabilityId: Identifier
    operations: List[str]
    requirementId: Identifier
    scope: ResourceScope


@dataclass(frozen=True)
class CapabilityReservation(object):
    """One intended consequential use. Created BEFORE the effect; finalized after (ledger Finding E)."""

    idempotencyKey: Identifier
    leaseId: Identifier
    operation: str
    operationFingerprint: Digest
    reservationId: Identifier
    reservedAt: Timestamp
    schemaVersion: SchemaVersion
    state: ReservationState


@dataclass(frozen=True)
class CapabilityRevocation(object):
    """Revocation is terminal and irreversible. Re-authorization requires a new grant with a new PolicyDecision."""

    reason: str
    revocationId: Identifier
    revokedAt: Timestamp
    revokedBy: ActorRef
    schemaVersion: SchemaVersion
    targetId: Identifier
    targetKind: RevocationTargetKind


class CapabilityState(str, Enum):
    """CapabilityState"""

    GRANTED = "granted"
    LEASED = "leased"
    RESERVED = "reserved"
    CONSUMED = "consumed"
    REVOKED = "revoked"
    EXPIRED = "expired"


class ConsumptionOutcome(str, Enum):
    """'indeterminate' NEVER permits automatic retry (invariant 12, ADR-0108)."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    INDETERMINATE = "indeterminate"


@dataclass(frozen=True)
class FilesystemScope(object):
    """FilesystemScope"""

    kind: Literal["filesystem"]
    recursive: bool
    rootPath: str


@dataclass(frozen=True)
class IsolatedWorktreeCondition(object):
    """IsolatedWorktreeCondition"""

    kind: Literal["isolated_worktree"]
    worktreeRoot: str


@dataclass(frozen=True)
class NoNetworkCondition(object):
    """NoNetworkCondition"""

    kind: Literal["no_network"]


@dataclass(frozen=True)
class RequiresApprovalCondition(object):
    """RequiresApprovalCondition"""

    approverRole: str
    kind: Literal["requires_approval"]


@dataclass(frozen=True)
class RequiresDryRunCondition(object):
    """RequiresDryRunCondition"""

    kind: Literal["requires_dry_run"]


# discriminated on 'kind'
GrantCondition = Union[RequiresApprovalCondition, RequiresDryRunCondition, IsolatedWorktreeCondition, NoNetworkCondition]


@dataclass(frozen=True)
class NetworkScope(object):
    """NetworkScope"""

    hosts: List[str]
    kind: Literal["network"]


@dataclass(frozen=True)
class NoneScope(object):
    """Explicit empty scope. Used for non-consequential capabilities. Distinct from a missing scope, which is invalid."""

    kind: Literal["none"]


@dataclass(frozen=True)
class RepositoryScope(object):
    """RepositoryScope"""

    kind: Literal["repository"]
    refPattern: str
    repositoryId: Identifier


class ReservationState(str, Enum):
    """ReservationState"""

    OPEN = "open"
    FINALIZED = "finalized"
    AWAITING_RECONCILIATION = "awaiting_reconciliation"


@dataclass(frozen=True)
class ToolScope(object):
    """ToolScope"""

    kind: Literal["tool"]
    toolIds: List[Identifier]


# discriminated on 'kind'
ResourceScope = Union[FilesystemScope, RepositoryScope, NetworkScope, ToolScope, NoneScope]


class RevocationTargetKind(str, Enum):
    """RevocationTargetKind"""

    GRANT = "grant"
    LEASE = "lease"


@dataclass(frozen=True)
class ArtifactHashEntry(object):
    """ArtifactHashEntry"""

    digest: Digest
    path: str


@dataclass(frozen=True)
class AwaitingReconciliationRecoveryState(object):
    """AwaitingReconciliationRecoveryState"""

    kind: Literal["awaiting_reconciliation"]
    openReservationIds: List[Identifier]


@dataclass(frozen=True)
class CheckpointManifest(object):
    """Self-verifying description of runtime state at a ledger position. integrityDigest is computed over the canonicalized manifest with integrityDigest itself removed (ADR-0109)."""

    activeLeaseIds: List[Identifier]
    activeReservationIds: List[Identifier]
    artifactHashes: List[ArtifactHashEntry]
    capabilityVersions: List[StreamVersionEntry]
    checkpointId: Identifier
    claimVersions: List[StreamVersionEntry]
    createdAt: Timestamp
    driverRunVersions: List[StreamVersionEntry]
    integrityDigest: Digest
    ledgerDigest: Digest
    ledgerPosition: LedgerPosition
    missionVersions: List[StreamVersionEntry]
    pendingOutboxEventIds: List[Identifier]
    policyBundleDigest: Digest
    recoveryState: RecoveryState
    runtimeVersion: str
    schemaVersion: SchemaVersion
    taskVersions: List[StreamVersionEntry]
    humanApprovalVersions: List[StreamVersionEntry] = field(default_factory=list)


@dataclass(frozen=True)
class CleanRecoveryState(object):
    """CleanRecoveryState"""

    kind: Literal["clean"]


@dataclass(frozen=True)
class DegradedRecoveryState(object):
    """DegradedRecoveryState"""

    kind: Literal["degraded"]
    reason: str


@dataclass(frozen=True)
class LedgerPosition(object):
    """LedgerPosition"""

    eventId: Optional[str]
    globalSequence: int


# discriminated on 'kind'
RecoveryState = Union[CleanRecoveryState, AwaitingReconciliationRecoveryState, DegradedRecoveryState]


@dataclass(frozen=True)
class StreamVersionEntry(object):
    """Explicit array of pairs rather than a free-form map, so the shape is closed and generator-friendly in both languages."""

    streamId: StreamId
    version: AggregateVersion


@dataclass(frozen=True)
class ClaimGuardDecision(object):
    """ClaimGuard controls emission/promotion. It cannot itself produce verification evidence; verificationId must reference an independently produced VerificationResult."""

    claimId: Identifier
    decidedAt: Timestamp
    decidedBy: ActorRef
    decisionId: Identifier
    rationale: str
    schemaVersion: SchemaVersion
    verdict: ClaimGuardVerdict
    qualification: Optional[str] = None
    verificationId: Optional[Identifier] = None


class ClaimGuardVerdict(str, Enum):
    """ClaimGuardVerdict"""

    ACCEPT = "accept"
    QUALIFY = "qualify"
    REJECT = "reject"
    ESCALATE = "escalate"


class ClaimKind(str, Enum):
    """completion is the strictest: it requires verified status plus required evidence (spec 12.2)."""

    COMPLETION = "completion"
    OBSERVATION = "observation"
    CAPABILITY_ASSERTION = "capability_assertion"
    VERIFICATION_SUMMARY = "verification_summary"


class ClaimPromotionState(str, Enum):
    """ClaimPromotionState"""

    PROPOSED = "proposed"
    VERIFIED = "verified"
    ACCEPTED = "accepted"
    QUALIFIED = "qualified"
    REJECTED = "rejected"
    ESCALATED = "escalated"
    SUPPRESSED = "suppressed"


@dataclass(frozen=True)
class ClaimRecord(object):
    """ClaimRecord"""

    claimId: Identifier
    evidenceIds: List[Identifier]
    kind: ClaimKind
    missionId: Identifier
    promotionState: ClaimPromotionState
    proposedAt: Timestamp
    proposedBy: ActorRef
    schemaVersion: SchemaVersion
    statement: str
    sourceProposalId: Optional[Identifier] = None
    taskId: Optional[Identifier] = None
    verificationId: Optional[Identifier] = None


class ActorKind(str, Enum):
    """ActorKind"""

    HUMAN = "human"
    GOVERNANCE_KERNEL = "governance_kernel"
    COGNITIVE_PLANE = "cognitive_plane"
    EXECUTION_PLANE = "execution_plane"
    VERIFICATION_PLANE = "verification_plane"
    CLAIM_AUTHORITY = "claim_authority"
    EXTERNAL_DRIVER = "external_driver"
    SYSTEM = "system"


@dataclass(frozen=True)
class ActorRef(object):
    """Who performed an action. 'kind' carries the authority domain and is checked by authority invariants."""

    actorId: Identifier
    kind: ActorKind
    displayName: Optional[str] = None


@dataclass(frozen=True)
class AgentIdentity(object):
    """An autonomous agent principal operating under delegated authority. Additive plane-convergence extension (ADR-DT-PLANE-CONV)."""

    agentId: Identifier
    delegatedBy: Identifier
    principalId: Identifier
    schemaVersion: SchemaVersion
    displayName: Optional[str] = None


AggregateVersion = int


@dataclass(frozen=True)
class ArtifactCandidate(object):
    """An untrusted object produced by a driver, awaiting validation. Additive plane-convergence extension (ADR-DT-PLANE-CONV)."""

    candidateId: Identifier
    contentDigest: Digest
    driverRunId: Identifier
    path: str
    schemaVersion: SchemaVersion


@dataclass(frozen=True)
class ArtifactManifest(object):
    """A manifest describing a set of artifacts and their digests. Additive plane-convergence extension (ADR-DT-PLANE-CONV)."""

    artifacts: List[ArtifactRecord]
    manifestId: Identifier
    schemaVersion: SchemaVersion


@dataclass(frozen=True)
class ArtifactPromotionDecision(object):
    """The governance/ClaimGuard decision on artifact promotion. Additive plane-convergence extension (ADR-DT-PLANE-CONV)."""

    decidedAt: Timestamp
    decidedBy: Identifier
    decision: str
    schemaVersion: SchemaVersion
    reason: Optional[str] = None
    verificationRef: Optional[str] = None


@dataclass(frozen=True)
class ArtifactRecord(object):
    """A promoted, authoritative artifact. Additive plane-convergence extension (ADR-DT-PLANE-CONV)."""

    artifactId: Identifier
    candidateId: Identifier
    contentDigest: Digest
    path: str
    promotionDecision: ArtifactPromotionDecision
    schemaVersion: SchemaVersion


@dataclass(frozen=True)
class AuthorityChain(object):
    """The unbroken chain of delegations from a root principal to the acting principal. Additive plane-convergence extension (ADR-DT-PLANE-CONV)."""

    chainId: Identifier
    entries: List[Delegation]
    schemaVersion: SchemaVersion


@dataclass(frozen=True)
class Budget(object):
    """Budget"""

    maxOperations: int
    wallClockSeconds: int


@dataclass(frozen=True)
class CapabilitySubject(object):
    """The subject (principal or resource) a capability is issued against. Additive plane-convergence extension (ADR-DT-PLANE-CONV)."""

    schemaVersion: SchemaVersion
    subjectId: Identifier
    subjectKind: str


@dataclass(frozen=True)
class CommandMetadata(object):
    """Mandatory envelope for every consequential command (ADR-0108)."""

    actor: ActorRef
    attempt: int
    commandId: Identifier
    correlationId: Identifier
    idempotencyKey: Identifier
    issuedAt: Timestamp
    operationFingerprint: Digest
    replayPolicy: ReplayPolicy
    schemaVersion: SchemaVersion
    causationId: Optional[Identifier] = None


@dataclass(frozen=True)
class ContextPack(object):
    """Governed, idempotent context packet assembled by CAPT from a mandatory memory query. Drivers receive only the authorized slice. Additive M1-memory extension under contract 1.0.0 (ADR-DT-M1-MEM-001)."""

    contextPackDigest: str
    contextPackId: Identifier
    contextUsageAfter: int
    contextUsageBefore: int
    excludedRecords: List[Dict[str, Any]]
    policyVersion: int
    schemaVersion: SchemaVersion
    selectedRecords: List[MemoryRecord]
    tokenBudget: int
    triggerBoundary: int
    compressionActions: List[Dict[str, Any]] = field(default_factory=list)
    driverRunId: Optional[str] = None
    exclusionReasons: List[Dict[str, Any]] = field(default_factory=list)
    missionId: Optional[str] = None
    previousContextPackDigest: Optional[str] = None
    provenanceRetained: Optional[bool] = None
    redactions: List[Dict[str, Any]] = field(default_factory=list)
    staleRecords: List[str] = field(default_factory=list)
    summariesGenerated: List[str] = field(default_factory=list)
    taskId: Optional[str] = None
    unresolvedConflicts: List[Dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class Delegation(object):
    """A bounded transfer of authority from a delegator to a delegate. Must not widen the delegator's own authority. Additive plane-convergence extension (ADR-DT-PLANE-CONV)."""

    delegateId: Identifier
    delegationId: Identifier
    delegatorId: Identifier
    expiresAt: Timestamp
    schemaVersion: SchemaVersion
    scope: str


Digest = str


@dataclass(frozen=True)
class DriverIdentity(object):
    """An external ExecutionDriver principal. Reuses the existing driver-identity attestation discipline (DriverRegistry.SpoofedDriverIdentity, hermes.probe_hermes_identity). Additive plane-convergence extension (ADR-DT-PLANE-CONV)."""

    driverId: Identifier
    executableDigest: Digest
    principalId: Identifier
    schemaVersion: SchemaVersion
    version: str


class ErrorCategory(str, Enum):
    """ErrorCategory"""

    VALIDATION = "validation"
    AUTHORITY = "authority"
    CONCURRENCY = "concurrency"
    IDEMPOTENCY = "idempotency"
    INTEGRITY = "integrity"
    NOT_FOUND = "not_found"
    ILLEGAL_TRANSITION = "illegal_transition"
    CAPABILITY_DENIED = "capability_denied"
    RECONCILIATION_REQUIRED = "reconciliation_required"
    INTERNAL = "internal"


@dataclass(frozen=True)
class ErrorEnvelope(object):
    """ErrorEnvelope"""

    category: ErrorCategory
    code: str
    message: str
    occurredAt: Timestamp
    schemaVersion: SchemaVersion
    actualVersion: Optional[int] = None
    correlationId: Optional[Identifier] = None
    expectedVersion: Optional[int] = None
    streamId: Optional[StreamId] = None


@dataclass(frozen=True)
class ExtensionEnvelope(object):
    """THE ONLY permitted generic payload boundary (ADR-0102). Namespaced, validated, and never present in a security-critical decision field."""

    namespace: str
    payloadDigest: Digest
    payloadJson: str


@dataclass(frozen=True)
class HumanApprovalConsumption(object):
    """Durable one-use admission of a previously approved model execution."""

    consumedAt: Timestamp
    driverRunId: Identifier
    missionId: Identifier
    operation: str
    promptAssemblyDigest: Digest
    requestId: Identifier
    resource: str
    schemaVersion: SchemaVersion
    taskId: Identifier
    useId: Identifier


@dataclass(frozen=True)
class HumanApprovalDecision(object):
    """Operator decision on a HumanApprovalRequest. 'approve' permits only the originally requested scope; 'deny' must prevent execution. Idempotent by idempotencyKey. Additive M1 extension under contract 1.0.0 (ADR-DT-M1-001)."""

    correlationId: Identifier
    decidedAt: Timestamp
    decision: str
    idempotencyKey: Identifier
    operatorId: Identifier
    requestId: Identifier
    schemaVersion: SchemaVersion
    note: Optional[str] = None
    sessionId: Optional[str] = None


@dataclass(frozen=True)
class HumanApprovalRequest(object):
    """A bounded request for operator authorization before a consequential action. Authored by the governance kernel / execution plane; decided by a human operator. Additive M1 extension under contract 1.0.0 (ADR-DT-M1-001)."""

    correlationId: Identifier
    createdAt: Timestamp
    expiresAt: Timestamp
    missionId: Identifier
    operation: str
    policyReason: str
    requestId: Identifier
    requestedBy: ActorRef
    requestedCapability: str
    resource: str
    riskClassification: RiskClassification
    schemaVersion: SchemaVersion
    scope: Dict[str, Any]
    taskId: Identifier
    promptAssemblyDigest: Optional[str] = None
    remainingUses: Optional[int] = None


@dataclass(frozen=True)
class HumanIdentity(object):
    """A human operator principal. Additive plane-convergence extension (ADR-DT-PLANE-CONV)."""

    operatorId: Identifier
    principalId: Identifier
    schemaVersion: SchemaVersion
    displayName: Optional[str] = None


Identifier = str


@dataclass(frozen=True)
class IdentityAttestation(object):
    """Cryptographic or process attestation that a principal is who it claims. Additive plane-convergence extension (ADR-DT-PLANE-CONV)."""

    digest: Digest
    method: str
    schemaVersion: SchemaVersion


@dataclass(frozen=True)
class LearningPromotionDecision(object):
    """Human-governed promotion decision for a model candidate. Additive plane-convergence extension (ADR-DT-PLANE-CONV)."""

    decidedAt: Timestamp
    decidedBy: Identifier
    decision: str
    schemaVersion: SchemaVersion
    reason: Optional[str] = None


@dataclass(frozen=True)
class LearningStrategy(object):
    """A registered learning strategy (GRPO/SFT/DPO/ORPO/KTO/RLOO). Interfaces only; no live training in M0. Additive plane-convergence extension (ADR-DT-PLANE-CONV)."""

    kind: str
    schemaVersion: SchemaVersion
    strategyId: Identifier
    enabled: Optional[bool] = None


@dataclass(frozen=True)
class MemoryQuery(object):
    """Typed mandatory memory query emitted by CAPT when a retrieval trigger fires. No anonymous text blobs. Additive M1-memory extension under contract 1.0.0 (ADR-DT-M1-MEM-001)."""

    actor: str
    contextUsage: int
    correlationId: Identifier
    missionId: Identifier
    purpose: str
    recordLimit: int
    requestedMemoryClasses: List[str]
    requestingSubsystem: str
    schemaVersion: SchemaVersion
    taskId: Identifier
    tokenBudget: int
    triggerBoundary: int
    causationId: Optional[str] = None
    consentScope: Optional[str] = None
    driverRunId: Optional[str] = None
    projectScope: Optional[str] = None
    provenanceRequirement: Optional[str] = None
    relevanceCriteria: Optional[str] = None
    sensitivityAllowance: Optional[str] = None
    timeRange: Optional[Any] = None
    trustThreshold: Optional[float] = None


@dataclass(frozen=True)
class MemoryRecord(object):
    """A returned memory record with full provenance and governance metadata. No anonymous text blobs. Additive M1-memory extension under contract 1.0.0 (ADR-DT-M1-MEM-001)."""

    consent: str
    digest: str
    memoryClass: str
    owner: str
    provenance: str
    recordId: Identifier
    sensitivity: str
    source: str
    trust: str
    verificationStatus: str
    conflictState: Optional[str] = None
    createdAt: Optional[str] = None
    downstreamUseRestriction: Optional[str] = None
    expiresAt: Optional[str] = None
    lastVerifiedAt: Optional[str] = None
    retrievalReason: Optional[str] = None
    retrievalScore: Optional[float] = None
    stale: Optional[bool] = None


@dataclass(frozen=True)
class MemoryTriggerPolicy(object):
    """CAPT-owned mandatory memory trigger policy. The trigger interval is a fixed 32,768 tokens; each trigger type has an independent step count. Drivers and the desktop may not widen a higher-authority bound. Additive M1-memory extension under contract 1.0.0 (ADR-DT-M1-MEM-001)."""

    checkpointTriggerSteps: int
    compressionTriggerSteps: int
    consolidationTriggerSteps: int
    hardStopTriggerSteps: int
    modelSafeLimitSteps: int
    policyVersion: int
    retrievalTriggerSteps: int
    schemaVersion: SchemaVersion
    source: str
    triggerIntervalTokens: Any
    operatorId: Optional[str] = None
    policyDigest: Optional[str] = None
    previousPolicyDigest: Optional[str] = None


@dataclass(frozen=True)
class ModelCandidate(object):
    """A candidate model produced by isolated training, awaiting offline evaluation. Additive plane-convergence extension (ADR-DT-PLANE-CONV)."""

    artifactDigest: Digest
    candidateId: Identifier
    schemaVersion: SchemaVersion
    sourceTrajectoryId: Identifier


@dataclass(frozen=True)
class ModelIdentity(object):
    """A model principal referenced by a driver. Additive plane-convergence extension (ADR-DT-PLANE-CONV)."""

    modelId: Identifier
    modelName: str
    principalId: Identifier
    provider: str
    schemaVersion: SchemaVersion


@dataclass(frozen=True)
class MutationReceipt(object):
    """A receipt for an artifact mutation (create/update/delete) within a workspace. Additive plane-convergence extension (ADR-DT-PLANE-CONV)."""

    artifactPath: str
    contentDigest: Digest
    operation: str
    receiptId: Identifier
    schemaVersion: SchemaVersion
    verified: bool


@dataclass(frozen=True)
class OperatorMissionIntent(object):
    """High-level operator intent submitted to CAPT Runtime to create a bounded mission. The runtime owns all planning: it constructs the MissionSpec, TaskNode, and (when requiresApproval) HumanApprovalRequest from this intent. The desktop never builds aggregates. Additive M1 extension under contract 1.0.0 (ADR-DT-M1-001)."""

    missionId: Identifier
    objective: str
    requiresApproval: bool
    schemaVersion: SchemaVersion
    scope: Dict[str, Any]
    budget: Optional[Any] = None
    constraints: List[Dict[str, Any]] = field(default_factory=list)
    normalizedRequest: Optional[str] = None
    operation: Optional[str] = None
    policyReason: Optional[str] = None
    rawRequest: Optional[str] = None
    requestId: Optional[str] = None
    requestedCapability: Optional[str] = None
    resource: Optional[str] = None
    riskClassification: Optional[RiskClassification] = None
    successCriteria: List[Dict[str, Any]] = field(default_factory=list)
    taskId: Optional[str] = None
    terminationCriteria: List[Dict[str, Any]] = field(default_factory=list)
    unresolvedAmbiguities: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class PathScope(object):
    """A bounded filesystem scope for an artifact workspace. Additive plane-convergence extension (ADR-DT-PLANE-CONV)."""

    allowedPaths: List[str]
    rootPath: str
    schemaVersion: SchemaVersion


@dataclass(frozen=True)
class Principal(object):
    """The actor on whose behalf authority is exercised. Identity establishes the actor; delegation transfers bounded authority; governance evaluates; capability issuance grants permission. Additive plane-convergence extension under contract 1.0.0 (ADR-DT-PLANE-CONV)."""

    attestation: IdentityAttestation
    kind: str
    principalId: Identifier
    schemaVersion: SchemaVersion
    displayName: Optional[str] = None


class ReplayPolicy(str, Enum):
    """never: no automatic re-execution. safe: externally idempotent. verify-before-retry: observe external state first (ADR-0108)."""

    NEVER = "never"
    SAFE = "safe"
    VERIFY_BEFORE_RETRY = "verify-before-retry"


@dataclass(frozen=True)
class RevocationRecord(object):
    """A revocation of a principal, delegation, or session. Additive plane-convergence extension (ADR-DT-PLANE-CONV)."""

    reason: str
    revocationId: Identifier
    revokedAt: Timestamp
    schemaVersion: SchemaVersion
    targetId: Identifier


@dataclass(frozen=True)
class RewardSignal(object):
    """A compiled reward signal for a trajectory segment. Additive plane-convergence extension (ADR-DT-PLANE-CONV)."""

    schemaVersion: SchemaVersion
    signalId: Identifier
    trajectoryId: Identifier
    value: float


class RiskClassification(str, Enum):
    """Operator-facing risk band for a bounded approval request. Advisory only; CAPT authority invariants remain the sole enforcement path."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CONSEQUENTIAL = "consequential"


@dataclass(frozen=True)
class RuntimeIdentity(object):
    """The CAPT runtime instance principal. Additive plane-convergence extension (ADR-DT-PLANE-CONV)."""

    principalId: Identifier
    runtimeId: Identifier
    schemaVersion: SchemaVersion
    version: str


SchemaVersion = Literal["1.0.0"]


SequenceNumber = int


@dataclass(frozen=True)
class SessionIdentity(object):
    """A bounded session under which authority is exercised. A session token alone must never become unrestricted authority. Additive plane-convergence extension (ADR-DT-PLANE-CONV)."""

    expiresAt: Timestamp
    issuedAt: Timestamp
    principalId: Identifier
    schemaVersion: SchemaVersion
    sessionId: str


@dataclass(frozen=True)
class SimulationEnvironment(object):
    """An isolated simulation environment with frozen initial state. Never inherits production authority. Additive plane-convergence extension (ADR-DT-PLANE-CONV)."""

    datasetDigest: Digest
    environmentDigest: Digest
    isSimulation: Any
    schemaVersion: SchemaVersion
    simId: Identifier
    productionAuthority: Optional[Any] = None


@dataclass(frozen=True)
class SimulationMarker(object):
    """An explicit marker that an artifact/result was produced in simulation and must never become production state. Additive plane-convergence extension (ADR-DT-PLANE-CONV)."""

    kind: str
    markerId: Identifier
    schemaVersion: SchemaVersion
    simId: Identifier


StreamId = str


@dataclass(frozen=True)
class TemporalContext(object):
    """Canonical temporal model distinguishing wall-clock, monotonic, logical, causal, mission-relative, lease, policy-effective, evidence-observation, verification, memory-freshness, training-cutoff, and replay times. Additive plane-convergence extension (ADR-DT-PLANE-CONV). Not a Time Plane."""

    causal: str
    logical: int
    missionRelative: float
    monotonic: float
    schemaVersion: SchemaVersion
    wallClock: Timestamp
    evidenceObservation: Optional[str] = None
    leaseExpiration: Optional[str] = None
    memoryFreshness: Optional[str] = None
    policyEffective: Optional[str] = None
    replayTime: Optional[str] = None
    trainingCutoff: Optional[str] = None
    verificationTime: Optional[str] = None


Timestamp = str


@dataclass(frozen=True)
class TrajectoryRecord(object):
    """An immutable record of a mission execution trajectory, admissible to Learning only after verification + ClaimGuard. Additive plane-convergence extension (ADR-DT-PLANE-CONV)."""

    claimGuardPassed: bool
    missionId: Identifier
    schemaVersion: SchemaVersion
    trajectoryId: Identifier
    verified: bool
    evidenceRef: Optional[str] = None


@dataclass(frozen=True)
class WorkspaceDescriptor(object):
    """An isolated worktree/staging directory for artifact production. Additive plane-convergence extension (ADR-DT-PLANE-CONV)."""

    pathScope: PathScope
    rootPath: str
    schemaVersion: SchemaVersion
    workspaceId: Identifier


@dataclass(frozen=True)
class WorkspaceLease(object):
    """A time-boxed, scoped lease over a workspace. Additive plane-convergence extension (ADR-DT-PLANE-CONV)."""

    expiresAt: Timestamp
    issuedAt: Timestamp
    leaseId: Identifier
    schemaVersion: SchemaVersion
    state: str
    workspaceId: Identifier


@dataclass(frozen=True)
class ContextSlice(object):
    """Minimal read-only projection handed to a driver. MUST NOT contain governance, policy, claim, capability-graph, ledger, or aggregate references (ADR-0125)."""

    budgets: DriverBudget
    expectedArtifacts: List[ExpectedArtifact]
    filesystemPolicy: FilesystemPolicy
    lease: Dict[str, Any]
    permittedTools: List[str]
    schemaVersion: SchemaVersion
    terminationConditions: DriverTerminationCondition
    contextPackRef: Optional[Any] = None
    networkPolicy: Optional[NetworkPolicy] = None


@dataclass(frozen=True)
class DriverArtifactCandidate(object):
    """A driver-produced artifact candidate. CAPT validates existence before creating an EvidenceRecord."""

    artifactDigest: str
    artifactPath: str
    candidateId: Identifier
    driverRunId: Identifier
    producedAt: Timestamp
    schemaVersion: SchemaVersion


@dataclass(frozen=True)
class DriverBudget(object):
    """Alias of DriverBudgets; resource ceilings for one run."""

    maxArtifacts: Optional[int] = None
    maxObservations: Optional[int] = None
    maxSeconds: Optional[int] = None


@dataclass(frozen=True)
class DriverBudgets(object):
    """DriverBudgets"""

    maxArtifacts: Optional[int] = None
    maxObservations: Optional[int] = None
    maxSeconds: Optional[int] = None


@dataclass(frozen=True)
class DriverCancellationRequest(object):
    """CAPT-authored request to cancel a driver run. The driver cannot self-cancel authoritatively."""

    driverRunId: Identifier
    reason: str
    requestedAt: Timestamp
    schemaVersion: SchemaVersion


@dataclass(frozen=True)
class DriverCapabilities(object):
    """Read-only capability set a driver may be granted. M0-B permits only read/analysis/artifact-candidate operations; RepositoryWrite is forbidden for drivers."""

    budgets: DriverBudget
    filesystemPolicy: FilesystemPolicy
    operations: List[str]
    permittedTools: List[str]
    schemaVersion: SchemaVersion


@dataclass(frozen=True)
class DriverCapabilityDeclaration(object):
    """What a driver declares it can do. A declaration grants NO execution authority (ADR-0120)."""

    declaredOperations: List[str]
    declaredScopes: List[ResourceScope]
    declaredTools: List[str]
    driverId: Identifier
    schemaVersion: SchemaVersion


@dataclass(frozen=True)
class DriverCompatibilityRecord(object):
    """Records the runtime/contract compatibility of a driver at registration time."""

    compatible: bool
    contractSchemaVersion: SchemaVersion
    driverId: Identifier
    runtimeVersion: str
    schemaVersion: SchemaVersion
    notes: Optional[str] = None


@dataclass(frozen=True)
class DriverDescriptor(object):
    """DriverDescriptor"""

    driverId: Identifier
    driverVersion: str
    schemaVersion: SchemaVersion
    supportedOperations: List[str]
    writeCapable: bool


@dataclass(frozen=True)
class DriverError(object):
    """Untrusted driver-reported error. CAPT decides failure disposition; the driver cannot set terminal state authoritatively."""

    driverRunId: Identifier
    errorId: Identifier
    message: str
    reportedAt: Timestamp
    schemaVersion: SchemaVersion


@dataclass(frozen=True)
class DriverProgressSignal(object):
    """DriverProgressSignal"""

    driverRunId: Identifier
    phase: str
    reportedAt: Timestamp
    schemaVersion: SchemaVersion
    signalId: Identifier
    fraction: Optional[float] = None


@dataclass(frozen=True)
class DriverReceiptCandidate(object):
    """Driver-claimed receipt of a step. CAPT validates against the ledger; fake receipts are rejected."""

    claimedAt: Timestamp
    driverRunId: Identifier
    receiptId: Identifier
    schemaVersion: SchemaVersion
    step: str
    contentDigest: Optional[str] = None


@dataclass(frozen=True)
class DriverReconciliationRecord(object):
    """CAPT-authored reconciliation report for a driver run."""

    anomalies: List[str]
    detectedAt: Timestamp
    driverRunId: Identifier
    result: DriverReconciliationResult
    schemaVersion: SchemaVersion


class DriverReconciliationResult(str, Enum):
    """Outcome of a CAPT reconciliation pass over a driver run. No automatic re-execution is implied."""

    RECONCILED_COMPLETED = "reconciled_completed"
    RECONCILED_FAILED = "reconciled_failed"
    RECONCILIATION_REQUIRES_HUMAN = "reconciliation_requires_human"
    SAFE_TO_RETRY = "safe_to_retry"
    RETRY_FORBIDDEN = "retry_forbidden"
    EXTERNAL_STATE_UNKNOWN = "external_state_unknown"


class DriverReconciliationStatus(str, Enum):
    """DriverReconciliationStatus"""

    NOT_REQUIRED = "not_required"
    REQUIRED = "required"
    IN_PROGRESS = "in_progress"
    RESOLVED_EFFECT_OCCURRED = "resolved_effect_occurred"
    RESOLVED_EFFECT_ABSENT = "resolved_effect_absent"
    UNRESOLVABLE = "unresolvable"


@dataclass(frozen=True)
class DriverResumeInput(object):
    """Optional CAPT-authored input to resume a suspended run."""

    driverRunId: Identifier
    schemaVersion: SchemaVersion
    resumeNote: Optional[str] = None


@dataclass(frozen=True)
class DriverRun(object):
    """DriverRun"""

    createdAt: Timestamp
    driverId: Identifier
    driverRunId: Identifier
    missionId: Identifier
    reconciliationStatus: DriverReconciliationStatus
    schemaVersion: SchemaVersion
    state: DriverRunState
    taskId: Identifier
    workOrderVersion: int
    externalRunId: Optional[str] = None


@dataclass(frozen=True)
class DriverRunCheckpoint(object):
    """Per-run recovery state embedded in the CAPT CheckpointManifest. Trusted only after integrity verification."""

    driverRunId: Identifier
    lastEventGlobalSequence: int
    lastObservationDigest: Optional[str]
    openReservations: int
    reconciliationStatus: DriverReconciliationStatus
    state: DriverRunState
    workOrderVersion: int


class DriverRunState(str, Enum):
    """DriverRunState"""

    CREATED = "created"
    QUEUED = "queued"
    SUBMITTED = "submitted"
    RUNNING = "running"
    SUSPENDED = "suspended"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"
    LOST = "lost"
    RECONCILED = "reconciled"


@dataclass(frozen=True)
class DriverTerminationCondition(object):
    """How CAPT terminates a run on anomaly."""

    onBudgetExceeded: Optional[str] = None
    onTimeout: Optional[str] = None
    onUnexpectedWrite: Optional[Any] = None


@dataclass(frozen=True)
class DriverWorkOrder(object):
    """Alias of ExecutionDriverWorkOrder retained for compatibility."""

    contextSlice: ContextSlice
    driverId: Identifier
    driverRunId: Identifier
    missionId: Identifier
    operations: List[str]
    schemaVersion: SchemaVersion
    taskId: Identifier
    workOrderVersion: int


@dataclass(frozen=True)
class ExecutionDriverDescriptor(object):
    """Authoritative CAPT name for the driver descriptor contract (ADR-0120). Structurally identical to DriverDescriptor."""

    driverId: Identifier
    driverVersion: str
    schemaVersion: SchemaVersion
    supportedOperations: List[str]
    writeCapable: bool


@dataclass(frozen=True)
class ExecutionDriverWorkOrder(object):
    """CAPT-authored instruction to a driver. Operations must be read-only (ADR-0122)."""

    contextSlice: ContextSlice
    driverId: Identifier
    driverRunId: Identifier
    missionId: Identifier
    operations: List[str]
    schemaVersion: SchemaVersion
    taskId: Identifier
    workOrderVersion: int
    memoryPolicyRef: Optional[Any] = None


@dataclass(frozen=True)
class ExpectedArtifact(object):
    """Descriptor for an artifact a driver may create in the CAPT staging area."""

    artifactKind: str
    artifactPath: str


@dataclass(frozen=True)
class FilesystemPolicy(object):
    """FilesystemPolicy"""

    allowedPaths: List[str]
    rootPath: str
    writesAllowed: Any


@dataclass(frozen=True)
class NetworkPolicy(object):
    """M0-B drivers are read-only; outbound network is denied by default."""

    allowedHosts: List[str]
    egressAllowed: Any


@dataclass(frozen=True)
class RequiredReceipt(object):
    """Alias of DriverReceiptCandidate; a driver-claimed step receipt."""

    claimedAt: Timestamp
    driverRunId: Identifier
    receiptId: Identifier
    schemaVersion: SchemaVersion
    step: str
    contentDigest: Optional[str] = None


@dataclass(frozen=True)
class CapabilityGrantRevokedPayload(object):
    """CapabilityGrantRevokedPayload"""

    eventType: Literal["CapabilityGrantRevoked"]
    revocation: CapabilityRevocation


@dataclass(frozen=True)
class CapabilityGrantedPayload(object):
    """CapabilityGrantedPayload"""

    eventType: Literal["CapabilityGranted"]
    grant: CapabilityGrant


@dataclass(frozen=True)
class CapabilityLeaseActivatedPayload(object):
    """CapabilityLeaseActivatedPayload"""

    eventType: Literal["CapabilityLeaseActivated"]
    lease: CapabilityLease


@dataclass(frozen=True)
class CapabilityLeaseRevokedPayload(object):
    """CapabilityLeaseRevokedPayload"""

    eventType: Literal["CapabilityLeaseRevoked"]
    revocation: CapabilityRevocation


@dataclass(frozen=True)
class CapabilityUseFinalizedPayload(object):
    """CapabilityUseFinalizedPayload"""

    consumption: CapabilityConsumptionRecord
    eventType: Literal["CapabilityUseFinalized"]


@dataclass(frozen=True)
class CapabilityUseReservedPayload(object):
    """CapabilityUseReservedPayload"""

    eventType: Literal["CapabilityUseReserved"]
    reservation: CapabilityReservation


@dataclass(frozen=True)
class CheckpointCreatedPayload(object):
    """CheckpointCreatedPayload"""

    checkpointId: Identifier
    eventType: Literal["CheckpointCreated"]
    integrityDigest: Digest


@dataclass(frozen=True)
class ClaimCreatedPayload(object):
    """ClaimCreatedPayload"""

    claim: ClaimRecord
    eventType: Literal["ClaimCreated"]


@dataclass(frozen=True)
class ClaimGuardDecidedPayload(object):
    """ClaimGuardDecidedPayload"""

    decision: ClaimGuardDecision
    eventType: Literal["ClaimGuardDecided"]


@dataclass(frozen=True)
class ClaimVerifiedPayload(object):
    """ClaimVerifiedPayload"""

    eventType: Literal["ClaimVerified"]
    verification: VerificationResult


@dataclass(frozen=True)
class DriverRunCreatedPayload(object):
    """DriverRunCreatedPayload"""

    driverRun: DriverRun
    eventType: Literal["DriverRunCreated"]


@dataclass(frozen=True)
class DriverRunReconciledPayload(object):
    """DriverRunReconciledPayload"""

    disposition: str
    driverRunId: Identifier
    eventType: Literal["DriverRunReconciled"]
    fromState: DriverRunState
    reason: str
    toState: Literal["reconciled"]


@dataclass(frozen=True)
class DriverRunStateChangedPayload(object):
    """DriverRunStateChangedPayload"""

    driverRunId: Identifier
    eventType: Literal["DriverRunStateChanged"]
    fromState: DriverRunState
    toState: DriverRunState


@dataclass(frozen=True)
class EventEnvelope(object):
    """Authoritative durable event. Only the CAPT runtime constructs this (ADR-0110)."""

    actor: ActorRef
    correlationId: Identifier
    eventId: Identifier
    eventType: EventType
    globalSequence: SequenceNumber
    occurredAt: Timestamp
    payload: EventPayload
    payloadDigest: Digest
    schemaVersion: SchemaVersion
    streamId: StreamId
    streamVersion: SequenceNumber
    causationId: Optional[Identifier] = None
    claimId: Optional[Identifier] = None
    extensions: List[ExtensionEnvelope] = field(default_factory=list)
    missionId: Optional[Identifier] = None
    taskId: Optional[Identifier] = None


@dataclass(frozen=True)
class EvidenceRecordedPayload(object):
    """EvidenceRecordedPayload"""

    eventType: Literal["EvidenceRecorded"]
    evidence: EvidenceRecord


@dataclass(frozen=True)
class HumanApprovalConsumedPayload(object):
    """HumanApprovalConsumedPayload"""

    consumption: HumanApprovalConsumption
    eventType: Literal["HumanApprovalConsumed"]


@dataclass(frozen=True)
class HumanApprovalDecidedPayload(object):
    """HumanApprovalDecidedPayload"""

    decision: HumanApprovalDecision
    eventType: Literal["HumanApprovalDecided"]


@dataclass(frozen=True)
class HumanApprovalRequestedPayload(object):
    """HumanApprovalRequestedPayload"""

    eventType: Literal["HumanApprovalRequested"]
    request: HumanApprovalRequest


@dataclass(frozen=True)
class MissionCreatedPayload(object):
    """MissionCreatedPayload"""

    eventType: Literal["MissionCreated"]
    missionSpec: MissionSpec


@dataclass(frozen=True)
class MissionResumedPayload(object):
    """MissionResumedPayload"""

    checkpointId: Identifier
    eventType: Literal["MissionResumed"]
    resumedFromGlobalSequence: SequenceNumber


@dataclass(frozen=True)
class MissionStateChangedPayload(object):
    """MissionStateChangedPayload"""

    eventType: Literal["MissionStateChanged"]
    fromState: MissionState
    reason: str
    toState: MissionState


@dataclass(frozen=True)
class PolicyEvaluatedPayload(object):
    """PolicyEvaluatedPayload"""

    eventType: Literal["PolicyEvaluated"]
    policyDecision: PolicyDecision


@dataclass(frozen=True)
class TaskCreatedPayload(object):
    """TaskCreatedPayload"""

    eventType: Literal["TaskCreated"]
    task: TaskNode


@dataclass(frozen=True)
class TaskResultSubmittedPayload(object):
    """TaskResultSubmittedPayload"""

    eventType: Literal["TaskResultSubmitted"]
    resultRef: str
    taskId: Identifier
    toState: TaskState


@dataclass(frozen=True)
class TaskTransitionedPayload(object):
    """TaskTransitionedPayload"""

    eventType: Literal["TaskTransitioned"]
    fromState: TaskState
    reason: str
    taskId: Identifier
    toState: TaskState


# discriminated on 'eventType'
EventPayload = Union[MissionCreatedPayload, PolicyEvaluatedPayload, MissionStateChangedPayload, CheckpointCreatedPayload, MissionResumedPayload, TaskCreatedPayload, TaskTransitionedPayload, TaskResultSubmittedPayload, CapabilityGrantedPayload, CapabilityLeaseActivatedPayload, CapabilityUseReservedPayload, CapabilityUseFinalizedPayload, CapabilityGrantRevokedPayload, CapabilityLeaseRevokedPayload, DriverRunCreatedPayload, DriverRunStateChangedPayload, DriverRunReconciledPayload, ClaimCreatedPayload, EvidenceRecordedPayload, ClaimVerifiedPayload, ClaimGuardDecidedPayload, HumanApprovalRequestedPayload, HumanApprovalDecidedPayload, HumanApprovalConsumedPayload]


class EventType(str, Enum):
    """Closed set of authoritative event types. A driver-supplied name is not a member and is rejected by the store (ADR-0110)."""

    MISSIONCREATED = "MissionCreated"
    POLICYEVALUATED = "PolicyEvaluated"
    MISSIONSTATECHANGED = "MissionStateChanged"
    CHECKPOINTCREATED = "CheckpointCreated"
    MISSIONRESUMED = "MissionResumed"
    TASKCREATED = "TaskCreated"
    TASKTRANSITIONED = "TaskTransitioned"
    TASKRESULTSUBMITTED = "TaskResultSubmitted"
    CAPABILITYGRANTED = "CapabilityGranted"
    CAPABILITYLEASEACTIVATED = "CapabilityLeaseActivated"
    CAPABILITYUSERESERVED = "CapabilityUseReserved"
    CAPABILITYUSEFINALIZED = "CapabilityUseFinalized"
    CAPABILITYGRANTREVOKED = "CapabilityGrantRevoked"
    CAPABILITYLEASEREVOKED = "CapabilityLeaseRevoked"
    DRIVERRUNCREATED = "DriverRunCreated"
    DRIVERRUNSTATECHANGED = "DriverRunStateChanged"
    DRIVERRUNRECONCILED = "DriverRunReconciled"
    CLAIMCREATED = "ClaimCreated"
    EVIDENCERECORDED = "EvidenceRecorded"
    CLAIMVERIFIED = "ClaimVerified"
    CLAIMGUARDDECIDED = "ClaimGuardDecided"
    HUMANAPPROVALREQUESTED = "HumanApprovalRequested"
    HUMANAPPROVALDECIDED = "HumanApprovalDecided"
    HUMANAPPROVALCONSUMED = "HumanApprovalConsumed"


@dataclass(frozen=True)
class ArtifactHashEvidence(object):
    """ArtifactHashEvidence"""

    artifactDigest: Digest
    artifactPath: str
    kind: Literal["artifact_hash"]


@dataclass(frozen=True)
class CommandExitEvidence(object):
    """CommandExitEvidence"""

    command: str
    exitCode: int
    kind: Literal["command_exit"]
    outputDigest: Digest


@dataclass(frozen=True)
class DriverClaimProposal(object):
    """UNTRUSTED Family B type. Can only enter CAPT as an UNVERIFIED ClaimRecord; promotion requires an independent VerificationResult (ADR-0110)."""

    observedBy: Identifier
    proposalId: Identifier
    proposedAt: Timestamp
    schemaVersion: SchemaVersion
    statement: str
    trust: Literal["untrusted"]
    workOrderId: Identifier


@dataclass(frozen=True)
class DriverObservation(object):
    """UNTRUSTED Family B type (ADR-0110). Deliberately has no streamId/streamVersion/eventType, so it cannot be appended to the ledger. Do not merge with EvidenceRecord."""

    observationId: Identifier
    observedAt: Timestamp
    observedBy: Identifier
    schemaVersion: SchemaVersion
    summary: str
    trust: Literal["untrusted"]
    workOrderId: Identifier


@dataclass(frozen=True)
class HumanAttestationEvidence(object):
    """HumanAttestationEvidence"""

    attestedBy: ActorRef
    kind: Literal["human_attestation"]
    statement: str


@dataclass(frozen=True)
class SchemaValidationEvidence(object):
    """SchemaValidationEvidence"""

    kind: Literal["schema_validation"]
    schemaId: str
    valid: bool


@dataclass(frozen=True)
class StateAssertionEvidence(object):
    """StateAssertionEvidence"""

    kind: Literal["state_assertion"]
    stateDigest: Digest
    streamId: StreamId
    streamVersion: AggregateVersion


# discriminated on 'kind'
EvidenceKind = Union[ArtifactHashEvidence, CommandExitEvidence, SchemaValidationEvidence, StateAssertionEvidence, HumanAttestationEvidence]


@dataclass(frozen=True)
class EvidenceRecord(object):
    """Authoritative record. CAPT-constructed only. A driver observation must be converted through validation (ADR-0110); provenance is preserved in sourceObservationId without transferring authority."""

    collectedAt: Timestamp
    collectedBy: ActorRef
    evidence: EvidenceKind
    evidenceId: Identifier
    missionId: Identifier
    schemaVersion: SchemaVersion
    trust: Literal["capt_authoritative"]
    sourceObservationId: Optional[Identifier] = None
    taskId: Optional[Identifier] = None


@dataclass(frozen=True)
class ApprovalRequiredConstraint(object):
    """ApprovalRequiredConstraint"""

    approverRole: str
    constraintId: Identifier
    kind: Literal["approval_required"]
    origin: ConstraintOrigin


@dataclass(frozen=True)
class BudgetConstraint(object):
    """BudgetConstraint"""

    budget: Budget
    constraintId: Identifier
    kind: Literal["budget"]
    origin: ConstraintOrigin


@dataclass(frozen=True)
class ForbiddenOperationConstraint(object):
    """ForbiddenOperationConstraint"""

    constraintId: Identifier
    kind: Literal["forbidden_operation"]
    operations: List[str]
    origin: ConstraintOrigin


@dataclass(frozen=True)
class ResourceBoundaryConstraint(object):
    """ResourceBoundaryConstraint"""

    constraintId: Identifier
    kind: Literal["resource_boundary"]
    origin: ConstraintOrigin
    scope: ResourceScope


# discriminated on 'kind'
Constraint = Union[ForbiddenOperationConstraint, ResourceBoundaryConstraint, BudgetConstraint, ApprovalRequiredConstraint]


class ConstraintOrigin(str, Enum):
    """Provenance of a constraint. 'inferred' constraints carry lower authority and are surfaced separately (spec 7.2)."""

    EXPLICIT_USER = "explicit_user"
    INFERRED = "inferred"
    POLICY_ADDED = "policy_added"


@dataclass(frozen=True)
class MissionSpec(object):
    """Compiled mission. Preserves raw and normalized input plus constraint provenance (spec 7.2)."""

    constraints: List[Constraint]
    createdAt: Timestamp
    missionId: Identifier
    normalizedRequest: str
    objectives: List[Objective]
    rawRequest: str
    schemaVersion: SchemaVersion
    successCriteria: List[SuccessCriterion]
    terminationCriteria: List[TerminationCriterion]
    unresolvedAmbiguities: List[str]
    taskGraphId: Optional[Identifier] = None


class MissionState(str, Enum):
    """MissionState"""

    DRAFT = "draft"
    AUTHORIZED = "authorized"
    EXECUTING = "executing"
    SUSPENDED = "suspended"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class Objective(object):
    """Objective"""

    objectiveId: Identifier
    priority: int
    statement: str


@dataclass(frozen=True)
class SuccessCriterion(object):
    """SuccessCriterion"""

    criterionId: Identifier
    requiresVerification: bool
    statement: str


@dataclass(frozen=True)
class TerminationCriterion(object):
    """TerminationCriterion"""

    criterionId: Identifier
    statement: str
    terminalState: str


@dataclass(frozen=True)
class PolicyDecision(object):
    """Binds authority to the exact policy version that produced it (ledger Finding I). A CapabilityGrant without a PolicyDecision reference is invalid."""

    decidedAt: Timestamp
    decidedBy: ActorRef
    effect: PolicyEffect
    policyBundleDigest: Digest
    policyDecisionId: Identifier
    rationale: str
    requestedOperations: List[str]
    requestedScope: ResourceScope
    schemaVersion: SchemaVersion
    subject: ActorRef
    conditions: List[GrantCondition] = field(default_factory=list)
    missionId: Optional[Identifier] = None
    taskId: Optional[Identifier] = None


class PolicyEffect(str, Enum):
    """PolicyEffect"""

    ALLOW = "allow"
    DENY = "deny"
    ALLOW_WITH_CONDITIONS = "allow_with_conditions"
    ESCALATE = "escalate"


class DependencyCondition(str, Enum):
    """Spec 8: 'parallel' is NOT an edge type. Parallelism emerges when predecessor conditions are simultaneously satisfied."""

    COMPLETED = "completed"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    VERIFIED = "verified"
    APPROVED = "approved"


@dataclass(frozen=True)
class TaskDependency(object):
    """TaskDependency"""

    condition: DependencyCondition
    dependencyId: Identifier
    predecessorTaskId: Identifier
    successorTaskId: Identifier


@dataclass(frozen=True)
class TaskGraph(object):
    """TaskGraph"""

    dependencies: List[TaskDependency]
    missionId: Identifier
    nodes: List[TaskNode]
    schemaVersion: SchemaVersion
    taskGraphId: Identifier


@dataclass(frozen=True)
class TaskNode(object):
    """TaskNode"""

    attempt: int
    capabilityRequirements: List[CapabilityRequirement]
    consequential: bool
    maxAttempts: int
    missionId: Identifier
    state: TaskState
    taskId: Identifier
    title: str
    assignedDriverId: Optional[Identifier] = None
    recoveryState: Optional[TaskRecoveryState] = None


class TaskRecoveryState(str, Enum):
    """TaskRecoveryState"""

    NONE = "none"
    AWAITING_RECONCILIATION = "awaiting_reconciliation"
    RECONCILED = "reconciled"
    ABANDONED = "abandoned"


class TaskState(str, Enum):
    """Closed task lifecycle. Terminal states are succeeded, failed, cancelled (ADR-0103)."""

    PENDING = "pending"
    READY = "ready"
    ASSIGNED = "assigned"
    RUNNING = "running"
    SUSPENDED = "suspended"
    AWAITING_VERIFICATION = "awaiting_verification"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class BooleanArgument(object):
    """BooleanArgument"""

    kind: Literal["boolean"]
    name: str
    value: bool


@dataclass(frozen=True)
class IntegerArgument(object):
    """IntegerArgument"""

    kind: Literal["integer"]
    name: str
    value: int


@dataclass(frozen=True)
class PathArgument(object):
    """PathArgument"""

    kind: Literal["path"]
    name: str
    value: str


@dataclass(frozen=True)
class StringArgument(object):
    """StringArgument"""

    kind: Literal["string"]
    name: str
    value: str


# discriminated on 'kind'
ToolArgument = Union[StringArgument, IntegerArgument, BooleanArgument, PathArgument]


@dataclass(frozen=True)
class ToolRequest(object):
    """leaseId is REQUIRED for a consequential request: no side effect without a lease (invariant 7)."""

    arguments: List[ToolArgument]
    consequential: bool
    idempotencyKey: Identifier
    operation: str
    operationFingerprint: Digest
    replayPolicy: ReplayPolicy
    requestedAt: Timestamp
    schemaVersion: SchemaVersion
    toolId: Identifier
    toolRequestId: Identifier
    leaseId: Optional[Identifier] = None
    reservationId: Optional[Identifier] = None


@dataclass(frozen=True)
class ToolResult(object):
    """ToolResult"""

    completedAt: Timestamp
    schemaVersion: SchemaVersion
    status: ToolResultStatus
    toolRequestId: Identifier
    toolResultId: Identifier
    error: Optional[ErrorEnvelope] = None
    exitCode: Optional[int] = None
    outputDigest: Optional[Digest] = None
    sideEffectIdentity: Optional[str] = None


class ToolResultStatus(str, Enum):
    """ToolResultStatus"""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    INDETERMINATE = "indeterminate"
    DENIED = "denied"


@dataclass(frozen=True)
class ContradictedStatus(object):
    """ContradictedStatus"""

    contradictingEvidenceIds: List[Identifier]
    kind: Literal["contradicted"]


@dataclass(frozen=True)
class InconclusiveStatus(object):
    """InconclusiveStatus"""

    kind: Literal["inconclusive"]
    reason: str


@dataclass(frozen=True)
class InferenceStatus(object):
    """InferenceStatus"""

    basis: str
    kind: Literal["inference"]


@dataclass(frozen=True)
class NotTestedStatus(object):
    """NotTestedStatus"""

    kind: Literal["not_tested"]


@dataclass(frozen=True)
class ObservedUnverifiedStatus(object):
    """ObservedUnverifiedStatus"""

    kind: Literal["observed_unverified"]
    reason: str


@dataclass(frozen=True)
class VerificationResult(object):
    """Produced by the verification plane. Verification must not mutate the artifact it verifies (invariant: authority separation)."""

    claimId: Identifier
    schemaVersion: SchemaVersion
    status: VerificationStatus
    strategy: VerificationStrategy
    verificationId: Identifier
    verifiedAt: Timestamp
    verifiedBy: ActorRef


@dataclass(frozen=True)
class VerifiedStatus(object):
    """VerifiedStatus"""

    kind: Literal["verified"]
    supportingEvidenceIds: List[Identifier]


# discriminated on 'kind'
VerificationStatus = Union[VerifiedStatus, ObservedUnverifiedStatus, InferenceStatus, ContradictedStatus, InconclusiveStatus, NotTestedStatus]


class VerificationStrategy(str, Enum):
    """VerificationStrategy"""

    DIRECT_OBSERVATION = "direct_observation"
    DETERMINISTIC_SCHEMA_VALIDATION = "deterministic_schema_validation"
    ARTIFACT_HASHING = "artifact_hashing"
    TEST_EXIT_STATUS = "test_exit_status"
    INVARIANT_CHECK = "invariant_check"
    INDEPENDENT_REPRODUCTION = "independent_reproduction"
    SOURCE_TRIANGULATION = "source_triangulation"
    COUNTERARGUMENT = "counterargument"
    HUMAN_REVIEW = "human_review"
