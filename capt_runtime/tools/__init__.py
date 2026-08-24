"""Governed tool metadata and adapters owned by the CAPT runtime.

This package does not grant authority. ToolRegistry describes implementations;
RuntimeService/ToolBroker admission remains authoritative.
"""

from .registry import (
    DuplicateToolId,
    InvalidToolDescriptor,
    ToolRegistry,
    UnknownToolId,
)

__all__ = [
    "DuplicateToolId",
    "InvalidToolDescriptor",
    "ToolRegistry",
    "UnknownToolId",
]
