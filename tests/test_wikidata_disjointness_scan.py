import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from scripts.run_wikidata_disjointness_candidate_scan import (  # noqa: E402
    PAIR_SEED_SCHEMA_VERSION,
    SCAN_SCHEMA_VERSION,
    _load_pair_seed,
    _normalize_binding,
    _rank_row,
    _render_zelph_instance_bundle,
    scan_candidates,
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


def test_load_pair_seed_smoke() -> None:
    seed_path = ROOT / "data" / "ontology" / "wikidata_disjointness_pair_seed_v1.json"
    rows = _load_pair_seed(seed_path)

    assert len(rows) >= 3
    assert rows[0]["holder_qid"].startswith("Q")
    assert rows[0]["left_label"]


def test_render_zelph_instance_bundle_includes_load_and_import(tmp_path) -> None:
    seed_path = ROOT / "data" / "ontology" / "wikidata_disjointness_pair_seed_v1.json"
    pair_seed = _load_pair_seed(seed_path)[:1]
    wikidata_script = tmp_path / "wikidata.zph"
    wikidata_script.write_text(".lang zelph\n", encoding="utf-8")

    bundle = _render_zelph_instance_bundle(
        pair_seed=pair_seed,
        zelph_load_path=Path("/tmp/test.bin"),
        zelph_wikidata_script=wikidata_script,
        zelph_prelude_text='"wikidata Q1" "wikidata P31" "wikidata Q2"\n',
    )

    assert bundle.startswith(".lang zelph\n")
    assert ".load /tmp/test.bin" in bundle
    assert f".import {wikidata_script}" in bundle
    assert 'X "sl/disjoint-instance-candidate" META' in bundle
    assert 'X "wikidata P31" "wikidata Q11432"' in bundle


@pytest.mark.skipif(shutil.which("zelph") is None, reason="zelph not installed")
def test_scan_candidates_zelph_prelude_end_to_end(tmp_path) -> None:
    pair_seed = {
        "schema_version": PAIR_SEED_SCHEMA_VERSION,
        "entries": [
            {
                "holder_qid": "Q102205",
                "holder_label": "fluid",
                "left_qid": "Q11432",
                "left_label": "gas",
                "right_qid": "Q11435",
                "right_label": "liquid",
            }
        ],
    }
    pair_seed_path = tmp_path / "pair_seed.json"
    pair_seed_path.write_text(json.dumps(pair_seed), encoding="utf-8")
    prelude_path = tmp_path / "network.zlp"
    prelude_path.write_text(
        '\n'.join(
            [
                ".lang zelph",
                '"wikidata Q217236" "wikidata P31" "wikidata Q11432"',
                '"wikidata Q217236" "wikidata P31" "wikidata Q11435"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    payload = scan_candidates(
        backend="zelph",
        limit=10,
        query_kind="instance",
        timeout=10,
        pair_seed_path=pair_seed_path,
        zelph_prelude_path=prelude_path,
    )

    assert payload["schema_version"] == SCAN_SCHEMA_VERSION
    assert payload["candidate_count"] == 1
    row = payload["candidates"][0]
    assert row["holder_qid"] == "Q102205"
    assert row["violator_qid"] == "Q217236"
    assert row["violation_kind"] == "instance"
    assert "zelph" in row["selection_reason"]


def test_scan_candidates_zelph_rejects_subclass_mode(tmp_path) -> None:
    pair_seed = {
        "schema_version": PAIR_SEED_SCHEMA_VERSION,
        "entries": [
            {
                "holder_qid": "Q1",
                "holder_label": "holder",
                "left_qid": "Q2",
                "left_label": "left",
                "right_qid": "Q3",
                "right_label": "right",
            }
        ],
    }
    pair_seed_path = tmp_path / "pair_seed.json"
    pair_seed_path.write_text(json.dumps(pair_seed), encoding="utf-8")
    prelude_path = tmp_path / "network.zlp"
    prelude_path.write_text(".lang zelph\n", encoding="utf-8")

    with pytest.raises(ValueError, match="only --query-kind instance"):
        scan_candidates(
            backend="zelph",
            limit=10,
            query_kind="subclass",
            timeout=10,
            pair_seed_path=pair_seed_path,
            zelph_prelude_path=prelude_path,
        )


@pytest.mark.skipif(shutil.which("zelph") is None, reason="zelph not installed")
def test_disjointness_scan_cli_zelph_prelude(tmp_path) -> None:
    pair_seed = {
        "schema_version": PAIR_SEED_SCHEMA_VERSION,
        "entries": [
            {
                "holder_qid": "Q102205",
                "holder_label": "fluid",
                "left_qid": "Q11432",
                "left_label": "gas",
                "right_qid": "Q11435",
                "right_label": "liquid",
            }
        ],
    }
    pair_seed_path = tmp_path / "pair_seed.json"
    pair_seed_path.write_text(json.dumps(pair_seed), encoding="utf-8")
    prelude_path = tmp_path / "network.zlp"
    prelude_path.write_text(
        '.lang zelph\n'
        '"wikidata Q217236" "wikidata P31" "wikidata Q11432"\n'
        '"wikidata Q217236" "wikidata P31" "wikidata Q11435"\n',
        encoding="utf-8",
    )
    output_path = tmp_path / "scan.json"

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "run_wikidata_disjointness_candidate_scan.py"),
            "--backend",
            "zelph",
            "--query-kind",
            "instance",
            "--pair-seed",
            str(pair_seed_path),
            "--zelph-prelude-path",
            str(prelude_path),
            "--output",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    payload = json.loads(result.stdout)
    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload == written
    assert payload["candidate_count"] == 1
    assert payload["candidates"][0]["violator_qid"] == "Q217236"


@pytest.mark.skipif(shutil.which("zelph") is None, reason="zelph not installed")
def test_scan_candidates_zelph_seedless_local_bin(tmp_path) -> None:
    bin_path = Path("/home/c/Documents/code/ITIR-suite/wikidata-20171227-pruned.bin")
    if not bin_path.exists():
        pytest.skip("pruned bin not available")

    payload = scan_candidates(
        backend="zelph-seedless",
        limit=10,
        query_kind="instance",
        timeout=10,
        zelph_load_path=bin_path,
        seedless_topn=5,
    )

    assert payload["schema_version"] == SCAN_SCHEMA_VERSION
    assert payload["query_kind"] == "instance"
    assert payload["candidate_count"] <= 5
    for row in payload["candidates"]:
        assert row["violation_kind"] == "instance"
        assert row["violator_qid"].startswith("Q")
        assert row["left_qid"].startswith("Q")
        assert row["right_qid"].startswith("Q")


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
