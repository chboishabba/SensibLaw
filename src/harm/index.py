from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable


_WEIGHTS_PATH = Path(__file__).with_name("weights.json")


def _load_weights(path: Path | None = None) -> Dict[str, Any]:
    with open(path or _WEIGHTS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


_WEIGHTS = _load_weights()


def _classify(score: float, medium: float, high: float) -> str:
    if score < medium:
        return "Low"
    if score < high:
        return "Medium"
    return "High"


def compute_harm(story: Dict[str, Any], weights: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Compute a harm score and classification for a story.

    Parameters
    ----------
    story:
        Mapping containing fields such as ``lost_evidence_items``, ``delay_months``
        and ``flags`` (an iterable of flag identifiers).
    weights:
        Optional explicit weights configuration. If not provided the default
        ``weights.json`` packaged with the module is used.
    """

    w = weights or _WEIGHTS
    lost_items = story.get("lost_evidence_items", 0)
    delay_months = story.get("delay_months", 0)
    flags: Iterable[str] = story.get("flags", [])

    score = 0.0
    score += lost_items * w.get("lost_evidence_items", 0)

    max_delay = w.get("max_delay_months", 1)
    delay_weight = w.get("delay_months", 0)
    score += min(delay_months, max_delay) / max_delay * delay_weight

    flag_weights: Dict[str, float] = w.get("flags", {})
    for f in flags:
        score += flag_weights.get(f, 0)

    score = max(0.0, min(score, 1.0))

    level = _classify(score, w.get("medium_threshold", 0.33), w.get("high_threshold", 0.66))
    return {"score": score, "level": level}
