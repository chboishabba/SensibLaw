from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.materialize_wikidata_migration_pack import (
    _discover_company_direct_statement_rows,
    _fetch_recent_revision_map,
    _filter_export_to_discovery_rows,
    _discover_qid_rows,
    _load_qids_from_file,
    _read_valid_export,
    _reconcile_discovery_row,
    _resolve_qid_rows,
)
from src.ontology.wikidata import (
    build_wikidata_migration_pack,
    build_wikidata_split_plan,
)
from src.policy.compiler_contract import build_wikidata_migration_pack_contract
from src.policy.product_gate import build_product_gate
from src.policy.statement_family_context import build_statement_family_context


def test_load_qids_from_file_supports_text_lines(tmp_path: Path) -> None:
    path = tmp_path / "qids.txt"
    path.write_text("Q1\n# comment\nQ2, Q3\n", encoding="utf-8")

    assert _load_qids_from_file(path) == ["Q1", "Q2", "Q3"]


def test_load_qids_from_file_supports_json_array(tmp_path: Path) -> None:
    path = tmp_path / "qids.json"
    path.write_text(json.dumps(["Q1", "Q2"]), encoding="utf-8")

    assert _load_qids_from_file(path) == ["Q1", "Q2"]


def test_fetch_recent_revision_map_pins_each_title_independently(monkeypatch) -> None:
    calls: list[str] = []

    def fake_recent(qid, **kwargs):
        calls.append(qid)
        return [{"revid": 10, "timestamp": "2026-07-17T00:00:00Z"}]

    monkeypatch.setattr(
        "scripts.materialize_wikidata_migration_pack._fetch_recent_revisions",
        fake_recent,
    )
    result = _fetch_recent_revision_map(
        ("Q1", "Q2"), revision_limit=2, timeout_seconds=30
    )

    assert calls == ["Q1", "Q2"]
    assert result["Q1"][0]["revid"] == 10


def test_read_valid_export_rejects_wrong_revision_and_corrupt_json(
    tmp_path: Path,
) -> None:
    export = tmp_path / "q1_t2_10.json"
    export.write_text('{"_source_qid": "Q1", "_source_revision": 10}', encoding="utf-8")
    assert _read_valid_export(export, qid="Q1", revid=10) is not None
    assert _read_valid_export(export, qid="Q1", revid=11) is None
    export.write_text("not json", encoding="utf-8")
    assert _read_valid_export(export, qid="Q1", revid=10) is None


def test_resolve_qid_rows_merges_explicit_file_and_discovered(
    monkeypatch, tmp_path: Path
) -> None:
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


def test_company_direct_discovery_preserves_statement_guids_and_direct_types(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "scripts.materialize_wikidata_migration_pack._fetch_json",
        lambda *args, **kwargs: {
            "results": {
                "bindings": [
                    {
                        "item": {"value": "http://www.wikidata.org/entity/Q10"},
                        "statement": {
                            "value": "http://www.wikidata.org/entity/statement/Q10-abc"
                        },
                        "rank": {"value": "http://wikiba.se/ontology#NormalRank"},
                        "type": {"value": "http://www.wikidata.org/entity/Q783794"},
                    },
                    {
                        "item": {"value": "http://www.wikidata.org/entity/Q10"},
                        "statement": {
                            "value": "http://www.wikidata.org/entity/statement/Q10-abc"
                        },
                        "rank": {"value": "http://wikiba.se/ontology#NormalRank"},
                        "type": {"value": "http://www.wikidata.org/entity/Q4830453"},
                    },
                ]
            }
        },
    )

    rows, metadata = _discover_company_direct_statement_rows(
        source_property="P5991",
        target_property="P14143",
        page_size=5,
        cursor_qid="Q9",
        timeout_seconds=30,
    )

    assert rows == [
        {
            "subject_qid": "Q10",
            "statement_id": "Q10$abc",
            "rank": "normal",
            "direct_p31": ["Q4830453", "Q783794"],
            "target_property_present_at_discovery": False,
            "stratum": "company_direct",
        }
    ]
    assert metadata["cursor_qid"] == "Q9"
    assert metadata["next_cursor"] == {
        "subject_qid": "Q10",
        "statement_id": "Q10$abc",
    }
    assert metadata["ordering"] == "subject_qid ASC, statement_id ASC"
    assert "FILTER NOT EXISTS" in str(metadata["query"])


