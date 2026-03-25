import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from scripts.run_wikidata_disjointness_candidate_scan import (  # noqa: E402
    SCAN_SCHEMA_VERSION,
    _normalize_binding,
    _rank_row,
)


def test_normalize_binding_extracts_qids_and_labels() -> None:
    binding = {
        "holder": {"type": "uri", "value": "http://www.wikidata.org/entity/Q53617489"},
        "holderLabel": {"type": "literal", "value": "independent continuant"},
        "left": {"type": "uri", "value": "http://www.wikidata.org/entity/Q53617407"},
        "leftLabel": {"type": "literal", "value": "material entity"},
        "right": {"type": "uri", "value": "http://www.wikidata.org/entity/Q124711467"},
        "rightLabel": {"type": "literal", "value": "immaterial entity"},
        "violator": {"type": "uri", "value": "http://www.wikidata.org/entity/Q27096213"},
        "violatorLabel": {"type": "literal", "value": "geographic entity"},
    }

    row = _normalize_binding(binding, violation_kind="subclass")

    assert row["holder_qid"] == "Q53617489"
    assert row["left_qid"] == "Q53617407"
    assert row["right_qid"] == "Q124711467"
    assert row["violator_qid"] == "Q27096213"
    assert row["violation_kind"] == "subclass"
    assert row["rank_score"] >= 45


def test_rank_row_prefers_fully_labeled_candidates() -> None:
    full = {
        "holder_qid": "Q1",
        "holder_label": "holder",
        "left_qid": "Q2",
        "left_label": "left",
        "right_qid": "Q3",
        "right_label": "right",
        "violator_qid": "Q4",
        "violator_label": "violator",
        "violation_kind": "subclass",
    }
    sparse = {
        "holder_qid": "Q1",
        "holder_label": None,
        "left_qid": "Q2",
        "left_label": None,
        "right_qid": "Q3",
        "right_label": None,
        "violator_qid": "Q4",
        "violator_label": None,
        "violation_kind": "instance",
    }

    assert _rank_row(full) > _rank_row(sparse)


def test_machine_readable_indexes_have_promotion_metadata() -> None:
    disjointness_index = json.loads(
        (ROOT.parent / "docs" / "planning" / "wikidata_disjointness_case_index_v1.json").read_text(
            encoding="utf-8"
        )
    )
    page_review_index = json.loads(
        (ROOT.parent / "docs" / "planning" / "wikidata_page_review_candidate_index_v1.json").read_text(
            encoding="utf-8"
        )
    )

    assert disjointness_index["version"] == "wikidata_disjointness_case_index_v1"
    assert page_review_index["version"] == "wikidata_page_review_candidate_index_v1"
    for payload in (disjointness_index, page_review_index):
        for entry in payload["entries"]:
            assert entry["promotion_status"]
            if entry["promotion_status"] != "promoted":
                assert entry["hold_reason"]
