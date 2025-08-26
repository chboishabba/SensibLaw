import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.concepts.matcher import MATCHER


def test_matcher_deterministic():
    text = "The doctrine of terra nullius was overturned; no permanent stay followed."
    out1 = [h.__dict__ for h in MATCHER.match(text)]
    out2 = [h.__dict__ for h in MATCHER.match(text)]
    assert out1 == out2
    ids = [n["concept_id"] for n in out1]
    assert ids == [
        "Concept#terra_nullius",
        "stay_permanent",
        "Concept#permanent_stay",
    ]
    starts = [n["start"] for n in out1]
    assert starts == sorted(starts)
