import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from src.ontology.wikidata_hotspot import (
    HOTSPOT_CLUSTER_SCHEMA_VERSION,
    generate_hotspot_cluster_pack,
    load_hotspot_manifest,
)


def test_generate_hotspot_cluster_pack_builds_selected_packs() -> None:
    manifest_path = ROOT.parent / "docs" / "planning" / "wikidata_hotspot_pilot_pack_v1.manifest.json"
    manifest = load_hotspot_manifest(manifest_path)

    pack = generate_hotspot_cluster_pack(
        manifest,
        repo_root=ROOT.parent,
        pack_ids=("mixed_order_live_pack_v1", "finance_entity_kind_collapse_pack_v0"),
    )

    assert pack["schema_version"] == HOTSPOT_CLUSTER_SCHEMA_VERSION
    assert pack["manifest_version"] == "wikidata_hotspot_pilot_pack_v1"
    assert pack["selected_pack_ids"] == [
        "mixed_order_live_pack_v1",
        "finance_entity_kind_collapse_pack_v0",
    ]
    mixed = next(item for item in pack["packs"] if item["pack_id"] == "mixed_order_live_pack_v1")
    assert mixed["cluster_count"] >= 2
    first_question = mixed["clusters"][0]["questions"][0]
    assert first_question["question_id"].endswith(":q0")
    assert isinstance(first_question["text"], str)
    finance = next(item for item in pack["packs"] if item["pack_id"] == "finance_entity_kind_collapse_pack_v0")
    assert finance["status"] == "fixture_backed"
    assert finance["promotion_status"] == "promotable"
    assert finance["hold_reason"] == "awaiting_manifest_promotion"
    assert any(cluster["cluster_family"] == "kind_disambiguation" for cluster in finance["clusters"])


def test_generate_hotspot_cluster_pack_uses_repo_pinned_qualifier_drift() -> None:
    manifest_path = ROOT.parent / "docs" / "planning" / "wikidata_hotspot_pilot_pack_v1.manifest.json"
    manifest = load_hotspot_manifest(manifest_path)

    pack = generate_hotspot_cluster_pack(
        manifest,
        repo_root=ROOT.parent,
        pack_ids=("qualifier_drift_p166_live_pack_v1",),
    )

    qualifier_pack = pack["packs"][0]
    assert qualifier_pack["cluster_count"] == 1
    cluster = qualifier_pack["clusters"][0]
    assert cluster["cluster_family"] == "temporalized_statement"
    assert cluster["evidence"]["severity"] == "medium"


def test_generate_hotspot_cluster_pack_builds_all_manifest_entries() -> None:
    manifest_path = ROOT.parent / "docs" / "planning" / "wikidata_hotspot_pilot_pack_v1.manifest.json"
    manifest = load_hotspot_manifest(manifest_path)

    pack = generate_hotspot_cluster_pack(
        manifest,
        repo_root=ROOT.parent,
    )

    expected_ids = [entry["pack_id"] for entry in manifest["entries"]]
    assert pack["selected_pack_ids"] == expected_ids
    assert pack["pack_count"] == len(expected_ids)
    assert pack["cluster_count"] > 0
    assert all("promotion_status" in emitted_pack for emitted_pack in pack["packs"])
    for emitted_pack in pack["packs"]:
        if emitted_pack["promotion_status"] == "promoted":
            assert emitted_pack["hold_reason"] is None
        else:
            assert isinstance(emitted_pack["hold_reason"], str)
        for cluster in emitted_pack["clusters"]:
            for index, question in enumerate(cluster["questions"]):
                assert question["question_id"] == f"{cluster['cluster_id']}:q{index}"
                assert question["text"]


def test_load_hotspot_manifest_requires_hold_reason_for_non_promoted(tmp_path) -> None:
    manifest_path = tmp_path / "bad_manifest.json"
    manifest_path.write_text(
        """
{
  "version": "wikidata_hotspot_pilot_pack_v1",
  "date": "2026-03-25",
  "selection_policy": {
    "priority_order": ["structural_legibility"],
    "real_first": true,
    "require_fixture_or_report_backing": true,
    "require_provenance_receipts": true
  },
  "entries": [
    {
      "pack_id": "bad_pack",
      "status": "fixture_backed",
      "promotion_status": "anchored",
      "hotspot_family": "mixed_order",
      "primary_story": "bad",
      "source_kind": "repo_fixture",
      "focus_qids": ["Q1"],
      "focus_pids": ["P31"],
      "source_artifacts": ["dummy.json"],
      "candidate_cluster_families": ["edge_yes"],
      "selection_reason": "bad",
      "expected_value": "bad",
      "commands": []
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )

    try:
        load_hotspot_manifest(manifest_path)
    except ValueError as exc:
        assert "hold_reason is required" in str(exc)
    else:
        raise AssertionError("expected manifest validation failure for missing hold_reason")