def test_company_direct_discovery_uses_composite_statement_cursor(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_fetch(*args, **kwargs):
        captured.update(kwargs.get("params") or {})
        return {"results": {"bindings": []}}

    monkeypatch.setattr(
        "scripts.materialize_wikidata_migration_pack._fetch_json", fake_fetch
    )
    _discover_company_direct_statement_rows(
        source_property="P5991",
        target_property="P14143",
        page_size=5,
        cursor_qid="Q10",
        cursor_statement="Q10$abc",
        timeout_seconds=30,
    )

    query = str(captured["query"])
    assert 'STR(?item) = "http://www.wikidata.org/entity/Q10"' in query
    assert (
        'STR(?statement) > "http://www.wikidata.org/entity/statement/Q10-abc"' in query
    )
    assert "GROUP BY ?item ?statement ?rank" in query


def test_discovery_reconciliation_preserves_complete_source_family_context() -> None:
    row = {
        "subject_qid": "Q10",
        "statement_id": "Q10$abc",
        "rank": "normal",
        "direct_p31": ["Q783794"],
        "target_property_present_at_discovery": False,
        "stratum": "company_direct",
    }
    export = {
        "_source_revision": 123,
        "entities": {
            "Q10": {
                "claims": {
                    "P5991": [{"id": "Q10$abc"}, {"id": "Q10$other"}],
                    "P31": [{"id": "Q10$type"}],
                    "P14143": [],
                }
            }
        },
    }

    reconciled = _reconcile_discovery_row(
        row,
        export,
        source_property="P5991",
        target_property="P14143",
    )

    assert reconciled["reconciliation_status"] == "statement_reconciled"
    assert reconciled["entity_revision"] == 123
    filtered = _filter_export_to_discovery_rows(
        export,
        [reconciled],
        source_property="P5991",
    )
    assert [
        claim["id"] for claim in filtered["entities"]["Q10"]["claims"]["P5991"]
    ] == ["Q10$abc", "Q10$other"]
    assert (
        export["entities"]["Q10"]["claims"]["P5991"]
        == filtered["entities"]["Q10"]["claims"]["P5991"]
    )


def test_migration_pack_preserves_source_statement_identifier() -> None:
    payload = {
        "windows": [
            {
                "id": "current",
                "statement_bundles": [
                    {
                        "subject": "Q1",
                        "property": "P5991",
                        "statement_id": "Q1$abc",
                        "value": "+100",
                        "rank": "normal",
                        "qualifiers": {},
                        "references": [],
                    }
                ],
            }
        ]
    }

    pack = build_wikidata_migration_pack(
        payload,
        source_property="P5991",
        target_property="P14143",
    )

    candidate = pack["candidates"][0]
    assert candidate["source_statement_id"] == "Q1$abc"
    assert candidate["claim_bundle_before"]["statement_id"] == "Q1$abc"


def test_parse_args_accepts_optional_openrefine_csv(
    monkeypatch, tmp_path: Path
) -> None:
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


def test_parse_args_accepts_optional_climate_text_source(
    monkeypatch, tmp_path: Path
) -> None:
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


def test_materializer_writes_climate_observation_claim_and_enriched_pack(
    monkeypatch, tmp_path: Path
) -> None:
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
        lambda qid, revid, **kwargs: {
            "id": qid,
            "entities": {qid: {"id": qid}},
            "_stub": revid,
        },
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

    migration_pack = json.loads(
        (out_dir / "migration_pack.json").read_text(encoding="utf-8")
    )
    observation_claim = json.loads(
        (out_dir / "climate_observation_claim.json").read_text(encoding="utf-8")
    )
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))

    assert migration_pack["candidates"][0]["pressure"] == "split_pressure"
    assert migration_pack["compiler_contract"]["lane"] == "wikidata_nat"
    assert (
        migration_pack["compiler_contract"]["evidence_bundle"]["bundle_kind"]
        == "revision_text_evidence_bundle"
    )
    assert migration_pack["promotion_gate"]["decision"] in {
        "promote",
        "audit",
        "abstain",
    }
    assert migration_pack["promotion_gate"]["product_ref"] == "wikidata_migration_pack"
    assert migration_pack["pilot_metrics"]["candidate_count"] == 1
    assert migration_pack["readiness_surface"]["state"] == "review_first"
    assert "pilot_metrics" not in migration_pack["compiler_contract"]
    assert "readiness_surface" not in migration_pack["compiler_contract"]
    assert "pilot_metrics" not in migration_pack["promotion_gate"]
    assert "readiness_surface" not in migration_pack["promotion_gate"]
    assert migration_pack["candidates"][0]["promotion_class"] == "review_only"
    assert migration_pack["candidates"][0]["promotion_eligibility"]["eligible"] is False
    assert (
        migration_pack["candidates"][0]["promotion_gate"]["decision"] == "review_only"
    )
    assert len(migration_pack["bridge_cases"]) == 1
    assert len(observation_claim["observations"]) == 2
    assert manifest["climate_text_source"] == str(climate_text_source)
    assert manifest["climate_observation_claim"] == str(
        out_dir / "climate_observation_claim.json"
    )


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
    assessment = candidate["domain_pressure_assessment"]
    assert (
        assessment["domain_invariant_ref"]
        == "wikidata:climate_ghg_p5991_to_p14143:v0_1"
    )
    assert assessment["review_disposition"] == "C"
    assert assessment["authority"] == "diagnostic_only"
    assert assessment["promotion_effect"] == "not_evaluated"
    assert {row["residual_kind"] for row in assessment["residuals"]} == {
        "target_model",
        "subject_type",
        "qualifier_structure",
        "reference_structure",
        "temporal_structure",
        "split_structure",
        "peer_cohort",
    }
    assert (
        next(
            row
            for row in assessment["residuals"]
            if row["residual_kind"] == "peer_cohort"
        )["state"]
        == "unresolved"
    )
    assert candidate["subject_family"] == "unknown"
    assert candidate["subject_resolution"]["status"] == "unresolved"
    assert candidate["subject_resolution"]["resolution_basis"] == "no_typed_evidence"
    assert (
        candidate["family_classifier"]["subject_resolution"]["subject_family"]
        == "unknown"
    )
    assert candidate["promotion_eligibility"]["instance_of_allowed"] is False
    assert candidate["ghg_semantic_family"] == "scope_specific_emissions"
    assert candidate["reporting_period_kind"] == "single_reporting_period"
    assert candidate["scope_resolution"] == "explicit_scope"
    assert candidate["method_resolution"] == "recognized_method"
    assert candidate["phase2_actions"] == []
    assert candidate["normalization_contract"]["phase2_eligible"] is True
    assert migration_pack["summary"]["family_summary"]["C"] == 1
    assert migration_pack[
        "compiler_contract"
    ] == build_wikidata_migration_pack_contract(migration_pack)
    assert migration_pack["promotion_gate"] == build_product_gate(
        lane="wikidata_nat",
        product_ref="wikidata_migration_pack",
        compiler_contract=migration_pack["compiler_contract"],
    )


