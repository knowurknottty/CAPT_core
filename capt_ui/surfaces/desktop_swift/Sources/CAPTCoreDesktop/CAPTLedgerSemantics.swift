import Foundation

/// Human-readable explanations for EventStore types. These are descriptions of
/// stored events only; they are not inferred state transitions or evidence.
public enum CAPTLedgerSemantics {
    public static let transportNoise: Set<String> = [
        "ToolExecutionPrepared", "ToolExecutionAdmitted",
        "ToolExecutionDispatching", "ToolExecutionSettling",
    ]

    public static func isDecisionOrResult(_ event: CAPTEventSummary) -> Bool {
        let name = event.type.lowercased()
        return name.contains("approval") || name.contains("verification") ||
            name.contains("security") || name.contains("rejection") ||
            name.contains("failed") || name.contains("cancel") ||
            name.contains("settled") || name.contains("completed") ||
            name.contains("claimaccepted") || name.contains("tasktransitioned")
    }

    public static func readableName(_ type: String) -> String {
        let known = [
            "ToolExecutionPrepared": "Tool request prepared",
            "ToolExecutionAdmitted": "Tool admitted",
            "ToolExecutionDispatching": "Tool dispatch started",
            "ToolExecutionSettling": "Tool awaiting settlement",
            "ToolExecutionTerminated": "Tool execution ended",
            "TaskTransitioned": "Task state changed",
            "ClaimCreated": "Claim recorded (not verified)",
            "EvidenceRecorded": "Evidence attached",
            "HumanApprovalRequested": "Human approval requested",
            "HumanApprovalDecided": "Human approval decision recorded",
            "DriverRunCompleted": "Driver finished",
            "DriverRunLost": "Driver run lost",
        ]
        return known[type] ?? type
    }
}
