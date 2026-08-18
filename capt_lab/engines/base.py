"""Shared protocol helpers for Lab engine adapters."""

from typing import Any, Dict, Mapping, Protocol

from capt_lab.contracts import LabEngineRequest, LabEngineResult


class LabEngine(Protocol):
    def execute(self, request: LabEngineRequest, context: Mapping[str, Any]) -> LabEngineResult:
        ...


LabContext = Dict[str, Any]
