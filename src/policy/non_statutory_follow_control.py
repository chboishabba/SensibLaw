from __future__ import annotations

from typing import Sequence

NON_STATUTORY_PRIORITY = {
    "standard": 0.4,
    "inquiry": 0.5,
    "regulator_guidance": 0.6,
}


def compute_non_statutory_weight(
    vouches: Sequence[str], *, base_score: float = 0.5
) -> float:
    score = base_score
    for vouch in vouches:
        normalized = str(vouch or "").strip().lower()
        score += NON_STATUTORY_PRIORITY.get(normalized, 0.0)
    return score
