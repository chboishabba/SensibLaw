from __future__ import annotations

from typing import Sequence

PARLIAMENTARY_PRIORITY = {
    "debate": 0.3,
    "committee_report": 0.4,
    "ministerial_statement": 0.5,
}


def compute_parliamentary_weight(
    materials: Sequence[str], *, base_score: float = 0.2
) -> dict[str, float]:
    score = base_score
    detailed = []
    for material in materials:
        normalized = str(material or "").strip().lower()
        boost = PARLIAMENTARY_PRIORITY.get(normalized, 0.0)
        if boost:
            score += boost
            detailed.append(normalized)
    return {"score": score, "sources": detailed}
