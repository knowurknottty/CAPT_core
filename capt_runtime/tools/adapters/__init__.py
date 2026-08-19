"""Governed tool implementation adapters.

Adapters implement effects only. ToolBroker remains the authority boundary.
"""

from .file import FileToolAdapter

__all__ = ["FileToolAdapter"]
