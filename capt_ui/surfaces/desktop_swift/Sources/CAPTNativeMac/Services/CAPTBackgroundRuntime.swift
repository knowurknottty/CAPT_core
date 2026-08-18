import Foundation
import CAPTCoreDesktop

actor CAPTBackgroundRuntime {
    private let client: CAPTRuntimeClient
    private let coordinator: CAPTChatCoordinator
    private let bootstrapper: CAPTRuntimeBootstrapper

    init(
        client: CAPTRuntimeClient = CAPTRuntimeClient(),
        bootstrapper: CAPTRuntimeBootstrapper = CAPTRuntimeBootstrapper()
    ) {
        self.client = client
        self.coordinator = CAPTChatCoordinator(client: client)
        self.bootstrapper = bootstrapper
    }

    func connect() throws -> [String: Any] {
        do {
            return try client.connect()
        } catch {
            client.disconnect()
            try bootstrapper.start()
            return try client.connect()
        }
    }

    func disconnect() { client.disconnect() }

    func identity() throws -> [String: Any] {
        try client.query(op: "identity", payload: [:])
    }

    func capabilities() throws -> [String: Any] {
        try client.query(op: "capabilities", payload: [:])
    }

    func historySnapshot() throws -> CAPTHistorySnapshot {
        let aggregateResponse = try client.query(op: "list_aggregates", payload: [:])
        let aggregates = aggregateResponse["result"] as? [[String: Any]] ?? []
        var states: [String: [String: Any]] = [:]
        for aggregate in aggregates {
            guard let streamID = aggregate["streamId"] as? String else { continue }
            let response = try client.query(
                op: "get_state", payload: ["streamId": streamID]
            )
            if let state = response["result"] as? [String: Any] {
                states[streamID] = state
            }
        }
        let taskStates = aggregates.compactMap { aggregate -> [String: Any]? in
            guard aggregate["kind"] as? String == "task",
                  let stream = aggregate["streamId"] as? String else { return nil }
            return states[stream]
        }
        let missions = aggregates.compactMap { aggregate -> CAPTMissionSummary? in
            guard aggregate["kind"] as? String == "mission",
                  let stream = aggregate["streamId"] as? String,
                  let state = states[stream] else { return nil }
            return CAPTOperatorProjection.mission(state, tasks: taskStates)
        }.reversed()

        let evidence = aggregates.compactMap { aggregate -> CAPTEvidenceSummary? in
            guard aggregate["kind"] as? String == "claim",
                  let stream = aggregate["streamId"] as? String,
                  let state = states[stream] else { return nil }
            return CAPTOperatorProjection.evidence(state)
        }.reversed()

        let eventResponse = try client.query(op: "event_timeline", payload: ["after": 0])
        let rawEvents = eventResponse["result"] as? [[String: Any]] ?? []
        let events = rawEvents.suffix(250).map(CAPTOperatorProjection.event).reversed()
        return CAPTHistorySnapshot(
            missions: Array(missions),
            evidence: Array(evidence),
            events: Array(events)
        )
    }

    func requestApproval(
        objective: String,
        targetRoot: String,
        provider: String,
        model: String
    ) throws -> CAPTPendingApproval {
        try coordinator.requestApproval(
            objective: objective,
            targetRoot: targetRoot,
            provider: provider,
            model: model
        )
    }

    func deny(_ pending: CAPTPendingApproval) throws {
        try coordinator.deny(pending)
    }

    func approveAndRun(_ pending: CAPTPendingApproval) throws -> CAPTExecutionResult {
        try coordinator.approveAndRun(pending)
    }
}
