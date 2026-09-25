from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from capt_runtime.vessel_dispatcher import (
    DISPOSITION_COMPLETED,
    DISPOSITION_FAILED,
    DISPOSITION_INVALIDATED,
    DISPOSITION_STARVED,
    DISPOSITION_TIMED_OUT,
    ProviderHostConfig,
    ProviderHostInvoker,
    VesselDispatcher,
    build_medium_council,
    build_small_council,
    nearest_legal_count,
    perspective_prompt,
)


def _completed(vessel, prompt, run_id, submitted_at):
    return {
        "driverRunId": run_id,
        "state": "completed",
        "observations": [
            {
                "summary": f"ok:{vessel.vessel_id}",
            }
        ],
        "diagnostics": {
            "promptDigest": "sha256:" + __import__("hashlib").sha256(prompt.encode()).hexdigest(),
        },
    }


def test_44_maps_explicitly_to_24_medium_without_silent_geometry():
    count, tier, cohorts, vessels = nearest_legal_count(44)
    assert count == 24
    assert tier.value == "medium"
    assert (cohorts, vessels) == (4, 6)


def test_medium_blast_has_24_unique_vessel_perspectives():
    definition = build_medium_council("independence")
    seen = {}
    lock = threading.Lock()

    def capture(vessel, prompt, run_id, submitted_at):
        with lock:
            seen[vessel.vessel_id] = prompt
        return _completed(vessel, prompt, run_id, submitted_at)

    result = VesselDispatcher(
        capture,
        max_concurrent_provider_calls=4,
    ).dispatch(
        definition,
        objective="Find weak spots and independent counterexamples.",
        requested_logical_vessels=44,
    )

    assert len(result.records) == 24
    assert result.request_shortfall_starved == 20
    assert set(seen) == {r.vessel.vessel_id for r in result.records}
    assert len(set(seen.values())) == 24
    for record in result.records:
        prompt = seen[record.vessel.vessel_id]
        assert record.vessel.vessel_id in prompt
        assert record.vessel.cohort_id in prompt
        assert perspective_prompt(
            "Find weak spots and independent counterexamples.", record.vessel
        ) == prompt


def test_governor_measures_and_never_exceeds_provider_slot_limit():
    active = 0
    observed_peak = 0
    lock = threading.Lock()

    def slow(vessel, prompt, run_id, submitted_at):
        nonlocal active, observed_peak
        with lock:
            active += 1
            observed_peak = max(observed_peak, active)
        try:
            time.sleep(0.025)
            return _completed(vessel, prompt, run_id, submitted_at)
        finally:
            with lock:
                active -= 1

    result = VesselDispatcher(
        slow,
        max_concurrent_provider_calls=3,
        slot_wait_timeout=2.0,
    ).dispatch(
        build_medium_council("bounded"),
        objective="bounded concurrency proof",
    )

    assert result.disposition_counts[DISPOSITION_COMPLETED] == 24
    assert observed_peak == 3
    assert result.governor_evidence["peakProviderCalls"] == 3
    assert result.governor_evidence["peakProviderCalls"] <= 3
    assert result.governor_evidence["activeProviderCalls"] == 0


def test_failed_timed_out_and_invalidated_dispositions_are_explicit():
    definition = build_small_council("terminal-kinds")
    ids = [v.vessel_id for v in __import__(
        "capt_runtime.council", fromlist=["build_logical_blast"]
    ).build_logical_blast(definition)]

    def mixed(vessel, prompt, run_id, submitted_at):
        if vessel.vessel_id == ids[0]:
            raise RuntimeError("synthetic provider failure")
        if vessel.vessel_id == ids[1]:
            raise TimeoutError("synthetic provider timeout")
        return _completed(vessel, prompt, run_id, submitted_at)

    result = VesselDispatcher(
        mixed,
        max_concurrent_provider_calls=3,
    ).dispatch(
        definition,
        objective="terminal disposition proof",
        invalidated_vessel_ids={ids[2]},
    )
    dispositions = {r.vessel.vessel_id: r.disposition for r in result.records}

    assert dispositions[ids[0]] == DISPOSITION_FAILED
    assert dispositions[ids[1]] == DISPOSITION_TIMED_OUT
    assert dispositions[ids[2]] == DISPOSITION_INVALIDATED
    assert all(r.disposition != "pending" for r in result.records)


