import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.concepts.matcher import Match, MatchResult, match


def test_single_match():
    text = "The quick brown fox jumps"
    result = match(text, ["quick"])
    assert len(result.matches) == 1
    m = result.matches[0]
    assert m.pattern == "quick"
    assert (m.start, m.end) == (4, 9)
    assert result.unmatched_spans is None


def test_multiple_matches():
    text = "alpha beta alpha gamma"
    result = match(text, ["alpha", "gamma"])
    patterns = [m.pattern for m in result.matches]
    spans = [(m.start, m.end) for m in result.matches]
    assert patterns == ["alpha", "alpha", "gamma"]
    assert spans == [(0, 5), (11, 16), (17, 22)]


def test_unmatched_spans():
    text = "one two three"
    result = match(text, ["one", "three"], return_unmatched=True)
    assert [(m.start, m.end) for m in result.matches] == [(0, 3), (8, 13)]
    assert result.unmatched_spans == [(3, 8)]
