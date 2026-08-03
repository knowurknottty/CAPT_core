// DO NOT EDIT. This file is GENERATED from contracts/schema/.
//
// generator:      contracts/tools/generate.py
// regenerate:     python3 contracts/tools/generate.py
// drift check:    python3 contracts/tools/check_drift.py
// schema version: 1.0.0
// source digest:  sha256:683ce7d3c261e0e855f0d88284855b2b003e6e0507be4601e93c8c96f7ee6525
//
// The JSON Schema source is normative (ADR-0101). Edits made here are
// erased on the next generation and will fail the CI drift check.

export const CONTRACT_SCHEMA_VERSION = "1.0.0" as const;
export const RUNTIME_VERSION = "0.1.0" as const;

/** Definition of what an operation permits. */
export interface Capability {
  readonly capabilityId: Identifier;
  readonly consequential: boolean;
  readonly name: string;
  readonly operations: readonly string[];
  readonly schemaVersion: SchemaVersion;
  readonly dependsOn?: readonly Identifier[];
}

/** CapabilityConsumptionRecord */
export interface CapabilityConsumptionRecord {
  readonly consumptionId: Identifier;
  readonly finalizedAt: Timestamp;
  readonly leaseId: Identifier;
  readonly outcome: ConsumptionOutcome;
  readonly reservationId: Identifier;
  readonly schemaVersion: SchemaVersion;
  readonly sideEffectIdentity?: string | null;
}

/** Scoped, conditioned, versioned authorization. policyDecisionId and policyBundleDigest are REQUIRED: authority cannot exist without a recorded decision (ledger Finding I). */
export interface CapabilityGrant {
  readonly capabilityId: Identifier;
  readonly conditions: readonly GrantCondition[];
  readonly grantId: Identifier;
  readonly issuedAt: Timestamp;
  readonly issuedBy: ActorRef;
  readonly operations: readonly string[];
  readonly policyBundleDigest: Digest;
  readonly policyDecisionId: Identifier;
  readonly schemaVersion: SchemaVersion;
  readonly scope: ResourceScope;
  readonly subject: ActorRef;
  readonly validFrom: Timestamp;
  readonly validUntil: Timestamp;
  readonly maxUses?: number | null;
}

/** Binds a grant to mission + task + execution context. A lease may only NARROW its parent grant (ADR-0107). */
export interface CapabilityLease {
  readonly activatedAt: Timestamp;
  readonly executionContextId: Identifier;
  readonly grantId: Identifier;
  readonly leaseId: Identifier;
  readonly missionId: Identifier;
  readonly operations: readonly string[];
  readonly schemaVersion: SchemaVersion;
  readonly scope: ResourceScope;
  readonly taskId: Identifier;
  readonly validFrom: Timestamp;
  readonly validUntil: Timestamp;
  readonly maxUses?: number | null;
}

/** CapabilityRequirement */
export interface CapabilityRequirement {
  readonly capabilityId: Identifier;
  readonly operations: readonly string[];
  readonly requirementId: Identifier;
  readonly scope: ResourceScope;
}

/** One intended consequential use. Created BEFORE the effect; finalized after (ledger Finding E). */
export interface CapabilityReservation {
  readonly idempotencyKey: Identifier;
  readonly leaseId: Identifier;
  readonly operation: string;
  readonly operationFingerprint: Digest;
  readonly reservationId: Identifier;
  readonly reservedAt: Timestamp;
  readonly schemaVersion: SchemaVersion;
  readonly state: ReservationState;
}

/** Revocation is terminal and irreversible. Re-authorization requires a new grant with a new PolicyDecision. */
export interface CapabilityRevocation {
  readonly reason: string;
  readonly revocationId: Identifier;
  readonly revokedAt: Timestamp;
  readonly revokedBy: ActorRef;
  readonly schemaVersion: SchemaVersion;
  readonly targetId: Identifier;
  readonly targetKind: RevocationTargetKind;
}

/** CapabilityState */
export type CapabilityState = "granted" | "leased" | "reserved" | "consumed" | "revoked" | "expired";
export const CapabilityStateValues = [
  "granted",
  "leased",
  "reserved",
  "consumed",
  "revoked",
  "expired",
] as const;

/** 'indeterminate' NEVER permits automatic retry (invariant 12, ADR-0108). */
export type ConsumptionOutcome = "succeeded" | "failed" | "indeterminate";
export const ConsumptionOutcomeValues = [
  "succeeded",
  "failed",
  "indeterminate",
] as const;

/** FilesystemScope */
export interface FilesystemScope {
  readonly kind: "filesystem";
  readonly recursive: boolean;
  readonly rootPath: string;
}

/** Discriminated union of grant preconditions. */
/** Discriminated on `kind`. */
export type GrantCondition =
  | RequiresApprovalCondition
  | RequiresDryRunCondition
  | IsolatedWorktreeCondition
  | NoNetworkCondition;

/** IsolatedWorktreeCondition */
export interface IsolatedWorktreeCondition {
  readonly kind: "isolated_worktree";
  readonly worktreeRoot: string;
}

/** NetworkScope */
export interface NetworkScope {
  readonly hosts: readonly string[];
  readonly kind: "network";
}

/** NoNetworkCondition */
export interface NoNetworkCondition {
  readonly kind: "no_network";
}

/** Explicit empty scope. Used for non-consequential capabilities. Distinct from a missing scope, which is invalid. */
export interface NoneScope {
  readonly kind: "none";
}

/** RepositoryScope */
export interface RepositoryScope {
  readonly kind: "repository";
  readonly refPattern: string;
  readonly repositoryId: Identifier;
}

/** RequiresApprovalCondition */
export interface RequiresApprovalCondition {
  readonly approverRole: string;
  readonly kind: "requires_approval";
}

/** RequiresDryRunCondition */
export interface RequiresDryRunCondition {
  readonly kind: "requires_dry_run";
}

/** ReservationState */
export type ReservationState = "open" | "finalized" | "awaiting_reconciliation";
export const ReservationStateValues = [
  "open",
  "finalized",
  "awaiting_reconciliation",
] as const;

/** Discriminated union. Ledger Finding C: an unconstrained object here would allow scope forgery. */
/** Discriminated on `kind`. */
export type ResourceScope =
  | FilesystemScope
  | RepositoryScope
  | NetworkScope
  | ToolScope
  | NoneScope;

/** RevocationTargetKind */
export type RevocationTargetKind = "grant" | "lease";
export const RevocationTargetKindValues = [
  "grant",
  "lease",
] as const;

/** ToolScope */
export interface ToolScope {
  readonly kind: "tool";
  readonly toolIds: readonly Identifier[];
}

/** ArtifactHashEntry */
export interface ArtifactHashEntry {
  readonly digest: Digest;
  readonly path: string;
}

/** AwaitingReconciliationRecoveryState */
export interface AwaitingReconciliationRecoveryState {
  readonly kind: "awaiting_reconciliation";
  readonly openReservationIds: readonly Identifier[];
}

