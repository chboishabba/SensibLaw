from __future__ import annotations

from pathlib import Path
import re


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return source.replace(old, new, 1)


def patch_projection() -> None:
    path = Path("src/storage/postgres/spacy_numeric_projection.py")
    source = path.read_text(encoding="utf-8")
    if "class NumericHeadProjectionError" in source:
        return

    source = replace_once(
        source,
        "from typing import Any\n",
        "from typing import Any, Mapping\n",
        "projection typing import",
    )
    source = replace_once(
        source,
        "\n\n@dataclass(frozen=True, slots=True)\nclass _RawSentence:",
        '\n\nclass NumericHeadProjectionError(RuntimeError):\n'
        '    """A declared non-root dependency head was not committed."""\n\n\n'
        "@dataclass(frozen=True, slots=True)\nclass _RawSentence:",
        "projection exception",
    )
    source = replace_once(
        source,
        "    dependency: str\n    head_start_char: int\n",
        "    dependency: str\n    head_is_self: bool\n    head_start_char: int\n",
        "raw root evidence",
    )
    source = replace_once(
        source,
        "                    dependency=str(token.dep_),\n"
        "                    head_start_char=head_start,\n",
        "                    dependency=str(token.dep_),\n"
        "                    head_is_self=bool(token.head == token),\n"
        "                    head_start_char=head_start,\n",
        "collect root evidence",
    )

    helper = '''


def _project_numeric_heads(
    raw_tokens: tuple[_RawToken, ...],
    token_rows_by_ref: Mapping[str, tuple[int, int, int]],
) -> tuple[tuple[int, int], ...]:
    """Resolve dependency heads without inventing root self-loops."""

    token_id_by_span: dict[tuple[int, int], int] = {}
    for token_id, start_char, end_char in token_rows_by_ref.values():
        span = (start_char, end_char)
        previous = token_id_by_span.setdefault(span, token_id)
        if previous != token_id:
            raise NumericHeadProjectionError(
                f"duplicate committed token span {span!r}"
            )

    updates: list[tuple[int, int]] = []
    for raw in raw_tokens:
        committed = token_rows_by_ref.get(raw.token_ref)
        if committed is None:
            raise NumericHeadProjectionError(
                f"numeric token row missing for {raw.token_ref}"
            )
        token_id, start_char, end_char = committed
        token_span = (start_char, end_char)
        head_span = (raw.head_start_char, raw.head_end_char)
        if raw.head_is_self:
            if head_span != token_span:
                raise NumericHeadProjectionError(
                    "explicit parser root has a non-self head span: "
                    f"token={token_span!r} head={head_span!r}"
                )
            head_token_id = token_id
        else:
            head_token_id = token_id_by_span.get(head_span)
            if head_token_id is None:
                raise NumericHeadProjectionError(
                    "declared non-root dependency head is absent: "
                    f"token={token_span!r} head={head_span!r}"
                )
            if head_token_id == token_id:
                raise NumericHeadProjectionError(
                    "non-root dependency resolved to its own token id"
                )
        updates.append((head_token_id, token_id))
    return tuple(updates)
'''
    source = replace_once(
        source,
        "\n\ndef _collect_doc(\n",
        helper + "\n\ndef _collect_doc(\n",
        "head helper insertion",
    )
    source = replace_once(
        source,
        "                    SELECT token_ref, token_id, start_char\n",
        "                    SELECT token_ref, token_id, start_char, end_char\n",
        "head span query",
    )

    pattern = re.compile(
        r"                token_rows_by_ref = \{.*?"
        r"\n                entity_rows = \[",
        re.DOTALL,
    )
    replacement = '''                token_rows_by_ref = {
                    str(token_ref): (
                        int(token_id),
                        int(start_char),
                        int(end_char),
                    )
                    for token_ref, token_id, start_char, end_char
                    in cursor.fetchall()
                }
                cursor.executemany(
                    """
                    UPDATE execution.semantic_parser_token
                       SET head_token_id = %s
                     WHERE token_id = %s
                    """,
                    _project_numeric_heads(raw_tokens, token_rows_by_ref),
                )

                entity_rows = ['''
    source, count = pattern.subn(replacement, source, count=1)
    if count != 1:
        raise RuntimeError(
            f"head projection block: expected one match, found {count}"
        )
    source = source.replace(
        '__all__ = ["commit_numeric_doc"]',
        '__all__ = ["NumericHeadProjectionError", "commit_numeric_doc"]',
    )
    if "token_id_by_start.get" in source:
        raise RuntimeError("silent head fallback remains")
    path.write_text(source, encoding="utf-8")


