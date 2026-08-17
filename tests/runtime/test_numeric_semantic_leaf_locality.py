from __future__ import annotations

from src.runtime.numeric_semantic_leaf_locality import compare_leaf_locality


def _audit(nodes):
    return {
        "schema_version": "sensiblaw.numeric-semantic-leaf-audit.v1",
        "parser_sentence_spans": [[0, 10], [11, 23]],
        "nodes": nodes,
    }


def _node(
    ref,
    family,
    digest,
    spans=(),
    dependencies=(),
    *,
    occurrence_key="",
):
    return {
        "ref": ref,
        "family": family,
        "digest_sha256": digest * 64,
        "source_spans": [list(span) for span in spans],
        "dependencies": list(dependencies),
        "occurrence_key": occurrence_key,
    }


def test_changed_leaf_reachable_from_edited_sentence_is_verified() -> None:
    cold = _audit(
        [
            _node("object:a", "object", "a", ((0, 5),)),
            _node("export:a", "export", "b", (), ("object:a",)),
        ]
    )
    edit = _audit(
        [
            _node("object:b", "object", "c", ((0, 5),)),
            _node("export:b", "export", "d", (), ("object:b",)),
        ]
    )

    result = compare_leaf_locality(
        cold, edit, cold_text="Alpha law.", edit_text="Beta law."
    )

    assert result["state"] == "verified"
    assert result["claim_made"] is True


def test_changed_leaf_outside_edited_sentence_is_a_violation() -> None:
    cold = _audit(
        [
            _node("object:edited", "object", "a", ((0, 5),)),
            _node("object:escaped", "object", "b", ((11, 17),)),
        ]
    )
    edit = _audit(
        [
            _node("object:edited", "object", "c", ((0, 4),)),
            _node("object:escaped", "object", "d", ((10, 16),)),
        ]
    )

    result = compare_leaf_locality(
        cold,
        edit,
        cold_text="Alpha law. Stable rule.",
        edit_text="Beta law. Stable rule.",
    )

    assert result["state"] == "violated"
    assert result["outside_closure_leaf_count"]["cold"] == 1


def test_ambiguous_source_alignment_is_indeterminate() -> None:
    cold = _audit(
        [
            _node("object:a", "object", "a", ((11, 17),)),
            _node("object:b", "object", "b", ((11, 17),)),
        ]
    )
    edit = _audit(
        [
            _node("object:c", "object", "c", ((10, 16),)),
            _node("object:d", "object", "d", ((10, 16),)),
        ]
    )

    result = compare_leaf_locality(
        cold,
        edit,
        cold_text="Alpha law. Stable rule.",
        edit_text="Beta law. Stable rule.",
    )

    assert result["state"] == "indeterminate"
    assert result["claim_made"] is False
    assert result["matching_ambiguity_by_family"] == {"object": 1}
    assert result["matching_ambiguity_by_multiplicity"] == {"2x2": 1}


def test_structural_occurrence_key_resolves_same_span_multiplicity() -> None:
    cold = _audit(
        [
            _node(
                "object:a", "object", "a", ((11, 17),), occurrence_key="kind-a"
            ),
            _node(
                "object:b", "object", "b", ((11, 17),), occurrence_key="kind-b"
            ),
        ]
    )
    edit = _audit(
        [
            _node(
                "object:c", "object", "a", ((10, 16),), occurrence_key="kind-a"
            ),
            _node(
                "object:d", "object", "b", ((10, 16),), occurrence_key="kind-b"
            ),
        ]
    )

    result = compare_leaf_locality(
        cold,
        edit,
        cold_text="Alpha law. Stable rule.",
        edit_text="Beta law. Stable rule.",
    )

    assert result["matching_ambiguity_count"] == 0
    assert result["matched_leaf_count"] == 2
    assert result["state"] == "verified"


def test_insertion_uses_exact_character_transport_for_unchanged_suffix() -> None:
    cold = _audit(
        [_node("object:a", "object", "a", ((11, 17),), occurrence_key="stable")]
    )
    edit = _audit(
        [_node("object:b", "object", "a", ((16, 22),), occurrence_key="stable")]
    )

    result = compare_leaf_locality(
        cold,
        edit,
        cold_text="Alpha law. Stable rule.",
        edit_text="Alpha PLUS law. Stable rule.",
    )

    assert result["matching_ambiguity_count"] == 0
    assert result["matched_leaf_count"] == 1
    assert result["edit_transport"]["net_character_delta"] == 5
    assert result["transport_match_coverage_by_family"]["cold"]["object"] == {
        "matched_leaf_count": 1,
        "eligible_leaf_count": 1,
        "kappa_delta": 1.0,
    }


def test_source_free_identity_propagates_from_dependency_and_slot() -> None:
    cold = _audit(
        [
            _node("object:a", "object", "a", ((11, 17),), occurrence_key="stable"),
            _node(
                "export:a",
                "export",
                "b",
                (),
                ("object:a",),
                occurrence_key="export-slot:1",
            ),
            _node(
                "proof:a",
                "proof",
                "c",
                (),
                ("object:a",),
                occurrence_key="proof-rule:r",
            ),
        ]
    )
    edit = _audit(
        [
            _node("object:b", "object", "a", ((10, 16),), occurrence_key="stable"),
            _node(
                "export:b",
                "export",
                "d",
                (),
                ("object:b",),
                occurrence_key="export-slot:1",
            ),
            _node(
                "proof:b",
                "proof",
                "e",
                (),
                ("object:b",),
                occurrence_key="proof-rule:r",
            ),
        ]
    )

    result = compare_leaf_locality(
        cold,
        edit,
        cold_text="Alpha law. Stable rule.",
        edit_text="Beta law. Stable rule.",
    )

    assert result["matching_ambiguity_count"] == 0
    assert result["matched_leaf_count"] == 3
    assert result["all_leaf_match_coverage_by_family"]["cold"]["export"][
        "kappa_delta"
    ] == 1.0
    assert result["all_leaf_match_coverage_by_family"]["cold"]["proof"][
        "kappa_delta"
    ] == 1.0


def test_repeated_source_free_ambiguity_is_counted_once() -> None:
    cold = _audit(
        [
            _node("object:a", "object", "a", ((11, 17),), occurrence_key="stable"),
            _node("export:a", "export", "a", (), ("object:a",)),
        ]
    )
    edit = _audit(
        [
            _node("object:b", "object", "a", ((10, 16),), occurrence_key="stable"),
            _node("export:b", "export", "a", (), ("object:b",)),
            _node("export:c", "export", "a", (), ("object:b",)),
        ]
    )

    result = compare_leaf_locality(
        cold,
        edit,
        cold_text="Alpha law. Stable rule.",
        edit_text="Beta law. Stable rule.",
    )

    assert result["state"] == "indeterminate"
    assert result["matching_ambiguity_count"] == 1
    assert result["matching_ambiguous_leaf_count"] == 3
    assert result["matching_ambiguity_by_family"] == {"export": 1}
    assert result["matching_ambiguity_by_multiplicity"] == {"1x2": 1}