def test_separate_scoped_claims_do_not_create_a_split_plan() -> None:
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

    assert (
        migration_pack["candidates"][0]["classification"]
        == "safe_with_reference_transfer"
    )
    assert migration_pack["candidates"][0]["pressure"] == "reinforce"
    assert migration_pack["candidates"][0]["pressure_summary"].startswith("model_safe;")
    assert migration_pack["candidates"][0]["family_bucket"] == "C"
    assert (
        migration_pack["candidates"][0]["family_classifier"]["bucket_label"]
        == "phase2_normalizable"
    )
    assert (
        migration_pack["candidates"][0]["promotion_eligibility"]["instance_of_allowed"]
        is False
    )
    assert migration_pack["summary"]["family_summary"]["C"] == 2
    assert split_plan["plans"] == []


def test_q101416961_style_components_and_total_are_preserved_not_split() -> None:
    def claim(statement_id: str, value: str, scope: str | None) -> dict[str, object]:
        qualifiers = {
            "P580": ["+2024-01-01T00:00:00Z"],
            "P582": ["+2024-12-31T00:00:00Z"],
            "P459": ["Q56296245"],
        }
        if scope:
            qualifiers["P3831"] = [scope]
        return {
            "subject": "Q101416961",
            "property": "P5991",
            "statement_id": statement_id,
            "value": value,
            "rank": "preferred",
            "unit": "http://www.wikidata.org/entity/Q57084755",
            "qualifiers": qualifiers,
            "references": [{"P854": ["https://example.org/report.pdf"]}],
        }

    payload = {
        "windows": [
            {
                "id": "pinned-2419927005",
                "statement_bundles": [
                    claim("Q101416961$component-a", "+394", "Q124883301"),
                    claim("Q101416961$component-b", "+66755", "Q124883309"),
                    claim("Q101416961$component-c", "+4024", "Q124883250"),
                    claim("Q101416961$total", "+71173", None),
                    {
                        "subject": "Q101416961",
                        "property": "P31",
                        "value": "Q783794",
                        "rank": "normal",
                        "qualifiers": {},
                        "references": [],
                    },
                ],
            }
        ]
    }

    pack = build_wikidata_migration_pack(
        payload,
        source_property="P5991",
        target_property="P14143",
        selected_statement_ids={
            "Q101416961$component-a",
            "Q101416961$component-b",
            "Q101416961$component-c",
        },
    )

    assert len(pack["candidates"]) == 3
    for candidate in pack["candidates"]:
        context = candidate["statement_family_context"]
        assert candidate["classification"] != "split_required"
        assert context["member_count"] == 4
        assert context["scope_partition_state"] == "already_partitioned"
        assert context["total_component_relation"] == "exact_reconciliation"
        assert context["split_requirement"] == "existing_partition_preserved"
        assert "time_range_requires_split" not in candidate["reasons"]
    assert build_wikidata_split_plan(pack)["plans"] == []


