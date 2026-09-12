"""CAPT SOMA adapter: governed trajectory compression primitives."""

from .reducer import CompressionReceipt, CompressedContext, ContextReducer, ReducerResult
from .trajectory import CodingTrajectory, TrajectoryEvent

__all__ = [
    "CodingTrajectory",
    "CompressionReceipt",
    "CompressedContext",
    "ContextReducer",
    "ReducerResult",
    "TrajectoryEvent",
]
