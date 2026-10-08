import Foundation

/// Deterministic read-only work board over CAPT authoritative projections.
/// Column movement is never a state transition: only RuntimeService commands
/// may change task, evidence, approval, or execution state.
public enum CAPTKanbanLane: String, CaseIterable, Identifiable, Sendable {
    case planned = "Planned"
    case ready = "Ready"
    case markedRunning = "Execution?"
    case verification = "Needs verification"
    case blocked = "Blocked / recovery"
    case resolved = "Closed history"

    public var id: String { rawValue }

    public static func lane(for storedState: String) -> Self {
        switch storedState {
        case "pending": return .planned
        case "ready", "assigned": return .ready
        case "running": return .markedRunning
        case "awaiting_verification": return .verification
        case "suspended", "failed": return .blocked
        case "succeeded", "cancelled": return .resolved
        default: return .blocked
        }
    }

    public var explanation: String {
        switch self {
        case .planned: return "Recorded task; dependencies or planning remain."
        case .ready: return "Assigned or ready, not yet confirmed executing."
        case .markedRunning: return "Stored running state. Worker heartbeat not attested."
        case .verification: return "External work returned; human verification still required."
        case .blocked: return "Suspended, failed, or unknown; inspect before retry."
        case .resolved: return "Terminal state preserved for audit, not erased."
        }
    }
}

public struct CAPTKanbanCard: Identifiable, Sendable, Equatable {
    public let task: CAPTTaskSummary
    public let missionTitle: String
    public let missionState: String
    public let run: CAPTDriverRunSummary?
    public let approval: CAPTApprovalSummary?
    public let cohortID: String?
    public let vessels: Int?

    public var id: String { task.id }
    public var lane: CAPTKanbanLane { .lane(for: task.state) }
    public var needsAttention: Bool {
        lane == .verification || lane == .blocked ||
        (approval?.isActionable() ?? false) || lane == .markedRunning
    }
    public var participants: [String] {
        var values: [String] = []
        if let assigned = task.assignedDriverID, !assigned.isEmpty {
            values.append("Driver: " + assigned)
        }
        if let cohortID {
            values.append("Cohort: " + cohortID)
            if let vessels { values.append("Declared vessels: " + String(vessels)) }
        }
        if let approval, !approval.model.isEmpty {
            values.append("Model approval: " + approval.model)
        }
        if approval?.isActionable() == true || task.state == "awaiting_verification" {
            values.append("Human decision required")
        }
        return values.isEmpty ? ["Unassigned / no verified participant"] : values
    }
    public var nextAction: String {
        if approval?.isActionable() == true { return "Inspect HumanApproval" }
        switch lane {
        case .verification: return "Inspect the DriverRun and evidence; review the result"
        case .blocked: return "Inspect failure/recovery receipt; prepare a governed continuation"
        case .markedRunning: return "Verify worker heartbeat before treating as live"
        case .ready: return "Check dependencies, scope and authorization"
        case .planned: return "Clarify the task and dependencies"
        case .resolved: return "Inspect stored completion/disposition evidence"
        }
    }
}

public enum CAPTKanbanProjection {
    public static func cards(
        missions: [CAPTMissionSummary],
        runs: [CAPTDriverRunSummary],
        approvals: [CAPTApprovalSummary],
        council: CAPTCouncilReview? = nil
    ) -> [CAPTKanbanCard] {
        let runIndex = Dictionary(grouping: runs, by: \.taskID)
        let approvalIndex = Dictionary(grouping: approvals, by: \.taskID)
        var cards: [CAPTKanbanCard] = []
        for mission in missions {
            for task in mission.tasks {
                let matchingRuns = runIndex[task.id] ?? []
                let chosenRun = matchingRuns.first(where: { $0.state == "completed" }) ??
                    matchingRuns.first(where: { $0.state == "running" }) ??
                    matchingRuns.first
                let matchingApprovals = approvalIndex[task.id] ?? []
                let activeApproval = matchingApprovals.first(where: { $0.isActionable() }) ??
                    matchingApprovals.first
                let cohort = council?.cohorts.first(where: { $0.taskID == task.id })
                cards.append(CAPTKanbanCard(
                    task: task, missionTitle: mission.title,
                    missionState: mission.missionState,
                    run: chosenRun, approval: activeApproval,
                    cohortID: cohort?.id, vessels: cohort?.vessels
                ))
            }
        }
        return cards.sorted {
            if $0.needsAttention != $1.needsAttention { return $0.needsAttention }
            if $0.lane != $1.lane {
                let order = CAPTKanbanLane.allCases
                return (order.firstIndex(of: $0.lane) ?? 0) <
                    (order.firstIndex(of: $1.lane) ?? 0)
            }
            return $0.task.id < $1.task.id
        }
    }
}