/** Self-verifying description of runtime state at a ledger position. integrityDigest is computed over the canonicalized manifest with integrityDigest itself removed (ADR-0109). */
export interface CheckpointManifest {
  readonly activeLeaseIds: readonly Identifier[];
  readonly activeReservationIds: readonly Identifier[];
  readonly artifactHashes: readonly ArtifactHashEntry[];
  readonly capabilityVersions: readonly StreamVersionEntry[];
  readonly checkpointId: Identifier;
  readonly claimVersions: readonly StreamVersionEntry[];
  readonly createdAt: Timestamp;
  readonly driverRunVersions: readonly StreamVersionEntry[];
  readonly integrityDigest: Digest;
  readonly ledgerDigest: Digest;
  readonly ledgerPosition: LedgerPosition;
  readonly missionVersions: readonly StreamVersionEntry[];
  readonly pendingOutboxEventIds: readonly Identifier[];
  readonly policyBundleDigest: Digest;
  readonly recoveryState: RecoveryState;
  readonly runtimeVersion: string;
  readonly schemaVersion: SchemaVersion;
  readonly taskVersions: readonly StreamVersionEntry[];
}

/** CleanRecoveryState */
export interface CleanRecoveryState {
  readonly kind: "clean";
}

/** DegradedRecoveryState */
export interface DegradedRecoveryState {
  readonly kind: "degraded";
  readonly reason: string;
}

/** LedgerPosition */
export interface LedgerPosition {
  readonly eventId: string | null;
  readonly globalSequence: number;
}

/** Discriminated union. awaiting_reconciliation blocks consequential dispatch after resume (ADR-0109). */
/** Discriminated on `kind`. */
export type RecoveryState =
  | CleanRecoveryState
  | AwaitingReconciliationRecoveryState
  | DegradedRecoveryState;

/** Explicit array of pairs rather than a free-form map, so the shape is closed and generator-friendly in both languages. */
export interface StreamVersionEntry {
  readonly streamId: StreamId;
  readonly version: AggregateVersion;
}

/** ClaimGuard controls emission/promotion. It cannot itself produce verification evidence; verificationId must reference an independently produced VerificationResult. */
export interface ClaimGuardDecision {
  readonly claimId: Identifier;
  readonly decidedAt: Timestamp;
  readonly decidedBy: ActorRef;
  readonly decisionId: Identifier;
  readonly rationale: string;
  readonly schemaVersion: SchemaVersion;
  readonly verdict: ClaimGuardVerdict;
  readonly qualification?: string | null;
  readonly verificationId?: Identifier | null;
}

/** ClaimGuardVerdict */
export type ClaimGuardVerdict = "accept" | "qualify" | "reject" | "escalate";
export const ClaimGuardVerdictValues = [
  "accept",
  "qualify",
  "reject",
  "escalate",
] as const;

/** completion is the strictest: it requires verified status plus required evidence (spec 12.2). */
export type ClaimKind = "completion" | "observation" | "capability_assertion" | "verification_summary";
export const ClaimKindValues = [
  "completion",
  "observation",
  "capability_assertion",
  "verification_summary",
] as const;

/** ClaimPromotionState */
export type ClaimPromotionState = "proposed" | "verified" | "accepted" | "qualified" | "rejected" | "escalated" | "suppressed";
export const ClaimPromotionStateValues = [
  "proposed",
  "verified",
  "accepted",
  "qualified",
  "rejected",
  "escalated",
  "suppressed",
] as const;

/** ClaimRecord */
export interface ClaimRecord {
  readonly claimId: Identifier;
  readonly evidenceIds: readonly Identifier[];
  readonly kind: ClaimKind;
  readonly missionId: Identifier;
  readonly promotionState: ClaimPromotionState;
  readonly proposedAt: Timestamp;
  readonly proposedBy: ActorRef;
  readonly schemaVersion: SchemaVersion;
  readonly statement: string;
  readonly sourceProposalId?: Identifier | null;
  readonly taskId?: Identifier | null;
  readonly verificationId?: Identifier | null;
}

/** ActorKind */
export type ActorKind = "human" | "governance_kernel" | "cognitive_plane" | "execution_plane" | "verification_plane" | "claim_authority" | "external_driver" | "system";
export const ActorKindValues = [
  "human",
  "governance_kernel",
  "cognitive_plane",
  "execution_plane",
  "verification_plane",
  "claim_authority",
  "external_driver",
  "system",
] as const;

/** Who performed an action. 'kind' carries the authority domain and is checked by authority invariants. */
export interface ActorRef {
  readonly actorId: Identifier;
  readonly kind: ActorKind;
  readonly displayName?: string | null;
}

/** An autonomous agent principal operating under delegated authority. Additive plane-convergence extension (ADR-DT-PLANE-CONV). */
export interface AgentIdentity {
  readonly agentId: Identifier;
  readonly delegatedBy: Identifier;
  readonly principalId: Identifier;
  readonly schemaVersion: SchemaVersion;
  readonly displayName?: string | null;
}

/** 0 means the stream does not yet exist. Increments by exactly 1 per event. */
export type AggregateVersion = number;

/** An untrusted object produced by a driver, awaiting validation. Additive plane-convergence extension (ADR-DT-PLANE-CONV). */
export interface ArtifactCandidate {
  readonly candidateId: Identifier;
  readonly contentDigest: Digest;
  readonly driverRunId: Identifier;
  readonly path: string;
  readonly schemaVersion: SchemaVersion;
}

/** A manifest describing a set of artifacts and their digests. Additive plane-convergence extension (ADR-DT-PLANE-CONV). */
export interface ArtifactManifest {
  readonly artifacts: readonly ArtifactRecord[];
  readonly manifestId: Identifier;
  readonly schemaVersion: SchemaVersion;
}

/** The governance/ClaimGuard decision on artifact promotion. Additive plane-convergence extension (ADR-DT-PLANE-CONV). */
export interface ArtifactPromotionDecision {
  readonly decidedAt: Timestamp;
  readonly decidedBy: Identifier;
  readonly decision: string;
  readonly schemaVersion: SchemaVersion;
  readonly reason?: string | null;
  readonly verificationRef?: string | null;
}

/** A promoted, authoritative artifact. Additive plane-convergence extension (ADR-DT-PLANE-CONV). */
export interface ArtifactRecord {
  readonly artifactId: Identifier;
  readonly candidateId: Identifier;
  readonly contentDigest: Digest;
  readonly path: string;
  readonly promotionDecision: ArtifactPromotionDecision;
  readonly schemaVersion: SchemaVersion;
}

/** The unbroken chain of delegations from a root principal to the acting principal. Additive plane-convergence extension (ADR-DT-PLANE-CONV). */
export interface AuthorityChain {
  readonly chainId: Identifier;
  readonly entries: readonly Delegation[];
  readonly schemaVersion: SchemaVersion;
}

/** Budget */
export interface Budget {
  readonly maxOperations: number;
  readonly wallClockSeconds: number;
}

/** The subject (principal or resource) a capability is issued against. Additive plane-convergence extension (ADR-DT-PLANE-CONV). */
export interface CapabilitySubject {
  readonly schemaVersion: SchemaVersion;
  readonly subjectId: Identifier;
  readonly subjectKind: string;
}

/** Mandatory envelope for every consequential command (ADR-0108). */
export interface CommandMetadata {
  readonly actor: ActorRef;
  readonly attempt: number;
  readonly commandId: Identifier;
  readonly correlationId: Identifier;
  readonly idempotencyKey: Identifier;
  readonly issuedAt: Timestamp;
  readonly operationFingerprint: Digest;
  readonly replayPolicy: ReplayPolicy;
  readonly schemaVersion: SchemaVersion;
  readonly causationId?: Identifier | null;
}

