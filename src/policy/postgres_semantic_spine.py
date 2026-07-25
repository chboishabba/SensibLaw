"""One active semantic flow: compile -> PNF lifecycle -> Domain IR -> follow rows.

This module is the runtime authority for AU/GWB/general profiles. Lane wrappers
provide profile configuration only. SQLite and nested JSON follow graphs are
not accepted as runtime semantic inputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable, Mapping

from src.pnf.pronominal_argument_projection import attach_parser_pronominal_arguments
from src.pnf.reference_binding import project_pronominal_reference_arguments
from src.pnf.semantic_lifecycle_spine import validate_projection_demand_factor_closure
from src.policy.follow_projection_builder import build_follow_projection_from_canonical_rows
from src.storage.postgres.follow_projection_store import (
    FollowProjectionQueryResult,
    persist_follow_projection,
    query_follow_projection,
)

POSTGRES_SEMANTIC_SPINE_CONTRACT = "postgres-semantic-spine:v0_8"


@dataclass(frozen=True)
class SemanticSpineProfile:
    profile_ref: str
    projection_kind: str
    relation_families: tuple[str, ...] = ()
    required_zelph_predicates: tuple[str, ...] = ()


@dataclass(frozen=True)
class SemanticSpineReceipt:
    document_ref: str
    profile_ref: str
    compiler_seconds: float
    reference_projection_seconds: float
    follow_build_seconds: float
    follow_persistence_seconds: float
    follow_query_seconds: float
    projection_ref: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_ref": self.document_ref,
            "profile_ref": self.profile_ref,
            "compiler_seconds": self.compiler_seconds,
            "reference_projection_seconds": self.reference_projection_seconds,
            "follow_build_seconds": self.follow_build_seconds,
            "follow_persistence_seconds": self.follow_persistence_seconds,
            "follow_query_seconds": self.follow_query_seconds,
            "projection_ref": self.projection_ref,
            "contract": POSTGRES_SEMANTIC_SPINE_CONTRACT,
            "postgresql_semantic_authority": True,
            "sqlite_runtime_authority": False,
            "json_presentation_only": True,
            "single_spine": True,
        }


@dataclass(frozen=True)
class SemanticSpineResult:
    artifacts: Mapping[str, Any]
    follow_projection: FollowProjectionQueryResult
    receipt: SemanticSpineReceipt

    def presentation_payload(self) -> dict[str, Any]:
        return {
            "follow_projection": self.follow_projection.presentation_payload(),
            "runtime_receipt": self.receipt.to_dict(),
            "presentation_only": True,
            "semantic_input_allowed": False,
        }


def _artifact_rows(
    artifacts: Mapping[str, Any], key: str
) -> tuple[Mapping[str, Any], ...]:
    return tuple(row for row in artifacts.get(key) or () if isinstance(row, Mapping))


def run_postgres_semantic_spine(
    *,
    connection: Any,
    document_input: Mapping[str, Any],
    compile_document: Callable[[Mapping[str, Any]], Mapping[str, Any]],
    profile: SemanticSpineProfile,
) -> SemanticSpineResult:
    if document_input.get("sqlite_path") or document_input.get("db_path"):
        raise ValueError("SQLite is import/replay only and cannot drive semantic runtime")

    compile_started = perf_counter()
    compilation = compile_document(document_input)
    artifacts = dict(compilation.get("artifacts") or compilation)
    compiler_seconds = perf_counter() - compile_started

    reference_started = perf_counter()
    artifacts = attach_parser_pronominal_arguments(artifacts)
    artifacts = project_pronominal_reference_arguments(artifacts)
    reference_seconds = perf_counter() - reference_started

    graph = artifacts.get("refined_pnf_graph") or artifacts.get("pnf_graph") or {}
    factors = tuple(
        row for row in graph.get("factors") or () if isinstance(row, Mapping)
    )
    durable_factor_refs = {str(row.get("factor_ref") or "") for row in factors}
    demands = tuple(
        row
        for row in (
            artifacts.get("projection_demands")
            or artifacts.get("resolution_demands")
            or ()
        )
        if isinstance(row, Mapping)
    )
    projection_demands = tuple(
        row
        for row in demands
        if row.get("domain")
        or row.get("source_resolution_ref")
        or row.get("resolution_ref")
    )
    validate_projection_demand_factor_closure(
        demands=projection_demands,
        durable_factor_refs=durable_factor_refs,
    )

    build_started = perf_counter()
    projection = build_follow_projection_from_canonical_rows(
        document_ref=str(
            graph.get("document_ref") or document_input.get("document_ref") or ""
        ),
        profile_ref=profile.profile_ref,
        scope_ref=str(
            document_input.get("scope_ref")
            or graph.get("document_ref")
            or "document"
        ),
        projection_kind=profile.projection_kind,
        factors=factors,
        resolutions=_artifact_rows(artifacts, "semantic_resolution_receipts"),
        domain_ir=_artifact_rows(artifacts, "domain_ir_projections"),
        relation_families=profile.relation_families,
        source_graph_ref=str(graph.get("graph_ref") or "") or None,
    )
    follow_build_seconds = perf_counter() - build_started

    persistence_started = perf_counter()
    with connection.cursor() as cursor:
        projection_ref = persist_follow_projection(cursor, projection)
    connection.commit()
    follow_persistence_seconds = perf_counter() - persistence_started

    query_started = perf_counter()
    with connection.cursor() as cursor:
        queried = query_follow_projection(cursor, projection_ref)
    follow_query_seconds = perf_counter() - query_started

    artifacts["postgres_semantic_spine_contract"] = POSTGRES_SEMANTIC_SPINE_CONTRACT
    artifacts["follow_projection_ref"] = projection_ref
    artifacts["follow_projection_is_relational"] = True
    artifacts["legacy_json_follow_graph_semantic_input"] = False
    artifacts["sqlite_runtime_authority"] = False
    artifacts["semantic_compiler_contract"] = POSTGRES_SEMANTIC_SPINE_CONTRACT
    return SemanticSpineResult(
        artifacts=artifacts,
        follow_projection=queried,
        receipt=SemanticSpineReceipt(
            document_ref=projection.document_ref,
            profile_ref=profile.profile_ref,
            compiler_seconds=compiler_seconds,
            reference_projection_seconds=reference_seconds,
            follow_build_seconds=follow_build_seconds,
            follow_persistence_seconds=follow_persistence_seconds,
            follow_query_seconds=follow_query_seconds,
            projection_ref=projection_ref,
        ),
    )


AU_FACT_REVIEW_PROFILE = SemanticSpineProfile(
    profile_ref="profile:au-fact-review-postgres:v0_1",
    projection_kind="legal",
    relation_families=("applies", "supports", "refines", "cites", "follows"),
    required_zelph_predicates=("au_procedural_fact",),
)
GWB_REVIEW_PROFILE = SemanticSpineProfile(
    profile_ref="profile:gwb-review-postgres:v0_1",
    projection_kind="nonlegal",
    relation_families=("references", "binds", "supports", "contradicts", "precedes"),
)


__all__ = [
    "AU_FACT_REVIEW_PROFILE",
    "GWB_REVIEW_PROFILE",
    "POSTGRES_SEMANTIC_SPINE_CONTRACT",
    "SemanticSpineProfile",
    "SemanticSpineReceipt",
    "SemanticSpineResult",
    "run_postgres_semantic_spine",
]
