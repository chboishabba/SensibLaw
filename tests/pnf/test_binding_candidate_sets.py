from pathlib import Path

from src.pnf.binding_candidate_sets import compact_binding_artifacts


ROOT = Path(__file__).resolve().parents[2]
MIGRATION_008 = ROOT / "database/postgres_migrations/008_binding_candidate_sets.sql"
MIGRATION_009 = ROOT / "database/postgres_migrations/009_structural_binding_index.sql"


def _factor(factor_ref: str, *, reference: bool = False) -> dict[str, object]:
    alternatives: list[dict[str, object]] = []
    if reference:
        alternatives.append(
            {
                "alternative_ref": f"{factor_ref}:reference",
                "type_ref": "semantic.reference_candidate",
                "value": {"referential_type": "entity_reference"},
                "derivation_refs": ["parser:test"],
            }
        )
    return {
        "factor_ref": factor_ref,
        "factor_type": (
            "semantic.argument_reference" if reference else "semantic.mention_identity"
        ),
        "alternatives": alternatives,
        "constraints": [],
        "residuals": ["antecedent_unresolved"] if reference else [],
        "closure_state": (
            "requires_external_resolution" if reference else "locally_closed"
        ),
        "metadata": {},
    }


def _binding_row(
    evidence_ref: str,
    reference_ref: str,
    candidate_ref: str,
    *,
    compatible: bool,
) -> dict[str, object]:
    return {
        "evidence_ref": evidence_ref,
        "document_ref": "document:test",
        "evidence_type": "typed_binding_candidate",
        "subject_refs": [reference_ref, candidate_ref],
        "relation": (
            "possible_coreference_with" if compatible else "binding_incompatible_with"
        ),
        "payload": {
            "referential_type": "entity_reference",
            "reference_position": {"sentence_index": 2, "start_token": 9},
            "candidate_position": {"sentence_index": 1, "start_token": 2},
        },
        "derivation_refs": ["grammar:test"],
        "provenance_refs": ["source:test"],
    }


def test_pairwise_compatibility_carrier_becomes_one_candidate_set() -> None:
    reference = _factor("factor:reference", reference=True)
    candidate = _factor("factor:candidate")
    inaccessible = _factor("factor:inaccessible")
    pair_alternative = {
        "alternative_ref": (
            "factor:reference:binding:entity_reference:factor:candidate"
        ),
        "type_ref": "semantic.binding_candidate",
        "value": {"candidate_factor_ref": "factor:candidate"},
        "derivation_refs": ["evidence:compatible"],
    }
    resulting = {
        **reference,
        "alternatives": [*reference["alternatives"], pair_alternative],
    }
    artifacts = {
        "pnf_graph": {
            "graph_ref": "pnf:test",
            "factors": [reference, candidate, inaccessible],
        },
        "refined_pnf_graph": {
            "graph_ref": "pnf:test-refined",
            "factors": [resulting, candidate, inaccessible],
        },
        "local_evidence": [
            _binding_row(
                "evidence:compatible",
                "factor:reference",
                "factor:candidate",
                compatible=True,
            ),
            _binding_row(
                "evidence:incompatible",
                "factor:reference",
                "factor:inaccessible",
                compatible=False,
            ),
            {
                "evidence_ref": "evidence:other",
                "document_ref": "document:test",
                "evidence_type": "local_type",
                "subject_refs": ["factor:reference"],
                "relation": "locally_typed_as",
                "payload": {},
                "derivation_refs": [],
                "provenance_refs": ["source:test"],
            },
        ],
        "typed_meets": [
            {
                "meet_ref": "meet:test",
                "left_ref": "factor:reference",
                "right_ref": "evidence:compatible",
                "meet_type": "document_local_evidence",
                "state": "compatible_with_refinement",
                "evidence_refs": ["evidence:compatible", "evidence:other"],
                "residual_refs": ["antecedent_unresolved"],
            }
        ],
        "factor_refinements": [
            {
                "refinement_ref": "refinement:test",
                "prior_factor": reference,
                "resulting_factor": resulting,
                "added_alternative_refs": [pair_alternative["alternative_ref"]],
                "retained_alternative_refs": ["factor:reference:reference"],
                "rejected_alternative_refs": [],
                "rejected_candidate_refs": [
                    "factor:reference:binding:entity_reference:factor:inaccessible"
                ],
                "residual_transitions": [],
                "evidence_refs": ["evidence:compatible", "evidence:incompatible"],
            }
        ],
    }

    compact = compact_binding_artifacts(artifacts)
    summary = compact["binding_compaction_summary"]

    assert summary["generation_mode"] == "legacy_pairwise_compatibility"
    assert summary["pairwise_binding_evidence_removed"] == 2
    assert summary["candidate_set_count"] == 1
    assert summary["candidate_member_count"] == 1
    assert summary["exclusion_summary_count"] == 1
    assert summary["accessibility_declaration_ref"] == (
        "binding-accessibility:document-structural:v0_3"
    )
    assert summary["compatibility_declaration_ref"] == (
        "binding-compatibility:pnf-kind-morphology:v0_3"
    )
    candidate_set = compact["binding_candidate_sets"][0]
    assert candidate_set["member_count"] == 1
    assert candidate_set["members"][0]["candidate_factor_ref"] == "factor:candidate"
    assert candidate_set["exclusion_summaries"][0]["excluded_count"] == 1
    assert [row["evidence_ref"] for row in compact["local_evidence"]] == [
        "evidence:other"
    ]
    refinement = compact["factor_refinements"][0]
    assert len(refinement["candidate_set_refs"]) == 1
    assert not any(
        row["type_ref"] == "semantic.binding_candidate"
        for row in refinement["resulting_factor"]["alternatives"]
    )
    assert any(
        row["type_ref"] == "semantic.binding_candidate_set"
        for row in refinement["resulting_factor"]["alternatives"]
    )