/** Governed, idempotent context packet assembled by CAPT from a mandatory memory query. Drivers receive only the authorized slice. Additive M1-memory extension under contract 1.0.0 (ADR-DT-M1-MEM-001). */
export interface ContextPack {
  readonly contextPackDigest: string;
  readonly contextPackId: Identifier;
  readonly contextUsageAfter: number;
  readonly contextUsageBefore: number;
  readonly excludedRecords: readonly Readonly<Record<string, unknown>>[];
  readonly policyVersion: number;
  readonly schemaVersion: SchemaVersion;
  readonly selectedRecords: readonly MemoryRecord[];
  readonly tokenBudget: number;
  readonly triggerBoundary: number;
  readonly compressionActions?: readonly Readonly<Record<string, unknown>>[];
  readonly driverRunId?: string | null;
  readonly exclusionReasons?: readonly Readonly<Record<string, unknown>>[];
  readonly missionId?: string | null;
  readonly previousContextPackDigest?: string | null;
  readonly provenanceRetained?: boolean;
  readonly redactions?: readonly Readonly<Record<string, unknown>>[];
  readonly staleRecords?: readonly string[];
  readonly summariesGenerated?: readonly string[];
  readonly taskId?: string | null;
  readonly unresolvedConflicts?: readonly Readonly<Record<string, unknown>>[];
}

/** A bounded transfer of authority from a delegator to a delegate. Must not widen the delegator's own authority. Additive plane-convergence extension (ADR-DT-PLANE-CONV). */
export interface Delegation {
  readonly delegateId: Identifier;
  readonly delegationId: Identifier;
  readonly delegatorId: Identifier;
  readonly expiresAt: Timestamp;
  readonly schemaVersion: SchemaVersion;
  readonly scope: string;
}

/** Lowercase hex SHA-256 with algorithm prefix. */
export type Digest = string;

/** An external ExecutionDriver principal. Reuses the existing driver-identity attestation discipline (DriverRegistry.SpoofedDriverIdentity, hermes.probe_hermes_identity). Additive plane-convergence extension (ADR-DT-PLANE-CONV). */
export interface DriverIdentity {
  readonly driverId: Identifier;
  readonly executableDigest: Digest;
  readonly principalId: Identifier;
  readonly schemaVersion: SchemaVersion;
  readonly version: string;
}

/** ErrorCategory */
export type ErrorCategory = "validation" | "authority" | "concurrency" | "idempotency" | "integrity" | "not_found" | "illegal_transition" | "capability_denied" | "reconciliation_required" | "internal";
export const ErrorCategoryValues = [
  "validation",
  "authority",
  "concurrency",
  "idempotency",
  "integrity",
  "not_found",
  "illegal_transition",
  "capability_denied",
  "reconciliation_required",
  "internal",
] as const;

/** ErrorEnvelope */
export interface ErrorEnvelope {
  readonly category: ErrorCategory;
  readonly code: string;
  readonly message: string;
  readonly occurredAt: Timestamp;
  readonly schemaVersion: SchemaVersion;
  readonly actualVersion?: number | null;
  readonly correlationId?: Identifier | null;
  readonly expectedVersion?: number | null;
  readonly streamId?: StreamId | null;
}

/** THE ONLY permitted generic payload boundary (ADR-0102). Namespaced, validated, and never present in a security-critical decision field. */
export interface ExtensionEnvelope {
  readonly namespace: string;
  readonly payloadDigest: Digest;
  readonly payloadJson: string;
}

/** Operator decision on a HumanApprovalRequest. 'approve' permits only the originally requested scope; 'deny' must prevent execution. Idempotent by idempotencyKey. Additive M1 extension under contract 1.0.0 (ADR-DT-M1-001). */
export interface HumanApprovalDecision {
  readonly correlationId: Identifier;
  readonly decidedAt: Timestamp;
  readonly decision: string;
  readonly idempotencyKey: Identifier;
  readonly operatorId: Identifier;
  readonly requestId: Identifier;
  readonly schemaVersion: SchemaVersion;
  readonly note?: string | null;
  readonly sessionId?: string | null;
}

/** A bounded request for operator authorization before a consequential action. Authored by the governance kernel / execution plane; decided by a human operator. Additive M1 extension under contract 1.0.0 (ADR-DT-M1-001). */
export interface HumanApprovalRequest {
  readonly correlationId: Identifier;
  readonly createdAt: Timestamp;
  readonly expiresAt: Timestamp;
  readonly missionId: Identifier;
  readonly operation: string;
  readonly policyReason: string;
  readonly requestId: Identifier;
  readonly requestedBy: ActorRef;
  readonly requestedCapability: string;
  readonly resource: string;
  readonly riskClassification: RiskClassification;
  readonly schemaVersion: SchemaVersion;
  readonly scope: Readonly<Record<string, unknown>>;
  readonly taskId: Identifier;
  readonly remainingUses?: number | null;
}

/** A human operator principal. Additive plane-convergence extension (ADR-DT-PLANE-CONV). */
export interface HumanIdentity {
  readonly operatorId: Identifier;
  readonly principalId: Identifier;
  readonly schemaVersion: SchemaVersion;
  readonly displayName?: string | null;
}

/** Opaque, caller-minted identifier. Bounded charset prevents injection into paths, SQL, and log lines. */
export type Identifier = string;

/** Cryptographic or process attestation that a principal is who it claims. Additive plane-convergence extension (ADR-DT-PLANE-CONV). */
export interface IdentityAttestation {
  readonly digest: Digest;
  readonly method: string;
  readonly schemaVersion: SchemaVersion;
}

/** Typed mandatory memory query emitted by CAPT when a retrieval trigger fires. No anonymous text blobs. Additive M1-memory extension under contract 1.0.0 (ADR-DT-M1-MEM-001). */
export interface MemoryQuery {
  readonly actor: string;
  readonly contextUsage: number;
  readonly correlationId: Identifier;
  readonly missionId: Identifier;
  readonly purpose: string;
  readonly recordLimit: number;
  readonly requestedMemoryClasses: readonly string[];
  readonly requestingSubsystem: string;
  readonly schemaVersion: SchemaVersion;
  readonly taskId: Identifier;
  readonly tokenBudget: number;
  readonly triggerBoundary: number;
  readonly causationId?: string | null;
  readonly consentScope?: string | null;
  readonly driverRunId?: string | null;
  readonly projectScope?: string | null;
  readonly provenanceRequirement?: string | null;
  readonly relevanceCriteria?: string | null;
  readonly sensitivityAllowance?: string | null;
  readonly timeRange?: unknown | null;
  readonly trustThreshold?: number;
}

/** A returned memory record with full provenance and governance metadata. No anonymous text blobs. Additive M1-memory extension under contract 1.0.0 (ADR-DT-M1-MEM-001). */
export interface MemoryRecord {
  readonly consent: string;
  readonly digest: string;
  readonly memoryClass: string;
  readonly owner: string;
  readonly provenance: string;
  readonly recordId: Identifier;
  readonly sensitivity: string;
  readonly source: string;
  readonly trust: string;
  readonly verificationStatus: string;
  readonly conflictState?: string | null;
  readonly createdAt?: string | null;
  readonly downstreamUseRestriction?: string | null;
  readonly expiresAt?: string | null;
  readonly lastVerifiedAt?: string | null;
  readonly retrievalReason?: string;
  readonly retrievalScore?: number;
  readonly stale?: boolean;
}

