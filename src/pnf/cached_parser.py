"""Content-addressed parser execution with immutable reuse receipts."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from src.pnf.stage_build_keys import stage_build_key
from src.pnf.stage_cache import (
    StageCache,
    StageCacheEntry,
    StageReuseReceipt,
)
from src.policy.carriers.canonical import canonical_sha256


CACHED_PARSER_CONTRACT = "cached-parser-stage:v0_1"


def parse_with_stage_cache(
    *,
    document_ref: str,
    canonical_text_digest: str,
    parser_contract_ref: str,
    parser: Callable[[], Mapping[str, Any]],
    cache: StageCache,
) -> tuple[dict[str, Any], StageReuseReceipt]:
    """Load or execute one parser stage without changing semantic output identity."""

    key = stage_build_key(
        "parser",
        inputs=(canonical_text_digest,),
        contract_ref=parser_contract_ref,
    )
    cached = cache.load(key)
    if cached is not None:
        if cached.document_ref != document_ref:
            raise ValueError("parser stage cache entry crosses document identity")
        receipt = StageReuseReceipt(
            document_ref=document_ref,
            stage="parser",
            stage_build_key=key,
            reused=True,
            source_output_ref=cached.output_ref,
        )
        return dict(cached.output_payload), receipt

    parsed = dict(parser())
    output_ref = "parser-output:" + canonical_sha256(
        {
            "document_ref": document_ref,
            "parser_contract_ref": parser_contract_ref,
            "parsed_document": parsed,
        }
    )
    entry = StageCacheEntry(
        stage_build_key=key,
        document_ref=document_ref,
        stage="parser",
        contract_ref=parser_contract_ref,
        input_refs=(canonical_text_digest,),
        declaration_refs=(),
        output_ref=output_ref,
        output_payload=parsed,
    )
    cache.persist(entry)
    receipt = StageReuseReceipt(
        document_ref=document_ref,
        stage="parser",
        stage_build_key=key,
        reused=False,
        source_output_ref=output_ref,
    )
    return parsed, receipt


__all__ = ["CACHED_PARSER_CONTRACT", "parse_with_stage_cache"]
