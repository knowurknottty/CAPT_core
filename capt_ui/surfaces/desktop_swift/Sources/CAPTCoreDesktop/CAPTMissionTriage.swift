import Foundation

/// Human-readable *derived* workflow triage. Stored mission/task states are
/// preserved and may be inspected verbatim; no state transition is inferred.
public enum CAPTMissionTriage: String, Sendable, CaseIterable {
    case interrupted = "Interrupted"
    case awaitingReview = "Needs verification"
    case failed = "Failed task"
    case markedRunning = "Marked running"
    case waiting = "Not started"
    case completed = "Completed"
    case historical = "Historical"

    public static func classify(_ mission: CAPTMissionSummary) -> Self {
        let states = Set(mission.tasks.map { $0.state.lowercased() })
        if states.contains("suspended") { return .interrupted }
        if states.contains("awaiting_verification") { return .awaitingReview }
        if states.contains("failed") { return .failed }
        if states.contains("running") { return .markedRunning }
        if states.contains("pending") || states.contains("ready") ||
           states.contains("assigned") { return .waiting }
        if mission.taskCount > 0 && mission.succeededTaskCount == mission.taskCount {
            return .completed
        }
        return .historical
    }

    public var needsHumanAttention: Bool {
        switch self {
        case .interrupted, .awaitingReview, .failed: return true
        default: return false
        }
    }

    public var priority: Int {
        switch self {
        case .interrupted: return 0
        case .awaitingReview: return 1
        case .failed: return 2
        case .markedRunning: return 3
        case .waiting: return 4
        case .completed: return 5
        case .historical: return 6
        }
    }

    public var explanation: String {
        switch self {
        case .interrupted:
            return "A task is suspended. Its previous run may be lost; this is not active execution."
        case .awaitingReview:
            return "Provider output is recorded, but a human has not accepted or rejected the result."
        case .failed:
            return "A task failed. Inspect its run receipt before deciding whether a new attempt is justified."
        case .markedRunning:
            return "A task is stored as running. This does not prove the external driver is still alive."
        case .waiting:
            return "Tasks are pending or assigned. No completed execution has been established."
        case .completed:
            return "All projected tasks succeeded. Stored mission state may not have transitioned."
        case .historical:
            return "No actionable execution is established by the projected task states."
        }
    }

    public var nextStep: String {
        switch self {
        case .interrupted: return "Inspect the lost DriverRun and reconcile or explicitly retry under authority."
        case .awaitingReview: return "Inspect the execution receipt, then perform human verification."
        case .failed: return "Read the failure and decide whether a governed retry is warranted."
        case .markedRunning: return "Check DriverRun/worker health and progress before calling it live."
        case .waiting: return "Inspect dependencies and existing approvals before dispatch."
        case .completed: return "Check the mission completion criteria; do not invent a closure event."
        case .historical: return "Keep for audit; no automatic action."
        }
    }

    public static func readableTitle(_ title: String, maxLength: Int = 125) -> String {
        let compact = title.split(whereSeparator: \.isWhitespace).joined(separator: " ")
        guard compact.count > maxLength else { return compact }
        let candidate = String(compact.prefix(maxLength))
        return candidate.trimmingCharacters(in: .whitespaces) + "…"
    }

    public static func counts(_ mission: CAPTMissionSummary) -> String {
        let states = mission.tasks.reduce(into: [String: Int]()) {
            $0[$1.state, default: 0] += 1
        }
        let order = ["running", "awaiting_verification", "suspended", "failed",
                     "pending", "ready", "assigned", "succeeded", "cancelled"]
        return order.compactMap { state -> String? in
            guard let amount = states[state], amount > 0 else { return nil }
            let names = ["awaiting_verification":"need review",
                         "suspended":"interrupted", "succeeded":"done"]
            return String(amount) + " " + (names[state] ?? state)
        }.joined(separator: " · ")
    }
}
