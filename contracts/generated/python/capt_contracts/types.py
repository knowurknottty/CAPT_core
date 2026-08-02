# DO NOT EDIT. This file is GENERATED from contracts/schema/.
#
# generator:      contracts/tools/generate.py
# regenerate:     python3 contracts/tools/generate.py
# drift check:    python3 contracts/tools/check_drift.py
# schema version: 1.0.0
# source digest:  sha256:6ab1e9d532c51fd0383e18ac82d8930accae4255fd21bf2ee698fc951b615e90
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


AggregateVersion = int


@dataclass(frozen=True)
class Budget(object):
    """Budget"""

    maxOperations: int
    wallClockSeconds: int


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


Digest = str


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


Identifier = str


class ReplayPolicy(str, Enum):
    """never: no automatic re-execution. safe: externally idempotent. verify-before-retry: observe external state first (ADR-0108)."""

    NEVER = "never"
    SAFE = "safe"
    VERIFY_BEFORE_RETRY = "verify-before-retry"


SchemaVersion = Literal["1.0.0"]


SequenceNumber = int


StreamId = str


Timestamp = str


@dataclass(frozen=True)
class DriverDescriptor(object):
    """DriverDescriptor"""

    driverId: Identifier
    driverVersion: str
    schemaVersion: SchemaVersion
    supportedOperations: List[str]
    writeCapable: bool


class DriverReconciliationStatus(str, Enum):
    """DriverReconciliationStatus"""

    NOT_REQUIRED = "not_required"
    REQUIRED = "required"
    IN_PROGRESS = "in_progress"
    RESOLVED_EFFECT_OCCURRED = "resolved_effect_occurred"
    RESOLVED_EFFECT_ABSENT = "resolved_effect_absent"
    UNRESOLVABLE = "unresolvable"


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


class DriverRunState(str, Enum):
    """DriverRunState"""

    CREATED = "created"
    SUBMITTED = "submitted"
    RUNNING = "running"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"
    LOST = "lost"
    RECONCILED = "reconciled"


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
class TaskTransitionedPayload(object):
    """TaskTransitionedPayload"""

    eventType: Literal["TaskTransitioned"]
    fromState: TaskState
    reason: str
    taskId: Identifier
    toState: TaskState


# discriminated on 'eventType'
EventPayload = Union[MissionCreatedPayload, PolicyEvaluatedPayload, MissionStateChangedPayload, CheckpointCreatedPayload, MissionResumedPayload, TaskCreatedPayload, TaskTransitionedPayload, CapabilityGrantedPayload, CapabilityLeaseActivatedPayload, CapabilityUseReservedPayload, CapabilityUseFinalizedPayload, CapabilityGrantRevokedPayload, CapabilityLeaseRevokedPayload, DriverRunCreatedPayload, DriverRunStateChangedPayload, ClaimCreatedPayload, EvidenceRecordedPayload, ClaimVerifiedPayload, ClaimGuardDecidedPayload]


class EventType(str, Enum):
    """Closed set of authoritative event types. A driver-supplied name is not a member and is rejected by the store (ADR-0110)."""

    MISSIONCREATED = "MissionCreated"
    POLICYEVALUATED = "PolicyEvaluated"
    MISSIONSTATECHANGED = "MissionStateChanged"
    CHECKPOINTCREATED = "CheckpointCreated"
    MISSIONRESUMED = "MissionResumed"
    TASKCREATED = "TaskCreated"
    TASKTRANSITIONED = "TaskTransitioned"
    CAPABILITYGRANTED = "CapabilityGranted"
    CAPABILITYLEASEACTIVATED = "CapabilityLeaseActivated"
    CAPABILITYUSERESERVED = "CapabilityUseReserved"
    CAPABILITYUSEFINALIZED = "CapabilityUseFinalized"
    CAPABILITYGRANTREVOKED = "CapabilityGrantRevoked"
    CAPABILITYLEASEREVOKED = "CapabilityLeaseRevoked"
    DRIVERRUNCREATED = "DriverRunCreated"
    DRIVERRUNSTATECHANGED = "DriverRunStateChanged"
    CLAIMCREATED = "ClaimCreated"
    EVIDENCERECORDED = "EvidenceRecorded"
    CLAIMVERIFIED = "ClaimVerified"
    CLAIMGUARDDECIDED = "ClaimGuardDecided"


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
