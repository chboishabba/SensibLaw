#!/usr/bin/env python
"""Batch corpus stats over PDFs with progress and worker parallelism."""

from __future__ import annotations

import argparse
import math
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Tuple

from pdfminer.high_level import extract_text

from src.text.tokenize_simple import count_tokens, repeat_ratio_ngrams, tokenize


def _analyze_pdf(path: Path, *, limit_chars: int | None = None) -> Dict:
    text = extract_text(path)
    if limit_chars:
        text = (text or "")[:limit_chars]
    toks = tokenize(text)
    vocab = set(toks)
    repeat_ratio = repeat_ratio_ngrams(toks, n=5)
    return {
        "tokens": len(toks),
        "unique": len(vocab),
        "repeat_ratio_5gram": repeat_ratio,
        "vocab": vocab,
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
                f"ETA={_eta(start, i, total)}"
            )

    # Cumulative growth
    cum_tokens = 0
    cum_vocab = set()
    print("\nCumulative growth (sorted by name):")
    print("doc | new_tokens | doc_vocab | new_vocab_added | cum_tokens | cum_vocab")
    for pdf in pdfs:
        r = results.get(pdf.name)
        if not r:
            continue
        new_tokens = r["tokens"]
        new_vocab = r["vocab"] - cum_vocab
        cum_tokens += new_tokens
        cum_vocab |= r["vocab"]
        print(
            f"{pdf.name} | {new_tokens} | {len(r['vocab'])} | {len(new_vocab)} | "
            f"{cum_tokens} | {len(cum_vocab)}"
        )

    # Corpus-level top tokens
    from collections import Counter

    corpus_counts = Counter()
    for r in results.values():
        corpus_counts.update(r["vocab"])
    print("\nCorpus top 20 tokens (by document presence):")
    for tok, cnt in corpus_counts.most_common(20):
        print(f"{tok}: {cnt}")

    duration = round(time.time() - start, 2)
    print(f"\nDone in {duration}s using {workers or 'cpu'} workers.")


if __name__ == "__main__":  # pragma: no cover
    main()
