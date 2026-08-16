from __future__ import annotations

from contextlib import contextmanager
import pytest

from src.pnf.numeric_hyperfabric import (
    MdlProfile,
    PromotionEvidence,
    RegionMeasure,
    ResolutionState,
    WorkOperation,
    WorkState,
)
from src.pnf.numeric_operator_composition import (
    NumericFactorSpec,
    NumericObjectSpec,
    NumericSentenceClosure,
    NumericSlotSpec,
)
from src.storage.postgres.numeric_hyperfabric_store import WorkLease
from src.storage.postgres.numeric_sentence_admission import (
    _copy_specs,
    persist_sentence_closure_setwise,
)


def _profile() -> MdlProfile:
    return MdlProfile(max_window=4, beam_width=4)


class _Copy:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self.rows = rows

    def write_row(self, row: tuple[object, ...]) -> None:
        self.rows.append(row)


class _CopyCursor:
    def __init__(self) -> None:
        self.copies: list[list[tuple[object, ...]]] = []
        self.copy_active = False

    @contextmanager
    def copy(self, _query: str):
        if self.copy_active:
            raise AssertionError("a PostgreSQL cursor cannot COPY two streams at once")
        rows: list[tuple[object, ...]] = []
        self.copies.append(rows)
        self.copy_active = True
        try:
            yield _Copy(rows)
        finally:
            self.copy_active = False


def _closure() -> NumericSentenceClosure:
    objects = (
        NumericObjectSpec(
            b"a" * 32,
            10,
            1,
            2,
            1.0,
            2.0,
            3.0,
            PromotionEvidence(1.0, 2.0, 3.0),
        ),
        NumericObjectSpec(
            b"b" * 32,
            10,
            1,
            3,
            4.0,
            5.0,
            6.0,
            PromotionEvidence(4.0, 5.0, 6.0),
        ),
    )
    factors = (
        NumericFactorSpec(
            b"c" * 32,
            4,
            5,
            0,
            0,
            (NumericSlotSpec(6, 10, ResolutionState.CANDIDATE, True),),
            (10,),
            (),
            1.0,
        ),
    )
    return NumericSentenceClosure(
        objects=objects,
        factors=factors,
        demands=(),
        measure=RegionMeasure(0, 0, 0, 0, 0, 0, 0, 0, 0.0),
    )


def test_copy_specs_preserves_ordinal_and_duplicate_token_order() -> None:
    cursor = _CopyCursor()

    _copy_specs(cursor, closure=_closure(), profile=_profile())

    object_rows = cursor.copies[0]
    assert [row[0] for row in object_rows] == [0, 1]
    assert [row[4] for row in object_rows] == [10, 10]
    assert cursor.copies[1][0][-1] == 1.0
    assert cursor.copies[3][0][0:2] == (0, 0)


class _FenceCursor:
    def execute(self, _query: str, _parameters: tuple[object, ...]) -> None:
        return None

    def fetchone(self) -> tuple[object, ...]:
        return (int(WorkState.READY), "other", 4, "run", "document", None, 0)


def test_setwise_admission_rejects_changed_work_fence_before_staging() -> None:
    lease = WorkLease(1, 2, WorkOperation.SENTENCE_CLOSE, "lease", 3)

    with pytest.raises(RuntimeError, match="work fence changed"):
        persist_sentence_closure_setwise(
            _FenceCursor(), lease=lease, closure=_closure(), profile=_profile()
        )
