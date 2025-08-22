import json
import string
from pathlib import Path

from hypothesis import given, settings, strategies as st

from src.checklists.run import evaluate

BASE = Path(__file__).parent
CHECKLIST = json.loads((BASE / "basic.json").read_text())


@settings(max_examples=50)
@given(st.sets(st.text(alphabet=string.ascii_lowercase, min_size=1), max_size=5))
def test_evaluate_deterministic_and_non_negative_score(tags):
    result1 = evaluate(CHECKLIST, tags)
    result2 = evaluate(CHECKLIST, tags)
    assert result1 == result2
    score = sum(1 for f in result1["factors"] if f["passed"])
    assert score >= 0
