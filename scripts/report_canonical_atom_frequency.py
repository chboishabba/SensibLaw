#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SENSIBLAW_ROOT = Path(__file__).resolve().parents[1]
if str(SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(SENSIBLAW_ROOT))

from benchmark_tokenizer_corpora import (
    _gwb_reference_texts,
    _gwb_timeline_texts,
    _legal_fixture_texts,
    _legal_principles_texts,
    _mixed_texts,
)


def _corpora() -> dict[str, list[str]]:
    return {
        "gwb_timeline_prose": _gwb_timeline_texts(),
        "legal_fixture_bodies": _legal_fixture_texts(),
        "legal_principles_timelines": _legal_principles_texts(),
        "mixed_general_and_legal_refs": _mixed_texts(),
        "gwb_reference_texts": _gwb_reference_texts(),
    }


def _structural_kinds() -> set[str]:
    return {
        "act_ref",
        "case_ref",
        "court_ref",
        "section_ref",
        "subsection_ref",
        "paragraph_ref",
        "part_ref",
        "division_ref",
        "rule_ref",
        "schedule_ref",
        "clause_ref",
        "article_ref",
        "instrument_ref",
    }


def main() -> None:
    from src.text.lexeme_index import collect_lexeme_occurrences

    structural_kinds = _structural_kinds()
    report: dict[str, dict] = {}
    overall_counter: Counter[str] = Counter()
    overall_kind_counter: Counter[str] = Counter()

    for corpus_name, texts in _corpora().items():
        atom_counter: Counter[str] = Counter()
        kind_counter: Counter[str] = Counter()
        for text in texts:
            for occ in collect_lexeme_occurrences(text, canonical_mode="deterministic_legal"):
                if occ.kind in structural_kinds:
                    atom_counter[occ.norm_text] += 1
                    kind_counter[occ.kind] += 1
        dedupe_candidate_bytes = sum(len(atom) * (count - 1) for atom, count in atom_counter.items() if count > 1)
        report[corpus_name] = {
            "documents": len(texts),
            "structural_occurrences": sum(atom_counter.values()),
            "unique_structural_atoms": len(atom_counter),
            "dedupe_candidate_bytes": dedupe_candidate_bytes,
            "top_structural_atoms": atom_counter.most_common(15),
            "structural_kind_counts": dict(kind_counter.most_common()),
        }
        overall_counter.update(atom_counter)
        overall_kind_counter.update(kind_counter)

    report["overall"] = {
        "structural_occurrences": sum(overall_counter.values()),
        "unique_structural_atoms": len(overall_counter),
        "dedupe_candidate_bytes": sum(
            len(atom) * (count - 1) for atom, count in overall_counter.items() if count > 1
        ),
        "top_structural_atoms": overall_counter.most_common(25),
        "structural_kind_counts": dict(overall_kind_counter.most_common()),
    }

    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
