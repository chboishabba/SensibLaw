from __future__ import annotations

from src.runtime.numeric_semantic_leaf_locality import compare_leaf_locality


def _audit(nodes):
    return {
        "schema_version": "sensiblaw.numeric-semantic-leaf-audit.v1",
        "parser_sentence_spans": [[0, 10], [11, 23]],
        "nodes": nodes,
    }


def _node(ref, family, digest, spans=(), dependencies=()):
    return {
        "ref": ref,
        "family": family,
        "digest_sha256": digest * 64,
        "source_spans": [list(span) for span in spans],
        "dependencies": list(dependencies),
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
