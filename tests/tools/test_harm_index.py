from pathlib import Path
import sys

import pytest

sys.path.append("src")
from tools.harm_index import compute_harm_index, compute_scores


def classify(score: float, thresholds: tuple[float, float]) -> str:
    low, high = thresholds
    if score < low:
        return "Low"
    if score < high:
        return "Medium"
    return "High"


def test_compute_harm_index():
    weights = {"privacy": 1, "safety": 2}
    scores = compute_harm_index(
        data_dir=Path("data/harm_inputs"),
        weights=weights,
    )
    assert scores["user"] == 3 * 1 + 5 * 2
    assert scores["admin"] == 1 * 1 + 2 * 2


@pytest.mark.parametrize("delay_a, delay_b", [(0, 6), (6, 12)])
def test_delay_months_monotonic(delay_a: float, delay_b: float) -> None:
    weights = {"delay_months": 0.1}
    metrics_a = {"case": {"delay_months": delay_a}}
    metrics_b = {"case": {"delay_months": delay_b}}
    score_a = compute_scores(metrics_a, weights)["case"]
    score_b = compute_scores(metrics_b, weights)["case"]
    assert score_b > score_a


def test_conflicting_factors_bound_score() -> None:
    metrics = {"case": {"delay_months": 10, "alternate_remedies": 1}}
    weights = {"delay_months": 0.1, "alternate_remedies": -0.5}
    score = compute_scores(metrics, weights)["case"]
    assert 0 <= score <= 1


THRESHOLDS = (0.3, 0.7)


@pytest.mark.parametrize(
    "delay, expected",
    [
        (2, "Low"),
        (3, "Medium"),
        (6, "Medium"),
        (7, "High"),
    ],
)
def test_classification_boundaries(delay: float, expected: str) -> None:
    weights = {"delay_months": 0.1}
    metrics = {"case": {"delay_months": delay}}
    score = compute_scores(metrics, weights)["case"]
    assert classify(score, THRESHOLDS) == expected
