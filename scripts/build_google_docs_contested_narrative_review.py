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


def build_google_docs_contested_narrative_review(
    *,
    affidavit_doc_url: str,
    response_doc_url: str,
    output_dir: Path,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    affidavit_text_raw = fetch_google_public_export_text(affidavit_doc_url)
    response_text_raw = fetch_google_public_export_text(response_doc_url)
    affidavit_text = extract_affidavit_text_from_doc_text(affidavit_text_raw)
    response_text = extract_contested_response_text_from_doc_text(response_text_raw)
    response_parsed = parse_google_public_url(response_doc_url)
    response_units = load_google_doc_units_from_text(
        response_text,
        source_id=f"google_doc:{response_parsed['doc_id']}",
    )
    response_units = _group_contested_response_units(response_units, affidavit_text)
    source_payload = build_fact_intake_payload_from_text_units(
        response_units,
        source_label="google_docs_contested_narrative_response",
        notes="public Google Docs contested narrative response",
    )
    run_block = source_payload.setdefault("run", {})
    if isinstance(run_block, dict):
        run_block["comparison_mode"] = "contested_narrative"
    result = write_affidavit_coverage_review(
        output_dir=output_dir,
        source_payload=source_payload,
        affidavit_text=affidavit_text,
        source_path=response_doc_url,
        affidavit_path=affidavit_doc_url,
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
    return {**result, "meta_path": str(meta_path)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build an affidavit-style contested narrative review from two public Google Docs.")
    parser.add_argument("--affidavit-doc-url", required=True)
    parser.add_argument("--response-doc-url", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    payload = build_google_docs_contested_narrative_review(
        affidavit_doc_url=str(args.affidavit_doc_url),
        response_doc_url=str(args.response_doc_url),
        output_dir=Path(args.output_dir).resolve(),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
