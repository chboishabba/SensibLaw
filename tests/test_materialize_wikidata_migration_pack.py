from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.materialize_wikidata_migration_pack import (
    _discover_qid_rows,
    _load_qids_from_file,
    _resolve_qid_rows,
)
from src.ontology.wikidata import build_wikidata_migration_pack, build_wikidata_split_plan


def test_load_qids_from_file_supports_text_lines(tmp_path: Path) -> None:
    path = tmp_path / "qids.txt"
    path.write_text("Q1\n# comment\nQ2, Q3\n", encoding="utf-8")

    assert _load_qids_from_file(path) == ["Q1", "Q2", "Q3"]


def test_load_qids_from_file_supports_json_array(tmp_path: Path) -> None:
    path = tmp_path / "qids.json"
    path.write_text(json.dumps(["Q1", "Q2"]), encoding="utf-8")

    assert _load_qids_from_file(path) == ["Q1", "Q2"]


def test_resolve_qid_rows_merges_explicit_file_and_discovered(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "qids.txt"
    path.write_text("Q2\nQ3\n", encoding="utf-8")

    monkeypatch.setattr(
        "scripts.materialize_wikidata_migration_pack._discover_qid_rows",
        lambda **_: [
            {"qid": "Q3", "label": "Q3", "source": "discovered"},
            {"qid": "Q4", "label": "Item 4", "source": "discovered"},
        ],
    )

    args = argparse.Namespace(
        qid=["Q1", "Q2"],
        qid_file=path,
        discover_qids=True,
        source_property="P5991",
        candidate_limit=5,
        query_timeout=60,
    )

    assert _resolve_qid_rows(args) == [
        {"qid": "Q1", "label": "Q1", "source": "explicit"},
        {"qid": "Q2", "label": "Q2", "source": "explicit"},
        {"qid": "Q3", "label": "Q3", "source": "file"},
        {"qid": "Q4", "label": "Item 4", "source": "discovered"},
    ]


def test_discover_qid_rows_parses_sparql_bindings(monkeypatch) -> None:
    monkeypatch.setattr(
        "scripts.materialize_wikidata_migration_pack._fetch_json",
        lambda *args, **kwargs: {
            "results": {
                "bindings": [
                    {
                        "item": {"value": "http://www.wikidata.org/entity/Q10"},
                        "itemLabel": {"value": "Thing 10"},
                        "statementCount": {"value": "2"},
                        "qualifierCount": {"value": "4"},
                    }
                ]
            }
        },
    )

    assert _discover_qid_rows(
        source_property="P5991",
        candidate_limit=5,
        timeout_seconds=30,
    ) == [
        {
            "qid": "Q10",
            "label": "Thing 10",
            "statement_count": 2,
            "qualifier_count": 4,
            "source": "discovered",
        }
    ]


def test_parse_args_accepts_optional_openrefine_csv(monkeypatch, tmp_path: Path) -> None:
    out_dir = tmp_path / "pack"
    csv_path = tmp_path / "pack.csv"
    monkeypatch.setattr(
        "sys.argv",
        [
            "materialize_wikidata_migration_pack.py",
            "--qid",
            "Q1",
            "--source-property",
            "P5991",
            "--target-property",
            "P14143",
            "--out-dir",
            str(out_dir),
            "--openrefine-csv",
            str(csv_path),
        ],
    )
    from scripts.materialize_wikidata_migration_pack import _parse_args

    args = _parse_args()
    assert args.openrefine_csv == csv_path


def test_parse_args_accepts_optional_climate_text_source(monkeypatch, tmp_path: Path) -> None:
    out_dir = tmp_path / "pack"
    source_path = tmp_path / "climate_text.json"
    claim_out = tmp_path / "climate_observation_claim.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "materialize_wikidata_migration_pack.py",
            "--qid",
            "Q1",
            "--source-property",
            "P5991",
            "--target-property",
            "P14143",
            "--out-dir",
            str(out_dir),
            "--climate-text-source",
            str(source_path),
            "--climate-observation-claim-output",
            str(claim_out),
        ],
    )
    from scripts.materialize_wikidata_migration_pack import _parse_args

    args = _parse_args()
    assert args.climate_text_source == source_path
    assert args.climate_observation_claim_output == claim_out


