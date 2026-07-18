from __future__ import annotations

from src.storage.postgres.binding_candidate_store import (
    persist_binding_candidate_sets,
)


class RecordingCursor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...] | None]] = []

    def execute(self, sql: str, params=None) -> None:
        normalized = " ".join(sql.split())
        self.calls.append((normalized, tuple(params) if params is not None else None))

    def fetchall(self):
        return []


def test_store_persists_indexes_sets_members_builds_and_links() -> None:
    cursor = RecordingCursor()
    candidate_set = {
        "candidate_set_ref": "binding-candidate-set:test",
        "document_ref": "document:test",
        "reference_factor_ref": "factor:reference",
        "reference_factor_revision_ref": "serialized:ignored",
        "referential_type_ref": "entity_reference",
        "accessibility_declaration_ref": (
            "binding-accessibility:document-structural:v0_3"
        ),
        "compatibility_declaration_ref": (
            "binding-compatibility:pnf-kind-morphology:v0_3"
        ),
        "generator_build_ref": "build:test",
        "compatibility_state": "compatible_members_present",
        "member_count": 1,
        "members": [
            {
                "candidate_factor_ref": "factor:candidate",
                "compatibility_state": "compatible_candidate",
                "accessibility_path_ref": "accessibility:preceding_discourse_unit",
                "compatibility_assessment_ref": "binding-compatibility:test",
                "distance_tokens": 4,
            }
        ],
        "exclusion_summaries": [
            {
                "reason_ref": "incompatible_morphology:Number",
                "excluded_count": 2,
                "generator_build_ref": "build:test",
            }
        ],
    }
    factor_anchor = {
        "factor_ref": "factor:reference",
        "factor_revision_ref": "serialized:ignored",
        "document_ref": "document:test",
        "pnf_kind_ref": "semantic.argument.subject",
        "start_token": 5,
        "end_token": 6,
        "sentence_index": 1,
        "clause_ref": "clause:one",
        "discourse_unit_ref": "sentence:1",
        "paragraph_index": 0,
        "quotation_depth": 0,
        "reporting_scope_ref": None,
        "coordination_group_ref": None,
        "parser_pos": "PRON",
        "parser_dependency": "nsubj",
        "morphology": {"Number": ["Sing"], "Person": ["3"]},
        "morphology_sha256": "abc",
    }
    build = {
        "generator_build_ref": "build:test",
        "candidate_set_ref": "binding-candidate-set:test",
        "reference_factor_revision_ref": "serialized:ignored",
        "document_pnf_index_ref": "pnf:test",
        "accessibility_declaration_ref": (
            "binding-accessibility:document-structural:v0_3"
        ),
        "compatibility_declaration_ref": (
            "binding-compatibility:pnf-kind-morphology:v0_3"
        ),
        "referential_type_ref": "entity_reference",
    }
    refinement = {
        "refinement_ref": "refinement:test",
        "candidate_set_refs": ["binding-candidate-set:test"],
    }
    meet = {
        "meet_ref": "meet:test",
        "candidate_set_refs": ["binding-candidate-set:test"],
    }

    persist_binding_candidate_sets(
        cursor,
        candidate_sets=[candidate_set],
        refinements=[refinement],
        factor_revisions={
            "factor:reference": "factor-revision:reference",
            "factor:candidate": "factor-revision:candidate",
        },
        factor_anchors=[factor_anchor],
        builds=[build],
        meets=[meet],
    )

    sql = "\n".join(call[0] for call in cursor.calls)
    assert "INSERT INTO pnf.factor_anchor" in sql
    assert sql.count("INSERT INTO pnf.factor_morphology") == 2
    assert "INSERT INTO execution.binding_candidate_set_build" in sql
    assert "INSERT INTO resolution.binding_candidate_set" in sql
    assert "INSERT INTO resolution.binding_compatibility_assessment" in sql
    assert "INSERT INTO resolution.binding_candidate_member" in sql
    assert "INSERT INTO resolution.binding_exclusion_summary" in sql
    assert "INSERT INTO resolution.refinement_candidate_set" in sql
    assert "INSERT INTO resolution.meet_candidate_set" in sql

    candidate_set_insert = next(
        params
        for statement, params in cursor.calls
        if "INSERT INTO resolution.binding_candidate_set" in statement
    )
    assert candidate_set_insert is not None
    assert candidate_set_insert[3] == "factor-revision:reference"


def test_store_rejects_candidate_set_without_persisted_reference_revision() -> None:
    cursor = RecordingCursor()
    candidate_set = {
        "candidate_set_ref": "binding-candidate-set:test",
        "document_ref": "document:test",
        "reference_factor_ref": "factor:missing",
        "reference_factor_revision_ref": "serialized:ignored",
        "referential_type_ref": "entity_reference",
        "accessibility_declaration_ref": "binding-accessibility:test",
        "compatibility_declaration_ref": "binding-compatibility:test",
        "generator_build_ref": "build:test",
        "compatibility_state": "no_compatible_member",
        "member_count": 0,
        "members": [],
        "exclusion_summaries": [],
    }

    try:
        persist_binding_candidate_sets(
            cursor,
            candidate_sets=[candidate_set],
            refinements=[],
            factor_revisions={},
        )
    except ValueError as error:
        assert "unpersisted factor revision" in str(error)
    else:
        raise AssertionError("missing reference revision must fail closed")
