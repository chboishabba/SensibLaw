from __future__ import annotations

from src.pnf.parser_delta_executor import (
    CanonicalParserRegion,
    PresegmentedRegionParserExecutor,
)


def _parser(text: str) -> dict[str, object]:
    token = {
        "index": 0,
        "text": text,
        "lemma": text.casefold(),
        "pos": "NOUN",
        "dep": "ROOT",
        "head_index": 0,
        "start": 0,
        "end": len(text),
    }
    return {
        "sents": [{"tokens": [token]}],
        "parser_receipt": {"contract_ref": "parser:test:v1"},
    }


def test_presegmented_executor_restores_global_coordinates() -> None:
    regions = (
        CanonicalParserRegion(
            document_ref="document:1",
            region_ref="section:1",
            sequence_no=0,
            canonical_text="Alpha",
            char_start=0,
            char_end=5,
            token_start=0,
            token_count=1,
        ),
        CanonicalParserRegion(
            document_ref="document:1",
            region_ref="section:2",
            sequence_no=1,
            canonical_text="Beta",
            char_start=5,
            char_end=9,
            token_start=1,
            token_count=1,
        ),
    )
    executor = PresegmentedRegionParserExecutor(
        regions=regions,
        workers=2,
        parser=_parser,
    )
    result = executor.execute(
        document_ref="document:1",
        canonical_text="AlphaBeta",
    )

    assert [row.token_start for row in result.deltas] == [0, 1]
    assert [row.char_start for row in result.deltas] == [0, 5]
    assert result.to_dict()["physical_completion_order_semantic_effect"] == "none"
