import Foundation
import CAPTCoreDesktop

actor CAPTBackgroundRuntime {
    private let client: CAPTRuntimeClient
    private let coordinator: CAPTChatCoordinator
    private let bootstrapper: CAPTRuntimeBootstrapper
    private let operatorCLI: CAPTOperatorCLI

    init(
        client: CAPTRuntimeClient = CAPTRuntimeClient(),
        bootstrapper: CAPTRuntimeBootstrapper = CAPTRuntimeBootstrapper(),
        operatorCLI: CAPTOperatorCLI = CAPTOperatorCLI()
    ) {
        self.client = client
        self.coordinator = CAPTChatCoordinator(client: client)
        self.bootstrapper = bootstrapper
        self.operatorCLI = operatorCLI
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

    func capabilitiesSnapshot() throws -> CAPTRuntimeCapabilitiesSnapshot {
        let response = try capabilities()
        let result = response["result"] as? [String: Any] ?? response
        return CAPTRuntimeControlProjection.capabilities(result)
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

        let driverRuns = aggregates.compactMap { aggregate -> CAPTDriverRunSummary? in
            guard aggregate["kind"] as? String == "driverrun",
                  let stream = aggregate["streamId"] as? String,
                  let state = states[stream] else { return nil }
            return CAPTOperatorProjection.driverRun(state)
        }.reversed()

        let evidence = aggregates.compactMap { aggregate -> CAPTEvidenceSummary? in
            guard aggregate["kind"] as? String == "claim",
                  let stream = aggregate["streamId"] as? String,
                  let state = states[stream] else { return nil }
            return CAPTOperatorProjection.evidence(state)
        }.reversed()

        let approvals = aggregates.compactMap { aggregate -> CAPTApprovalSummary? in
            guard aggregate["kind"] as? String == "human_approval",
                  let stream = aggregate["streamId"] as? String,
                  let state = states[stream] else { return nil }
            return CAPTOperatorProjection.approval(state)
        }.reversed()

        let eventResponse = try client.query(op: "event_timeline", payload: ["after": 0])
        let rawEvents = eventResponse["result"] as? [[String: Any]] ?? []
        let events = rawEvents.suffix(250).map(CAPTOperatorProjection.event).reversed()
        return CAPTHistorySnapshot(
            missions: Array(missions),
            evidence: Array(evidence),
            approvals: Array(approvals),
            driverRuns: Array(driverRuns),
            events: Array(events)
        )
    }

    func operatorSnapshot() throws -> (providers: [CAPTProviderSnapshot], models: CAPTModelSelectionSnapshot, verbosity: String) {
        (try operatorCLI.providers(), try operatorCLI.models(), try operatorCLI.verbosity())
    }

    func activateProvider(_ providerID: String) throws -> [CAPTProviderSnapshot] {
        try operatorCLI.activateProvider(providerID)
    }

    func testProvider(_ providerID: String) throws -> [CAPTProviderSnapshot] {
        try operatorCLI.testProvider(providerID)
    }

    func prewarmProvider(providerID: String, modelID: String) throws -> CAPTProviderWarmupSnapshot {
        try operatorCLI.prewarmProvider(providerID: providerID, modelID: modelID)
    }

    func setProviderKeyReference(providerID: String, reference: String) throws -> [CAPTProviderSnapshot] {
        try operatorCLI.setProviderKeyReference(providerID, reference: reference)
    }

    func setDefaultModel(providerID: String, modelID: String) throws -> CAPTModelSelectionSnapshot {
        try operatorCLI.setDefaultModel(providerID: providerID, modelID: modelID)
    }

    func setVerbosity(_ value: String) throws -> String {
        try operatorCLI.setVerbosity(value)
    }

    func memorySnapshot(missionID: String = "") throws -> CAPTMemoryRuntimeSnapshot {
        let policy = try client.query(op: "get_memory_policy", payload: [:])["result"] as? [String: Any] ?? [:]
        let state = try client.query(op: "get_memory_state", payload: ["missionId": missionID])["result"] as? [String: Any] ?? [:]
        return CAPTRuntimeControlProjection.memory(policy: policy, state: state)
    }

    func checkpoint() throws -> CAPTCheckpointSnapshot {
        let receipt = try client.command(op: "checkpoint_runtime", payload: [:], idempotencyKey: "native-checkpoint-" + UUID().uuidString.lowercased())
        guard let snapshot = CAPTRuntimeControlProjection.checkpoint(receipt) else {
            throw CAPTRuntimeClientError.malformedResponse("checkpoint receipt missing result")
        }
        return snapshot
    }

    func resume() throws -> [String: Any] {
        try client.command(op: "resume_runtime", payload: [:], idempotencyKey: "native-resume-" + UUID().uuidString.lowercased())
    }

    func shutdown() throws -> [String: Any] {
        let receipt = try client.command(
            op: "shutdown", payload: [:],
            idempotencyKey: "native-shutdown-" + UUID().uuidString.lowercased()
        )
        client.disconnect()
        return receipt
    }

    func cancelTask(_ taskID: String) throws -> [String: Any] {
        try client.command(
            op: "cancel_task",
            payload: ["taskId": taskID, "reason": "Operator cancelled from CAPT native macOS surface"],
            idempotencyKey: "native-cancel-task-" + taskID
        )
    }

    func cancelDriverRun(_ driverRunID: String) throws -> [String: Any] {
        try client.command(
            op: "cancel_driver_run",
            payload: ["driverRunId": driverRunID, "reason": "Operator cancelled from CAPT native macOS surface"],
            idempotencyKey: "native-cancel-run-" + driverRunID
        )
    }

    func updateMemoryPolicy(
        retrieval: Int, compression: Int, checkpoint: Int,
        consolidation: Int, hardStop: Int, modelSafe: Int
    ) throws -> CAPTMemoryRuntimeSnapshot {
        _ = try client.command(
            op: "update_memory_trigger_policy",
            payload: [
                "retrievalTriggerSteps": retrieval,
                "compressionTriggerSteps": compression,
                "checkpointTriggerSteps": checkpoint,
                "consolidationTriggerSteps": consolidation,
                "hardStopTriggerSteps": hardStop,
                "modelSafeLimitSteps": modelSafe,
            ],
            idempotencyKey: "native-memory-policy-" + UUID().uuidString.lowercased()
        )
        return try memorySnapshot()
    }

    func claimReview(claimID: String, statement: String) throws -> CAPTClaimReviewSnapshot {
        let guardResponse = try client.query(
            op: "claimguard", payload: ["statement": statement, "claimId": claimID]
        )
        let verificationResponse = try client.query(
            op: "verification", payload: ["claimId": claimID]
        )
        return CAPTRuntimeControlProjection.claimReview(
            claimID: claimID,
            guardResult: guardResponse["result"] as? [String: Any] ?? guardResponse,
            verification: verificationResponse["result"] as? [String: Any] ?? verificationResponse
        )
    }

    func decideApproval(requestID: String, decision: String) throws -> [String: Any] {
        try client.command(
            op: "submit_approval_decision",
            payload: [
                "requestId": requestID,
                "decision": decision,
                "note": "Decision from CAPT native approval queue"
            ],
            idempotencyKey: "native-queue-" + decision + "-" + requestID
        )
    }

    func requestApproval(
        objective: String,
        targetRoot: String,
        provider: String,
        model: String,
        missionID: String? = nil
    ) throws -> CAPTPendingApproval {
        try coordinator.requestApproval(
            objective: objective,
            targetRoot: targetRoot,
            provider: provider,
            model: model,
            missionID: missionID
        )
    }

    func deny(_ pending: CAPTPendingApproval) throws {
        try coordinator.deny(pending)
    }

    func approveAndRun(_ pending: CAPTPendingApproval) throws -> CAPTExecutionResult {
        try coordinator.approveAndRun(pending)
    }
}
