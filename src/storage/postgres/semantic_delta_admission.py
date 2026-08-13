"""Compatibility import for the generic PostgreSQL delta admission boundary."""

from .distributed_semantic_execution import (
    Lease,
    replay_accepted_deltas,
    semantic_delta_admission,
)

__all__ = ["Lease", "semantic_delta_admission", "replay_accepted_deltas"]
