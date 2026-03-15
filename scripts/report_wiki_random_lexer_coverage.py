#!/usr/bin/env python3
"""Score stored Wikipedia snapshot manifests against tokenizer and shared-reducer coverage."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

_THIS_DIR = Path(__file__).resolve().parent
_SENSIBLAW_ROOT = _THIS_DIR.parent
if str(_SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(_SENSIBLAW_ROOT))

from sensiblaw.interfaces.shared_reducer import (  # noqa: E402
    collect_canonical_lexeme_occurrences_with_profile,
    collect_canonical_structure_occurrences,
    get_canonical_tokenizer_profile,
    tokenize_canonical_detailed,
)


SCHEMA_VERSION = "wiki_random_lexer_coverage_report_v0_1"
_WORD_RE = re.compile(r"\w+", re.UNICODE)
_NON_STRUCTURAL_TYPES = {"WORD", "NUMBER", "PUNCT"}
_NON_STRUCTURAL_KINDS = {"word", "number", "punct"}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _merge_spans(spans: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted((int(a), int(b)) for a, b in spans if int(b) > int(a)):
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    return merged


def _covered_chars(spans: Iterable[tuple[int, int]]) -> int:
    return sum(end - start for start, end in _merge_spans(spans))


def _covered_words(text: str, spans: Iterable[tuple[int, int]]) -> int:
    merged = _merge_spans(spans)
    if not merged:
        return 0
    count = 0
    for match in _WORD_RE.finditer(text):
        start, end = match.span()
        if any(start < span_end and end > span_start for span_start, span_end in merged):
            count += 1
    return count


def _ratio(numerator: int | float, denominator: int | float) -> float:
    if not denominator:
        return 0.0
    return round(float(numerator) / float(denominator), 6)


def _structural_token_rows(text: str) -> tuple[list[Any], list[Any]]:
    tokens = tokenize_canonical_detailed(text)
    structural = [token for token in tokens if token.token_type.value not in _NON_STRUCTURAL_TYPES]
    return tokens, structural


def score_snapshot_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    text = str(payload.get("wikitext") or "")
    token_rows, structural_tokens = _structural_token_rows(text)
    token_type_counts = Counter(token.token_type.value for token in token_rows)
    structural_token_type_counts = Counter(token.token_type.value for token in structural_tokens)
    tokenizer_spans = [(token.start, token.end) for token in structural_tokens]

    lexemes, profile = collect_canonical_lexeme_occurrences_with_profile(text)
    structures = collect_canonical_structure_occurrences(text)
    lexeme_kind_counts = Counter(occ.kind for occ in lexemes)
    structure_kind_counts = Counter(occ.kind for occ in structures)
    meaningful_lexemes = [occ for occ in lexemes if occ.kind not in _NON_STRUCTURAL_KINDS]
    meaningful_structures = [occ for occ in structures if occ.kind not in _NON_STRUCTURAL_KINDS]
    reducer_spans = [(occ.start_char, occ.end_char) for occ in meaningful_structures]

    total_words = len(_WORD_RE.findall(text))
    tokenizer_word_ratio = _ratio(_covered_words(text, tokenizer_spans), total_words)
    reducer_word_ratio = _ratio(_covered_words(text, reducer_spans), total_words)
    tokenizer_char_ratio = _ratio(_covered_chars(tokenizer_spans), len(text))
    reducer_char_ratio = _ratio(_covered_chars(reducer_spans), len(text))

    tokenizer_signal = len(structural_tokens) > 0
    reducer_signal = len(meaningful_lexemes) > 0 or len(meaningful_structures) > 0
    suspicious_density = len(structural_tokens) >= 8 and tokenizer_char_ratio >= 0.35
    alignment_ok = tokenizer_signal == reducer_signal or (tokenizer_signal and reducer_signal) or (not tokenizer_signal and not reducer_signal)
    abstention_ok = (not tokenizer_signal and not reducer_signal) or (tokenizer_signal and not suspicious_density)

    structural_coverage_score = round(max(tokenizer_word_ratio, reducer_word_ratio), 6)
    abstention_quality_score = 1.0 if abstention_ok else 0.0
    shared_reducer_alignment_score = 1.0 if alignment_ok else 0.0
    overall_quality_score = round(
        (structural_coverage_score + abstention_quality_score + shared_reducer_alignment_score) / 3.0,
        6,
    )

    issues: list[str] = []
    if not text.strip():
        issues.append("empty_text")
    if not tokenizer_signal and not reducer_signal:
        issues.append("no_structural_signal")
    if tokenizer_signal and not reducer_signal:
        issues.append("tokenizer_without_reducer")
    if reducer_signal and not tokenizer_signal:
        issues.append("reducer_without_tokenizer")
    if suspicious_density:
        issues.append("suspicious_structural_density")

    return {
        "title": str(payload.get("title") or ""),
        "pageid": payload.get("pageid"),
        "revid": payload.get("revid"),
        "source_url": payload.get("source_url"),
        "text_chars": len(text),
        "word_count": total_words,
        "token_count": len(token_rows),
        "structural_token_count": len(structural_tokens),
        "token_type_counts": dict(sorted(token_type_counts.items())),
        "structural_token_type_counts": dict(sorted(structural_token_type_counts.items())),
        "lexeme_count": len(lexemes),
        "meaningful_lexeme_count": len(meaningful_lexemes),
        "lexeme_kind_counts": dict(sorted(lexeme_kind_counts.items())),
        "structure_count": len(structures),
        "meaningful_structure_count": len(meaningful_structures),
        "structure_kind_counts": dict(sorted(structure_kind_counts.items())),
        "tokenizer_word_coverage_ratio": tokenizer_word_ratio,
        "shared_reducer_word_coverage_ratio": reducer_word_ratio,
        "tokenizer_char_coverage_ratio": tokenizer_char_ratio,
        "shared_reducer_char_coverage_ratio": reducer_char_ratio,
        "profile": {
            "canonical_mode": profile.canonical_mode,
            "canonical_tokenizer_id": profile.canonical_tokenizer_id,
            "canonical_tokenizer_version": profile.canonical_tokenizer_version,
        },
        "scores": {
            "structural_coverage_score": structural_coverage_score,
            "abstention_quality_score": abstention_quality_score,
            "shared_reducer_alignment_score": shared_reducer_alignment_score,
            "overall_quality_score": overall_quality_score,
        },
        "issues": issues,
    }


def build_coverage_report(manifest: Mapping[str, Any], *, sample_limit: int | None = None, emit_page_rows: bool = True) -> dict[str, Any]:
    sample_rows = manifest.get("samples")
    if not isinstance(sample_rows, list):
        raise ValueError("manifest samples must be a list")
    if sample_limit is not None:
        sample_rows = sample_rows[: max(0, int(sample_limit))]

    page_rows: list[dict[str, Any]] = []
    aggregate_token_types: Counter[str] = Counter()
    aggregate_lexeme_kinds: Counter[str] = Counter()
    aggregate_structure_kinds: Counter[str] = Counter()
    issue_counts: Counter[str] = Counter()
    score_sums = {
        "structural_coverage_score": 0.0,
        "abstention_quality_score": 0.0,
        "shared_reducer_alignment_score": 0.0,
        "overall_quality_score": 0.0,
    }

    for row in sample_rows:
        if not isinstance(row, Mapping):
            continue
        snapshot_path = row.get("snapshot_path")
        if not isinstance(snapshot_path, str):
            continue
        payload = _load_json(Path(snapshot_path))
        page_row = score_snapshot_payload(payload)
        page_rows.append(page_row)
        aggregate_token_types.update(page_row["token_type_counts"])
        aggregate_lexeme_kinds.update(page_row["lexeme_kind_counts"])
        aggregate_structure_kinds.update(page_row["structure_kind_counts"])
        issue_counts.update(page_row["issues"])
        for key in score_sums:
            score_sums[key] += float(page_row["scores"][key])

    page_count = len(page_rows)
    summary = {
        "page_count": page_count,
        "token_type_counts": dict(sorted(aggregate_token_types.items())),
        "lexeme_kind_counts": dict(sorted(aggregate_lexeme_kinds.items())),
        "structure_kind_counts": dict(sorted(aggregate_structure_kinds.items())),
        "issue_counts": dict(sorted(issue_counts.items())),
        "pages_with_structural_signal": sum(1 for row in page_rows if row["structural_token_count"] > 0),
        "pages_with_shared_reducer_signal": sum(
            1 for row in page_rows if row["meaningful_lexeme_count"] > 0 or row["meaningful_structure_count"] > 0
        ),
        "pages_with_no_signal": sum(1 for row in page_rows if "no_structural_signal" in row["issues"]),
        "pages_with_suspicious_density": sum(1 for row in page_rows if "suspicious_structural_density" in row["issues"]),
        "average_scores": {
            key: round((value / page_count), 6) if page_count else 0.0
            for key, value in score_sums.items()
        },
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": manifest.get("generated_at"),
        "manifest": {
            "wiki": manifest.get("wiki"),
            "requested_count": manifest.get("requested_count"),
            "sampled_count": manifest.get("sampled_count"),
            "namespace": manifest.get("namespace"),
        },
        "supported_surface": {
            "shared_reducer_profile": get_canonical_tokenizer_profile(),
            "tokenizer_surface": "diagnostic",
            "shared_reducer_surface": "scored",
        },
        "summary": summary,
        "pages": page_rows if emit_page_rows else [],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score stored random-page Wikipedia snapshots against tokenizer and shared-reducer coverage.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--sample-limit", type=int, default=None)
    parser.add_argument("--emit-page-rows", action="store_true")
    parser.add_argument("--fail-on-empty", action="store_true")
    args = parser.parse_args(argv)

    manifest = _load_json(args.manifest)
    report = build_coverage_report(
        manifest,
        sample_limit=args.sample_limit,
        emit_page_rows=args.emit_page_rows,
    )
    if args.fail_on_empty and report["summary"]["page_count"] == 0:
        raise SystemExit("no pages scored")
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
