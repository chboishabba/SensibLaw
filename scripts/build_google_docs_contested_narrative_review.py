#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import re
import sys
import tempfile

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

_SENSIBLAW_ROOT = _THIS_DIR.parent
if str(_SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(_SENSIBLAW_ROOT))

from build_affidavit_coverage_review import write_affidavit_coverage_review  # noqa: E402
from src.fact_intake.google_public_import import (  # noqa: E402
    extract_affidavit_text_from_doc_text,
    extract_contested_response_text_from_doc_text,
    fetch_google_public_export_text,
    load_google_doc_units_from_text,
    parse_google_public_url,
)
from src.fact_intake.read_model import build_fact_intake_payload_from_text_units  # noqa: E402
from src.reporting.structure_report import TextUnit  # noqa: E402

try:
    from scripts.cli_runtime import build_event_callback, build_progress_callback, configure_cli_logging  # noqa: E402
except (ModuleNotFoundError, ImportError):
    from cli_runtime import build_event_callback, build_progress_callback, configure_cli_logging  # noqa: E402


def _tokenize_for_duplicate_filter(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[A-Za-z0-9']+", text.casefold())
        if len(token) >= 2
    }


def _strip_enumeration_prefix(text: str) -> str:
    return re.sub(r"^\s*\d+(?:[-.]\d+)*[.)]?\s*", "", text).strip()


def _similarity(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    shared = left & right
    if not shared:
        return 0.0
    return (2.0 * len(shared)) / (len(left) + len(right))


def _is_duplicate_affidavit_unit(text: str, affidavit_text: str) -> bool:
    affidavit_candidates = []
    for raw_line in affidavit_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        tokens = _tokenize_for_duplicate_filter(_strip_enumeration_prefix(line))
        if tokens:
            affidavit_candidates.append(tokens)
    unit_tokens = _tokenize_for_duplicate_filter(_strip_enumeration_prefix(text))
    return any(_similarity(unit_tokens, aff_tokens) >= 0.85 for aff_tokens in affidavit_candidates)


def _group_contested_response_units(response_units: list[TextUnit], affidavit_text: str) -> list[TextUnit]:
    grouped: list[TextUnit] = []
    current_heading: TextUnit | None = None
    current_parts: list[str] = []
    for unit in response_units:
        text = str(unit.text or "").strip()
        if not text:
            continue
        looks_numbered = bool(re.match(r"^\s*\d+(?:[-.]\d+)*[.)]?\s+", text))
        is_duplicate_heading = looks_numbered and _is_duplicate_affidavit_unit(text, affidavit_text)
        if is_duplicate_heading:
            if current_heading is not None and current_parts:
                grouped.append(
                    TextUnit(
                        unit_id=f"{current_heading.unit_id}:block",
                        source_id=current_heading.source_id,
                        source_type=current_heading.source_type,
                        text="\n".join(current_parts).strip(),
                    )
                )
            current_heading = unit
            current_parts = [text]
            continue
        if current_heading is not None:
            current_parts.append(text)
            continue
        grouped.append(unit)
    if current_heading is not None and current_parts:
        grouped.append(
            TextUnit(
                unit_id=f"{current_heading.unit_id}:block",
                source_id=current_heading.source_id,
                source_type=current_heading.source_type,
                text="\n".join(current_parts).strip(),
            )
        )
    return grouped


def _emit_progress(progress_callback: ProgressCallback | None, stage: str, **details: Any) -> None:
    if progress_callback is None:
        return
    progress_callback(stage, details)


def _emit_trace(trace_callback, stage: str, **details):
    if trace_callback is None:
        return
    trace_callback(stage, details)


def build_google_docs_contested_narrative_review(
    *,
    affidavit_doc_url: str,
    response_doc_url: str,
    output_dir: Path,
    progress_callback=None,
    trace_callback=None,
    trace_level: str = "verbose",
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    _emit_trace(trace_callback, "google_docs_run_started", affidavit_doc_url=affidavit_doc_url, response_doc_url=response_doc_url)
    _emit_progress(progress_callback, "google_affidavit_fetch_started", section="google_docs", completed=0, total=2, message="Fetching affidavit Google Doc.")
    affidavit_text_raw = fetch_google_public_export_text(affidavit_doc_url)
    _emit_progress(progress_callback, "google_affidavit_fetch_finished", section="google_docs", completed=1, total=2, message="Affidavit Google Doc fetched.", character_count=len(affidavit_text_raw))
    _emit_progress(progress_callback, "google_response_fetch_started", section="google_docs", completed=1, total=2, message="Fetching response Google Doc.")
    response_text_raw = fetch_google_public_export_text(response_doc_url)
    _emit_progress(progress_callback, "google_response_fetch_finished", section="google_docs", completed=2, total=2, message="Response Google Doc fetched.", character_count=len(response_text_raw))
    affidavit_text = extract_affidavit_text_from_doc_text(affidavit_text_raw)
    response_text = extract_contested_response_text_from_doc_text(response_text_raw)
    if trace_level == "verbose":
        _emit_trace(
            trace_callback,
            "google_docs_text_extracted",
            affidavit_character_count=len(affidavit_text),
            response_character_count=len(response_text),
            affidavit_preview=affidavit_text[:240],
            response_preview=response_text[:240],
        )
    _emit_progress(progress_callback, "google_doc_extract_finished", section="google_docs", message="Extracted affidavit and response text blocks.", affidavit_character_count=len(affidavit_text), response_character_count=len(response_text))
    response_parsed = parse_google_public_url(response_doc_url)
    response_units = load_google_doc_units_from_text(
        response_text,
        source_id=f"google_doc:{response_parsed['doc_id']}",
    )
    _emit_progress(progress_callback, "google_response_units_loaded", section="google_docs", completed=len(response_units), total=len(response_units), message="Loaded raw response units.")
    response_units = _group_contested_response_units(response_units, affidavit_text)
    _emit_progress(progress_callback, "google_response_units_grouped", section="google_docs", completed=len(response_units), total=len(response_units), message="Grouped contested response units.")
    if trace_level == "verbose":
        _emit_trace(
            trace_callback,
            "google_docs_units_grouped",
            grouped_unit_count=len(response_units),
            grouped_unit_ids=[unit.unit_id for unit in response_units[:10]],
        )
    source_payload = build_fact_intake_payload_from_text_units(
        response_units,
        source_label="google_docs_contested_narrative_response",
        notes="public Google Docs contested narrative response",
    )
    run_block = source_payload.setdefault("run", {})
    if isinstance(run_block, dict):
        run_block["comparison_mode"] = "contested_narrative"
    _emit_progress(progress_callback, "google_affidavit_review_started", section="google_docs", message="Building affidavit coverage review.")
    result = write_affidavit_coverage_review(
        output_dir=output_dir,
        source_payload=source_payload,
        affidavit_text=affidavit_text,
        source_path=response_doc_url,
        affidavit_path=affidavit_doc_url,
        progress_callback=progress_callback,
        trace_callback=trace_callback,
        trace_level=trace_level,
    )
    meta = {
        "affidavit_doc_url": affidavit_doc_url,
        "response_doc_url": response_doc_url,
        "affidavit_character_count": len(affidavit_text),
        "response_unit_count": len(response_units),
        **result,
    }
    meta_path = output_dir / "google_docs_contested_narrative_review.meta.json"
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8")
    _emit_progress(progress_callback, "google_affidavit_review_finished", section="google_docs", message="Google Docs contested narrative review written.", meta_path=str(meta_path))
    return {**result, "meta_path": str(meta_path)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build an affidavit-style contested narrative review from two public Google Docs.")
    parser.add_argument("--affidavit-doc-url", required=True)
    parser.add_argument("--response-doc-url", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--progress", action="store_true", help="Emit progress updates to stderr.")
    parser.add_argument("--progress-format", default="human", choices=["human", "json", "bar"], help="Progress output format.")
    parser.add_argument("--trace", action="store_true", help="Emit detailed trace events to stderr.")
    parser.add_argument("--trace-format", default="human", choices=["human", "json"], help="Trace output format.")
    parser.add_argument("--trace-level", default="verbose", choices=["summary", "verbose"], help="Trace verbosity level.")
    parser.add_argument("--log-level", default="INFO", help="Logging level for stderr output.")
    args = parser.parse_args(argv)
    configure_cli_logging(str(args.log_level))
    payload = build_google_docs_contested_narrative_review(
        affidavit_doc_url=str(args.affidavit_doc_url),
        response_doc_url=str(args.response_doc_url),
        output_dir=Path(args.output_dir).resolve(),
        progress_callback=build_progress_callback(enabled=bool(args.progress), fmt=str(args.progress_format)),
        trace_callback=build_event_callback(enabled=bool(args.trace), fmt=str(args.trace_format), label="trace"),
        trace_level=str(args.trace_level),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