/** CAPT-owned mandatory memory trigger policy. The trigger interval is a fixed 32,768 tokens; each trigger type has an independent step count. Drivers and the desktop may not widen a higher-authority bound. Additive M1-memory extension under contract 1.0.0 (ADR-DT-M1-MEM-001). */
export interface MemoryTriggerPolicy {
  readonly checkpointTriggerSteps: number;
  readonly compressionTriggerSteps: number;
  readonly consolidationTriggerSteps: number;
  readonly hardStopTriggerSteps: number;
  readonly modelSafeLimitSteps: number;
  readonly policyVersion: number;
  readonly retrievalTriggerSteps: number;
  readonly schemaVersion: SchemaVersion;
  readonly source: string;
  readonly triggerIntervalTokens: unknown;
  readonly operatorId?: string | null;
  readonly policyDigest?: string | null;
  readonly previousPolicyDigest?: string | null;
}

/** A model principal referenced by a driver. Additive plane-convergence extension (ADR-DT-PLANE-CONV). */
export interface ModelIdentity {
  readonly modelId: Identifier;
  readonly modelName: string;
  readonly principalId: Identifier;
  readonly provider: string;
  readonly schemaVersion: SchemaVersion;
}

/** A receipt for an artifact mutation (create/update/delete) within a workspace. Additive plane-convergence extension (ADR-DT-PLANE-CONV). */
export interface MutationReceipt {
  readonly artifactPath: string;
  readonly contentDigest: Digest;
  readonly operation: string;
  readonly receiptId: Identifier;
  readonly schemaVersion: SchemaVersion;
  readonly verified: boolean;
}

/** High-level operator intent submitted to CAPT Runtime to create a bounded mission. The runtime owns all planning: it constructs the MissionSpec, TaskNode, and (when requiresApproval) HumanApprovalRequest from this intent. The desktop never builds aggregates. Additive M1 extension under contract 1.0.0 (ADR-DT-M1-001). */
export interface OperatorMissionIntent {
  readonly missionId: Identifier;
  readonly objective: string;
  readonly requiresApproval: boolean;
  readonly schemaVersion: SchemaVersion;
  readonly scope: Readonly<Record<string, unknown>>;
  readonly budget?: unknown | null;
  readonly constraints?: readonly Readonly<Record<string, unknown>>[];
  readonly normalizedRequest?: string | null;
  readonly operation?: string | null;
  readonly policyReason?: string | null;
  readonly rawRequest?: string | null;
  readonly requestId?: string | null;
  readonly requestedCapability?: string;
  readonly resource?: string | null;
  readonly riskClassification?: RiskClassification;
  readonly successCriteria?: readonly Readonly<Record<string, unknown>>[];
  readonly taskId?: string | null;
  readonly terminationCriteria?: readonly Readonly<Record<string, unknown>>[];
  readonly unresolvedAmbiguities?: readonly string[];
}

/** A bounded filesystem scope for an artifact workspace. Additive plane-convergence extension (ADR-DT-PLANE-CONV). */
export interface PathScope {
  readonly allowedPaths: readonly string[];
  readonly rootPath: string;
  readonly schemaVersion: SchemaVersion;
}

/** The actor on whose behalf authority is exercised. Identity establishes the actor; delegation transfers bounded authority; governance evaluates; capability issuance grants permission. Additive plane-convergence extension under contract 1.0.0 (ADR-DT-PLANE-CONV). */
export interface Principal {
  readonly attestation: IdentityAttestation;
  readonly kind: string;
  readonly principalId: Identifier;
  readonly schemaVersion: SchemaVersion;
  readonly displayName?: string | null;
}

/** never: no automatic re-execution. safe: externally idempotent. verify-before-retry: observe external state first (ADR-0108). */
export type ReplayPolicy = "never" | "safe" | "verify-before-retry";
export const ReplayPolicyValues = [
  "never",
  "safe",
  "verify-before-retry",
] as const;

/** A revocation of a principal, delegation, or session. Additive plane-convergence extension (ADR-DT-PLANE-CONV). */
export interface RevocationRecord {
  readonly reason: string;
  readonly revocationId: Identifier;
  readonly revokedAt: Timestamp;
  readonly schemaVersion: SchemaVersion;
  readonly targetId: Identifier;
}

/** Operator-facing risk band for a bounded approval request. Advisory only; CAPT authority invariants remain the sole enforcement path. */
export type RiskClassification = "none" | "low" | "medium" | "high" | "consequential";
export const RiskClassificationValues = [
  "none",
  "low",
  "medium",
  "high",
  "consequential",
] as const;

/** The CAPT runtime instance principal. Additive plane-convergence extension (ADR-DT-PLANE-CONV). */
export interface RuntimeIdentity {
  readonly principalId: Identifier;
  readonly runtimeId: Identifier;
  readonly schemaVersion: SchemaVersion;
  readonly version: string;
}

/** Contract-set version. Readers MUST reject an unequal value (ADR-0101). */
export type SchemaVersion = "1.0.0";

/** SequenceNumber */
export type SequenceNumber = number;

/** A bounded session under which authority is exercised. A session token alone must never become unrestricted authority. Additive plane-convergence extension (ADR-DT-PLANE-CONV). */
export interface SessionIdentity {
  readonly expiresAt: Timestamp;
  readonly issuedAt: Timestamp;
  readonly principalId: Identifier;
  readonly schemaVersion: SchemaVersion;
  readonly sessionId: string;
}

/** Aggregate stream identifier. The prefix declares the owning aggregate (ADR-0103) and is enforced by the store. */
export type StreamId = string;

/** RFC 3339 UTC instant. Descriptive only: never used for ordering or conflict resolution (ADR-0106). */
export type Timestamp = string;

/** An isolated worktree/staging directory for artifact production. Additive plane-convergence extension (ADR-DT-PLANE-CONV). */
export interface WorkspaceDescriptor {
  readonly pathScope: PathScope;
  readonly rootPath: string;
  readonly schemaVersion: SchemaVersion;
  readonly workspaceId: Identifier;
}

/** A time-boxed, scoped lease over a workspace. Additive plane-convergence extension (ADR-DT-PLANE-CONV). */
export interface WorkspaceLease {
  readonly expiresAt: Timestamp;
  readonly issuedAt: Timestamp;
  readonly leaseId: Identifier;
  readonly schemaVersion: SchemaVersion;
  readonly state: string;
  readonly workspaceId: Identifier;
}

/** Minimal read-only projection handed to a driver. MUST NOT contain governance, policy, claim, capability-graph, ledger, or aggregate references (ADR-0125). */
export interface ContextSlice {
  readonly budgets: DriverBudget;
  readonly expectedArtifacts: readonly ExpectedArtifact[];
  readonly filesystemPolicy: FilesystemPolicy;
  readonly lease: Readonly<Record<string, unknown>>;
  readonly permittedTools: readonly string[];
  readonly schemaVersion: SchemaVersion;
  readonly terminationConditions: DriverTerminationCondition;
  readonly contextPackRef?: unknown | null;
  readonly networkPolicy?: NetworkPolicy;
}

