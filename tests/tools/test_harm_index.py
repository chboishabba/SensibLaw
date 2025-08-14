from pathlib import Path
import sys

sys.path.append("src")
from tools.harm_index import compute_harm_index


def test_compute_harm_index():
    weights = {"privacy": 1, "safety": 2}
    scores = compute_harm_index(
        data_dir=Path("data/harm_inputs"),
        weights=weights,
    )
    assert scores["user"] == 3 * 1 + 5 * 2
    assert scores["admin"] == 1 * 1 + 2 * 2
