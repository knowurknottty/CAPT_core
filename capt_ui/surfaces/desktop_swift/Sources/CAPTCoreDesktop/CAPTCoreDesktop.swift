// CAPT Desktop Client Contract (native macOS MVP - first slice)
//
// Thin SwiftUI value-type projections of the SAME operator concepts the CLI/TUI
// consume (see capt_ui/operator/contract.py). This is a RENDERER contract, not
// a second runtime. All values are derived from RuntimeService queries.
//
// Status: NATIVE_DESKTOP_TRACK_INITIATED. Not yet a shipped app; this defines
// the wire-contract and view-model shape the SwiftUI app renders from.

import Foundation

// CaveCAPT verbosity (presentation only - never weakens governance/evidence).
enum CaveCAPTVerbosity: String, CaseIterable, Codable {
    case minimal, normal, detailed, diagnostic
}

// Provider kind and transport, mirroring ProviderKind.
enum ProviderKind: String, Codable { case local, cloud, hybrid, unknown }
enum ProviderHealth: String, Codable { case green, yellow, red, unknown }

// Where a model selection applies.
enum ModelScope: String, Codable { case `default`, mission, temporary, workflow }

// Top-line runtime status shown in every surface.
struct OperatorStatus: Codable {
    var health: String = "unknown"        // healthy | degraded | stopped | unknown
    var runtimeVersion: String = ""
    var integrity: String = ""
    var headSequence: Int = 0
    var activeProvider: String = ""
    var activeModel: String = ""
    var contextUsed: Int = 0
    var contextLimit: Int = 0
    var approvalsPending: Int = 0
    var checkpointAvailable: Bool = false
}

// A configured provider (registration/support classification is honest).
struct ProviderState: Codable {
    var id: String
    var name: String
    var kind: ProviderKind
    var transport: String        // openai_compatible | ollama | native | subprocess
    var supportLevel: String     // REGISTERED_ONLY .. CROSS_MODEL_PROVEN
    var health: ProviderHealth = .unknown
    var latencyMs: Int?
    var models: [String] = []
    var keyRef: String = ""      // reference only, never a raw token
}

// A pinned selection value.
struct ModelPin: Codable {
    var provider: String = ""
    var model: String = ""
}

// Active-model selection (scope precedence: temporary > mission > workflow > default).
struct ModelSelection: Codable {
    var activeProvider: String = ""
    var activeModel: String = ""
    var kind: ProviderKind = .unknown
    var context: Int = 0
    var defaultModel: ModelPin? = nil
    var missionOverride: ModelPin? = nil
    var temporaryOverride: ModelPin? = nil
}

struct ApprovalRequest: Codable {
    var requestId: String
    var missionId: String
    var taskId: String
    var capability: String
    var operation: String
    var scope: String
    var risk: String
    var state: String
}

struct EvidenceView: Codable {
    var claim: String = ""
    var verdict: String = ""
    var reason: String = ""
    var verification: [String: String] = [:]
    var artifactCount: Int = 0
}

// Whole-operator projection (no hidden state).
struct Dashboard: Codable {
    var status: OperatorStatus = OperatorStatus()
    var missionCount: Int = 0
    var taskCount: Int = 0
    var approvals: [ApprovalRequest] = []
    var driverRunCount: Int = 0
    var eventCount: Int = 0
    var evidence: EvidenceView = EvidenceView()
    var ledgerChainDigest: String = ""
    var memoryActive: Bool = false
    var verbosity: CaveCAPTVerbosity = .normal
}

// The contract the SwiftUI app consumes. A thin facade over authenticated IPC.
protocol CAPTDesktopClientContract {
    func connect() throws -> OperatorStatus
    func dashboard() throws -> Dashboard
    func providers() throws -> [ProviderState]
    func modelSelection() throws -> ModelSelection
    func decide(approval requestId: String, _ decision: String) throws
    func checkpoint() throws
    func resume() throws
    func set(verbosity: CaveCAPTVerbosity) throws
    func shutdown() throws
}

// MARK: - Honest classification note
// The Swift client is a projection only. It must never mutate the CAPT ledger,
// promote driver output, or fabricate authoritative state. All mutations route
// through governed RuntimeService command ops (create_mission,
// submit_approval_decision, checkpoint_runtime, resume_runtime, shutdown).