/** A driver-produced artifact candidate. CAPT validates existence before creating an EvidenceRecord. */
export interface DriverArtifactCandidate {
  readonly artifactDigest: string;
  readonly artifactPath: string;
  readonly candidateId: Identifier;
  readonly driverRunId: Identifier;
  readonly producedAt: Timestamp;
  readonly schemaVersion: SchemaVersion;
}

/** Alias of DriverBudgets; resource ceilings for one run. */
export interface DriverBudget {
  readonly maxArtifacts?: number;
  readonly maxObservations?: number;
  readonly maxSeconds?: number;
}

/** DriverBudgets */
export interface DriverBudgets {
  readonly maxArtifacts?: number;
  readonly maxObservations?: number;
  readonly maxSeconds?: number;
}

/** CAPT-authored request to cancel a driver run. The driver cannot self-cancel authoritatively. */
export interface DriverCancellationRequest {
  readonly driverRunId: Identifier;
  readonly reason: string;
  readonly requestedAt: Timestamp;
  readonly schemaVersion: SchemaVersion;
}

/** Read-only capability set a driver may be granted. M0-B permits only read/analysis/artifact-candidate operations; RepositoryWrite is forbidden for drivers. */
export interface DriverCapabilities {
  readonly budgets: DriverBudget;
  readonly filesystemPolicy: FilesystemPolicy;
  readonly operations: readonly string[];
  readonly permittedTools: readonly string[];
  readonly schemaVersion: SchemaVersion;
}

/** What a driver declares it can do. A declaration grants NO execution authority (ADR-0120). */
export interface DriverCapabilityDeclaration {
  readonly declaredOperations: readonly string[];
  readonly declaredScopes: readonly ResourceScope[];
  readonly declaredTools: readonly string[];
  readonly driverId: Identifier;
  readonly schemaVersion: SchemaVersion;
}

/** Records the runtime/contract compatibility of a driver at registration time. */
export interface DriverCompatibilityRecord {
  readonly compatible: boolean;
  readonly contractSchemaVersion: SchemaVersion;
  readonly driverId: Identifier;
  readonly runtimeVersion: string;
  readonly schemaVersion: SchemaVersion;
  readonly notes?: string | null;
}

/** DriverDescriptor */
export interface DriverDescriptor {
  readonly driverId: Identifier;
  readonly driverVersion: string;
  readonly schemaVersion: SchemaVersion;
  readonly supportedOperations: readonly string[];
  readonly writeCapable: boolean;
}

/** Untrusted driver-reported error. CAPT decides failure disposition; the driver cannot set terminal state authoritatively. */
export interface DriverError {
  readonly driverRunId: Identifier;
  readonly errorId: Identifier;
  readonly message: string;
  readonly reportedAt: Timestamp;
  readonly schemaVersion: SchemaVersion;
}

/** DriverProgressSignal */
export interface DriverProgressSignal {
  readonly driverRunId: Identifier;
  readonly phase: string;
  readonly reportedAt: Timestamp;
  readonly schemaVersion: SchemaVersion;
  readonly signalId: Identifier;
  readonly fraction?: number;
}

/** Driver-claimed receipt of a step. CAPT validates against the ledger; fake receipts are rejected. */
export interface DriverReceiptCandidate {
  readonly claimedAt: Timestamp;
  readonly driverRunId: Identifier;
  readonly receiptId: Identifier;
  readonly schemaVersion: SchemaVersion;
  readonly step: string;
  readonly contentDigest?: string;
}

/** CAPT-authored reconciliation report for a driver run. */
export interface DriverReconciliationRecord {
  readonly anomalies: readonly string[];
  readonly detectedAt: Timestamp;
  readonly driverRunId: Identifier;
  readonly result: DriverReconciliationResult;
  readonly schemaVersion: SchemaVersion;
}

/** Outcome of a CAPT reconciliation pass over a driver run. No automatic re-execution is implied. */
export type DriverReconciliationResult = "reconciled_completed" | "reconciled_failed" | "reconciliation_requires_human" | "safe_to_retry" | "retry_forbidden" | "external_state_unknown";
export const DriverReconciliationResultValues = [
  "reconciled_completed",
  "reconciled_failed",
  "reconciliation_requires_human",
  "safe_to_retry",
  "retry_forbidden",
  "external_state_unknown",
] as const;

/** DriverReconciliationStatus */
export type DriverReconciliationStatus = "not_required" | "required" | "in_progress" | "resolved_effect_occurred" | "resolved_effect_absent" | "unresolvable";
export const DriverReconciliationStatusValues = [
  "not_required",
  "required",
  "in_progress",
  "resolved_effect_occurred",
  "resolved_effect_absent",
  "unresolvable",
] as const;

/** Optional CAPT-authored input to resume a suspended run. */
export interface DriverResumeInput {
  readonly driverRunId: Identifier;
  readonly schemaVersion: SchemaVersion;
  readonly resumeNote?: string | null;
}

/** DriverRun */
export interface DriverRun {
  readonly createdAt: Timestamp;
  readonly driverId: Identifier;
  readonly driverRunId: Identifier;
  readonly missionId: Identifier;
  readonly reconciliationStatus: DriverReconciliationStatus;
  readonly schemaVersion: SchemaVersion;
  readonly state: DriverRunState;
  readonly taskId: Identifier;
  readonly workOrderVersion: number;
  readonly externalRunId?: string | null;
}

/** Per-run recovery state embedded in the CAPT CheckpointManifest. Trusted only after integrity verification. */
export interface DriverRunCheckpoint {
  readonly driverRunId: Identifier;
  readonly lastEventGlobalSequence: number;
  readonly lastObservationDigest: string | null;
  readonly openReservations: number;
  readonly reconciliationStatus: DriverReconciliationStatus;
  readonly state: DriverRunState;
  readonly workOrderVersion: number;
}

/** DriverRunState */
export type DriverRunState = "created" | "queued" | "submitted" | "running" | "suspended" | "completed" | "cancelled" | "failed" | "lost" | "reconciled";
export const DriverRunStateValues = [
  "created",
  "queued",
  "submitted",
  "running",
  "suspended",
  "completed",
  "cancelled",
  "failed",
  "lost",
  "reconciled",
] as const;

/** How CAPT terminates a run on anomaly. */
export interface DriverTerminationCondition {
  readonly onBudgetExceeded?: string;
  readonly onTimeout?: string;
  readonly onUnexpectedWrite?: unknown;
}

/** Alias of ExecutionDriverWorkOrder retained for compatibility. */
export interface DriverWorkOrder {
  readonly contextSlice: ContextSlice;
  readonly driverId: Identifier;
  readonly driverRunId: Identifier;
  readonly missionId: Identifier;
  readonly operations: readonly string[];
  readonly schemaVersion: SchemaVersion;
  readonly taskId: Identifier;
  readonly workOrderVersion: number;
}

/** Authoritative CAPT name for the driver descriptor contract (ADR-0120). Structurally identical to DriverDescriptor. */
export interface ExecutionDriverDescriptor {
  readonly driverId: Identifier;
  readonly driverVersion: string;
  readonly schemaVersion: SchemaVersion;
  readonly supportedOperations: readonly string[];
  readonly writeCapable: boolean;
}

