"""Deterministic, dependency-light token utilities shared across reports and tests."""

from __future__ import annotations

import re
from collections import Counter
from typing import Iterable, List, Sequence, Tuple

_TOKEN_RE = re.compile(r"\b\w+\b", re.UNICODE)


def tokenize(text: str) -> List[str]:
    """Return lowercase word tokens using the project-standard regex tokenizer."""

    if not text:
        return []
    return _TOKEN_RE.findall(text.lower())


def count_tokens(text: str) -> int:
    """Count tokens in ``text`` using the shared tokenizer."""

    return len(tokenize(text))


def repeat_ratio_ngrams(tokens: Sequence[str], n: int = 5) -> float:
    """Share of n-gram occurrences that are repeats (simple repetition indicator)."""

    if len(tokens) < n:
        return 0.0
    counts = Counter(tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1))
    total = sum(counts.values())
    repeats = sum(c for c in counts.values() if c > 1)
    return repeats / total if total else 0.0


__all__ = ["tokenize", "count_tokens", "repeat_ratio_ngrams"]
