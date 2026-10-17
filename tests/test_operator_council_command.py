"""Read-only council operator CLI exposure regression."""
from __future__ import annotations

from capt_runtime.council import CouncilTier
from capt_ui.operator import cli
from capt_ui.operator.runtime import Operator
from tests.capt_ui.test_council_chamber import admitted_state


def test_operator_council_chamber_reads_authoritative_state_without_commands():
    store, definition, state = admitted_state(CouncilTier.SMALL)
    class Client:
        def __init__(self):
            self.commands = []
        def get_state(self, stream_id):
            assert stream_id == "council-" + definition.council_id
            return state
        def command(self, *args, **kwargs):
            raise AssertionError("council display may not mutate runtime")
    try:
        operator = Operator.__new__(Operator)
        operator._client = Client()
        view = operator.council_chamber(definition.council_id, vessel_preview_limit=2)
        assert view["authority"] == "projection_only"
        assert view["logicalVessels"] == 6
        assert len(view["vesselPreview"]) == 2
        assert view["vesselPreviewTruncated"] is True
        assert operator._client.commands == []
    finally:
        store.close()


def test_council_cli_wires_id_and_preview_without_executing(monkeypatch):
    calls = []
    class FakeOperator:
        def council_chamber(self, council_id, preview):
            calls.append((council_id, preview))
            return {"authority": "projection_only"}
    monkeypatch.setattr(cli, "_op", lambda: FakeOperator())
    monkeypatch.setattr(cli, "_out", lambda value, as_json: calls.append((value, as_json)))
    assert cli.main(["council", "council-demo", "--preview", "2", "--json"]) == 0
    assert calls == [
        ("council-demo", 2),
        ({"authority": "projection_only"}, True),
    ]
