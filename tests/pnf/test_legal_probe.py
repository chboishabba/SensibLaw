from __future__ import annotations

import hashlib

from src.pnf.legal_adjunct import project_legal_ir
from src.pnf.legal_probe import (
    build_legal_pnf_probe,
    legal_entity_lookup_demands,
    plan_legal_entity_resolution,
)
from src.policy.corpus_compilation import compile_document, default_compiler_context


def _compilation(text: str) -> dict[str, object]:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return compile_document(
        {
            "document_ref": "document:" + digest,
            "source_ref": "source:" + digest,
            "media_type": "text/plain",
            "content_sha256": digest,
            "canonical_text": text,
        },
        default_compiler_context(),
    ).to_dict()


def test_real_legal_text_runs_through_universal_pnf_and_emits_honest_ledger() -> None:
    compilation = _compilation(
        "A person must not drive a motor vehicle on a road unless licensed. "
        "The Court held that section 5 applied."
    )
    legacy = (
        {
            "type": "prohibition",
            "modality": "must not",
            "actor": {"normalized": "a person"},
            "action": {"normalized": "drive"},
            "object": {"normalized": "a motor vehicle"},
            "conditions": ({"type": "unless"},),
        },
    )

    probe = build_legal_pnf_probe(compilation, legacy_rows=legacy)

    assert probe["canonical_text"].startswith("A person must not drive")
    assert probe["parser_receipt"]
    assert probe["pnf_graph"]["factors"]
    assert len(probe["comparison_ledger"]) == 9
    assert probe["summary"]["identity_closure_count"] == 0
    assert probe["summary"]["legal_conclusion_promotion_count"] == 0
    assert any(
        row["state"] in {"legacy_only_gap", "pnf_only", "pnf_and_legal_ir"}
        for row in probe["comparison_ledger"]
    )


def test_entity_lookup_requires_legal_role_blocker_not_merely_proper_name() -> None:
    artifacts = {
        "licensing": {
            "mentions": (
                {
                    "mention_ref": "mention:minister",
                    "canonical_surface": "Minister for Health",
                },
                {
                    "mention_ref": "mention:brisbane",
                    "canonical_surface": "Brisbane",
                },
            )
        },
        "refined_pnf_graph": {
            "factors": (
                {
                    "factor_ref": "factor:minister",
                    "factor_type": "semantic.mention_identity",
                    "alternatives": (
                        {
                            "type_ref": "semantic.person_candidate",
                            "value": {"semantic_family": "entity"},
                        },
                    ),
                    "residuals": ("external_identity_unresolved",),
                    "metadata": {
                        "mention_ref": "mention:minister",
                        "factor_revision_ref": "revision:minister",
                    },
                },
                {
                    "factor_ref": "factor:brisbane",
                    "factor_type": "semantic.mention_identity",
                    "alternatives": (
                        {
                            "type_ref": "semantic.location_candidate",
                            "value": {"semantic_family": "entity"},
                        },
                    ),
                    "residuals": ("external_identity_unresolved",),
                    "metadata": {
                        "mention_ref": "mention:brisbane",
                        "factor_revision_ref": "revision:brisbane",
                    },
                },
                {
                    "factor_ref": "factor:norm",
                    "factor_revision_ref": "revision:norm",
                    "factor_type_ref": "semantic.normative_relation",
                    "structural_signature_ref": "signature:grant-power",
                    "predicate_ref": "normative.power",
                    "role_bindings": {
                        "bearer": "factor:minister",
                        "conduct": "factor:grant",
                    },
                    "qualifier_state": {"modality": "power"},
                    "wrapper_state": {"authority_class": "legislation"},
                    "provenance_refs": ("span:norm",),
                    "residual_refs": ("bearer_identity_unresolved",),
                },
            )
        },
    }
    legal_ir = project_legal_ir(artifacts["refined_pnf_graph"]["factors"])

    decisions = plan_legal_entity_resolution(artifacts, legal_ir)
    by_factor = {row.factor_ref: row for row in decisions}

    assert by_factor["factor:minister"].should_lookup is True
    assert by_factor["factor:brisbane"].should_lookup is False
    demands = legal_entity_lookup_demands(decisions)
    assert len(demands) == 1
    assert demands[0].surface == "Minister for Health"
    assert demands[0].subject_ref == "factor:minister"


def test_explicit_legal_identity_residual_can_warrant_lookup_without_ir_role() -> None:
    artifacts = {
        "licensing": {
            "mentions": (
                {
                    "mention_ref": "mention:court",
                    "canonical_surface": "High Court of Australia",
                },
            )
        },
        "refined_pnf_graph": {
            "factors": (
                {
                    "factor_ref": "factor:court",
                    "factor_type": "semantic.mention_identity",
                    "alternatives": (
                        {
                            "type_ref": "semantic.organization_candidate",
                            "value": {"semantic_family": "entity"},
                        },
                    ),
                    "residuals": ("legal_authority_identity_unresolved",),
                    "metadata": {
                        "mention_ref": "mention:court",
                        "factor_revision_ref": "revision:court",
                    },
                },
            )
        },
    }

    decisions = plan_legal_entity_resolution(artifacts, ())

    assert decisions[0].should_lookup is True
    assert decisions[0].reasons == (
        "entity_identity_open",
        "legal_coordinate_blocked",
    )