/** CAPT-authored instruction to a driver. Operations must be read-only (ADR-0122). */
export interface ExecutionDriverWorkOrder {
  readonly contextSlice: ContextSlice;
  readonly driverId: Identifier;
  readonly driverRunId: Identifier;
  readonly missionId: Identifier;
  readonly operations: readonly string[];
  readonly schemaVersion: SchemaVersion;
  readonly taskId: Identifier;
  readonly workOrderVersion: number;
  readonly memoryPolicyRef?: unknown | null;
}

/** Descriptor for an artifact a driver may create in the CAPT staging area. */
export interface ExpectedArtifact {
  readonly artifactKind: string;
  readonly artifactPath: string;
}

/** FilesystemPolicy */
export interface FilesystemPolicy {
  readonly allowedPaths: readonly string[];
  readonly rootPath: string;
  readonly writesAllowed: unknown;
}

/** M0-B drivers are read-only; outbound network is denied by default. */
export interface NetworkPolicy {
  readonly allowedHosts: readonly string[];
  readonly egressAllowed: unknown;
}

/** Alias of DriverReceiptCandidate; a driver-claimed step receipt. */
export interface RequiredReceipt {
  readonly claimedAt: Timestamp;
  readonly driverRunId: Identifier;
  readonly receiptId: Identifier;
  readonly schemaVersion: SchemaVersion;
  readonly step: string;
  readonly contentDigest?: string;
}

/** CapabilityGrantRevokedPayload */
export interface CapabilityGrantRevokedPayload {
  readonly eventType: "CapabilityGrantRevoked";
  readonly revocation: CapabilityRevocation;
}

/** CapabilityGrantedPayload */
export interface CapabilityGrantedPayload {
  readonly eventType: "CapabilityGranted";
  readonly grant: CapabilityGrant;
}

/** CapabilityLeaseActivatedPayload */
export interface CapabilityLeaseActivatedPayload {
  readonly eventType: "CapabilityLeaseActivated";
  readonly lease: CapabilityLease;
}

/** CapabilityLeaseRevokedPayload */
export interface CapabilityLeaseRevokedPayload {
  readonly eventType: "CapabilityLeaseRevoked";
  readonly revocation: CapabilityRevocation;
}

/** CapabilityUseFinalizedPayload */
export interface CapabilityUseFinalizedPayload {
  readonly consumption: CapabilityConsumptionRecord;
  readonly eventType: "CapabilityUseFinalized";
}

/** CapabilityUseReservedPayload */
export interface CapabilityUseReservedPayload {
  readonly eventType: "CapabilityUseReserved";
  readonly reservation: CapabilityReservation;
}

/** CheckpointCreatedPayload */
export interface CheckpointCreatedPayload {
  readonly checkpointId: Identifier;
  readonly eventType: "CheckpointCreated";
  readonly integrityDigest: Digest;
}

/** ClaimCreatedPayload */
export interface ClaimCreatedPayload {
  readonly claim: ClaimRecord;
  readonly eventType: "ClaimCreated";
}

/** ClaimGuardDecidedPayload */
export interface ClaimGuardDecidedPayload {
  readonly decision: ClaimGuardDecision;
  readonly eventType: "ClaimGuardDecided";
}

/** ClaimVerifiedPayload */
export interface ClaimVerifiedPayload {
  readonly eventType: "ClaimVerified";
  readonly verification: VerificationResult;
}

/** DriverRunCreatedPayload */
export interface DriverRunCreatedPayload {
  readonly driverRun: DriverRun;
  readonly eventType: "DriverRunCreated";
}

/** DriverRunStateChangedPayload */
export interface DriverRunStateChangedPayload {
  readonly driverRunId: Identifier;
  readonly eventType: "DriverRunStateChanged";
  readonly fromState: DriverRunState;
  readonly toState: DriverRunState;
}

/** Authoritative durable event. Only the CAPT runtime constructs this (ADR-0110). */
export interface EventEnvelope {
  readonly actor: ActorRef;
  readonly correlationId: Identifier;
  readonly eventId: Identifier;
  readonly eventType: EventType;
  readonly globalSequence: SequenceNumber;
  readonly occurredAt: Timestamp;
  readonly payload: EventPayload;
  readonly payloadDigest: Digest;
  readonly schemaVersion: SchemaVersion;
  readonly streamId: StreamId;
  readonly streamVersion: SequenceNumber;
  readonly causationId?: Identifier | null;
  readonly claimId?: Identifier | null;
  readonly extensions?: readonly ExtensionEnvelope[];
  readonly missionId?: Identifier | null;
  readonly taskId?: Identifier | null;
}

/** Discriminated union on eventType. Ledger Finding C: no arbitrary event payload is permitted. */
/** Discriminated on `eventType`. */
export type EventPayload =
  | MissionCreatedPayload
  | PolicyEvaluatedPayload
  | MissionStateChangedPayload
  | CheckpointCreatedPayload
  | MissionResumedPayload
  | TaskCreatedPayload
  | TaskTransitionedPayload
  | CapabilityGrantedPayload
  | CapabilityLeaseActivatedPayload
  | CapabilityUseReservedPayload
  | CapabilityUseFinalizedPayload
  | CapabilityGrantRevokedPayload
  | CapabilityLeaseRevokedPayload
  | DriverRunCreatedPayload
  | DriverRunStateChangedPayload
  | ClaimCreatedPayload
  | EvidenceRecordedPayload
  | ClaimVerifiedPayload
  | ClaimGuardDecidedPayload
  | HumanApprovalRequestedPayload
  | HumanApprovalDecidedPayload;

/** Closed set of authoritative event types. A driver-supplied name is not a member and is rejected by the store (ADR-0110). */
export type EventType = "MissionCreated" | "PolicyEvaluated" | "MissionStateChanged" | "CheckpointCreated" | "MissionResumed" | "TaskCreated" | "TaskTransitioned" | "CapabilityGranted" | "CapabilityLeaseActivated" | "CapabilityUseReserved" | "CapabilityUseFinalized" | "CapabilityGrantRevoked" | "CapabilityLeaseRevoked" | "DriverRunCreated" | "DriverRunStateChanged" | "ClaimCreated" | "EvidenceRecorded" | "ClaimVerified" | "ClaimGuardDecided" | "HumanApprovalRequested" | "HumanApprovalDecided";
export const EventTypeValues = [
  "MissionCreated",
  "PolicyEvaluated",
  "MissionStateChanged",
  "CheckpointCreated",
  "MissionResumed",
  "TaskCreated",
  "TaskTransitioned",
  "CapabilityGranted",
  "CapabilityLeaseActivated",
  "CapabilityUseReserved",
  "CapabilityUseFinalized",
  "CapabilityGrantRevoked",
  "CapabilityLeaseRevoked",
  "DriverRunCreated",
  "DriverRunStateChanged",
  "ClaimCreated",
  "EvidenceRecorded",
  "ClaimVerified",
  "ClaimGuardDecided",
  "HumanApprovalRequested",
  "HumanApprovalDecided",
] as const;

/** EvidenceRecordedPayload */
export interface EvidenceRecordedPayload {
  readonly eventType: "EvidenceRecorded";
  readonly evidence: EvidenceRecord;
}

