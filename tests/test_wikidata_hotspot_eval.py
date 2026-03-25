import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from src.ontology.wikidata_hotspot import generate_hotspot_cluster_pack, load_hotspot_manifest
from src.ontology.wikidata_hotspot_eval import (
    HOTSPOT_EVAL_SCHEMA_VERSION,
    HOTSPOT_RESPONSE_SCHEMA_VERSION,
    evaluate_hotspot_cluster_pack,
    load_hotspot_response_bundle,
)

FIXTURE_DIR = ROOT / "tests" / "fixtures" / "wikidata" / "hotspot_eval_v1"


def _cluster_pack(*pack_ids: str) -> dict:
    manifest = load_hotspot_manifest(
        ROOT.parent / "docs" / "planning" / "wikidata_hotspot_pilot_pack_v1.manifest.json"
    )
    return generate_hotspot_cluster_pack(
        manifest,
        repo_root=ROOT.parent,
        pack_ids=pack_ids,
    )


def test_load_hotspot_response_bundle_rejects_wrong_schema(tmp_path: Path) -> None:
    path = tmp_path / "responses.json"
    path.write_text(json.dumps({"schema_version": "wrong", "responses": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="schema_version"):
        load_hotspot_response_bundle(path)


@pytest.mark.parametrize(
    ("pack_id", "fixture_name", "expected_classification", "expected_total", "expected_count"),
    [
        (
            "qualifier_drift_p166_live_pack_v1",
            "qualifier_drift_p166_live_pack_v1_responses_consistent.json",
            "consistent",
            1,
            1,
        ),
        (
            "software_entity_kind_collapse_pack_v0",
            "software_entity_kind_collapse_pack_v0_responses_inconsistent.json",
            "inconsistent",
            8,
            1,
        ),
        (
            "finance_entity_kind_collapse_pack_v0",
            "finance_entity_kind_collapse_pack_v0_responses_incomplete.json",
            "incomplete",
            10,
            10,
        ),
    ],
)
def test_evaluate_hotspot_cluster_pack_uses_canned_response_fixtures(
    pack_id: str,
    fixture_name: str,
    expected_classification: str,
    expected_total: int,
    expected_count: int,
) -> None:
    cluster_pack = _cluster_pack(pack_id)
    response_bundle = load_hotspot_response_bundle(FIXTURE_DIR / fixture_name)

    report = evaluate_hotspot_cluster_pack(cluster_pack, response_bundle)

    assert report["schema_version"] == HOTSPOT_EVAL_SCHEMA_VERSION
    assert report["manifest_version"] == "wikidata_hotspot_pilot_pack_v1"
    counts = report["summary"]["cluster_counts"]
    assert counts["total"] == expected_total
    assert counts[expected_classification] == expected_count


def test_evaluate_hotspot_cluster_pack_rejects_missing_question_response() -> None:
    cluster_pack = _cluster_pack("software_entity_kind_collapse_pack_v0")
    cluster = cluster_pack["packs"][0]["clusters"][0]
    partial_bundle = {
        "schema_version": HOTSPOT_RESPONSE_SCHEMA_VERSION,
        "model_run_id": "run-001",
        "model_id": "external-or-human-labels",
        "prompt_profile": "default_yes_no_v1",
        "responses": [
            {
                "cluster_id": cluster["cluster_id"],
                "question_id": cluster["questions"][0]["question_id"],
                "label": "yes",
            }
        ],
    }

    with pytest.raises(ValueError, match="missing responses"):
        evaluate_hotspot_cluster_pack(cluster_pack, partial_bundle)


def test_evaluate_hotspot_cluster_pack_rejects_duplicate_question_response() -> None:
    cluster_pack = _cluster_pack("software_entity_kind_collapse_pack_v0")
    cluster = cluster_pack["packs"][0]["clusters"][0]
    question = cluster["questions"][0]
    bundle = {
        "schema_version": HOTSPOT_RESPONSE_SCHEMA_VERSION,
        "model_run_id": "run-001",
        "model_id": "external-or-human-labels",
        "prompt_profile": "default_yes_no_v1",
        "responses": [
            {
                "cluster_id": cluster["cluster_id"],
                "question_id": question["question_id"],
                "label": "yes",
            },
            {
                "cluster_id": cluster["cluster_id"],
                "question_id": question["question_id"],
                "label": "yes",
            },
        ],
    }

    with pytest.raises(ValueError, match="duplicate response"):
        evaluate_hotspot_cluster_pack(cluster_pack, bundle)


def test_evaluate_hotspot_cluster_pack_rejects_invalid_label() -> None:
    cluster_pack = _cluster_pack("software_entity_kind_collapse_pack_v0")
    cluster = cluster_pack["packs"][0]["clusters"][0]
    question = cluster["questions"][0]
    bundle = {
        "schema_version": HOTSPOT_RESPONSE_SCHEMA_VERSION,
        "model_run_id": "run-001",
        "model_id": "external-or-human-labels",
        "prompt_profile": "default_yes_no_v1",
        "responses": [
            {
                "cluster_id": cluster["cluster_id"],
                "question_id": question["question_id"],
                "label": "maybe",
            }
        ],
    }

    with pytest.raises(ValueError, match="invalid response label"):
        evaluate_hotspot_cluster_pack(cluster_pack, bundle)
