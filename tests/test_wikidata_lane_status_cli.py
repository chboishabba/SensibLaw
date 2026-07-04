import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from cli import __main__ as cli_main


def test_wikidata_lane_status_cli_writes_report(tmp_path, capsys) -> None:
    out_path = tmp_path / "wikidata_lane_status.json"

    cli_main.main(
        [
            "wikidata",
            "lane-status",
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert stdout["output"] == str(out_path)
    assert stdout["lane_count"] == 5
    assert stdout["direct_zelph_096_lane_ids"] == ["disjointness_report"]
    assert payload["schema_version"] == "sl.wikidata_lane_status.v0_4"


def test_wikidata_lane_bundle_cli_writes_report(tmp_path, capsys) -> None:
    out_path = tmp_path / "wikidata_lane_bundle.json"

    cli_main.main(
        [
            "wikidata",
            "lane-bundle",
            "--lane",
            "disjointness_report",
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert stdout["output"] == str(out_path)
    assert stdout["lane_id"] == "disjointness_report"
    assert stdout["promotion_status"] == "candidate_only"
    assert payload["schema_version"] == "sl.wikidata_signal_review_bundle.v0_1"


def test_wikidata_lane_graph_cli_writes_report(tmp_path, capsys) -> None:
    out_path = tmp_path / "wikidata_lane_graph.json"

    cli_main.main(
        [
            "wikidata",
            "lane-graph",
            "--lane",
            "hotspot_eval",
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert stdout["output"] == str(out_path)
    assert stdout["lane_id"] == "hotspot_eval"
    assert stdout["flatness_posture"]
    assert stdout["duplicate_node_id_count"] == 1
    assert payload["schema_version"] == "sl.wikidata_latent_slice_graph.v0_1"


def test_wikidata_lane_flatness_cli_writes_report(tmp_path, capsys) -> None:
    out_path = tmp_path / "wikidata_lane_flatness.json"

    cli_main.main(
        [
            "wikidata",
            "lane-flatness",
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert stdout == {
        "output": str(out_path),
        "schema_version": "sl.wikidata_lane_flatness_audit.v0_1",
        "lane_count": 5,
        "duplicate_identity_lane_ids": ["hotspot_eval"],
        "renderer_followup_status": "defer_to_itir_svelte_priority_list",
    }
    assert payload["summary"]["structured_lane_count"] == 0


def test_wikidata_linkage_depth_cli_writes_report(tmp_path, capsys) -> None:
    out_path = tmp_path / "wikidata_linkage_depth.json"

    cli_main.main(
        [
            "wikidata",
            "linkage-depth",
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert stdout == {
        "output": str(out_path),
        "schema_version": "sl.wikidata_linkage_depth_audit.v0_1",
        "case_count": 3,
        "complete_case_ids": [
            "dog_soft_stitch",
            "climate_review_demonstrator",
            "disjointness_report",
        ],
        "anchor_failure_case_ids": [],
    }
    assert [row["contract_id"] for row in payload["contracts"]] == [
        "sensiblaw_pnf_wd_linkage",
        "wikidata_disjointness_review_linkage",
    ]


def test_wikidata_lane_proof_cli_writes_report(tmp_path, capsys) -> None:
    out_path = tmp_path / "wikidata_lane_proof.json"

    cli_main.main(
        [
            "wikidata",
            "lane-proof",
            "--lane",
            "disjointness_report",
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert stdout == {
        "output": str(out_path),
        "schema_version": "sl.wikidata_zelph_lane_proof.v0_1",
        "lane_id": "disjointness_report",
        "overall_status": "bounded_local_ready",
        "hosted_wd_acceptance_status": "pending_manifest_alignment",
    }
    assert payload["transport_artifact"]["summary"]["manifest_version"] == "zelph-hf-layout/v2"


def test_wikidata_lane_plan_cli_writes_report(tmp_path, capsys) -> None:
    out_path = tmp_path / "wikidata_lane_plan.json"

    cli_main.main(
        [
            "wikidata",
            "lane-plan",
            "--lane",
            "nat_live_follow_preflight",
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert stdout == {
        "output": str(out_path),
        "schema_version": "sl.wikidata_zelph_lane_plan.v0_1",
        "lane_id": "nat_live_follow_preflight",
        "overall_status": "ready_for_parallel_discovery",
        "query_pressure_count": 2,
    }
    assert payload["readiness"]["hosted_wd_dependency_status"] == "not_blocking"
