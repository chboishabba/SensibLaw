from __future__ import annotations

from typing import Sequence

JURISDICTION_PRIORITY = {
    "international": 0.2,
    "regional": 0.5,
    "national": 0.8,
    "domestic": 1.0,
}


def compute_jurisdiction_fit_score(
    jurisdictions: Sequence[str], *, base_score: float = 1.0
) -> float:
    seen: set[str] = set()
    score = base_score
    for level in jurisdictions:
        normalized = str(level or "").strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        score += JURISDICTION_PRIORITY.get(normalized, 0.0)
    if "international" in seen and "domestic" in seen:
        score -= 0.3
    return max(score, 0.0)
