#!/usr/bin/env python
"""Batch corpus stats over PDFs with progress and worker parallelism."""

from __future__ import annotations

import argparse
import math
import time
import zlib
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Tuple

from pdfminer.high_level import extract_text

from src.text.tokenize_simple import count_tokens, repeat_ratio_ngrams, tokenize


def _block_entropy(data: bytes, block_size: int) -> float:
    if len(data) < block_size or block_size == 0:
        return 0.0
    window_count = len(data) - block_size + 1
    counts: dict[bytes, int] = {}
    for i in range(window_count):
        chunk = data[i : i + block_size]
        counts[chunk] = counts.get(chunk, 0) + 1
    entropy = 0.0
    for count in counts.values():
        probability = count / window_count
        entropy -= probability * math.log2(probability)
    return entropy


def _estimate_entropy_rate(data: bytes, max_order: int = 3) -> float:
    if not data or max_order <= 0:
        return 0.0
    entropies: list[float] = []
    for k in range(1, max_order + 1):
        if len(data) < k:
            break
        entropies.append(_block_entropy(data, k))
    if not entropies:
        return 0.0
    rate_candidates: list[float] = [entropies[0]]
    for previous, current in zip(entropies, entropies[1:]):
        rate_candidates.append(max(current - previous, 0.0))
    return min(rate_candidates)


def _lz78_phrase_count(tokens: list[str]) -> int:
    dictionary: set[tuple[str, ...]] = set()
    phrase: list[str] = []
    phrases = 0
    for token in tokens:
        phrase.append(token)
        key = tuple(phrase)
        if key not in dictionary:
            dictionary.add(key)
            phrases += 1
            phrase = []
    if phrase:
        phrases += 1
    return phrases


def _estimate_lz_ratio(tokens: list[str], raw_bytes_len: int) -> tuple[float, float]:
    if not tokens or raw_bytes_len == 0:
        return 0.0, 0.0
    phrases = _lz78_phrase_count(tokens)
    bits_per_token = (phrases * math.log2(len(tokens))) / len(tokens)
    bits_per_byte = (bits_per_token * len(tokens)) / raw_bytes_len
    return bits_per_token, bits_per_byte / 8.0


def _analyze_pdf(path: Path, *, limit_chars: int | None = None) -> Dict:
    text = extract_text(path)
    if limit_chars:
        text = (text or "")[:limit_chars]
    body_bytes = (text or "").encode("utf-8")
    raw_bytes_len = len(body_bytes)
    compressed_len = len(zlib.compress(body_bytes)) if body_bytes else 0
    compression_ratio = (compressed_len / raw_bytes_len) if raw_bytes_len else 0.0
    entropy_rate_bits = _estimate_entropy_rate(body_bytes, max_order=3)
    shannon_ratio = entropy_rate_bits / 8.0 if body_bytes else 0.0
    toks = tokenize(text)
    lz_bits_per_token, lz_entropy_floor = _estimate_lz_ratio(toks, raw_bytes_len)
    vocab = set(toks)
    repeat_ratio = repeat_ratio_ngrams(toks, n=5)
    return {
        "tokens": len(toks),
        "unique": len(vocab),
        "repeat_ratio_5gram": repeat_ratio,
        "entropy_rate_bits": round(entropy_rate_bits, 4),
        "token_entropy_proxy": round(shannon_ratio, 4),
        "empirical_compression_ratio": round(compression_ratio, 4),
        "lz_bits_per_token": round(lz_bits_per_token, 4),
        "lz_entropy_floor": round(lz_entropy_floor, 4),
        "raw_bytes": raw_bytes_len,
        "compressed_bytes": compressed_len,
        "vocab": vocab,
    }