def test_empty_legacy_candidate_search_does_not_infer_expletivity() -> None:
    reference = _factor("factor:it", reference=True)
    reference["alternatives"].append(
        {
            "alternative_ref": "factor:it:expletive",
            "type_ref": "semantic.expletive_realisation",
            "value": {},
            "derivation_refs": ["parser:expl"],
        }
    )
    compact = compact_binding_artifacts(
        {
            "pnf_graph": {"graph_ref": "pnf:it", "factors": [reference]},
            "refined_pnf_graph": {"graph_ref": "pnf:it", "factors": [reference]},
            "local_evidence": [],
            "typed_meets": [],
            "factor_refinements": [],
        }
    )
    assert compact["binding_candidate_sets"] == []
    assert compact["binding_compaction_summary"]["candidate_set_count"] == 0


def test_compaction_is_idempotent() -> None:
    artifacts = {
        "pnf_graph": {"graph_ref": "pnf:empty", "factors": []},
        "local_evidence": [],
        "typed_meets": [],
        "factor_refinements": [],
    }
    once = compact_binding_artifacts(artifacts)
    assert compact_binding_artifacts(once) == once


def test_postgres_schema_is_normalized_indexed_and_queryable() -> None:
    migration_008 = MIGRATION_008.read_text(encoding="utf-8")
    migration_009 = MIGRATION_009.read_text(encoding="utf-8")
    assert "resolution.binding_candidate_set" in migration_008
    assert "resolution.binding_candidate_member" in migration_008
    assert "resolution.binding_compatibility_assessment" in migration_008
    assert "resolution.binding_exclusion_summary" in migration_008
    assert "resolution.refinement_candidate_set" in migration_008
    assert "factor_anchor_document_position_idx" in migration_008
    assert "binding_candidate_member_candidate_idx" in migration_008
    assert "candidate_payload JSONB" not in migration_008

    assert "pnf.factor_morphology" in migration_009
    assert "execution.binding_candidate_set_build" in migration_009
    assert "resolution.meet_candidate_set" in migration_009
    assert "resolution.binding_referential_kind" in migration_009
    assert "resolution.binding_accessibility_path" in migration_009
    assert "resolution.query_binding_candidates" in migration_009
    assert "factor_anchor_structural_accessibility_idx" in migration_009
    assert "two_sentence" not in migration_009.casefold()
    assert "candidate_payload JSONB" not in migration_009