/** HumanApprovalDecidedPayload */
export interface HumanApprovalDecidedPayload {
  readonly decision: HumanApprovalDecision;
  readonly eventType: "HumanApprovalDecided";
}

/** HumanApprovalRequestedPayload */
export interface HumanApprovalRequestedPayload {
  readonly eventType: "HumanApprovalRequested";
  readonly request: HumanApprovalRequest;
}

/** MissionCreatedPayload */
export interface MissionCreatedPayload {
  readonly eventType: "MissionCreated";
  readonly missionSpec: MissionSpec;
}

/** MissionResumedPayload */
export interface MissionResumedPayload {
  readonly checkpointId: Identifier;
  readonly eventType: "MissionResumed";
  readonly resumedFromGlobalSequence: SequenceNumber;
}

/** MissionStateChangedPayload */
export interface MissionStateChangedPayload {
  readonly eventType: "MissionStateChanged";
  readonly fromState: MissionState;
  readonly reason: string;
  readonly toState: MissionState;
}

/** PolicyEvaluatedPayload */
export interface PolicyEvaluatedPayload {
  readonly eventType: "PolicyEvaluated";
  readonly policyDecision: PolicyDecision;
}

/** TaskCreatedPayload */
export interface TaskCreatedPayload {
  readonly eventType: "TaskCreated";
  readonly task: TaskNode;
}

/** TaskTransitionedPayload */
export interface TaskTransitionedPayload {
  readonly eventType: "TaskTransitioned";
  readonly fromState: TaskState;
  readonly reason: string;
  readonly taskId: Identifier;
  readonly toState: TaskState;
}

/** ArtifactHashEvidence */
export interface ArtifactHashEvidence {
  readonly artifactDigest: Digest;
  readonly artifactPath: string;
  readonly kind: "artifact_hash";
}

/** CommandExitEvidence */
export interface CommandExitEvidence {
  readonly command: string;
  readonly exitCode: number;
  readonly kind: "command_exit";
  readonly outputDigest: Digest;
}

/** UNTRUSTED Family B type. Can only enter CAPT as an UNVERIFIED ClaimRecord; promotion requires an independent VerificationResult (ADR-0110). */
export interface DriverClaimProposal {
  readonly observedBy: Identifier;
  readonly proposalId: Identifier;
  readonly proposedAt: Timestamp;
  readonly schemaVersion: SchemaVersion;
  readonly statement: string;
  readonly trust: "untrusted";
  readonly workOrderId: Identifier;
}

/** UNTRUSTED Family B type (ADR-0110). Deliberately has no streamId/streamVersion/eventType, so it cannot be appended to the ledger. Do not merge with EvidenceRecord. */
export interface DriverObservation {
  readonly observationId: Identifier;
  readonly observedAt: Timestamp;
  readonly observedBy: Identifier;
  readonly schemaVersion: SchemaVersion;
  readonly summary: string;
  readonly trust: "untrusted";
  readonly workOrderId: Identifier;
}

/** EvidenceKind */
/** Discriminated on `kind`. */
export type EvidenceKind =
  | ArtifactHashEvidence
  | CommandExitEvidence
  | SchemaValidationEvidence
  | StateAssertionEvidence
  | HumanAttestationEvidence;

/** Authoritative record. CAPT-constructed only. A driver observation must be converted through validation (ADR-0110); provenance is preserved in sourceObservationId without transferring authority. */
export interface EvidenceRecord {
  readonly collectedAt: Timestamp;
  readonly collectedBy: ActorRef;
  readonly evidence: EvidenceKind;
  readonly evidenceId: Identifier;
  readonly missionId: Identifier;
  readonly schemaVersion: SchemaVersion;
  readonly trust: "capt_authoritative";
  readonly sourceObservationId?: Identifier | null;
  readonly taskId?: Identifier | null;
}

/** HumanAttestationEvidence */
export interface HumanAttestationEvidence {
  readonly attestedBy: ActorRef;
  readonly kind: "human_attestation";
  readonly statement: string;
}

/** SchemaValidationEvidence */
export interface SchemaValidationEvidence {
  readonly kind: "schema_validation";
  readonly schemaId: string;
  readonly valid: boolean;
}

/** StateAssertionEvidence */
export interface StateAssertionEvidence {
  readonly kind: "state_assertion";
  readonly stateDigest: Digest;
  readonly streamId: StreamId;
  readonly streamVersion: AggregateVersion;
}

/** ApprovalRequiredConstraint */
export interface ApprovalRequiredConstraint {
  readonly approverRole: string;
  readonly constraintId: Identifier;
  readonly kind: "approval_required";
  readonly origin: ConstraintOrigin;
}

/** BudgetConstraint */
export interface BudgetConstraint {
  readonly budget: Budget;
  readonly constraintId: Identifier;
  readonly kind: "budget";
  readonly origin: ConstraintOrigin;
}

/** Discriminated union. Ledger Finding C: no arbitrary payload is permitted in a constraint. */
/** Discriminated on `kind`. */
export type Constraint =
  | ForbiddenOperationConstraint
  | ResourceBoundaryConstraint
  | BudgetConstraint
  | ApprovalRequiredConstraint;

/** Provenance of a constraint. 'inferred' constraints carry lower authority and are surfaced separately (spec 7.2). */
export type ConstraintOrigin = "explicit_user" | "inferred" | "policy_added";
export const ConstraintOriginValues = [
  "explicit_user",
  "inferred",
  "policy_added",
] as const;

/** ForbiddenOperationConstraint */
export interface ForbiddenOperationConstraint {
  readonly constraintId: Identifier;
  readonly kind: "forbidden_operation";
  readonly operations: readonly string[];
  readonly origin: ConstraintOrigin;
}

/** Compiled mission. Preserves raw and normalized input plus constraint provenance (spec 7.2). */
export interface MissionSpec {
  readonly constraints: readonly Constraint[];
  readonly createdAt: Timestamp;
  readonly missionId: Identifier;
  readonly normalizedRequest: string;
  readonly objectives: readonly Objective[];
  readonly rawRequest: string;
  readonly schemaVersion: SchemaVersion;
  readonly successCriteria: readonly SuccessCriterion[];
  readonly terminationCriteria: readonly TerminationCriterion[];
  readonly unresolvedAmbiguities: readonly string[];
  readonly taskGraphId?: Identifier | null;
}

/** MissionState */
export type MissionState = "draft" | "authorized" | "executing" | "suspended" | "completed" | "failed" | "cancelled";
export const MissionStateValues = [
  "draft",
  "authorized",
  "executing",
  "suspended",
  "completed",
  "failed",
  "cancelled",
] as const;

/** Objective */
export interface Objective {
  readonly objectiveId: Identifier;
  readonly priority: number;
  readonly statement: string;
}

/** ResourceBoundaryConstraint */
export interface ResourceBoundaryConstraint {
  readonly constraintId: Identifier;
  readonly kind: "resource_boundary";
  readonly origin: ConstraintOrigin;
  readonly scope: ResourceScope;
}

/** SuccessCriterion */
export interface SuccessCriterion {
  readonly criterionId: Identifier;
  readonly requiresVerification: boolean;
  readonly statement: string;
}

/** TerminationCriterion */
export interface TerminationCriterion {
  readonly criterionId: Identifier;
  readonly statement: string;
  readonly terminalState: string;
}

