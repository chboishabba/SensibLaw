"""Pure orchestration for the curated ordinary-PNF to Legal-IR proof.

The caller supplies already-compiled ordinary documents, persisted legal-source
lookups, and the same fibred compiler for selected legal sources. Missing source
coordinates remain blocked acquisition requirements; no network operation is
available in this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, Sequence

from src.pnf.legal_adjunct import (
    AcquisitionRequirement,
    LegalIRObservation,
    LegalSourcePlan,
    LegalTypedMeet,
    NormativeInteractionDemand,
    plan_legal_sources,
    project_acquisition_requirements,
    project_legal_ir,
    project_normative_interaction_demands,
    typed_legal_meet,
)
from src.pnf.legal_ir_parity import (
    CuratedLegalIRParityReceipt,
    SemanticIdentitySnapshot,
    compare_identity_snapshots,
    snapshot_from_build_artifacts,
)
from src.pnf.legal_ir_projection_bridge import (
    project_legal_ir_from_domain_ir,
)
from src.pnf.legal_source_registry import RegisteredLegalSource
from src.policy.carriers.canonical import canonical_sha256

SourceLookup = Callable[
    [NormativeInteractionDemand], Sequence[RegisteredLegalSource]
]
PayloadLookup = Callable[[str], Mapping[str, Any] | None]
LegalCompiler = Callable[[Mapping[str, Any]], Mapping[str, Any]]


def _artifacts(compilation: Mapping[str, Any]) -> Mapping[str, Any]:
    return compilation.get("artifacts") or compilation


def _factor_projection_rows(
    artifact: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    graph = artifact.get("refined_pnf_graph") or artifact.get("pnf_graph") or {}
    rows = []
    for factor in graph.get("factors") or ():
        metadata = dict(factor.get("metadata") or {})
        revision_ref = str(
            metadata.get("factor_revision_ref")
            or "factor-revision:"
            + canonical_sha256(
                {
                    "factor_ref": factor.get("factor_ref"),
                    "closure_state": factor.get("closure_state"),
                    "alternatives": factor.get("alternatives") or (),
                    "residuals": factor.get("residuals") or (),
                }
            )
        )
        signature_ref = str(
            metadata.get("structural_signature_ref")
            or metadata.get("signature_ref")
            or factor.get("factor_type")
            or ""
        )
        rows.append(
            {
                **dict(factor),
                "factor_type_ref": str(factor.get("factor_type") or ""),
                "factor_revision_ref": revision_ref,
                "structural_signature_ref": signature_ref,
                "role_bindings": dict(metadata.get("role_bindings") or {}),
                "qualifier_state": dict(
                    metadata.get("qualifier_state") or {}
                ),
                "wrapper_state": dict(metadata.get("wrapper_state") or {}),
                "provenance_refs": tuple(
                    metadata.get("provenance_refs") or ()
                ),
                "residual_refs": tuple(factor.get("residuals") or ()),
                "legal_coordinates": dict(
                    metadata.get("legal_coordinates") or {}
                ),
            }
        )
    return tuple(rows)


def _lawful_legal_ir(
    legal_compilations: Iterable[Mapping[str, Any]],
) -> tuple[LegalIRObservation, ...]:
    artifacts = tuple(_artifacts(row) for row in legal_compilations)
    domain_rows = tuple(
        projection
        for artifact in artifacts
        for projection in artifact.get("domain_ir_projections") or ()
        if isinstance(projection, Mapping)
        and str(projection.get("domain") or "") == "legal"
    )
    if domain_rows:
        return project_legal_ir_from_domain_ir(domain_rows)
    # Compatibility only for caller-supplied historical fixtures. Active v0_2
    # compiler builds always expose lawful Domain IR projections.
    factor_rows = tuple(
        row for artifact in artifacts for row in _factor_projection_rows(artifact)
    )
    return project_legal_ir(factor_rows)


@dataclass(frozen=True)
class CuratedLegalIRFlowResult:
    demands: tuple[NormativeInteractionDemand, ...]
    plans: tuple[LegalSourcePlan, ...]
    acquisition_requirements: tuple[AcquisitionRequirement, ...]
    legal_compilations: tuple[Mapping[str, Any], ...]
    legal_ir: tuple[LegalIRObservation, ...]
    typed_meets: tuple[LegalTypedMeet, ...]
    identity_snapshot: SemanticIdentitySnapshot
    parity_receipt: CuratedLegalIRParityReceipt

    def to_dict(self) -> dict[str, Any]:
        return {
            "demands": [row.to_dict() for row in self.demands],
            "plans": [row.to_dict() for row in self.plans],
            "acquisition_requirements": [
                {
                    **row.__dict__,
                    "requirement_ref": "acquisition-requirement:"
                    + canonical_sha256(row.__dict__),
                    "network_operation_performed": False,
                }
                for row in self.acquisition_requirements
            ],
            "legal_compilations": [dict(row) for row in self.legal_compilations],
            "legal_ir": [row.to_dict() for row in self.legal_ir],
            "typed_meets": [row.to_dict() for row in self.typed_meets],
            "identity_snapshot": self.identity_snapshot.to_dict(),
            "parity_receipt": self.parity_receipt.to_dict(),
        }


def run_curated_legal_ir_flow(
    *,
    corpus_ref: str,
    admission_profile_ref: str,
    compiler_contract_ref: str,
    ordinary_compilations: Iterable[Mapping[str, Any]],
    source_lookup: SourceLookup,
    payload_lookup: PayloadLookup,
    compile_legal_source: LegalCompiler,
    legacy_witness_refs: Iterable[str] = (),
    control_snapshot: SemanticIdentitySnapshot | None = None,
    network_attempt_count: int = 0,
    unexpected_failure_refs: Iterable[str] = (),
) -> CuratedLegalIRFlowResult:
    """Run the offline parity flow over persisted inputs only."""

    if network_attempt_count != 0:
        raise ValueError("curated Legal IR parity requires zero network attempts")
    ordinary = tuple(dict(row) for row in ordinary_compilations)
    demands = project_normative_interaction_demands(
        row
        for compilation in ordinary
        for row in _artifacts(compilation).get("resolution_demands") or ()
    )
    plans: list[LegalSourcePlan] = []
    for demand in demands:
        sources = tuple(source_lookup(demand))
        plans.extend(
            plan_legal_sources(
                (demand,),
                persisted_sources=(row.planning_row() for row in sources),
            )
        )
    ordered_plans = tuple(
        sorted(plans, key=lambda row: (row.demand_ref, row.plan_key))
    )
    requirements = project_acquisition_requirements(ordered_plans)

    selected_refs = tuple(
        sorted(
            {
                ref
                for plan in ordered_plans
                if plan.state == "ready_persisted"
                for ref in plan.selected_source_revision_refs
            }
        )
    )
    legal_compilations: list[Mapping[str, Any]] = []
    for source_ref in selected_refs:
        payload = payload_lookup(source_ref)
        if payload is None:
            raise ValueError(
                "selected persisted legal source is unavailable: " f"{source_ref}"
            )
        compilation = compile_legal_source(payload)
        artifacts = _artifacts(compilation)
        streaming = artifacts.get("streaming_semantic_build") or {}
        if (
            (streaming.get("fixed_point_certificate") or {}).get(
                "local_fixed_point"
            )
            != "reached"
        ):
            raise ValueError(
                "selected legal source did not reach local fixed point"
            )
        legal_compilations.append(dict(compilation))

    legal_ir = _lawful_legal_ir(legal_compilations)
    ordinary_factor_rows = tuple(
        row
        for compilation in ordinary
        for row in _factor_projection_rows(_artifacts(compilation))
    )
    typed_meets = tuple(
        sorted(
            (
                typed_legal_meet(world_row, observation)
                for world_row in ordinary_factor_rows
                for observation in legal_ir
                if world_row["structural_signature_ref"]
                == observation.structural_signature_ref
            ),
            key=lambda row: (row.world_pnf_ref, row.legal_ir_ref),
        )
    )
    witness_refs = tuple(sorted(set(str(value) for value in legacy_witness_refs)))
    all_artifacts = tuple(_artifacts(row) for row in (*ordinary, *legal_compilations))
    snapshot = snapshot_from_build_artifacts(
        all_artifacts,
        legal_ir_refs=(row.observation_ref for row in legal_ir),
        typed_meet_refs=(
            "legal-typed-meet:" + canonical_sha256(row.to_dict())
            for row in typed_meets
        ),
        legacy_witness_refs=witness_refs,
    )
    parity = (
        compare_identity_snapshots(control_snapshot, snapshot)
        if control_snapshot is not None
        else None
    )
    receipt = CuratedLegalIRParityReceipt(
        corpus_ref=corpus_ref,
        admission_profile_ref=admission_profile_ref,
        compiler_contract_ref=compiler_contract_ref,
        source_revision_refs=selected_refs,
        ordinary_graph_refs=tuple(
            sorted(
                str((_artifacts(row).get("pnf_graph") or {}).get("graph_ref") or "")
                for row in ordinary
                if (_artifacts(row).get("pnf_graph") or {}).get("graph_ref")
            )
        ),
        legal_graph_refs=tuple(
            sorted(
                str((_artifacts(row).get("pnf_graph") or {}).get("graph_ref") or "")
                for row in legal_compilations
                if (_artifacts(row).get("pnf_graph") or {}).get("graph_ref")
            )
        ),
        demand_refs=tuple(row.demand_ref for row in demands),
        plan_refs=tuple(
            "legal-source-plan:" + canonical_sha256(row.to_dict())
            for row in ordered_plans
        ),
        legal_ir_refs=tuple(row.observation_ref for row in legal_ir),
        typed_meet_refs=tuple(
            "legal-typed-meet:" + canonical_sha256(row.to_dict())
            for row in typed_meets
        ),
        legacy_witness_refs=witness_refs,
        identity_snapshot=snapshot.to_dict(),
        control_snapshot=(control_snapshot.to_dict() if control_snapshot else None),
        identity_parity=parity.identical if parity else None,
        network_attempt_count=network_attempt_count,
        unexpected_failure_refs=tuple(sorted(set(unexpected_failure_refs))),
    )
    return CuratedLegalIRFlowResult(
        demands=demands,
        plans=ordered_plans,
        acquisition_requirements=requirements,
        legal_compilations=tuple(legal_compilations),
        legal_ir=legal_ir,
        typed_meets=typed_meets,
        identity_snapshot=snapshot,
        parity_receipt=receipt,
    )


__all__ = [
    "CuratedLegalIRFlowResult",
    "run_curated_legal_ir_flow",
]
