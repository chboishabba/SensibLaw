from __future__ import annotations

from pathlib import Path

from src.pnf.demands import derive_resolution_demands
from src.pnf.graph import PNFGraph
from src.policy.algebra import Factor


ROOT = Path(__file__).resolve().parents[1]


def _factor(
    *,
    factor_type: str,
    role_bindings: dict[str, str],
    provenance_refs: tuple[str, ...],
    residuals: tuple[str, ...],
) -> Factor[object]:
    return Factor(
        factor_ref=f"factor:{factor_type}",
        factor_type=factor_type,
        residuals=residuals,
        closure_state="requires_external_resolution",
        metadata={
            "role_bindings": role_bindings,
            "provenance_refs": provenance_refs,
            "composition_contract_ref": "grammar:semantic:operator-composition:v0_1",
        },
    )


def test_transition_demand_carries_distinct_trigger_and_target() -> None:
    graph = PNFGraph(
        graph_ref="graph:test",
        document_ref="document:test",
        factors=(
            _factor(
                factor_type="semantic.legal_transition",
                role_bindings={
                    "transition": "parser-token:repeal",
                    "legal_object": "parser-token:act",
                },
                provenance_refs=("parser-token:repeal",),
                residuals=(
                    "legal_object_identity_unresolved",
                    "effective_time_unresolved",
                ),
            ),
        ),
    )

    (demand,) = derive_resolution_demands(graph)
    provenance = demand["occurrence_provenance"]
    legal_object_rows = [
        row
        for row in provenance
        if row["residual_type"] == "legal_object_identity_unresolved"
    ]
    assert any(
        row["occurrence_role"] == "trigger"
        and row["parser_token_ref"] == "parser-token:repeal"
        for row in legal_object_rows
    )
    assert any(
        row["occurrence_role"] == "target"
        and row["parser_token_ref"] == "parser-token:act"
        for row in legal_object_rows
    )
    effective_time_rows = [
        row for row in provenance if row["residual_type"] == "effective_time_unresolved"
    ]
    assert any(row["occurrence_role"] == "trigger" for row in effective_time_rows)
    assert not any(row["occurrence_role"] == "target" for row in effective_time_rows)


def test_missing_typed_target_role_stays_targetless() -> None:
    graph = PNFGraph(
        graph_ref="graph:test",
        document_ref="document:test",
        factors=(
            _factor(
                factor_type="semantic.normative_relation",
                role_bindings={"conduct": "parser-token:believed"},
                provenance_refs=("parser-token:may", "parser-token:believed"),
                residuals=("norm_bearer_unresolved", "jurisdiction_unresolved"),
            ),
        ),
    )

    (demand,) = derive_resolution_demands(graph)
    provenance = demand["occurrence_provenance"]
    assert any(
        row["occurrence_role"] == "trigger"
        and row["parser_token_ref"] == "parser-token:believed"
        for row in provenance
    )
    assert not any(row["occurrence_role"] == "target" for row in provenance)


def test_condition_attachment_uses_typed_host_not_nearby_evidence() -> None:
    graph = PNFGraph(
        graph_ref="graph:test",
        document_ref="document:test",
        factors=(
            _factor(
                factor_type="semantic.legal_condition",
                role_bindings={
                    "condition": "parser-token:applies",
                    "host": "parser-token:provision",
                },
                provenance_refs=("parser-token:if", "parser-token:applies"),
                residuals=("condition_attachment_unresolved",),
            ),
        ),
    )

    (demand,) = derive_resolution_demands(graph)
    provenance = demand["occurrence_provenance"]
    assert any(
        row["occurrence_role"] == "target"
        and row["semantic_role"] == "host"
        and row["parser_token_ref"] == "parser-token:provision"
        for row in provenance
    )
    assert not any(
        row["occurrence_role"] == "target"
        and row["parser_token_ref"] == "parser-token:if"
        for row in provenance
    )


def test_persistence_projects_only_exact_coordinate_provenance() -> None:
    store_source = (ROOT / "src/storage/postgres/demand_occurrence_store.py").read_text(
        encoding="utf-8"
    )
    semantic_source = (ROOT / "src/storage/postgres/semantic_store.py").read_text(
        encoding="utf-8"
    )
    migration = (
        ROOT
        / "database/postgres_migrations/137_operational_demand_occurrence_projection.sql"
    ).read_text(encoding="utf-8")

    assert "numeric_parser_token_coordinate_map" in semantic_source
    assert "persist_resolution_demand_occurrences" in semantic_source
    assert ".casefold(" not in store_source
    assert "symbol_text" not in store_source
    assert "start_char" in migration and "end_char" in migration
    assert "candidate_count<>1" in migration
    assert "object_count<>1" in migration
    assert "register_numeric_pnf_demand_occurrence" in migration
    assert "nearest-noun" in migration
    assert "LIKE 'operational-demand:%'" in migration


def test_pre_provenance_completed_builds_are_not_reused() -> None:
    source = (ROOT / "src/storage/postgres/operational_build_store.py").read_text(
        encoding="utf-8"
    )
    assert '_OPERATION_VERSION = "v0_9"' in source
    assert "build.operation_version = %s" in source
