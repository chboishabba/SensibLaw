import re
import sys
from dataclasses import dataclass
from itertools import zip_longest
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from src.ingestion.section_parser import TOKEN_RE


@dataclass
class MatchSpan:
    start: int
    end: int


@dataclass
class MatchResult:
    matches: List[MatchSpan]
    unmatched_spans: List[str]


def run_matcher(text: str) -> MatchResult:
    matches: List[MatchSpan] = []
    unmatched: List[str] = []
    last = 0
    for m in TOKEN_RE.finditer(text):
        start, end = m.span()
        if start > last:
            unmatched.append(text[last:start])
        matches.append(MatchSpan(start, end))
        last = end
    if last < len(text):
        unmatched.append(text[last:])
    else:
        unmatched.append("")
    return MatchResult(matches=matches, unmatched_spans=unmatched)


def test_match_boundaries():
    text = "1 A person must not drive if intoxicated under s 5B."
    res = run_matcher(text)

    parts = []
    for unmatched, match in zip_longest(res.unmatched_spans, res.matches, fillvalue=None):
        if unmatched:
            parts.append(unmatched)
        if match:
            parts.append(text[match.start:match.end])
    reconstructed = "".join(parts)

    assert " ".join(reconstructed.split()) == " ".join(text.split())