def patch_sentence_loader() -> None:
    path = Path("src/storage/postgres/numeric_hyperfabric_store.py")
    source = path.read_text(encoding="utf-8")
    if "numeric sentence region lacks a parser capability receipt" in source:
        return

    marker = '''def _load_sentence_tokens(
    cursor: Any,
    region_id: int,
) -> tuple[NumericToken, ...]:
    cursor.execute(
'''
    replacement = '''def _load_sentence_tokens(
    cursor: Any,
    region_id: int,
) -> tuple[NumericToken, ...]:
    cursor.execute(
        """
        SELECT receipt.dependencies, receipt.part_of_speech
          FROM execution.semantic_pnf_sentence_region AS link
          JOIN execution.semantic_parser_sentence AS sentence
            ON sentence.sentence_id = link.sentence_id
          JOIN execution.semantic_parser_partition_receipt AS receipt
            ON receipt.partition_ref = sentence.partition_ref
         WHERE link.region_id = %s
        """,
        (region_id,),
    )
    capability = cursor.fetchone()
    if capability is None:
        raise RuntimeError(
            "numeric sentence region lacks a parser capability receipt"
        )
    if not bool(capability[0]):
        raise RuntimeError(
            "numeric sentence closure requires dependency annotations"
        )
    if not bool(capability[1]):
        raise RuntimeError("numeric sentence closure requires POS annotations")
    cursor.execute(
'''
    source = replace_once(source, marker, replacement, "sentence capability gate")
    source = replace_once(
        source,
        "    rows = cursor.fetchall()\n    tokens = tuple(\n",
        "    rows = cursor.fetchall()\n"
        "    missing_head_ids = tuple(int(row[0]) for row in rows if row[6] is None)\n"
        "    if missing_head_ids:\n"
        "        raise RuntimeError(\n"
        "            \"numeric sentence contains unprojected dependency heads: \"\n"
        "            f\"{missing_head_ids!r}\"\n"
        "        )\n"
        "    tokens = tuple(\n",
        "reject nullable heads",
    )
    source = replace_once(
        source,
        "            head_token_id=int(row[6] or row[0]),\n",
        "            head_token_id=int(row[6]),\n",
        "remove load fallback",
    )
    path.write_text(source, encoding="utf-8")


def patch_planner() -> None:
    path = Path("src/storage/postgres/numeric_hierarchy_planner.py")
    source = path.read_text(encoding="utf-8")
    if "class _SketchState" in source:
        return

    start = source.index("def plan_interface_segments(\n")
    end = source.index("\n\ndef _load_paragraph_sketches(", start)
    planner = '''@dataclass(frozen=True, slots=True)
class _SketchState:
    total_cost: float
    segment: PlannedSegment | None
    previous: "_SketchState | None"
    segment_count: int
    serial: int


def _unwind_planned_segments(
    state: _SketchState,
) -> tuple[PlannedSegment, ...]:
    segments: list[PlannedSegment] = []
    current: _SketchState | None = state
    while current is not None and current.segment is not None:
        segments.append(current.segment)
        current = current.previous
    segments.reverse()
    return tuple(segments)


def plan_interface_segments(
    sketches: Sequence[InterfaceSketch],
    *,
    profile: MdlProfile,
) -> SketchSegmentation:
    """Windowed beam DP with constant-size predecessor cells.

    Candidate-state count is O(N * W * B) and retained DP state is O(N * B).
    Exact key-set union cost remains proportional to the bounded planning
    window's interface-sketch cardinality.
    """

    if not sketches:
        return SketchSegmentation((), 0.0, 0, 0)
    n = len(sketches)
    window = min(profile.max_window, n)
    beam = profile.beam_width
    root = _SketchState(0.0, None, None, 0, 0)
    paths: list[list[_SketchState]] = [[] for _ in range(n + 1)]
    paths[0] = [root]
    evaluations = 0
    serial = 1

    for end in range(1, n + 1):
        candidates: list[_SketchState] = []
        aggregate: InterfaceSketch | None = None
        raw_demand_count = 0
        for start in range(end - 1, max(-1, end - window - 1), -1):
            sketch = sketches[start]
            aggregate = sketch if aggregate is None else sketch.join(aggregate)
            raw_demand_count += len(sketch.demand_keys)
            child_count = end - start
            measure = aggregate.measure(
                child_count=child_count,
                raw_demand_count=raw_demand_count,
            )
            local_cost = description_length(measure, profile)
            if child_count > 1:
                local_cost += profile.merge_threshold
            if not isfinite(local_cost):
                raise ValueError("interface-sketch MDL cost must be finite")
            segment = PlannedSegment(start, end, local_cost, measure)
            for prior in paths[start][:beam]:
                candidates.append(
                    _SketchState(
                        total_cost=prior.total_cost + local_cost,
                        segment=segment,
                        previous=prior,
                        segment_count=prior.segment_count + 1,
                        serial=serial,
                    )
                )
                serial += 1
                evaluations += 1
        candidates.sort(
            key=lambda state: (
                state.total_cost,
                state.segment_count,
                state.segment.start if state.segment else -1,
                state.serial,
            )
        )
        paths[end] = candidates[:beam]

    best = paths[n][0]
    return SketchSegmentation(
        segments=_unwind_planned_segments(best),
        total_cost=best.total_cost,
        evaluated_candidates=evaluations,
        asymptotic_bound=n * window * beam,
    )
'''
    source = source[:start] + planner + source[end:]
    if "*prior_segments" in source:
        raise RuntimeError("copied planner path remains")
    path.write_text(source, encoding="utf-8")