def _aggregate_corpus(results: Dict[str, Dict]) -> Dict[str, float]:
    total_raw = sum(r.get("raw_bytes", 0) for r in results.values())
    total_compressed = sum(r.get("compressed_bytes", 0) for r in results.values())
    total_tokens = sum(r.get("tokens", 0) for r in results.values())
    total_lz_bits = sum(
        r.get("lz_bits_per_token", 0.0) * r.get("tokens", 0) for r in results.values()
    )
    if total_raw:
        corpus_compression_ratio = total_compressed / total_raw
        shannon_weighted = sum(
            (r.get("token_entropy_proxy", 0.0) * r.get("raw_bytes", 0)) for r in results.values()
        ) / total_raw
        lz_ratio_weighted = (total_lz_bits / total_raw) / 8.0 if total_lz_bits else 0.0
    else:
        corpus_compression_ratio = 0.0
        shannon_weighted = 0.0
        lz_ratio_weighted = 0.0
    return {
        "corpus_empirical_compression_ratio": round(corpus_compression_ratio, 4),
        "corpus_token_entropy_proxy": round(shannon_weighted, 4),
        "corpus_lz_entropy_floor": round(lz_ratio_weighted, 4),
    }


def _eta(start: float, done: int, total: int) -> str:
    if done == 0:
        return "?"
    rate = (time.time() - start) / done
    remaining = rate * (total - done)
    return f"{int(remaining)}s"


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute corpus growth stats over PDFs.")
    parser.add_argument("path", type=Path, help="Directory containing PDFs")
    parser.add_argument("--workers", type=int, default=0, help="Number of parallel workers (default: cpu count)")
    parser.add_argument("--limit-chars", type=int, default=None, help="Optionally truncate text per file")
    args = parser.parse_args()

    pdfs: List[Path] = sorted(p for p in args.path.glob("*.pdf"))
    if not pdfs:
        raise SystemExit("No PDFs found.")

    workers = args.workers or None
    start = time.time()
    results: Dict[str, Dict] = {}

    with ProcessPoolExecutor(max_workers=workers) as pool:
        future_map = {
            pool.submit(_analyze_pdf, pdf, limit_chars=args.limit_chars): pdf for pdf in pdfs
        }
        total = len(future_map)
        for i, future in enumerate(as_completed(future_map), start=1):
            pdf = future_map[future]
            try:
                results[pdf.name] = future.result()
            except Exception as exc:  # pragma: no cover - surfaced to user
                print(f"[{i}/{total}] {pdf.name}: ERROR {exc}")
                continue
            print(
                f"[{i}/{total}] {pdf.name}: "
                f"tokens={results[pdf.name]['tokens']} "
                f"unique={results[pdf.name]['unique']} "
                f"rr5={results[pdf.name]['repeat_ratio_5gram']:.3f} "
                f"token_entropy={results[pdf.name]['token_entropy_proxy']:.3f} "
                f"empirical_cr={results[pdf.name]['empirical_compression_ratio']:.3f} "
                f"lz_floor={results[pdf.name]['lz_entropy_floor']:.3f} "
                f"ETA={_eta(start, i, total)}"
            )

    # Cumulative growth
    cum_tokens = 0
    cum_vocab = set()
    print("\nCumulative growth (sorted by name):")
    print(
        "doc | new_tokens | doc_vocab | new_vocab_added | mvd | cum_tokens | cum_vocab"
    )
    for pdf in pdfs:
        r = results.get(pdf.name)
        if not r:
            continue
        new_tokens = r["tokens"]
        new_vocab = r["vocab"] - cum_vocab
        mvd = len(new_vocab) / max(new_tokens, 1)
        cum_tokens += new_tokens
        cum_vocab |= r["vocab"]
        print(
            f"{pdf.name} | {new_tokens} | {len(r['vocab'])} | {len(new_vocab)} | "
            f"{mvd:.4f} | {cum_tokens} | {len(cum_vocab)}"
        )

    # Corpus-level top tokens
    from collections import Counter

    corpus_counts = Counter()
    for r in results.values():
        corpus_counts.update(r["vocab"])
    print("\nCorpus top 20 tokens (by document presence):")
    for tok, cnt in corpus_counts.most_common(20):
        print(f"{tok}: {cnt}")

    corpus_stats = _aggregate_corpus(results)
    print(
        "\nCorpus compression ratios: "
        f"empirical_compression_ratio={corpus_stats['corpus_empirical_compression_ratio']:.4f} "
        f"token_entropy_proxy={corpus_stats['corpus_token_entropy_proxy']:.4f} "
        f"lz_entropy_floor={corpus_stats['corpus_lz_entropy_floor']:.4f}"
    )

    duration = round(time.time() - start, 2)
    print(f"\nDone in {duration}s using {workers or 'cpu'} workers.")


if __name__ == "__main__":  # pragma: no cover
    main()