def test_slot_wait_exhaustion_is_starved_not_failed():
    def slow(vessel, prompt, run_id, submitted_at):
        time.sleep(0.06)
        return _completed(vessel, prompt, run_id, submitted_at)

    result = VesselDispatcher(
        slow,
        max_concurrent_provider_calls=1,
        slot_wait_timeout=0.005,
    ).dispatch(
        build_small_council("starvation"),
        objective="starvation proof",
    )

    assert result.disposition_counts[DISPOSITION_COMPLETED] >= 1
    assert result.disposition_counts[DISPOSITION_STARVED] >= 1
    for record in result.records:
        if record.disposition == DISPOSITION_STARVED:
            assert record.timing.transport_admitted_at is not None
            assert record.timing.provider_started_at is None
            assert record.timing.completed_at is None


class _CouncilStub(BaseHTTPRequestHandler):
    lock = threading.Lock()
    active = 0
    peak = 0
    seen = []

    def do_POST(self):  # noqa: N802
        raw = self.rfile.read(int(self.headers["Content-Length"]))
        body = json.loads(raw)
        cls = self.__class__
        with cls.lock:
            cls.active += 1
            cls.peak = max(cls.peak, cls.active)
            cls.seen.append(body)
        try:
            time.sleep(0.015)
            content = "COUNCIL_STUB_OK:" + body["messages"][0]["content"].split(
                "- vessel_id: ", 1
            )[1].splitlines()[0]
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    {
                        "choices": [{"message": {"content": content}}],
                        "usage": {"prompt_tokens": 20, "completion_tokens": 5},
                    }
                ).encode()
            )
        finally:
            with cls.lock:
                cls.active -= 1

    def log_message(self, format, *args):  # noqa: N802,A002
        return


def test_real_driverhost_provider_dispatch_hits_localhost_stub(tmp_path: Path):
    _CouncilStub.active = 0
    _CouncilStub.peak = 0
    _CouncilStub.seen = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _CouncilStub)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        target = tmp_path / "target"
        target.mkdir()
        (target / "README.md").write_text("dispatcher integration target\n")
        invoker = ProviderHostInvoker(
            ProviderHostConfig(
                target_repo=str(target),
                staging_root=str(tmp_path / "staging"),
                base_urls={
                    "hermes-local-stub": f"http://127.0.0.1:{server.server_port}/v1"
                },
                max_seconds=15,
                max_tokens=4096,
            )
        )
        result = VesselDispatcher(
            invoker,
            max_concurrent_provider_calls=2,
            slot_wait_timeout=2.0,
        ).dispatch(
            build_small_council("real-local-provider"),
            objective="Reply with a bounded observation proving this exact Vessel crossed the provider boundary.",
        )

        assert result.disposition_counts[DISPOSITION_COMPLETED] == 6
        assert result.governor_evidence["totalProviderCalls"] == 6
        assert result.governor_evidence["peakProviderCalls"] <= 2
        assert _CouncilStub.peak <= 2
        assert len(_CouncilStub.seen) == 6
        assert len(
            {
                body["messages"][0]["content"]
                for body in _CouncilStub.seen
            }
        ) == 6
        for record in result.records:
            assert record.provider_observation == f"COUNCIL_STUB_OK:{record.vessel.vessel_id}"
            assert record.prompt_digest and record.prompt_digest.startswith("sha256:")
            assert record.timing.transport_admitted_at is not None
            assert record.timing.provider_started_at is not None
            assert record.timing.completed_at is not None
            artifact = Path(
                record.dispatch_result["artifactCandidate"]["artifactPath"]
            )
            assert artifact.exists()
    finally:
        server.shutdown()
        server.server_close()