/** Binds authority to the exact policy version that produced it (ledger Finding I). A CapabilityGrant without a PolicyDecision reference is invalid. */
export interface PolicyDecision {
  readonly decidedAt: Timestamp;
  readonly decidedBy: ActorRef;
  readonly effect: PolicyEffect;
  readonly policyBundleDigest: Digest;
  readonly policyDecisionId: Identifier;
  readonly rationale: string;
  readonly requestedOperations: readonly string[];
  readonly requestedScope: ResourceScope;
  readonly schemaVersion: SchemaVersion;
  readonly subject: ActorRef;
  readonly conditions?: readonly GrantCondition[];
  readonly missionId?: Identifier | null;
  readonly taskId?: Identifier | null;
}

/** PolicyEffect */
export type PolicyEffect = "allow" | "deny" | "allow_with_conditions" | "escalate";
export const PolicyEffectValues = [
  "allow",
  "deny",
  "allow_with_conditions",
  "escalate",
] as const;

/** Spec 8: 'parallel' is NOT an edge type. Parallelism emerges when predecessor conditions are simultaneously satisfied. */
export type DependencyCondition = "completed" | "succeeded" | "failed" | "verified" | "approved";
export const DependencyConditionValues = [
  "completed",
  "succeeded",
  "failed",
  "verified",
  "approved",
] as const;

/** TaskDependency */
export interface TaskDependency {
  readonly condition: DependencyCondition;
  readonly dependencyId: Identifier;
  readonly predecessorTaskId: Identifier;
  readonly successorTaskId: Identifier;
}

/** TaskGraph */
export interface TaskGraph {
  readonly dependencies: readonly TaskDependency[];
  readonly missionId: Identifier;
  readonly nodes: readonly TaskNode[];
  readonly schemaVersion: SchemaVersion;
  readonly taskGraphId: Identifier;
}

/** TaskNode */
export interface TaskNode {
  readonly attempt: number;
  readonly capabilityRequirements: readonly CapabilityRequirement[];
  readonly consequential: boolean;
  readonly maxAttempts: number;
  readonly missionId: Identifier;
  readonly state: TaskState;
  readonly taskId: Identifier;
  readonly title: string;
  readonly assignedDriverId?: Identifier | null;
  readonly recoveryState?: TaskRecoveryState;
}

/** TaskRecoveryState */
export type TaskRecoveryState = "none" | "awaiting_reconciliation" | "reconciled" | "abandoned";
export const TaskRecoveryStateValues = [
  "none",
  "awaiting_reconciliation",
  "reconciled",
  "abandoned",
] as const;

/** Closed task lifecycle. Terminal states are succeeded, failed, cancelled (ADR-0103). */
export type TaskState = "pending" | "ready" | "assigned" | "running" | "suspended" | "awaiting_verification" | "succeeded" | "failed" | "cancelled";
export const TaskStateValues = [
  "pending",
  "ready",
  "assigned",
  "running",
  "suspended",
  "awaiting_verification",
  "succeeded",
  "failed",
  "cancelled",
] as const;

/** BooleanArgument */
export interface BooleanArgument {
  readonly kind: "boolean";
  readonly name: string;
  readonly value: boolean;
}

/** IntegerArgument */
export interface IntegerArgument {
  readonly kind: "integer";
  readonly name: string;
  readonly value: number;
}

/** PathArgument */
export interface PathArgument {
  readonly kind: "path";
  readonly name: string;
  readonly value: string;
}

/** StringArgument */
export interface StringArgument {
  readonly kind: "string";
  readonly name: string;
  readonly value: string;
}

/** Typed argument. A generic map would allow injection of unvalidated parameters into a consequential call. */
/** Discriminated on `kind`. */
export type ToolArgument =
  | StringArgument
  | IntegerArgument
  | BooleanArgument
  | PathArgument;

/** leaseId is REQUIRED for a consequential request: no side effect without a lease (invariant 7). */
export interface ToolRequest {
  readonly arguments: readonly ToolArgument[];
  readonly consequential: boolean;
  readonly idempotencyKey: Identifier;
  readonly operation: string;
  readonly operationFingerprint: Digest;
  readonly replayPolicy: ReplayPolicy;
  readonly requestedAt: Timestamp;
  readonly schemaVersion: SchemaVersion;
  readonly toolId: Identifier;
  readonly toolRequestId: Identifier;
  readonly leaseId?: Identifier | null;
  readonly reservationId?: Identifier | null;
}

/** ToolResult */
export interface ToolResult {
  readonly completedAt: Timestamp;
  readonly schemaVersion: SchemaVersion;
  readonly status: ToolResultStatus;
  readonly toolRequestId: Identifier;
  readonly toolResultId: Identifier;
  readonly error?: ErrorEnvelope | null;
  readonly exitCode?: number | null;
  readonly outputDigest?: Digest | null;
  readonly sideEffectIdentity?: string | null;
}

/** ToolResultStatus */
export type ToolResultStatus = "succeeded" | "failed" | "indeterminate" | "denied";
export const ToolResultStatusValues = [
  "succeeded",
  "failed",
  "indeterminate",
  "denied",
] as const;

/** ContradictedStatus */
export interface ContradictedStatus {
  readonly contradictingEvidenceIds: readonly Identifier[];
  readonly kind: "contradicted";
}

/** InconclusiveStatus */
export interface InconclusiveStatus {
  readonly kind: "inconclusive";
  readonly reason: string;
}

/** InferenceStatus */
export interface InferenceStatus {
  readonly basis: string;
  readonly kind: "inference";
}

/** NotTestedStatus */
export interface NotTestedStatus {
  readonly kind: "not_tested";
}

/** ObservedUnverifiedStatus */
export interface ObservedUnverifiedStatus {
  readonly kind: "observed_unverified";
  readonly reason: string;
}

/** Produced by the verification plane. Verification must not mutate the artifact it verifies (invariant: authority separation). */
export interface VerificationResult {
  readonly claimId: Identifier;
  readonly schemaVersion: SchemaVersion;
  readonly status: VerificationStatus;
  readonly strategy: VerificationStrategy;
  readonly verificationId: Identifier;
  readonly verifiedAt: Timestamp;
  readonly verifiedBy: ActorRef;
}

/** Discriminated union. Spec workflow section 9 requires every completion statement to be classified. */
/** Discriminated on `kind`. */
export type VerificationStatus =
  | VerifiedStatus
  | ObservedUnverifiedStatus
  | InferenceStatus
  | ContradictedStatus
  | InconclusiveStatus
  | NotTestedStatus;

/** VerificationStrategy */
export type VerificationStrategy = "direct_observation" | "deterministic_schema_validation" | "artifact_hashing" | "test_exit_status" | "invariant_check" | "independent_reproduction" | "source_triangulation" | "counterargument" | "human_review";
export const VerificationStrategyValues = [
  "direct_observation",
  "deterministic_schema_validation",
  "artifact_hashing",
  "test_exit_status",
  "invariant_check",
  "independent_reproduction",
  "source_triangulation",
  "counterargument",
  "human_review",
] as const;

/** VerifiedStatus */
export interface VerifiedStatus {
  readonly kind: "verified";
  readonly supportingEvidenceIds: readonly Identifier[];
}
