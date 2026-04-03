from __future__ import annotations

from typing import Sequence

POLITY_PRIORITY = {
    "eu": 0.5,
    "member_state": 0.8,
    "regional_body": 0.4,
    "constitutional_court": 0.9,
    "national_court": 0.6,
}


def compute_polity_awareness_score(
    authorities: Sequence[str], *, base_score: float = 1.0
) -> float:
    seen: set[str] = set()
    score = base_score
    for authority in authorities:
        normalized = str(authority or "").strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        score += POLITY_PRIORITY.get(normalized, 0.0)
    if "eu" in seen and "member_state" in seen:
        score -= 0.2
    if "constitutional_court" in seen and "national_court" in seen:
        score += 0.2
    return max(score, 0.0)
