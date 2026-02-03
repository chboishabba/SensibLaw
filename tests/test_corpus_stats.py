from __future__ import annotations

from pathlib import Path
import random

import pytest

pytest.importorskip("pdfminer.high_level")

import scripts.corpus_stats as corpus_stats


def test_analyze_pdf_reports_shannon_metrics(monkeypatch, tmp_path: Path) -> None:
    text = "abc" * 200
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    monkeypatch.setattr(corpus_stats, "extract_text", lambda _path: text)
    result = corpus_stats._analyze_pdf(pdf_path)

    assert result["tokens"] > 0
    assert result["entropy_rate_bits"] >= 0
    assert result["token_entropy_proxy"] >= 0
    assert result["token_entropy_proxy"] == round(result["entropy_rate_bits"] / 8.0, 4)


def test_token_entropy_proxy_increases_with_entropy(monkeypatch, tmp_path: Path) -> None:
    low_entropy = "abc" * 200
    rng = random.Random(0)
    high_entropy = "".join(rng.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(800))
    pdf_path = tmp_path / "entropy.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    monkeypatch.setattr(corpus_stats, "extract_text", lambda _path: low_entropy)
    low = corpus_stats._analyze_pdf(pdf_path)

    monkeypatch.setattr(corpus_stats, "extract_text", lambda _path: high_entropy)
    high = corpus_stats._analyze_pdf(pdf_path)

    assert high["token_entropy_proxy"] > low["token_entropy_proxy"]


def test_compression_ratio_respects_shannon_bound(monkeypatch, tmp_path: Path) -> None:
    text = "abc" * 300
    pdf_path = tmp_path / "compress.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    monkeypatch.setattr(corpus_stats, "extract_text", lambda _path: text)
    result = corpus_stats._analyze_pdf(pdf_path)

    assert result["empirical_compression_ratio"] >= result["token_entropy_proxy"]
    assert result["raw_bytes"] > 0
    assert result["compressed_bytes"] > 0
    assert result["lz_entropy_floor"] >= 0
    assert result["lz_bits_per_token"] >= 0


def test_corpus_aggregate_compression_matches_weighted_shannon() -> None:
    results = {
        "a.pdf": {
            "raw_bytes": 100,
            "compressed_bytes": 60,
            "token_entropy_proxy": 0.4,
            "lz_bits_per_token": 2.0,
            "tokens": 50,
        },
        "b.pdf": {
            "raw_bytes": 50,
            "compressed_bytes": 40,
            "token_entropy_proxy": 0.2,
            "lz_bits_per_token": 1.0,
            "tokens": 20,
        },
    }
    stats = corpus_stats._aggregate_corpus(results)

    expected_ratio = round((60 + 40) / (100 + 50), 4)
    expected_shannon = round(((0.4 * 100) + (0.2 * 50)) / (100 + 50), 4)
    expected_lz = round(((2.0 * 50) + (1.0 * 20)) / (100 + 50) / 8.0, 4)
    assert stats["corpus_empirical_compression_ratio"] == expected_ratio
    assert stats["corpus_token_entropy_proxy"] == expected_shannon
    assert stats["corpus_lz_entropy_floor"] == expected_lz
