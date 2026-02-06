from __future__ import annotations

import zlib
from collections import Counter
from dataclasses import dataclass
from typing import Sequence

from src.text.lexeme_normalizer import normalize_lexeme
from src.text.tokenize_simple import tokenize


@dataclass(frozen=True)
class CompressionStats:
    token_count: int
    unique_lexemes: int
    rr5_lexeme: float
    mvd_lexeme: float
    compression_ratio: float

    def to_dict(self) -> dict:
        return {
            "token_count": self.token_count,
            "unique_lexemes": self.unique_lexemes,
            "rr5_lexeme": self.rr5_lexeme,
            "mvd_lexeme": self.mvd_lexeme,
            "compression_ratio": self.compression_ratio,
            "tokenizer_id": "lexeme_normalizer_v1",
        }


def _rr_k(tokens: Sequence[str], k: int = 5) -> float:
    if len(tokens) < k:
        return 0.0
    grams = [tuple(tokens[i : i + k]) for i in range(len(tokens) - k + 1)]
    counts = Counter(grams)
    repeats = sum(max(v - 1, 0) for v in counts.values())
    return repeats / max(len(grams), 1)


def _mvd(tokens: Sequence[str], window: int = 50) -> float:
    if not tokens:
        return 0.0
    if len(tokens) <= window:
        return len(set(tokens)) / len(tokens)
    vals = []
    for i in range(0, len(tokens) - window + 1):
        w = tokens[i : i + window]
        vals.append(len(set(w)) / window)
    return sum(vals) / len(vals)


def compute_compression_stats(text: str) -> CompressionStats:
    tokens = tokenize(text)
    lexemes = [normalize_lexeme(token).norm_text for token in tokens]

    body_bytes = text.encode("utf-8")
    compression_ratio = 0.0
    if body_bytes:
        compression_ratio = len(zlib.compress(body_bytes)) / len(body_bytes)

    return CompressionStats(
        token_count=len(tokens),
        unique_lexemes=len(set(lexemes)),
        rr5_lexeme=round(_rr_k(lexemes, k=5), 3),
        mvd_lexeme=round(_mvd(lexemes, window=50), 3),
        compression_ratio=round(compression_ratio, 3),
    )


__all__ = ["CompressionStats", "compute_compression_stats"]
