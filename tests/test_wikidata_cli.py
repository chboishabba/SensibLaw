import json
import sys
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from cli import __main__ as cli_main
from scripts.build_gwb_broader_review import build_gwb_broader_review
from SensibLaw.src.fact_intake.au_review_bundle import build_au_fact_review_bundle_world_model_report
from SensibLaw.src.ontology.wikidata_nat_cohort_b_operator_packet import (
    build_nat_cohort_b_operator_packet_world_model_report,
)
from src.policy.gwb_broader_review_world_model import (
    build_gwb_broader_review_world_model_report,
)
from SensibLaw.src.sources.national_archives.brexit_national_archives_lane import (
    build_brexit_national_archives_world_model_report,
    fetch_brexit_archive_records,
)
from SensibLaw.tests.test_au_fact_review_bundle import _prepare_au_fact_review_bundle_fixture
from src.ontology.wikidata_nat_automation_graduation import build_nat_claim_convergence_report


def test_wikidata_project_cli_writes_report(tmp_path, capsys) -> None:
    in_path = tmp_path / "wikidata_slice.json"
    out_path = tmp_path / "wikidata_report.json"
    in_path.write_text(
        json.dumps(
            {
                "windows": [
                    {
                        "id": "t1",
                        "statement_bundles": [
                            {
                                "subject": "Q1",
                                "property": "P31",
                                "value": "Q2",
                                "rank": "preferred",
                                "references": [{"P248": "Qsrc"}],
                            }
                        ],
                    },
                    {
                        "id": "t2",
                        "statement_bundles": [
                            {
                                "subject": "Q1",
                                "property": "P31",
                                "value": "Q2",
                                "rank": "deprecated",
                                "references": [{"P248": "Qsrc"}],
                            }
                        ],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    cli_main.main(
        [
            "wikidata",
            "project",
            "--input",
            str(in_path),
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    file_payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert stdout["output"] == str(out_path)
    assert file_payload["unstable_slots"][0]["slot_id"] == "Q1|P31"


def test_wikidata_build_slice_cli_groups_window_files(tmp_path, capsys) -> None:
    root = Path(__file__).resolve().parent
    source_a = root / "fixtures" / "wikidata" / "entitydata_window_a.json"
    source_b = root / "fixtures" / "wikidata" / "entitydata_window_b.json"
    out_path = tmp_path / "built_slice.json"

    cli_main.main(
        [
            "wikidata",
            "build-slice",
            "--window-file",
            f"t1:{source_a}",
            "--window-file",
            f"t2:{source_b}",
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    file_payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert stdout["output"] == str(out_path)
    assert [window["id"] for window in file_payload["windows"]] == ["t1", "t2"]
    assert file_payload["windows"][0]["statement_bundles"][0]["subject"] == "Q9779"


def test_wikidata_project_cli_emits_qualifier_drift(tmp_path, capsys) -> None:
    root = Path(__file__).resolve().parent
    in_path = root / "fixtures" / "wikidata" / "qualifier_drift_slice_20260307.json"
    out_path = tmp_path / "qualifier_report.json"

    cli_main.main(
        [
            "wikidata",
            "project",
            "--input",
            str(in_path),
            "--property",
            "P166",
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    file_payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert stdout["output"] == str(out_path)
    assert file_payload["qualifier_drift"][0]["slot_id"] == "Qposthumous_case|P166"


def test_wikidata_build_slice_and_project_real_qualifier_baseline(tmp_path, capsys) -> None:
    root = Path(__file__).resolve().parent
    out_slice = tmp_path / "real_qualifier_slice.json"
    out_report = tmp_path / "real_qualifier_report.json"

    cli_main.main(
        [
            "wikidata",
            "build-slice",
            "--window-file",
            f"t1:{root / 'fixtures' / 'wikidata' / 'entitydata_qualifier_q28792860_prev.json'}",
            "--window-file",
            f"t1:{root / 'fixtures' / 'wikidata' / 'entitydata_qualifier_q1336181_prev.json'}",
            "--window-file",
            f"t2:{root / 'fixtures' / 'wikidata' / 'entitydata_qualifier_q28792860_current.json'}",
            "--window-file",
            f"t2:{root / 'fixtures' / 'wikidata' / 'entitydata_qualifier_q1336181_current.json'}",
            "--property",
            "P166",
            "--output",
            str(out_slice),
        ]
    )
    capsys.readouterr()

    cli_main.main(
        [
            "wikidata",
            "project",
            "--input",
            str(out_slice),
            "--property",
            "P166",
            "--output",
            str(out_report),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    file_payload = json.loads(out_report.read_text(encoding="utf-8"))

    assert stdout["output"] == str(out_report)
    assert file_payload["qualifier_drift"] == []
    assert {
        slot["slot_id"] for slot in file_payload["windows"][0]["slots"]
    } == {"Q1336181|P166", "Q28792860|P166"}


def test_wikidata_project_cli_matches_repo_pinned_live_drift_case(tmp_path, capsys) -> None:
    root = Path(__file__).resolve().parent
    in_path = (
        root
        / "fixtures"
        / "wikidata"
        / "q100104196_p166_2277985537_2277985693"
        / "slice.json"
    )
    out_path = tmp_path / "repo_pinned_live_drift_report.json"

    cli_main.main(
        [
            "wikidata",
            "project",
            "--input",
            str(in_path),
            "--property",
            "P166",
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    file_payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert stdout["output"] == str(out_path)
    assert file_payload["qualifier_drift"][0]["slot_id"] == "Q100104196|P166"
    assert file_payload["qualifier_drift"][0]["severity"] == "medium"


def test_wikidata_project_cli_matches_repo_pinned_second_live_drift_case(tmp_path, capsys) -> None:
    root = Path(__file__).resolve().parent
    in_path = (
        root
        / "fixtures"
        / "wikidata"
        / "q100152461_p54_2456615151_2456615274"
        / "slice.json"
    )
    out_path = tmp_path / "repo_pinned_second_live_drift_report.json"

    cli_main.main(
        [
            "wikidata",
            "project",
            "--input",
            str(in_path),
            "--property",
            "P54",
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    file_payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert stdout["output"] == str(out_path)
    assert file_payload["qualifier_drift"][0]["slot_id"] == "Q100152461|P54"
    assert file_payload["qualifier_drift"][0]["severity"] == "medium"


def test_wikidata_nat_live_follow_campaign_cli_writes_plan(tmp_path, capsys) -> None:
    root = Path(__file__).resolve().parent
    in_path = (
        root
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_live_follow_campaign_20260403.json"
    )
    out_path = tmp_path / "nat_live_follow_plan.json"

    cli_main.main(
        [
            "wikidata",
            "nat-live-follow-campaign",
            "--input",
            str(in_path),
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    file_payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert stdout["output"] == str(out_path)
    assert file_payload["schema_version"] == "sl.wikidata_nat.live_follow_campaign_plan.v0_1"
    assert file_payload["campaign_id"] == "wikidata_nat_live_follow_campaign_20260403"
    assert file_payload["plan_count"] == 11


def test_wikidata_nat_live_follow_execute_cli_writes_result(tmp_path, capsys, monkeypatch) -> None:
    root = Path(__file__).resolve().parent
    in_path = (
        root
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_live_follow_campaign_20260403.json"
    )
    out_path = tmp_path / "nat_live_follow_result.json"

    from src.ontology import wikidata_nat_live_follow_executor as executor

    def fake_fetch_json(url: str, *, params=None, timeout_seconds: int = 30):
        if "w/api.php" in url:
            return {
                "query": {
                    "pages": {
                        "1": {
                            "revisions": [
                                {"revid": 2474420124, "timestamp": "2026-04-01T12:00:00Z"},
                            ]
                        }
                    }
                }
            }
        if "Special:EntityData" in url:
            return {
                "entities": {
                    "Q10403939": {
                        "labels": {"en": {"value": "Example company"}},
                        "claims": {"P31": [], "P5991": []},
                    }
                }
            }
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr(executor, "_http_get_json", fake_fetch_json)

    cli_main.main(
        [
            "wikidata",
            "nat-live-follow-execute",
            "--input",
            str(in_path),
            "--category",
            "hard_grounding_packet",
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    file_payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert stdout["output"] == str(out_path)
    assert file_payload["schema_version"] == "sl.wikidata_nat.live_follow_result.v0_1"
    assert file_payload["selected_count"] == 1
    assert file_payload["status_counts"] == {"fetched": 1}


def test_wikidata_nat_live_follow_preflight_cli_writes_report(tmp_path, capsys) -> None:
    root = Path(__file__).resolve().parent
    in_path = (
        root
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_live_follow_campaign_20260403.json"
    )
    out_path = tmp_path / "policy_risk_preflight.json"

    cli_main.main(
        [
            "wikidata",
            "nat-live-follow-preflight",
            "--input",
            str(in_path),
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    file_payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert stdout["output"] == str(out_path)
    assert stdout["schema_version"] == "sl.wikidata_nat.policy_risk_population_preview_preflight.v0_1"
    assert stdout["top_n"] == 2
    assert stdout["candidate_count"] == 2
    assert file_payload["candidate_count"] == 2
    assert len(file_payload["candidates"]) == 2


def test_wikidata_build_migration_pack_cli_writes_pack(tmp_path, capsys) -> None:
    in_path = tmp_path / "migration_slice.json"
    out_path = tmp_path / "migration_pack.json"
    in_path.write_text(
        json.dumps(
            {
                "windows": [
                    {
                        "id": "t1",
                        "statement_bundles": [
                            {
                                "subject": "Q1",
                                "property": "P5991",
                                "value": "100",
                                "rank": "normal",
                                "references": [{"P248": "Qsrc"}],
                            }
                        ],
                    },
                    {
                        "id": "t2",
                        "statement_bundles": [
                            {
                                "subject": "Q1",
                                "property": "P5991",
                                "value": "100",
                                "rank": "normal",
                                "references": [{"P248": "Qsrc"}],
                            }
                        ],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    cli_main.main(
        [
            "wikidata",
            "build-migration-pack",
            "--input",
            str(in_path),
            "--source-property",
            "P5991",
            "--target-property",
            "P14143",
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    file_payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert stdout["output"] == str(out_path)
    assert stdout["candidate_count"] == 1
    assert file_payload["source_property"] == "P5991"
    assert file_payload["target_property"] == "P14143"
    assert file_payload["candidates"][0]["claim_bundle_after"]["property"] == "P14143"
    assert file_payload["summary"]["checked_safe_subset"] == [
        file_payload["candidates"][0]["candidate_id"]
    ]


def test_wikidata_project_cli_accepts_prepopulation_core_profile(tmp_path, capsys) -> None:
    in_path = tmp_path / "prepopulation_core_slice.json"
    out_path = tmp_path / "prepopulation_core_report.json"
    in_path.write_text(
        json.dumps(
            {
                "windows": [
                    {
                        "id": "t1",
                        "statement_bundles": [
                            {"subject": "Q1", "property": "P31", "value": "QClass", "rank": "preferred"},
                            {"subject": "Q1", "property": "P361", "value": "QWhole", "rank": "preferred"},
                            {"subject": "QWhole", "property": "P527", "value": "Q1", "rank": "preferred"},
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    cli_main.main(
        [
            "wikidata",
            "project",
            "--input",
            str(in_path),
            "--profile",
            "prepopulation_core",
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    file_payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert stdout["output"] == str(out_path)
    assert file_payload["bounded_slice"]["profile"] == "prepopulation_core"
    assert file_payload["bounded_slice"]["properties"] == ["P279", "P31", "P361", "P527"]
    assert file_payload["windows"][0]["diagnostics"]["parthood_typing"]["classifications"]


def test_wikidata_export_migration_pack_openrefine_cli_writes_csv(tmp_path, capsys) -> None:
    in_path = tmp_path / "migration_pack.json"
    out_path = tmp_path / "migration_pack_openrefine.csv"
    in_path.write_text(
        json.dumps(
            {
                "target_property": "P14143",
                "candidates": [
                    {
                        "candidate_id": "Q1|P5991|1",
                        "entity_qid": "Q1",
                        "slot_id": "Q1|P5991",
                        "statement_index": 1,
                        "classification": "safe_with_reference_transfer",
                        "action": "migrate_with_refs",
                        "confidence": 0.9,
                        "requires_review": False,
                        "reasons": [],
                        "split_axes": [],
                        "claim_bundle_before": {
                            "property": "P5991",
                            "value": "100",
                            "rank": "normal",
                            "qualifiers": {"P585": ["2024"]},
                            "references": [{"P248": ["Qsrc"]}],
                        },
                        "qualifier_diff": {"status": "unchanged", "severity": None},
                        "reference_diff": {"status": "unchanged", "severity": None},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    cli_main.main(
        [
            "wikidata",
            "export-migration-pack-openrefine",
            "--input",
            str(in_path),
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    rows = list(csv.DictReader(out_path.open(encoding="utf-8")))
    assert stdout["output"] == str(out_path)
    assert stdout["row_count"] == 1
    assert rows[0]["entity_qid"] == "Q1"
    assert rows[0]["action"] == "migrate_with_refs"
    assert rows[0]["suggested_action"] == "migrate_with_refs"
    assert rows[0]["split_axis_count"] == "0"


def test_wikidata_export_migration_pack_checked_safe_cli_writes_csv(tmp_path, capsys) -> None:
    in_path = tmp_path / "migration_pack.json"
    out_path = tmp_path / "migration_pack_checked_safe.csv"
    in_path.write_text(
        json.dumps(
            {
                "target_property": "P14143",
                "candidates": [
                    {
                        "candidate_id": "Q1|P5991|1",
                        "entity_qid": "Q1",
                        "slot_id": "Q1|P5991",
                        "statement_index": 1,
                        "classification": "safe_with_reference_transfer",
                        "action": "migrate_with_refs",
                        "claim_bundle_before": {
                            "property": "P5991",
                            "value": "100",
                            "rank": "normal",
                            "qualifiers": {"P585": ["2024"]},
                            "references": [{"P248": ["Qsrc"]}],
                        },
                        "claim_bundle_after": {
                            "property": "P14143",
                            "value": "100",
                            "rank": "normal",
                            "qualifiers": {"P585": ["2024"]},
                            "references": [{"P248": ["Qsrc"]}],
                        },
                    },
                    {
                        "candidate_id": "Q2|P5991|1",
                        "entity_qid": "Q2",
                        "slot_id": "Q2|P5991",
                        "statement_index": 1,
                        "classification": "split_required",
                        "action": "split",
                        "claim_bundle_before": {
                            "property": "P5991",
                            "value": "200",
                            "rank": "normal",
                            "qualifiers": {},
                            "references": [],
                        },
                        "claim_bundle_after": {
                            "property": "P14143",
                            "value": "200",
                            "rank": "normal",
                            "qualifiers": {},
                            "references": [],
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    cli_main.main(
        [
            "wikidata",
            "export-migration-pack-checked-safe",
            "--input",
            str(in_path),
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    rows = list(csv.DictReader(out_path.open(encoding="utf-8")))
    assert stdout["output"] == str(out_path)
    assert stdout["row_count"] == 1
    assert stdout["export_scope"] == "checked_safe_subset_only"
    assert rows[0]["candidate_id"] == "Q1|P5991|1"
    assert rows[0]["action"] == "migrate_with_refs"


def test_wikidata_verify_migration_pack_cli_writes_json(tmp_path, capsys) -> None:
    migration_pack_path = tmp_path / "migration_pack.json"
    after_path = tmp_path / "after.json"
    out_path = tmp_path / "verification.json"
    migration_pack_path.write_text(
        json.dumps(
            {
                "source_property": "P5991",
                "target_property": "P14143",
                "candidates": [
                    {
                        "candidate_id": "Q1|P5991|1",
                        "entity_qid": "Q1",
                        "classification": "safe_with_reference_transfer",
                        "action": "migrate_with_refs",
                        "claim_bundle_before": {
                            "subject": "Q1",
                            "property": "P5991",
                            "value": "100",
                            "rank": "normal",
                            "qualifiers": {"P585": ["2024"]},
                            "references": [{"P248": ["Qsrc"]}],
                            "window_id": "t1",
                        },
                        "claim_bundle_after": {
                            "subject": "Q1",
                            "property": "P14143",
                            "value": "100",
                            "rank": "normal",
                            "qualifiers": {"P585": ["2024"]},
                            "references": [{"P248": ["Qsrc"]}],
                            "window_id": "t1",
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    after_path.write_text(
        json.dumps(
            {
                "windows": [
                    {
                        "id": "after",
                        "statement_bundles": [
                            {
                                "subject": "Q1",
                                "property": "P14143",
                                "value": "100",
                                "rank": "normal",
                                "qualifiers": {"P585": "2024"},
                                "references": [{"P248": "Qsrc"}],
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    cli_main.main(
        [
            "wikidata",
            "verify-migration-pack",
            "--input",
            str(migration_pack_path),
            "--after",
            str(after_path),
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert stdout["output"] == str(out_path)
    assert stdout["verified_candidate_count"] == 1
    assert stdout["counts_by_status"] == {"verified": 1}
    assert payload["rows"][0]["status"] == "verified"


def test_wikidata_build_split_plan_cli_writes_json(tmp_path, capsys) -> None:
    in_path = tmp_path / "migration_pack.json"
    out_path = tmp_path / "split_plan.json"
    in_path.write_text(
        json.dumps(
            {
                "source_property": "P5991",
                "target_property": "P14143",
                "candidates": [
                    {
                        "candidate_id": "Q1|P5991|1",
                        "entity_qid": "Q1",
                        "slot_id": "Q1|P5991",
                        "statement_index": 1,
                        "classification": "split_required",
                        "action": "split",
                        "split_axes": [
                            {"property": "__value__", "cardinality": 2, "source": "slot", "reason": "multi_value_slot"},
                        ],
                        "claim_bundle_before": {
                            "subject": "Q1",
                            "property": "P5991",
                            "value": "100",
                            "rank": "normal",
                            "qualifiers": {"P585": ["2023"]},
                            "references": [{"P248": ["Qsrc"]}],
                            "window_id": "t1",
                        },
                        "claim_bundle_after": {
                            "subject": "Q1",
                            "property": "P14143",
                            "value": "100",
                            "rank": "normal",
                            "qualifiers": {"P585": ["2023"]},
                            "references": [{"P248": ["Qsrc"]}],
                            "window_id": "t1",
                        },
                    },
                    {
                        "candidate_id": "Q1|P5991|2",
                        "entity_qid": "Q1",
                        "slot_id": "Q1|P5991",
                        "statement_index": 2,
                        "classification": "split_required",
                        "action": "split",
                        "split_axes": [
                            {"property": "__value__", "cardinality": 2, "source": "slot", "reason": "multi_value_slot"},
                        ],
                        "claim_bundle_before": {
                            "subject": "Q1",
                            "property": "P5991",
                            "value": "120",
                            "rank": "normal",
                            "qualifiers": {"P585": ["2024"]},
                            "references": [{"P248": ["Qsrc"]}],
                            "window_id": "t1",
                        },
                        "claim_bundle_after": {
                            "subject": "Q1",
                            "property": "P14143",
                            "value": "120",
                            "rank": "normal",
                            "qualifiers": {"P585": ["2024"]},
                            "references": [{"P248": ["Qsrc"]}],
                            "window_id": "t1",
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    cli_main.main(
        [
            "wikidata",
            "build-split-plan",
            "--input",
            str(in_path),
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert stdout["output"] == str(out_path)
    assert stdout["plan_count"] == 1
    assert stdout["counts_by_status"] == {"structurally_decomposable": 1}
    assert payload["plans"][0]["status"] == "structurally_decomposable"


def test_wikidata_cohort_c_operator_packet_cli_wraps_scan_payload(tmp_path, capsys) -> None:
    root = Path(__file__).resolve().parent
    in_path = root / "fixtures" / "wikidata" / "wikidata_nat_cohort_c_population_scan_20260402.json"
    out_path = tmp_path / "cohort_c_operator_packet.json"

    cli_main.main(
        [
            "wikidata",
            "cohort-c-operator-packet",
            "--input",
            str(in_path),
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert stdout["output"] == str(out_path)
    assert stdout["decision"] == "review"
    assert stdout["candidate_count"] == 3
    assert payload["decision"] == "review"
    assert payload["triage_prompts"][0].startswith("Review the candidate P459 status split")


def test_wikidata_cohort_d_operator_review_cli_materializes_queue_surface(tmp_path, capsys) -> None:
    root = Path(__file__).resolve().parent
    in_path = (
        root
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_cohort_d_type_probing_surface_20260402.json"
    )
    out_path = tmp_path / "cohort_d_operator_review_surface.json"

    cli_main.main(
        [
            "wikidata",
            "cohort-d-operator-review",
            "--input",
            str(in_path),
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert stdout["output"] == str(out_path)
    assert stdout["readiness"] == "review_queue_ready"
    assert stdout["queue_size"] == 2
    assert stdout["unresolved_packet_ref_count"] == 0
    assert payload["readiness"] == "review_queue_ready"
    assert payload["queue_size"] == 2
    assert payload["governance"]["automation_allowed"] is False
    assert payload["governance"]["can_execute_edits"] is False
    assert all(row["execution_allowed"] is False for row in payload["operator_queue"])


def test_wikidata_cohort_d_operator_report_cli_materializes_report_surface(tmp_path, capsys) -> None:
    root = Path(__file__).resolve().parent
    in_path = (
        root
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_cohort_d_operator_review_surface_20260402.json"
    )
    out_path = tmp_path / "cohort_d_operator_report.json"

    cli_main.main(
        [
            "wikidata",
            "cohort-d-operator-report",
            "--input",
            str(in_path),
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert stdout["output"] == str(out_path)
    assert stdout["readiness"] == "review_queue_ready"
    assert stdout["decision"] == "review"
    assert stdout["promotion_allowed"] is False
    assert stdout["queue_size"] == 2
    assert payload["decision"] == "review"
    assert payload["promotion_allowed"] is False
    assert payload["summary"]["queue_size"] == 2
    assert payload["governance"]["automation_allowed"] is False
    assert payload["governance"]["can_execute_edits"] is False


def test_wikidata_cohort_d_operator_report_batch_cli_materializes_batch_report(tmp_path, capsys) -> None:
    root = Path(__file__).resolve().parent
    in_path = (
        root
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_cohort_d_operator_report_batch_input_20260402.json"
    )
    out_path = tmp_path / "cohort_d_operator_report_batch.json"

    cli_main.main(
        [
            "wikidata",
            "cohort-d-operator-report-batch",
            "--input",
            str(in_path),
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert stdout["output"] == str(out_path)
    assert stdout["batch_id"] == "cohort_d_operator_batch_20260402"
    assert stdout["decision"] == "review"
    assert stdout["promotion_allowed"] is False
    assert stdout["case_count"] == 2
    assert stdout["all_cases_ready"] is False
    assert payload["summary"]["case_count"] == 2
    assert payload["summary"]["total_unresolved_packet_ref_count"] == 1


def test_wikidata_cohort_d_review_control_index_cli_materializes_control_index(tmp_path, capsys) -> None:
    root = Path(__file__).resolve().parent
    in_path = (
        root
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_cohort_d_review_control_index_input_20260402.json"
    )
    out_path = tmp_path / "cohort_d_review_control_index.json"

    cli_main.main(
        [
            "wikidata",
            "cohort-d-review-control-index",
            "--input",
            str(in_path),
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert stdout["output"] == str(out_path)
    assert stdout["index_id"] == "cohort_d_review_control_index_20260402"
    assert stdout["decision"] == "review"
    assert stdout["promotion_allowed"] is False
    assert stdout["batch_count"] == 2
    assert stdout["all_batches_ready"] is False
    assert payload["summary"]["batch_count"] == 2
    assert payload["summary"]["all_batches_ready"] is False
    assert "batch_not_all_cases_ready" in payload["blocked_signals"]


def test_wikidata_automation_graduation_eval_cli_approves_gate_a(tmp_path, capsys) -> None:
    root = Path(__file__).resolve().parent
    criteria_path = (
        root / "fixtures" / "wikidata" / "wikidata_nat_automation_graduation_criteria_20260402.json"
    )
    proposal_path = (
        root
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_automation_promotion_proposal_gate_a_promote_20260402.json"
    )
    out_path = tmp_path / "automation_graduation_report_gate_a.json"

    cli_main.main(
        [
            "wikidata",
            "automation-graduation-eval",
            "--criteria",
            str(criteria_path),
            "--proposal",
            str(proposal_path),
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert stdout["output"] == str(out_path)
    assert stdout["status"] == "approved"
    assert stdout["decision"] == "promote"
    assert stdout["promotion_allowed"] is True
    assert payload["status"] == "approved"
    assert payload["failed_checks"] == []


def test_wikidata_automation_graduation_eval_cli_holds_gate_b_with_blocker(tmp_path, capsys) -> None:
    root = Path(__file__).resolve().parent
    criteria_path = (
        root / "fixtures" / "wikidata" / "wikidata_nat_automation_graduation_criteria_20260402.json"
    )
    proposal_path = (
        root
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_automation_promotion_proposal_gate_b_hold_20260402.json"
    )
    out_path = tmp_path / "automation_graduation_report_gate_b.json"

    cli_main.main(
        [
            "wikidata",
            "automation-graduation-eval",
            "--criteria",
            str(criteria_path),
            "--proposal",
            str(proposal_path),
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert stdout["output"] == str(out_path)
    assert stdout["status"] == "rejected"
    assert stdout["decision"] == "hold"
    assert stdout["promotion_allowed"] is False
    assert payload["status"] == "rejected"
    assert "blocked_signal_triggered" in payload["failed_checks"]


def test_wikidata_automation_graduation_eval_batch_cli_writes_index_report(tmp_path, capsys) -> None:
    root = Path(__file__).resolve().parent
    criteria_path = (
        root / "fixtures" / "wikidata" / "wikidata_nat_automation_graduation_criteria_20260402.json"
    )
    proposal_batch_path = (
        root
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_automation_promotion_proposal_batch_20260402.json"
    )
    out_path = tmp_path / "automation_graduation_batch_report.json"

    cli_main.main(
        [
            "wikidata",
            "automation-graduation-eval-batch",
            "--criteria",
            str(criteria_path),
            "--proposal-batch",
            str(proposal_batch_path),
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert stdout["output"] == str(out_path)
    assert stdout["batch_id"] == "nat-grad-batch-v1"
    assert stdout["proposal_count"] == 2
    assert stdout["summary"]["approved_count"] == 1
    assert stdout["summary"]["rejected_count"] == 1
    assert stdout["summary"]["fail_closed_count"] == 1
    assert payload["proposal_count"] == 2
    assert payload["summary"]["approved_count"] == 1
    assert payload["summary"]["rejected_count"] == 1

def test_wikidata_nat_migration_batch_export_cli(tmp_path, capsys) -> None:
    root = Path(__file__).resolve().parent
    in_path = (
        root
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_cohort_a_gate_b_candidate_verification_runs_ready_20260403.json"
    )
    out_path = tmp_path / "nat_migration_batch_export.json"

    cli_main.main(
        [
            "wikidata",
            "nat-migration-batch-export",
            "--input",
            str(in_path),
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert stdout["output"] == str(out_path)
    assert stdout["export_id"] == payload["export_id"]
    assert stdout["row_count"] == payload["summary"]["row_count"]
    assert payload["family_id"] == "business_family_reconciled_low_qualifier_checked_safe_subset"
    assert payload["export_status"] == "ready_for_review_export"
    assert payload["summary"]["candidate_count"] == 2
    assert len(payload["artifacts"]) == 2
    assert payload["artifacts"][0]["artifact_kind"] == "openrefine_review_rows"


def test_wikidata_nat_migration_executed_rows_cli(tmp_path, capsys) -> None:
    root = Path(__file__).resolve().parent
    in_path = (
        root
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_business_family_migration_execution_proof_20260404.json"
    )
    out_path = tmp_path / "nat_migration_executed_rows.json"

    cli_main.main(
        [
            "wikidata",
            "nat-migration-executed-rows",
            "--input",
            str(in_path),
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert stdout["output"] == str(out_path)
    assert stdout["execution_status"] == "ready_execution_receipts"
    assert stdout["row_count"] == payload["summary"]["row_count"]
    assert payload["export_id"] == "business_family_reconciled_low_qualifier_checked_safe_subset-migration-export-5d9264e28e7f"
    assert payload["summary"]["row_count"] == 2


def test_wikidata_nat_post_write_verification_cli(tmp_path, capsys) -> None:
    root = Path(__file__).resolve().parent
    in_path = (
        root
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_cohort_a_gate_b_candidate_verification_runs_ready_20260403.json"
    )
    out_path = tmp_path / "nat_post_write_verification.json"

    cli_main.main(
        [
            "wikidata",
            "nat-post-write-verification",
            "--input",
            str(in_path),
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert stdout["output"] == str(out_path)
    assert stdout["run_count"] == payload["summary"]["run_count"]
    assert stdout["verified_run_count"] == payload["summary"]["verified_run_count"]
    assert payload["summary"]["verification_ready"] is True
    assert payload["summary"]["verified_run_count"] == 2
    assert stdout["subject_aware_summary"]["subject_count"] == 2
    assert stdout["subject_aware_summary"]["verified_subject_count"] == 2
    assert stdout["subject_aware_summary"]["drift_subject_count"] == 0
    assert stdout["subject_aware_summary"]["subject_aware_ready"] is True
    assert stdout["subject_aware_summary"]["subject_aware_state"] == "verified"


def test_wikidata_nat_sandbox_post_write_verification_cli(tmp_path, capsys) -> None:
    packet_path = tmp_path / "sandbox_packet.json"
    observed_path = tmp_path / "sandbox_observed.json"
    out_path = tmp_path / "sandbox_post_write_verification.json"

    packet_path.write_text(
        json.dumps(
            {
                "packet_id": "nat-sandbox-packet",
                "target_item": {"qid": "Q4115189"},
                "rows": [
                    {
                        "row_id": "sandbox-row-1",
                        "subject": "Q4115189",
                        "expected_after_state": {
                            "subject": "Q4115189",
                            "property": "P14143",
                            "value": "+13",
                            "unit_qid": "Q57084755",
                            "rank": "normal",
                            "qualifiers": {"P585": ["+2024-00-00T00:00:00Z"]},
                            "references": [{"P854": ["https://www.wikidata.org/wiki/Property:P14143"]}],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    observed_path.write_text(
        json.dumps(
            {
                "capture_id": "sandbox-capture-1",
                "target_item": "Q4115189",
                "observed_rows": [
                    {
                        "row_id": "sandbox-row-1",
                        "observed": {
                            "subject": "Q4115189",
                            "property": "P14143",
                            "value": "+13",
                            "unit_qid": "Q57084755",
                            "rank": "normal",
                            "qualifiers": {"P585": ["+2024-00-00T00:00:00Z"]},
                            "references": [{"P854": ["https://www.wikidata.org/wiki/Property:P14143"]}],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    cli_main.main(
        [
            "wikidata",
            "nat-sandbox-post-write-verification",
            "--packet",
            str(packet_path),
            "--observed",
            str(observed_path),
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert stdout["output"] == str(out_path)
    assert stdout["sandbox_packet_id"] == "nat-sandbox-packet"
    assert stdout["observed_capture_id"] == "sandbox-capture-1"
    assert stdout["verified_run_count"] == 1
    assert stdout["verification_ready"] is True
    assert payload["sandbox_packet_id"] == "nat-sandbox-packet"
    assert payload["observed_capture_id"] == "sandbox-capture-1"
    assert payload["summary"]["verified_run_count"] == 1


def test_wikidata_nat_completion_gate_cli(tmp_path, capsys) -> None:
    root = Path(__file__).resolve().parent
    in_path = (
        root
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_cohort_a_gate_b_candidate_verification_runs_ready_20260403.json"
    )
    out_path = tmp_path / "nat_completion_gate.json"

    cli_main.main(
        [
            "wikidata",
            "nat-completion-gate",
            "--input",
            str(in_path),
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert stdout["output"] == str(out_path)
    assert stdout["candidate_yield"] == 2
    assert stdout["dry_run_pass_rate"] == 1.0
    assert stdout["live_verification_pass_rate"] == 0.5
    assert payload["data_loss_zero"] is True
    assert payload["idempotency_score"] == 1.0


def test_wikidata_world_model_lane_summary_cli(tmp_path, capsys, monkeypatch) -> None:
    root = Path(__file__).resolve().parent

    nat_runs = json.loads(
        (
            root
            / "fixtures"
            / "wikidata"
            / "wikidata_nat_cohort_a_gate_b_candidate_verification_runs_ready_20260403.json"
        ).read_text(encoding="utf-8")
    )
    nat_report = build_nat_claim_convergence_report(nat_runs)
    nat_path = tmp_path / "nat_report.json"
    nat_path.write_text(json.dumps(nat_report), encoding="utf-8")

    bundle, *_ = _prepare_au_fact_review_bundle_fixture(tmp_path / "au")
    au_report = build_au_fact_review_bundle_world_model_report(bundle)
    au_path = tmp_path / "au_report.json"
    au_path.write_text(json.dumps(au_report), encoding="utf-8")

    monkeypatch.setattr(
        "src.sources.uk_legislation.fetch_legislation_act_payload",
        lambda **_kwargs: {},
    )
    gwb_result = build_gwb_broader_review(tmp_path / "gwb")
    gwb_payload = json.loads(Path(gwb_result["artifact_path"]).read_text(encoding="utf-8"))
    gwb_report = build_gwb_broader_review_world_model_report(gwb_payload)
    gwb_path = tmp_path / "gwb_report.json"
    gwb_path.write_text(json.dumps(gwb_report), encoding="utf-8")

    monkeypatch.setattr(
        "SensibLaw.src.sources.national_archives.brexit_national_archives_lane.requests.get",
        lambda _url, **_kwargs: (_ for _ in ()).throw(RuntimeError("dialing blocked")),
    )
    brexit_report = build_brexit_national_archives_world_model_report(fetch_brexit_archive_records(limit=1))
    brexit_path = tmp_path / "brexit_report.json"
    brexit_path.write_text(json.dumps(brexit_report), encoding="utf-8")

    reviewer_packet = json.loads(
        (
            root
            / "fixtures"
            / "wikidata"
            / "wikidata_nat_cohort_b_operator_packet_20260402.json"
        ).read_text(encoding="utf-8")
    )
    reviewer_report = build_nat_cohort_b_operator_packet_world_model_report(reviewer_packet)
    reviewer_path = tmp_path / "reviewer_report.json"
    reviewer_path.write_text(json.dumps(reviewer_report), encoding="utf-8")

    out_path = tmp_path / "world_model_lane_summary.json"
    cli_main.main(
        [
            "wikidata",
            "world-model-lane-summary",
            "--input",
            str(nat_path),
            "--input",
            str(au_path),
            "--input",
            str(gwb_path),
            "--input",
            str(brexit_path),
            "--input",
            str(reviewer_path),
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert stdout["output"] == str(out_path)
    assert stdout["lane_count"] == 5
    assert stdout["ready_lane_count"] >= 2
    assert stdout["gate_decision"] == "hold"
    assert payload["summary"]["lane_count"] == 5
    assert payload["summary"]["total_claim_count"] >= 14
    assert payload["summary"]["total_must_review_count"] >= 10
    assert payload["summary"]["open_follow_conjectures"] > 10
    assert payload["summary"]["total_can_act_count"] == 2
    assert "business_family_reconciled_low_qualifier_checked_safe_subset" in payload["governance_gate"]["ready_lanes"]


def test_report_world_model_lane_summary_cli_alias(tmp_path, capsys, monkeypatch) -> None:
    root = Path(__file__).resolve().parent

    nat_runs = json.loads(
        (
            root
            / "fixtures"
            / "wikidata"
            / "wikidata_nat_cohort_a_gate_b_candidate_verification_runs_ready_20260403.json"
        ).read_text(encoding="utf-8")
    )
    nat_report = build_nat_claim_convergence_report(nat_runs)
    nat_path = tmp_path / "nat_report.json"
    nat_path.write_text(json.dumps(nat_report), encoding="utf-8")

    bundle, *_ = _prepare_au_fact_review_bundle_fixture(tmp_path / "au_alias")
    au_report = build_au_fact_review_bundle_world_model_report(bundle)
    au_path = tmp_path / "au_report.json"
    au_path.write_text(json.dumps(au_report), encoding="utf-8")

    monkeypatch.setattr(
        "src.sources.uk_legislation.fetch_legislation_act_payload",
        lambda **_kwargs: {},
    )
    gwb_result = build_gwb_broader_review(tmp_path / "gwb_alias")
    gwb_payload = json.loads(Path(gwb_result["artifact_path"]).read_text(encoding="utf-8"))
    gwb_report = build_gwb_broader_review_world_model_report(gwb_payload)
    gwb_path = tmp_path / "gwb_report.json"
    gwb_path.write_text(json.dumps(gwb_report), encoding="utf-8")

    monkeypatch.setattr(
        "SensibLaw.src.sources.national_archives.brexit_national_archives_lane.requests.get",
        lambda _url, **_kwargs: (_ for _ in ()).throw(RuntimeError("dialing blocked")),
    )
    brexit_report = build_brexit_national_archives_world_model_report(fetch_brexit_archive_records(limit=1))
    brexit_path = tmp_path / "brexit_report.json"
    brexit_path.write_text(json.dumps(brexit_report), encoding="utf-8")

    reviewer_packet = json.loads(
        (
            root
            / "fixtures"
            / "wikidata"
            / "wikidata_nat_cohort_b_operator_packet_20260402.json"
        ).read_text(encoding="utf-8")
    )
    reviewer_report = build_nat_cohort_b_operator_packet_world_model_report(reviewer_packet)
    reviewer_path = tmp_path / "reviewer_report.json"
    reviewer_path.write_text(json.dumps(reviewer_report), encoding="utf-8")

    out_path = tmp_path / "world_model_lane_summary_alias.json"
    cli_main.main(
        [
            "report",
            "world-model-lane-summary",
            "--input",
            str(nat_path),
            "--input",
            str(au_path),
            "--input",
            str(gwb_path),
            "--input",
            str(brexit_path),
            "--input",
            str(reviewer_path),
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert stdout["output"] == str(out_path)
    assert stdout["gate_decision"] == "hold"
    assert payload["summary"]["lane_count"] == 5
    assert payload["summary"]["total_claim_count"] >= 14
    assert payload["summary"]["open_follow_conjectures"] > 10
    assert payload["summary"]["total_can_act_count"] == 2


def test_wikidata_climate_review_demonstrator_cli(tmp_path, capsys) -> None:
    root = Path(__file__).resolve().parent.parent
    migration_pack_path = (
        root
        / "data"
        / "ontology"
        / "wikidata_migration_packs"
        / "p5991_p14143_climate_pilot_20260328"
        / "migration_pack.json"
    )
    climate_text_path = (
        root
        / "data"
        / "ontology"
        / "wikidata_migration_packs"
        / "p5991_p14143_climate_pilot_20260328"
        / "climate_text_source_q10403939_akademiska_hus_scope1_2018_2020.json"
    )
    review_packet_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_review_packet_20260401.json"
    )
    out_path = tmp_path / "climate_review_demonstrator.json"

    cli_main.main(
        [
            "wikidata",
            "climate-review-demonstrator",
            "--migration-pack",
            str(migration_pack_path),
            "--climate-text",
            str(climate_text_path),
            "--review-packet",
            str(review_packet_path),
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert stdout["output"] == str(out_path)
    assert stdout["entity_qid"] == "Q10403939"
    assert stdout["candidate_count"] == 24
    assert stdout["bridge_case_count"] == 24
    assert stdout["final_state"] == "held"
    assert payload["review_disposition"]["final_state"] == "held"
    assert payload["residual_completeness_surface"]["pressure_counts"] == {"split_pressure": 24}


def test_wikidata_nat_migration_execution_proof_cli(tmp_path, capsys) -> None:
    root = Path(__file__).resolve().parent
    in_path = (
        root
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_cohort_a_gate_b_candidate_verification_runs_ready_20260403.json"
    )
    out_path = tmp_path / "nat_migration_execution_proof.json"

    cli_main.main(
        [
            "wikidata",
            "nat-migration-execution-proof",
            "--input",
            str(in_path),
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert stdout["output"] == str(out_path)
    assert stdout["family_id"] == payload["family_id"]
    assert stdout["lifecycle_state"] == payload["summary"]["lifecycle_state"]
    assert payload["summary"]["lifecycle_state"] == "EXECUTED"
    assert payload["summary"]["candidate_count"] == 2


def test_wikidata_nat_migration_execution_proof_cli_accepts_external_receipts(tmp_path, capsys) -> None:
    root = Path(__file__).resolve().parent
    verification_runs_path = (
        root
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_cohort_a_gate_b_candidate_verification_runs_ready_20260403.json"
    )
    executed_rows_path = (
        root
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_business_family_migration_executed_rows_20260404.json"
    )
    post_execution_batches_path = verification_runs_path
    out_path = tmp_path / "nat_migration_execution_proof_external.json"

    cli_main.main(
        [
            "wikidata",
            "nat-migration-execution-proof",
            "--input",
            str(verification_runs_path),
            "--executed-rows",
            str(executed_rows_path),
            "--post-execution-batches",
            str(post_execution_batches_path),
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert stdout["output"] == str(out_path)
    assert payload["summary"]["execution_status"] == "external_execution_receipts"
    assert payload["summary"]["lifecycle_state"] == "VERIFIED"
    assert payload["executed_rows_report"]["summary"]["row_count"] == 2


def test_wikidata_automation_graduation_evidence_report_cli_writes_readiness_surface(tmp_path, capsys) -> None:
    root = Path(__file__).resolve().parent
    criteria_path = (
        root / "fixtures" / "wikidata" / "wikidata_nat_automation_graduation_criteria_20260402.json"
    )
    proposal_batches_path = (
        root
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_automation_promotion_proposal_batches_20260402.json"
    )
    out_path = tmp_path / "automation_graduation_evidence_report.json"

    cli_main.main(
        [
            "wikidata",
            "automation-graduation-evidence-report",
            "--criteria",
            str(criteria_path),
            "--proposal-batches",
            str(proposal_batches_path),
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert stdout["output"] == str(out_path)
    assert stdout["evidence_batch_id"] == "nat-grad-evidence-v1"
    assert stdout["status"] == "not_ready"
    assert stdout["decision"] == "hold"
    assert stdout["promotion_ready"] is False
    assert stdout["summary"]["rejected_count"] == 2
    assert payload["status"] == "not_ready"
    assert "rejected_proposals_present" in payload["readiness_failed_reasons"]
    assert "fail_closed_proposals_present" in payload["readiness_failed_reasons"]


def test_wikidata_automation_graduation_governance_index_cli_writes_snapshot_summary(tmp_path, capsys) -> None:
    root = Path(__file__).resolve().parent
    criteria_path = (
        root / "fixtures" / "wikidata" / "wikidata_nat_automation_graduation_criteria_20260402.json"
    )
    evidence_snapshots_path = (
        root
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_automation_evidence_snapshots_20260402.json"
    )
    out_path = tmp_path / "automation_graduation_governance_index.json"

    cli_main.main(
        [
            "wikidata",
            "automation-graduation-governance-index",
            "--criteria",
            str(criteria_path),
            "--evidence-snapshots",
            str(evidence_snapshots_path),
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert stdout["output"] == str(out_path)
    assert stdout["governance_batch_id"] == "nat-grad-governance-v1"
    assert stdout["status"] == "not_ready"
    assert stdout["decision"] == "hold"
    assert stdout["promotion_ready"] is False
    assert stdout["summary"]["ready_count"] == 0
    assert stdout["summary"]["not_ready_count"] == 2
    assert payload["status"] == "not_ready"
    assert "not_ready_snapshots_present" in payload["readiness_failed_reasons"]


def test_wikidata_automation_graduation_governance_summary_cli_writes_repeated_index_summary(
    tmp_path, capsys
) -> None:
    root = Path(__file__).resolve().parent
    criteria_path = (
        root / "fixtures" / "wikidata" / "wikidata_nat_automation_graduation_criteria_20260402.json"
    )
    governance_snapshots_path = (
        root
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_automation_governance_snapshots_20260402.json"
    )
    out_path = tmp_path / "automation_graduation_governance_summary.json"

    cli_main.main(
        [
            "wikidata",
            "automation-graduation-governance-summary",
            "--criteria",
            str(criteria_path),
            "--governance-snapshots",
            str(governance_snapshots_path),
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert stdout["output"] == str(out_path)
    assert stdout["governance_summary_id"] == "nat-grad-governance-summary-v1"
    assert stdout["status"] == "not_ready"
    assert stdout["decision"] == "hold"
    assert stdout["promotion_ready"] is False
    assert stdout["summary"]["ready_count"] == 0
    assert stdout["summary"]["not_ready_count"] == 2
    assert payload["status"] == "not_ready"
    assert "not_ready_governance_indexes_present" in payload["readiness_failed_reasons"]
