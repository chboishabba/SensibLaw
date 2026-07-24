from src.pnf.curated_legal_ir_flow import run_curated_legal_ir_flow
from src.pnf.legal_source_registry import RegisteredLegalSource


def _graph(document_ref: str, factor_ref: str) -> dict[str, object]:
    return {
        "graph_ref": f"graph:{document_ref}",
        "document_ref": document_ref,
        "factors": [
            {
                "factor_ref": factor_ref,
                "factor_type": "semantic.normative_relation",
                "alternatives": [],
                "constraints": [],
                "residuals": [],
                "closure_state": "locally_closed",
                "metadata": {
                    "factor_revision_ref": f"revision:{factor_ref}",
                    "structural_signature_ref": "signature:normative:drive",
                },
            }
        ],
        "constraints": [],
        "relation_refs": [],
        "residuals": [],
    }


def _compilation(document_ref: str, *, legal_demand: bool) -> dict[str, object]:
    demand = {
        "demand_ref": "demand:law",
        "factor_ref": "factor:world",
        "factor_revision_ref": "revision:factor:world",
        "structural_signature_ref": "signature:normative:drive",
        "requested_facets": [
            "legal.authority_absent",
            "legal.jurisdiction:AU-QLD",
            "legal.source_role:primary_legislation",
            "legal.authority_level:primary",
        ],
    }
    return {
        "artifacts": {
            "pnf_graph": _graph(document_ref, f"factor:{document_ref}"),
            "refined_pnf_graph": _graph(document_ref, f"factor:{document_ref}"),
            "resolution_demands": [demand] if legal_demand else [],
            "streaming_semantic_build": {
                "fibre_ledger_ref": f"ledger:{document_ref}",
                "proposals": [],
                "materialized_reduction": {"residuals": []},
                "fixed_point_certificate": {"local_fixed_point": "reached"},
            },
        }
    }


def _source() -> RegisteredLegalSource:
    return RegisteredLegalSource(
        source_revision_ref="source:act",
        document_ref="document:act",
        admission_receipt_ref="admission:act",
        jurisdiction_ref="AU-QLD",
        source_role="primary_legislation",
        authority_level="primary",
        canonical_text_sha256="a" * 64,
    )


def test_flow_selects_persisted_source_and_never_fetches() -> None:
    source = _source()
    payload_reads = []

    result = run_curated_legal_ir_flow(
        corpus_ref="corpus:hca",
        admission_profile_ref="profile:offline-hca-regression:v0_2",
        compiler_contract_ref="postgres-fibred-semantic-compiler:v0_1",
        ordinary_compilations=(_compilation("world", legal_demand=True),),
        source_lookup=lambda demand: (source,),
        payload_lookup=lambda source_ref: payload_reads.append(source_ref)
        or {"source_revision_ref": source_ref},
        compile_legal_source=lambda payload: _compilation("law", legal_demand=False),
        network_attempt_count=0,
    )

    assert result.plans[0].state == "ready_persisted"
    assert result.acquisition_requirements == ()
    assert payload_reads == ["source:act"]
    assert result.legal_ir
    assert result.parity_receipt.network_attempt_count == 0
    assert result.parity_receipt.to_dict()["legal_truth_closed"] is False


def test_active_lifecycle_with_no_legal_projection_does_not_fallback() -> None:
    source = _source()
    legal_compilation = _compilation("law", legal_demand=False)
    artifacts = legal_compilation["artifacts"]
    assert isinstance(artifacts, dict)
    artifacts["domain_ir_build"] = {
        "build_ref": "domain-ir-build:law",
        "projections": [],
        "demands": [
            {
                "demand_ref": "pnf-projection-demand:jurisdiction",
                "domain": "legal",
                "demand_kind": "missing_jurisdiction",
            }
        ],
    }
    artifacts["domain_ir_projections"] = []

    result = run_curated_legal_ir_flow(
        corpus_ref="corpus:hca",
        admission_profile_ref="profile:offline-hca-regression:v0_2",
        compiler_contract_ref="postgres-fibred-semantic-compiler:v0_2",
        ordinary_compilations=(_compilation("world", legal_demand=True),),
        source_lookup=lambda demand: (source,),
        payload_lookup=lambda source_ref: {"source_revision_ref": source_ref},
        compile_legal_source=lambda payload: legal_compilation,
        network_attempt_count=0,
    )

    assert result.legal_compilations
    assert result.legal_ir == ()
    assert result.typed_meets == ()


def test_flow_preserves_missing_source_as_blocked_requirement() -> None:
    result = run_curated_legal_ir_flow(
        corpus_ref="corpus:hca",
        admission_profile_ref="profile:offline-hca-regression:v0_2",
        compiler_contract_ref="postgres-fibred-semantic-compiler:v0_1",
        ordinary_compilations=(_compilation("world", legal_demand=True),),
        source_lookup=lambda demand: (),
        payload_lookup=lambda source_ref: (_ for _ in ()).throw(AssertionError(source_ref)),
        compile_legal_source=lambda payload: (_ for _ in ()).throw(AssertionError(payload)),
        network_attempt_count=0,
    )

    assert result.plans[0].state == "blocked_acquisition_required"
    assert len(result.acquisition_requirements) == 1
    assert result.legal_compilations == ()