def patch_operator_composition() -> None:
    path = Path("src/pnf/numeric_operator_composition.py")
    source = path.read_text(encoding="utf-8")
    if "children_by_head: dict[int, list[NumericToken]]" in source:
        return

    old = '''def _children(
    token_id: int,
    tokens: Sequence[NumericToken],
) -> tuple[NumericToken, ...]:
    return tuple(token for token in tokens if token.head_token_id == token_id)


def _subject_and_object(
    head: NumericToken,
    tokens: Sequence[NumericToken],
    lexicon: OperatorLexicon,
) -> tuple[NumericToken | None, NumericToken | None]:
    children = _children(head.token_id, tokens)
'''
    new = '''def _subject_and_object(
    children: Sequence[NumericToken],
    lexicon: OperatorLexicon,
) -> tuple[NumericToken | None, NumericToken | None]:
'''
    source = replace_once(source, old, new, "dependency adjacency helper")
    source = replace_once(
        source,
        "    token_by_id = {token.token_id: token for token in tokens}\n"
        "    objects: dict[int, NumericObjectSpec] = {}\n",
        "    token_by_id = {token.token_id: token for token in tokens}\n"
        "    children_by_head: dict[int, list[NumericToken]] = {}\n"
        "    for token in tokens:\n"
        "        children_by_head.setdefault(token.head_token_id, []).append(token)\n"
        "    objects: dict[int, NumericObjectSpec] = {}\n",
        "build dependency adjacency",
    )
    source = source.replace(
        "_subject_and_object(head, tokens, lexicon)",
        "_subject_and_object(children_by_head.get(head.token_id, ()), lexicon)",
    )
    source = source.replace(
        "_subject_and_object(predicate, tokens, lexicon)",
        "_subject_and_object(\n"
        "            children_by_head.get(predicate.token_id, ()), lexicon\n"
        "        )",
    )
    old = '''        negation = next(
            (
                token
                for token in tokens
                if token.lemma_id in negation_lemmas
                and token.head_token_id in {head.token_id, modal.token_id}
            ),
            None,
        )'''
    new = '''        negation = next(
            (
                token
                for head_id in (head.token_id, modal.token_id)
                for token in children_by_head.get(head_id, ())
                if token.lemma_id in negation_lemmas
            ),
            None,
        )'''
    source = replace_once(source, old, new, "indexed negation")
    path.write_text(source, encoding="utf-8")


def add_tests() -> None:
    projection_test = Path("tests/storage/test_spacy_numeric_projection.py")
    projection_test.write_text(
        '''from __future__ import annotations

import pytest

from src.storage.postgres.spacy_numeric_projection import (
    NumericHeadProjectionError,
    _RawToken,
    _project_numeric_heads,
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
        "root", start=10, end=14,
        head_start=10, head_end=14, is_root=True,
    )
    child = _token(
        "child", start=0, end=5,
        head_start=10, head_end=14, is_root=False,
    )
    assert _project_numeric_heads(
        (root, child),
        {"root": (101, 10, 14), "child": (102, 0, 5)},
    ) == ((101, 101), (101, 102))


def test_missing_non_root_head_fails_closed() -> None:
    child = _token(
        "child", start=0, end=5,
        head_start=10, head_end=14, is_root=False,
    )
    with pytest.raises(
        NumericHeadProjectionError,
        match="declared non-root dependency head is absent",
    ):
        _project_numeric_heads((child,), {"child": (102, 0, 5)})


def test_root_requires_matching_self_span() -> None:
    root = _token(
        "root", start=10, end=14,
        head_start=0, head_end=5, is_root=True,
    )
    with pytest.raises(
        NumericHeadProjectionError,
        match="explicit parser root has a non-self head span",
    ):
        _project_numeric_heads((root,), {"root": (101, 10, 14)})
''',
        encoding="utf-8",
    )

    planner_test = Path("tests/storage/test_numeric_hierarchy_planner.py")
    tests = planner_test.read_text(encoding="utf-8")
    if "test_beam_cells_store_constant_size_backpointers" not in tests:
        tests += '''


def test_beam_cells_store_constant_size_backpointers() -> None:
    from src.storage.postgres import numeric_hierarchy_planner as planner

    assert set(planner._SketchState.__slots__) == {
        "total_cost",
        "segment",
        "previous",
        "segment_count",
        "serial",
    }
    assert "segments" not in planner._SketchState.__slots__
'''
        planner_test.write_text(tests, encoding="utf-8")


def main() -> None:
    patch_projection()
    patch_sentence_loader()
    patch_planner()
    patch_operator_composition()
    add_tests()


if __name__ == "__main__":
    main()
