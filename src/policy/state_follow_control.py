from __future__ import annotations

from typing import Sequence

STATE_LEVELS_PRIORITY = {
    "state": 0.8,
    "local": 0.6,
}


def compute_state_awareness_priority(
    reference_levels: Sequence[str], *, base_score: float = 1.0
) -> float:
    """Return a follow/search priority boost when state sources should dominate."""

    priority = base_score
    seen_levels: set[str] = set()
    for level in reference_levels:
        normalized = str(level or "").strip().lower()
        if not normalized or normalized in seen_levels:
            continue
        seen_levels.add(normalized)
        priority += STATE_LEVELS_PRIORITY.get(normalized, 0.0)
    if "federal" in seen_levels and "state" in seen_levels:
        priority -= 0.1  # preserve federal-state separation by penalizing mixed contexts
    return max(priority, 0.0)