def test_materializer_writes_climate_observation_claim_and_enriched_pack(monkeypatch, tmp_path: Path) -> None:
    from scripts import materialize_wikidata_migration_pack as script

    climate_text_source = tmp_path / "climate_text_source.json"
    climate_text_source.write_text(
        json.dumps(
            {
                "schema_version": "sl.wikidata.climate_text_source.v1",
                "sources": [
                    {
                        "source_id": "climate-src:1",
                        "entity_qid": "Q1",
                        "source_unit_id": "unit:q1:r1",
                        "revision_id": "123",
                        "revision_timestamp": "2026-03-28T00:00:00Z",
                        "text": "Carbon footprint 2018: 100 tCO2e\nCarbon footprint 2019: 100 tCO2e\n",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        script,
        "_resolve_qid_rows",
        lambda args: [{"qid": "Q1", "label": "Q1", "source": "explicit"}],
    )
    monkeypatch.setattr(
        script,
        "_fetch_recent_revisions",
        lambda qid, **kwargs: [
            {"revid": 200, "timestamp": "2026-03-28T00:00:00Z"},
            {"revid": 100, "timestamp": "2026-03-27T00:00:00Z"},
        ],
    )
    monkeypatch.setattr(
        script,
        "_fetch_entity_export",
        lambda qid, revid, **kwargs: {"id": qid, "entities": {qid: {"id": qid}}, "_stub": revid},
    )
    monkeypatch.setattr(
        script,
        "build_slice_from_entity_exports",
        lambda payloads, property_filter=None: {
            "windows": [
                {
                    "id": "t1_previous",
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
                    "id": "t2_current",
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
        },
    )

    out_dir = tmp_path / "out"
    monkeypatch.setattr(
        "sys.argv",
        [
            "materialize_wikidata_migration_pack.py",
            "--qid",
            "Q1",
            "--source-property",
            "P5991",
            "--target-property",
            "P14143",
            "--out-dir",
            str(out_dir),
            "--climate-text-source",
            str(climate_text_source),
        ],
    )

    script.main()

    migration_pack = json.loads((out_dir / "migration_pack.json").read_text(encoding="utf-8"))
    observation_claim = json.loads((out_dir / "climate_observation_claim.json").read_text(encoding="utf-8"))
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))

    assert migration_pack["candidates"][0]["pressure"] == "split_pressure"
    assert migration_pack["compiler_contract"]["lane"] == "wikidata_nat"
    assert migration_pack["compiler_contract"]["evidence_bundle"]["bundle_kind"] == "revision_text_evidence_bundle"
    assert migration_pack["promotion_gate"]["decision"] in {"promote", "audit", "abstain"}
    assert migration_pack["promotion_gate"]["product_ref"] == "wikidata_migration_pack"
    assert migration_pack["candidates"][0]["promotion_class"] == "review_only"
    assert migration_pack["candidates"][0]["promotion_eligibility"]["eligible"] is False
    assert migration_pack["candidates"][0]["promotion_gate"]["decision"] == "review_only"
    assert len(migration_pack["bridge_cases"]) == 1
    assert len(observation_claim["observations"]) == 2
    assert manifest["climate_text_source"] == str(climate_text_source)
    assert manifest["climate_observation_claim"] == str(out_dir / "climate_observation_claim.json")


def test_build_wikidata_migration_pack_marks_climate_direct_rows() -> None:
    payload = {
        "windows": [
            {
                "id": "t1",
                "statement_bundles": [
                    {
                        "subject": "Q1",
                        "property": "P5991",
                        "value": "+100",
                        "rank": "normal",
                        "unit": "http://www.wikidata.org/entity/Q57084901",
                        "qualifiers": {
                            "P585": ["+2023-00-00T00:00:00Z"],
                            "P459": ["Q56296245"],
                            "P3831": ["Q124946884"],
                        },
                        "references": [{"P854": ["https://example.org/report.pdf"]}],
                    }
                ],
            }
        ]
    }

    migration_pack = build_wikidata_migration_pack(
        payload,
        source_property="P5991",
        target_property="P14143",
    )

    candidate = migration_pack["candidates"][0]
    assert candidate["classification"] == "safe_with_reference_transfer"
    assert candidate["pressure"] == "reinforce"
    assert candidate["pressure_summary"].startswith("model_safe;")
    assert "model_safe" in candidate["reasons"]
    assert candidate["promotion_class"] == "review_only"
    assert candidate["promotion_eligibility"]["eligible"] is False
    assert candidate["promotion_gate"]["decision"] == "review_only"
    assert candidate["family_bucket"] == "C"
    assert candidate["family_classifier"]["bucket_label"] == "phase2_normalizable"
    assert candidate["subject_family"] == "unknown"
    assert candidate["subject_resolution"]["status"] == "unresolved"
    assert candidate["subject_resolution"]["resolution_basis"] == "no_typed_evidence"
    assert candidate["family_classifier"]["subject_resolution"]["subject_family"] == "unknown"
    assert candidate["promotion_eligibility"]["instance_of_allowed"] is False
    assert candidate["ghg_semantic_family"] == "scope_specific_emissions"
    assert candidate["reporting_period_kind"] == "single_reporting_period"
    assert candidate["scope_resolution"] == "explicit_scope"
    assert candidate["method_resolution"] == "recognized_method"
    assert candidate["phase2_actions"] == []
    assert candidate["normalization_contract"]["phase2_eligible"] is True
    assert migration_pack["summary"]["family_summary"]["C"] == 1


def test_build_wikidata_split_plan_emits_climate_model_axis() -> None:
    payload = {
        "windows": [
            {
                "id": "t1",
                "statement_bundles": [
                    {
                        "subject": "Q1",
                        "property": "P5991",
                        "value": "+100",
                        "rank": "normal",
                        "unit": "http://www.wikidata.org/entity/Q57084901",
                        "qualifiers": {
                            "P585": ["+2023-00-00T00:00:00Z"],
                            "P459": ["Q56296245"],
                            "P3831": ["Q124946884"],
                        },
                        "references": [{"P854": ["https://example.org/report.pdf"]}],
                    },
                    {
                        "subject": "Q1",
                        "property": "P5991",
                        "value": "+120",
                        "rank": "normal",
                        "unit": "http://www.wikidata.org/entity/Q57084901",
                        "qualifiers": {
                            "P585": ["+2023-00-00T00:00:00Z"],
                            "P459": ["Q56296245"],
                            "P3831": ["Q124946885"],
                        },
                        "references": [{"P854": ["https://example.org/report.pdf"]}],
                    },
                ],
            }
        ]
    }

    migration_pack = build_wikidata_migration_pack(
        payload,
        source_property="P5991",
        target_property="P14143",
    )
    split_plan = build_wikidata_split_plan(migration_pack)

    assert migration_pack["candidates"][0]["classification"] == "split_required"
    assert migration_pack["candidates"][0]["pressure"] == "split_pressure"
    assert migration_pack["candidates"][0]["pressure_summary"].startswith("model_safe_with_split;")
    assert migration_pack["candidates"][0]["family_bucket"] == "C"
    assert migration_pack["candidates"][0]["family_classifier"]["bucket_label"] == "phase2_normalizable"
    assert migration_pack["candidates"][0]["promotion_eligibility"]["instance_of_allowed"] is False
    assert migration_pack["summary"]["family_summary"]["C"] == 2
    assert split_plan["plans"][0]["status"] == "structurally_decomposable"
    assert any(axis["property"] == "__ghg_model__" for axis in split_plan["plans"][0]["merged_split_axes"])
    assert split_plan["plans"][0]["proposed_bundle_count"] == 2


def test_build_wikidata_migration_pack_resolves_company_subject_family_from_typed_evidence() -> None:
    payload = {
        "windows": [
            {
                "id": "t1",
                "statement_bundles": [
                    {
                        "subject": "Q1",
                        "property": "P5991",
                        "value": "+100",
                        "rank": "normal",
                        "unit": "http://www.wikidata.org/entity/Q57084901",
                        "qualifiers": {
                            "P585": ["+2023-00-00T00:00:00Z"],
                            "P459": ["Q56296245"],
                            "P3831": ["Q124946884"],
                        },
                        "references": [{"P854": ["https://example.org/report.pdf"]}],
                    },
                    {
                        "subject": "Q1",
                        "property": "P31",
                        "value": "Q6881511",
                        "rank": "normal",
                        "unit": None,
                        "qualifiers": {},
                        "references": [],
                    },
                ],
            }
        ]
    }

    migration_pack = build_wikidata_migration_pack(
        payload,
        source_property="P5991",
        target_property="P14143",
    )

    candidate = migration_pack["candidates"][0]
    assert candidate["subject_family"] == "company"
    assert candidate["subject_resolution"]["status"] == "resolved"
    assert candidate["subject_resolution"]["resolution_basis"] == "typed_evidence"
    assert candidate["subject_resolution"]["direct_instance_of"] == ["Q6881511"]
    assert candidate["subject_resolution"]["matched_type_qids"] == ["Q6881511"]
    assert candidate["family_bucket"] == "A"
    assert candidate["family_classifier"]["bucket_label"] == "clean_direct"
    assert candidate["promotion_eligibility"]["instance_of_allowed"] is True
    assert candidate["promotion_class"] == "review_only"


def test_build_wikidata_migration_pack_resolves_non_company_subject_family_from_typed_evidence() -> None:
    payload = {
        "windows": [
            {
                "id": "t1",
                "statement_bundles": [
                    {
                        "subject": "Q1",
                        "property": "P5991",
                        "value": "+100",
                        "rank": "normal",
                        "unit": "http://www.wikidata.org/entity/Q57084901",
                        "qualifiers": {
                            "P585": ["+2023-00-00T00:00:00Z"],
                            "P459": ["Q56296245"],
                            "P3831": ["Q124946884"],
                        },
                        "references": [{"P854": ["https://example.org/report.pdf"]}],
                    },
                    {
                        "subject": "Q1",
                        "property": "P31",
                        "value": "Q5",
                        "rank": "normal",
                        "unit": None,
                        "qualifiers": {},
                        "references": [],
                    },
                ],
            }
        ]
    }

    migration_pack = build_wikidata_migration_pack(
        payload,
        source_property="P5991",
        target_property="P14143",
    )

    candidate = migration_pack["candidates"][0]
    assert candidate["subject_family"] == "non_company"
    assert candidate["subject_resolution"]["status"] == "resolved"
    assert candidate["subject_resolution"]["matched_type_qids"] == ["Q5"]
    assert candidate["family_bucket"] == "C"
    assert candidate["promotion_eligibility"]["instance_of_allowed"] is False


def test_build_wikidata_migration_pack_keeps_unknown_when_typed_evidence_is_not_mapped() -> None:
    payload = {
        "windows": [
            {
                "id": "t1",
                "statement_bundles": [
                    {
                        "subject": "Q1",
                        "property": "P5991",
                        "value": "+100",
                        "rank": "normal",
                        "unit": "http://www.wikidata.org/entity/Q57084901",
                        "qualifiers": {
                            "P585": ["+2023-00-00T00:00:00Z"],
                            "P459": ["Q56296245"],
                            "P3831": ["Q124946884"],
                        },
                        "references": [{"P854": ["https://example.org/report.pdf"]}],
                    },
                    {
                        "subject": "Q1",
                        "property": "P31",
                        "value": "Q999999",
                        "rank": "normal",
                        "unit": None,
                        "qualifiers": {},
                        "references": [],
                    },
                    {
                        "subject": "Q999999",
                        "property": "P279",
                        "value": "Q888888",
                        "rank": "normal",
                        "unit": None,
                        "qualifiers": {},
                        "references": [],
                    },
                ],
            }
        ]
    }

    migration_pack = build_wikidata_migration_pack(
        payload,
        source_property="P5991",
        target_property="P14143",
    )

    candidate = migration_pack["candidates"][0]
    assert candidate["subject_family"] == "unknown"
    assert candidate["subject_resolution"]["status"] == "unresolved"
    assert candidate["subject_resolution"]["resolution_basis"] == "typed_evidence_not_mapped"
    assert candidate["subject_resolution"]["direct_instance_of"] == ["Q999999"]
    assert candidate["subject_resolution"]["traversed_subclass_of"] == [
        {"from_qid": "Q999999", "to_qid": "Q888888", "property": "P279"}
    ]
    assert candidate["family_bucket"] == "C"
    assert candidate["promotion_eligibility"]["instance_of_allowed"] is False


def test_build_wikidata_migration_pack_marks_phase2_normalizable_rows() -> None:
    payload = {
        "windows": [
            {
                "id": "t1",
                "statement_bundles": [
                    {
                        "subject": "Q1",
                        "property": "P5991",
                        "value": "+100",
                        "rank": "normal",
                        "unit": "http://www.wikidata.org/entity/Q57084901",
                        "qualifiers": {
                            "P585": ["+2023-00-00T00:00:00Z"],
                        },
                        "references": [{"P854": ["https://example.org/report.pdf"]}],
                    }
                ],
            }
        ]
    }

    migration_pack = build_wikidata_migration_pack(
        payload,
        source_property="P5991",
        target_property="P14143",
    )

    candidate = migration_pack["candidates"][0]
    assert candidate["family_bucket"] == "C"
    assert candidate["family_classifier"]["bucket_label"] == "phase2_normalizable"
    assert candidate["method_resolution"] == "missing_but_inferable"
    assert "infer_method" in candidate["phase2_actions"]
    assert candidate["normalization_contract"]["phase2_eligible"] is True
    assert candidate["phase2_method_inference"]["status"] == "pending"
    assert migration_pack["summary"]["family_summary"]["C"] == 1
