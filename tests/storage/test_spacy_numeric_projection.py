from __future__ import annotations

import pytest

from src.storage.postgres.spacy_numeric_projection import (
    NumericHeadProjectionError,
    _RawToken,
    _project_numeric_heads,
    _require_numeric_pnf_capabilities,
)


def _token(
    ref: str,
    *,
    start: int,
    end: int,
    head_start: int,
    head_end: int,
    is_root: bool,
) -> _RawToken:
    return _RawToken(
        token_ref=ref,
        token_digest=b"x" * 32,
        sentence_ref="sentence",
        ordinal=0,
        start_char=start,
        end_char=end,
        orth=ref,
        lemma=ref,
        pos="NOUN",
        tag="NN",
        dependency="ROOT" if is_root else "nsubj",
        head_is_self=is_root,
        head_start_char=head_start,
        head_end_char=head_end,
        morphology=(),
    )


def test_explicit_root_and_dependent_head_project() -> None:
    root = _token(
        "root",
        start=10,
        end=14,
        head_start=10,
        head_end=14,
        is_root=True,
    )
    child = _token(
        "child",
        start=0,
        end=5,
        head_start=10,
        head_end=14,
        is_root=False,
    )

    assert _project_numeric_heads(
        (root, child),
        {"root": (101, 10, 14), "child": (102, 0, 5)},
    ) == ((101, 101), (101, 102))


def test_missing_non_root_head_fails_closed() -> None:
    child = _token(
        "child",
        start=0,
        end=5,
        head_start=10,
        head_end=14,
        is_root=False,
    )

    with pytest.raises(
        NumericHeadProjectionError,
        match="declared non-root dependency head is absent",
    ):
        _project_numeric_heads((child,), {"child": (102, 0, 5)})


def test_root_requires_matching_self_span() -> None:
    root = _token(
        "root",
        start=10,
        end=14,
        head_start=0,
        head_end=5,
        is_root=True,
    )

    with pytest.raises(
        NumericHeadProjectionError,
        match="explicit parser root has a non-self head span",
    ):
        _project_numeric_heads((root,), {"root": (101, 10, 14)})


def test_non_root_cannot_resolve_to_its_own_id() -> None:
    token = _token(
        "token",
        start=0,
        end=5,
        head_start=0,
        head_end=5,
        is_root=False,
    )

    with pytest.raises(
        NumericHeadProjectionError,
        match="non-root dependency resolved to its own token id",
    ):
        _project_numeric_heads((token,), {"token": (102, 0, 5)})


def test_strict_numeric_pnf_requires_pos_dependencies_and_sentences() -> None:
    with pytest.raises(
        RuntimeError,
        match="sentence_segmentation, part_of_speech, dependencies",
    ):
        _require_numeric_pnf_capabilities(
            {
                "tokenization": True,
                "sentence_segmentation": False,
                "part_of_speech": False,
                "dependencies": False,
            }
        )


def test_strict_capability_boundary_accepts_required_annotations() -> None:
    _require_numeric_pnf_capabilities(
        {
            "sentence_segmentation": True,
            "part_of_speech": True,
            "dependencies": True,
        }
    )
