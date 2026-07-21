"""Versioned legal semantic build over PNF, Legal IR, and diagnostic witnesses.

The refined PNF graph remains the candidate semantic authority. Legal IR is a
materialized projection of that graph. Legacy extractor output is retained only
as diagnostic witness evidence. The comparison ledger is the sole alignment
surface and cannot promote a witness into PNF.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping, Sequence

from src.ontology.external_enrichment import canonical_sha256
from src.pnf.legal_adjunct import LegalIRObservation

LEGAL_SEMANTIC_BUILD_CONTRACT = "legal-semantic-build:v0_1"
LEGAL_IR_MATERIALIZED_VIEW_CONTRACT = "legal-ir-materialized-view:v0_1"
LEGACY_WITNESS_CONTRACT = "legacy-semantic-witness:v0_1"
SEMANTIC_COMPARISON_LEDGER_CONTRACT = "semantic-comparison-ledger:v0_1"
PNF_COVERAGE_DEMAND_CONTRACT = "pnf-coverage-demand:v0_1"

_COORDINATE_SIGNATURES: Mapping[str, str] = {
    "actor": "signature:legal-actor-role:v1",
    "modality": "signature:normative-operation:v1",
    "conduct": "signature:regulated-conduct:v1",
    "object": "signature:regulated-object:v1",
    "condition": "signature:legal-condition:v1",
    "exception": "signature:legal-exception:v1",
    "jurisdiction": "signature:legal-jurisdiction:v1",
    "temporal_validity": "signature:legal-transition:v1",
    "authority_wrapper": "signature:legal-authority:v1",
}


@dataclass(frozen=True)
class LegacySemanticWitness:
    witness_ref: str
    extractor_contract_ref: str
    source_span_refs: tuple[str, ...]
    candidate_kind: str
    candidate_payload: Mapping[str, Any]
    match_state: str
    provenance_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "candidate_payload": dict(self.candidate_payload),
            "authority": "diagnostic_only",
            "promotes_pnf": False,
        }


@dataclass(frozen=True)
class SemanticComparisonRow:
    row_ref: str
    document_ref: str
    source_span_refs: tuple[str, ...]
    comparison_kind: str
    structural_signature_ref: str
    pnf_factor_refs: tuple[str, ...]
    legal_ir_observation_refs: tuple[str, ...]
    legacy_witness_refs: tuple[str, ...]
    comparison_state: str
    coordinate_states: Mapping[str, str]
    discrepancy_refs: tuple[str, ...]
    proposed_actions: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "coordinate_states": dict(self.coordinate_states),
            "authority": "audit_only",
            "promotion_authority": False,
        }


@dataclass(frozen=True)
class PNFCoverageDemand:
    demand_ref: str
    document_ref: str
    source_observation_refs: tuple[str, ...]
    candidate_composition_kind: str
    expected_role_shape: tuple[str, ...]
    missing_factor_type: str
    witness_refs: tuple[str, ...]
    structural_signature_ref: str
    state: str = "requires_pnf_reconstruction"

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "contract_ref": PNF_COVERAGE_DEMAND_CONTRACT,
            "authority": "diagnostic_demand_only",
            "may_create_factor_directly": False,
        }


@dataclass(frozen=True)
class LegalIRProjection:
    projection_ref: str
    pnf_build_ref: str
    projection_contract_ref: str
    observation_refs: tuple[str, ...]
    omitted_factor_refs: tuple[str, ...]
    projection_residuals: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "authority": "pnf_projection_only",
            "rebuildable": True,
        }


@dataclass(frozen=True)
class LegalSemanticBuild:
    build_ref: str
    document_ref: str
    source_revision_ref: str
    canonical_text_ref: str
    parser_build_ref: str
    pnf_build_ref: str
    refined_pnf_graph_ref: str
    legal_ir_projection_ref: str
    legacy_observation_set_ref: str
    comparison_ledger_ref: str
    coverage_demand_refs: tuple[str, ...]
    declaration_revision_refs: tuple[str, ...]
    build_state: str
    provenance_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "contract_ref": LEGAL_SEMANTIC_BUILD_CONTRACT,
            "surface_authority": {
                "refined_pnf_graph": "candidate_semantic_state",
                "legal_ir": "deterministic_pnf_projection",
                "legacy_observations": "diagnostic_witness_only",
                "comparison_ledger": "audit_only",
            },
            "flattened_union": False,
        }


def _span_refs(row: Mapping[str, Any]) -> tuple[str, ...]:
    values: set[str] = set()
    for key in ("span_refs", "source_span_refs", "provenance_refs"):
        raw = row.get(key) or ()
        if isinstance(raw, str):
            values.add(raw)
        else:
            values.update(str(value) for value in raw if value)
    span = row.get("span")
    if isinstance(span, Mapping):
        values.add("span:" + canonical_sha256(dict(span)))
    return tuple(sorted(values))


def normalize_legacy_witnesses(
    rows: Iterable[Mapping[str, Any]],
    *,
    document_ref: str,
    extractor_contract_ref: str = "legacy-obligation-extractor:v0_1",
) -> tuple[LegacySemanticWitness, ...]:
    witnesses: dict[str, LegacySemanticWitness] = {}
    for row in rows:
        candidate_kind = str(row.get("type") or row.get("modality") or "untyped_legal_candidate")
        spans = _span_refs(row)
        payload = {
            key: value
            for key, value in row.items()
            if key not in {"span_refs", "source_span_refs", "provenance_refs"}
        }
        identity = {
            "contract": LEGACY_WITNESS_CONTRACT,
            "document_ref": document_ref,
            "extractor": extractor_contract_ref,
            "candidate_kind": candidate_kind,
            "payload": payload,
            "spans": spans,
        }
        witness_ref = "legacy-witness:" + canonical_sha256(identity)
        witnesses[witness_ref] = LegacySemanticWitness(
            witness_ref=witness_ref,
            extractor_contract_ref=extractor_contract_ref,
            source_span_refs=spans,
            candidate_kind=candidate_kind,
            candidate_payload=payload,
            match_state="candidate_detected",
            provenance_refs=tuple(sorted({document_ref, extractor_contract_ref, *spans})),
        )
    return tuple(sorted(witnesses.values(), key=lambda row: row.witness_ref))


def materialize_legal_ir_projection(
    *,
    pnf_build_ref: str,
    legal_ir: Sequence[LegalIRObservation],
    all_factor_refs: Iterable[str],
) -> LegalIRProjection:
    projected = {row.pnf_factor_ref for row in legal_ir}
    omitted = tuple(sorted(set(str(value) for value in all_factor_refs) - projected))
    residuals = ("non_legal_pnf_factors_omitted",) if omitted else ()
    identity = {
        "contract": LEGAL_IR_MATERIALIZED_VIEW_CONTRACT,
        "pnf_build_ref": pnf_build_ref,
        "observations": [row.observation_ref for row in legal_ir],
        "omitted": omitted,
    }
    return LegalIRProjection(
        projection_ref="legal-ir-projection:" + canonical_sha256(identity),
        pnf_build_ref=pnf_build_ref,
        projection_contract_ref=LEGAL_IR_MATERIALIZED_VIEW_CONTRACT,
        observation_refs=tuple(sorted(row.observation_ref for row in legal_ir)),
        omitted_factor_refs=omitted,
        projection_residuals=residuals,
    )


def _feature_factor_refs(
    factors: Sequence[Mapping[str, Any]], coordinate: str
) -> tuple[str, ...]:
    refs: list[str] = []
    for factor in factors:
        factor_ref = str(factor.get("factor_ref") or "")
        factor_type = str(factor.get("factor_type") or factor.get("factor_type_ref") or "")
        metadata = factor.get("metadata") or {}
        role = str(metadata.get("role") or "") if isinstance(metadata, Mapping) else ""
        matched = (
            coordinate == "actor" and role in {"subject", "actor", "agent", "bearer"}
            or coordinate == "conduct" and (factor_type == "semantic.eventuality" or "conduct" in factor_type)
            or coordinate == "object" and role in {"object", "patient", "theme"}
            or coordinate == "modality" and factor_type == "semantic.normative_relation"
            or coordinate == "condition" and factor_type == "semantic.legal_condition"
            or coordinate == "exception" and factor_type == "semantic.legal_exception"
            or coordinate == "jurisdiction" and ("jurisdiction" in factor_type or role == "jurisdiction")
            or coordinate == "temporal_validity" and factor_type == "semantic.legal_transition"
            or coordinate == "authority_wrapper" and factor_type in {"semantic.legal_authority", "semantic.judicial_treatment"}
        )
        if matched and factor_ref:
            refs.append(factor_ref)
    return tuple(sorted(set(refs)))


def _feature_ir_refs(
    legal_ir: Sequence[LegalIRObservation], coordinate: str
) -> tuple[str, ...]:
    refs: list[str] = []
    for row in legal_ir:
        roles = {key.casefold() for key in row.role_bindings}
        matched = (
            coordinate == "actor" and bool(roles.intersection({"actor", "bearer", "court", "party"}))
            or coordinate == "conduct" and bool(roles.intersection({"conduct", "action", "predicate"}))
            or coordinate == "object" and bool(roles.intersection({"object", "patient", "theme"}))
            or coordinate == "modality" and bool(row.qualifier_state.get("modality") or "normative" in row.predicate_ref)
            or coordinate == "condition" and bool(row.qualifier_state.get("condition_ref"))
            or coordinate == "exception" and bool(row.qualifier_state.get("exception_ref"))
            or coordinate == "jurisdiction" and bool(row.wrapper_state.get("jurisdiction_ref"))
            or coordinate == "temporal_validity" and bool(row.wrapper_state.get("validity_interval"))
            or coordinate == "authority_wrapper" and bool(row.wrapper_state.get("authority_class"))
        )
        if matched:
            refs.append(row.observation_ref)
    return tuple(sorted(set(refs)))


def _feature_witness_refs(
    witnesses: Sequence[LegacySemanticWitness], coordinate: str
) -> tuple[str, ...]:
    refs: list[str] = []
    for witness in witnesses:
        row = witness.candidate_payload
        matched = (
            coordinate == "actor" and bool(row.get("actor"))
            or coordinate == "modality" and bool(row.get("modality") or row.get("type"))
            or coordinate == "conduct" and bool(row.get("action"))
            or coordinate == "object" and bool(row.get("object") or row.get("obj"))
            or coordinate == "condition" and bool(row.get("conditions"))
            or coordinate == "exception" and any(
                str(item.get("type") or "") in {"unless", "except", "exception"}
                for item in row.get("conditions") or ()
                if isinstance(item, Mapping)
            )
            or coordinate == "jurisdiction" and bool(row.get("scopes"))
            or coordinate == "temporal_validity" and bool(row.get("lifecycle"))
            or coordinate == "authority_wrapper" and bool(row.get("references") or row.get("reference_identities"))
        )
        if matched:
            refs.append(witness.witness_ref)
    return tuple(sorted(set(refs)))


def build_semantic_comparison_ledger(
    *,
    document_ref: str,
    factors: Sequence[Mapping[str, Any]],
    legal_ir: Sequence[LegalIRObservation],
    witnesses: Sequence[LegacySemanticWitness],
) -> tuple[SemanticComparisonRow, ...]:
    rows: list[SemanticComparisonRow] = []
    for coordinate, signature in _COORDINATE_SIGNATURES.items():
        pnf_refs = _feature_factor_refs(factors, coordinate)
        ir_refs = _feature_ir_refs(legal_ir, coordinate)
        witness_refs = _feature_witness_refs(witnesses, coordinate)
        discrepancies: list[str] = []
        actions: list[str] = []
        if pnf_refs and ir_refs:
            state = "aligned"
        elif pnf_refs and not ir_refs:
            state = "legal_ir_projection_gap"
            discrepancies.append(f"pnf_{coordinate}_not_projected_to_legal_ir")
            actions.append("inspect_legal_ir_projection_contract")
        elif witness_refs and not pnf_refs:
            state = "legacy_only"
            discrepancies.append(f"legacy_{coordinate}_candidate_not_reconstructed_in_pnf")
            actions.append("request_pnf_reconstruction")
        elif pnf_refs:
            state = "pnf_only"
        elif witness_refs:
            state = "legacy_only"
        else:
            state = "unresolved"
        span_refs = tuple(
            sorted(
                {
                    span
                    for witness in witnesses
                    if witness.witness_ref in witness_refs
                    for span in witness.source_span_refs
                }
            )
        )
        identity = {
            "contract": SEMANTIC_COMPARISON_LEDGER_CONTRACT,
            "document_ref": document_ref,
            "coordinate": coordinate,
            "signature": signature,
            "pnf": pnf_refs,
            "legal_ir": ir_refs,
            "witnesses": witness_refs,
            "state": state,
        }
        rows.append(
            SemanticComparisonRow(
                row_ref="semantic-comparison:" + canonical_sha256(identity),
                document_ref=document_ref,
                source_span_refs=span_refs,
                comparison_kind=coordinate,
                structural_signature_ref=signature,
                pnf_factor_refs=pnf_refs,
                legal_ir_observation_refs=ir_refs,
                legacy_witness_refs=witness_refs,
                comparison_state=state,
                coordinate_states={
                    "pnf": "present" if pnf_refs else "absent",
                    "legal_ir": "present" if ir_refs else "absent",
                    "legacy_witness": "present" if witness_refs else "absent",
                },
                discrepancy_refs=tuple(discrepancies),
                proposed_actions=tuple(actions),
            )
        )
    return tuple(rows)


def project_pnf_coverage_demands(
    ledger: Iterable[SemanticComparisonRow],
) -> tuple[PNFCoverageDemand, ...]:
    demands: list[PNFCoverageDemand] = []
    factor_types = {
        "modality": "semantic.normative_relation",
        "condition": "semantic.legal_condition",
        "exception": "semantic.legal_exception",
        "temporal_validity": "semantic.legal_transition",
        "authority_wrapper": "semantic.legal_authority",
        "actor": "semantic.argument",
        "conduct": "semantic.eventuality",
        "object": "semantic.argument",
        "jurisdiction": "semantic.legal.jurisdiction",
    }
    role_shapes = {
        "modality": ("bearer", "content"),
        "condition": ("condition", "consequent"),
        "exception": ("exception", "base_norm"),
        "temporal_validity": ("legal_object", "prior_state", "new_state", "effective_time"),
        "authority_wrapper": ("authority", "content"),
        "actor": ("actor",),
        "conduct": ("conduct",),
        "object": ("object",),
        "jurisdiction": ("jurisdiction",),
    }
    for row in ledger:
        if row.comparison_state != "legacy_only":
            continue
        identity = {
            "contract": PNF_COVERAGE_DEMAND_CONTRACT,
            "comparison_row_ref": row.row_ref,
            "missing_factor_type": factor_types[row.comparison_kind],
        }
        demands.append(
            PNFCoverageDemand(
                demand_ref="pnf-coverage-demand:" + canonical_sha256(identity),
                document_ref=row.document_ref,
                source_observation_refs=row.source_span_refs,
                candidate_composition_kind=row.comparison_kind,
                expected_role_shape=role_shapes[row.comparison_kind],
                missing_factor_type=factor_types[row.comparison_kind],
                witness_refs=row.legacy_witness_refs,
                structural_signature_ref=row.structural_signature_ref,
            )
        )
    return tuple(sorted(demands, key=lambda row: row.demand_ref))


def build_legal_semantic_build(
    *,
    compilation: Mapping[str, Any],
    legal_ir: Sequence[LegalIRObservation],
    legacy_rows: Sequence[Mapping[str, Any]],
    declaration_revision_refs: Iterable[str] = (),
) -> dict[str, Any]:
    artifacts = compilation.get("artifacts") or compilation
    document_ref = str(compilation.get("document_ref") or artifacts.get("document_ref") or "")
    refined_graph = artifacts.get("refined_pnf_graph") or artifacts.get("pnf_graph") or {}
    factors = tuple(row for row in refined_graph.get("factors") or () if isinstance(row, Mapping))
    pnf_build_ref = str(refined_graph.get("graph_ref") or "pnf-build:" + canonical_sha256(refined_graph))
    witnesses = normalize_legacy_witnesses(legacy_rows, document_ref=document_ref)
    projection = materialize_legal_ir_projection(
        pnf_build_ref=pnf_build_ref,
        legal_ir=legal_ir,
        all_factor_refs=(str(row.get("factor_ref") or "") for row in factors),
    )
    ledger = build_semantic_comparison_ledger(
        document_ref=document_ref,
        factors=factors,
        legal_ir=legal_ir,
        witnesses=witnesses,
    )
    demands = project_pnf_coverage_demands(ledger)
    source_revision_ref = str(artifacts.get("build_key_sha256") or compilation.get("content_sha256") or "")
    canonical_text_ref = "canonical-text:" + canonical_sha256(artifacts.get("canonical_text") or "")
    parser_build_ref = "parser-build:" + canonical_sha256(artifacts.get("parser_receipt") or {})
    legacy_set_ref = "legacy-witness-set:" + canonical_sha256([row.to_dict() for row in witnesses])
    ledger_ref = "semantic-comparison-ledger:" + canonical_sha256([row.to_dict() for row in ledger])
    declarations = tuple(sorted(set(str(value) for value in declaration_revision_refs if value)))
    identity = {
        "contract": LEGAL_SEMANTIC_BUILD_CONTRACT,
        "document_ref": document_ref,
        "source_revision_ref": source_revision_ref,
        "canonical_text_ref": canonical_text_ref,
        "parser_build_ref": parser_build_ref,
        "pnf_build_ref": pnf_build_ref,
        "legal_ir_projection_ref": projection.projection_ref,
        "legacy_observation_set_ref": legacy_set_ref,
        "comparison_ledger_ref": ledger_ref,
        "declarations": declarations,
    }
    build = LegalSemanticBuild(
        build_ref="legal-semantic-build:" + canonical_sha256(identity),
        document_ref=document_ref,
        source_revision_ref=source_revision_ref,
        canonical_text_ref=canonical_text_ref,
        parser_build_ref=parser_build_ref,
        pnf_build_ref=pnf_build_ref,
        refined_pnf_graph_ref=pnf_build_ref,
        legal_ir_projection_ref=projection.projection_ref,
        legacy_observation_set_ref=legacy_set_ref,
        comparison_ledger_ref=ledger_ref,
        coverage_demand_refs=tuple(row.demand_ref for row in demands),
        declaration_revision_refs=declarations,
        build_state="candidate_semantic_build",
        provenance_refs=tuple(sorted({document_ref, source_revision_ref, pnf_build_ref})),
    )
    return {
        "build": build.to_dict(),
        "legal_ir_projection": projection.to_dict(),
        "legacy_witnesses": [row.to_dict() for row in witnesses],
        "comparison_ledger": [row.to_dict() for row in ledger],
        "coverage_demands": [row.to_dict() for row in demands],
        "summary": {
            "legal_ir_observation_count": len(legal_ir),
            "legacy_witness_count": len(witnesses),
            "comparison_row_count": len(ledger),
            "coverage_demand_count": len(demands),
            "semantic_promotion_count": 0,
        },
    }


__all__ = [
    "LEGAL_SEMANTIC_BUILD_CONTRACT",
    "LegacySemanticWitness",
    "LegalIRProjection",
    "LegalSemanticBuild",
    "PNFCoverageDemand",
    "SemanticComparisonRow",
    "build_legal_semantic_build",
    "build_semantic_comparison_ledger",
    "materialize_legal_ir_projection",
    "normalize_legacy_witnesses",
    "project_pnf_coverage_demands",
]
