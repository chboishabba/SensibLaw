import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from cli import __main__ as cli_main

FIXTURE_DIR = ROOT / "tests" / "fixtures" / "wikidata" / "hotspot_eval_v1"


def test_wikidata_hotspot_generate_clusters_cli_writes_report(tmp_path, capsys) -> None:
    manifest_path = ROOT.parent / "docs" / "planning" / "wikidata_hotspot_pilot_pack_v1.manifest.json"
    out_path = tmp_path / "hotspot_cluster_pack.json"

    cli_main.main(
        [
            "wikidata",
            "hotspot-generate-clusters",
            "--manifest",
            str(manifest_path),
            "--pack-id",
            "software_entity_kind_collapse_pack_v0",
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert stdout["output"] == str(out_path)
    assert payload["selected_pack_ids"] == ["software_entity_kind_collapse_pack_v0"]
    assert payload["packs"][0]["cluster_count"] >= 3
    assert payload["packs"][0]["clusters"][0]["questions"][0]["question_id"].endswith(":q0")


def test_wikidata_hotspot_generate_clusters_cli_defaults_to_all_entries(tmp_path, capsys) -> None:
    manifest_path = ROOT.parent / "docs" / "planning" / "wikidata_hotspot_pilot_pack_v1.manifest.json"
    out_path = tmp_path / "hotspot_cluster_pack_all.json"

    cli_main.main(
        [
            "wikidata",
            "hotspot-generate-clusters",
            "--manifest",
            str(manifest_path),
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert stdout["pack_count"] == 5
    assert payload["pack_count"] == 5
    assert payload["manifest_version"] == "wikidata_hotspot_pilot_pack_v1"
    assert payload["cluster_count"] > 0


def test_wikidata_hotspot_eval_cli_writes_report(tmp_path, capsys) -> None:
    manifest_path = ROOT.parent / "docs" / "planning" / "wikidata_hotspot_pilot_pack_v1.manifest.json"
    cluster_path = tmp_path / "cluster_pack.json"
    out_path = tmp_path / "eval_report.json"

    cli_main.main(
        [
            "wikidata",
            "hotspot-generate-clusters",
            "--manifest",
            str(manifest_path),
            "--pack-id",
            "qualifier_drift_p166_live_pack_v1",
            "--output",
            str(cluster_path),
        ]
    )
    capsys.readouterr()

    cli_main.main(
        [
            "wikidata",
            "hotspot-eval",
            "--cluster-pack",
            str(cluster_path),
            "--responses",
            str(FIXTURE_DIR / "qualifier_drift_p166_live_pack_v1_responses_consistent.json"),
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert stdout["output"] == str(out_path)
    assert payload["schema_version"] == "wikidata_hotspot_eval/v1"
    assert payload["summary"]["cluster_counts"]["total"] == len(payload["cluster_results"])