def test_statement_family_context_marks_overload_overlap_and_total_conflict() -> None:
    base = {"subject": "Q1", "property": "P1"}
    overloaded = build_statement_family_context(
        [
            {
                **base,
                "statement_id": "Q1$overloaded",
                "value": "+10",
                "qualifiers": {"Pscope": ["A", "B"]},
            }
        ],
        scope_properties=["Pscope"],
    )["Q1|P1"]
    overlap = build_statement_family_context(
        [
            {
                **base,
                "statement_id": "Q1$a",
                "value": "+10",
                "qualifiers": {"Pscope": ["A"]},
            },
            {
                **base,
                "statement_id": "Q1$b",
                "value": "+20",
                "qualifiers": {"Pscope": ["A"]},
            },
        ],
        scope_properties=["Pscope"],
    )["Q1|P1"]
    contradiction = build_statement_family_context(
        [
            {
                **base,
                "statement_id": "Q1$a",
                "value": "+10",
                "qualifiers": {"Pscope": ["A"]},
            },
            {
                **base,
                "statement_id": "Q1$b",
                "value": "+20",
                "qualifiers": {"Pscope": ["B"]},
            },
            {**base, "statement_id": "Q1$total", "value": "+40", "qualifiers": {}},
        ],
        scope_properties=["Pscope"],
    )["Q1|P1"]

    assert overloaded["split_requirement"] == "new_split_required"
    assert overlap["scope_partition_state"] == "overlapping"
    assert overlap["split_requirement"] == "manual_reconstruction"
    assert contradiction["total_component_relation"] == "contradiction"
    assert contradiction["split_requirement"] == "manual_reconstruction"


def test_build_wikidata_migration_pack_resolves_company_subject_family_from_typed_evidence() -> (
    None
):
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
    assessment = candidate["domain_pressure_assessment"]
    assert assessment["review_disposition"] == "A"
    assert (
        next(
            row
            for row in assessment["residuals"]
            if row["residual_kind"] == "target_model"
        )["state"]
        == "exact"
    )
    assert (
        next(
            row
            for row in assessment["residuals"]
            if row["residual_kind"] == "subject_type"
        )["state"]
        == "exact"
    )
    assert candidate["promotion_eligibility"]["instance_of_allowed"] is True
    assert candidate["promotion_class"] == "review_only"


def test_build_wikidata_migration_pack_resolves_non_company_subject_family_from_typed_evidence() -> (
    None
):
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


def test_build_wikidata_migration_pack_keeps_unknown_when_typed_evidence_is_not_mapped() -> (
    None
):
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
    assert (
        candidate["subject_resolution"]["resolution_basis"]
        == "typed_evidence_not_mapped"
    )
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
