"""SLR-owned source parser -> Leech grammar-observation JSONL contract.

Export boundary, NOT a second spaCy implementation and NOT evidential/world
admission. Reads original typed PostgreSQL numeric parser rows, refuses
incomplete parser coverage, missing source bytes, mixed model contracts,
uncommitted/cross-sentence dependency heads and reserved/test partitions.

The caller supplies the *same immutable source text* under explicit
train/development split; database SHA256 must match exactly. Database-local
BIGINT IDs retain their original identity. Leech compacts them using train
documents only. This is an export, never a hot-path PNF computation.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

SOURCE_SQL = """
SELECT source_ref, content_sha256, byte_count, encoding_ref
FROM execution.semantic_parser_source
WHERE run_ref = %s AND document_ref = %s
ORDER BY source_ref
"""
COVERAGE_SQL = """
SELECT state, total_partitions, completed_partitions, open_boundary_obligations,
       part_of_speech, dependencies, morphology
FROM execution.semantic_parser_document_coverage
WHERE run_ref = %s AND document_ref = %s
"""
PARTITION_SQL = """
SELECT p.partition_ref, p.parser_contract_ref, p.state,
       r.receipt_sha256, r.model_name, r.model_version
FROM execution.semantic_parser_partition AS p
LEFT JOIN execution.semantic_parser_partition_receipt AS r
       ON r.partition_ref = p.partition_ref
WHERE p.run_ref = %s AND p.document_ref = %s AND p.source_ref = %s
ORDER BY p.sequence_no, p.partition_ref
"""
TOKEN_SQL = """
SELECT t.token_id, t.start_char, t.end_char, t.pos_symbol_id,
       t.dependency_symbol_id, t.morph_set_id, t.head_token_id,
       t.sentence_id, t.token_digest, t.representation_version
FROM execution.semantic_parser_token AS t
WHERE t.run_ref = %s AND t.document_ref = %s
ORDER BY t.start_char, t.end_char, t.token_id
"""

SCHEMA = "slr.numeric_spacy.leech_grammar.v1"
DOC_RECEIPT_DOMAIN = "slr-leech-grammar-document-receipt-v1"
CONTRACT_DOMAIN = "slr-leech-grammar-parser-contract-v1"


def _bytes32(value: Any, name: str) -> bytes:
    if not isinstance(value, (bytes, bytearray, memoryview)) or len(value) != 32:
        raise ValueError(name + " requires actual 32-byte source digest")
    return bytes(value)


def _hash_canonical(value: Mapping[str, Any]) -> str:
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                             separators=(",", ":")).encode("utf-8")).hexdigest()


def build_leech_grammar_observation(
    *, run_ref: str, document_ref: str, split: str, source_text: str,
    source_rows: Sequence[tuple], coverage_rows: Sequence[tuple],
    partition_rows: Sequence[tuple], token_rows: Sequence[tuple],
) -> dict[str, Any]:
    """Pure strict projection from source PostgreSQL rows; no inferred facts."""
    if split not in ("train", "development"):
        raise ValueError("only train/development; no reserved/holdout/F5 export")
    if not isinstance(source_text, str) or not source_text:
        raise ValueError("nonempty immutable source text required")
    if not all(isinstance(v,str) and v for v in (run_ref,document_ref)):
        raise ValueError("original run and document refs required")
    if len(source_rows)!=1:
        raise ValueError("exactly one original source revision required")
    source_ref,digest,byte_count,encoding=source_rows[0]
    if not isinstance(source_ref,str) or not source_ref:
        raise ValueError("missing source occurrence ref")
    source_bytes=source_text.encode("utf-8")
    digest=_bytes32(digest,"semantic_parser_source.content_sha256")
    if (sha256(source_bytes).digest()!=digest or byte_count!=len(source_bytes)
        or encoding!="utf8-canonical-source:v1"):
        raise ValueError("source bytes/SHA/encoding disagree with SLR authority")
    if len(coverage_rows)!=1:
        raise ValueError("exactly one parser document coverage row required")
    state,total,completed,open_boundary,pos,dep,morph=coverage_rows[0]
    if (state!="complete" or type(total)!=int or total<1 or
        completed!=total or open_boundary!=0 or
        not (pos and dep and morph)):
        raise ValueError("parser coverage or required capabilities incomplete")
    if len(partition_rows)!=total:
        raise ValueError("parser partition count differs from closed coverage")
    model_contracts=set()
    partition_receipts=[]
    for partition_ref,contract,partition_state,receipt,model_name,model_version in partition_rows:
        if partition_state!="completed" or not all(
            isinstance(v,str) and v for v in
            (partition_ref,contract,model_name,model_version)):
            raise ValueError("incomplete partition or missing parser model provenance")
        r=_bytes32(receipt,"parser partition receipt")
        model_contracts.add((contract,model_name,model_version))
        partition_receipts.append(dict(partition_ref=partition_ref,
                                       receipt_sha256=r.hex()))
    if len(model_contracts)!=1:
        raise ValueError("mixed parser contracts/models in original source")
    contract,model_name,model_version=next(iter(model_contracts))
    if not token_rows:
        raise ValueError("zero numeric parser observations")
    tokens=[]
    token_by_id={}
    previous_end=0
    for row in token_rows:
        (token_id,start,end,pos_id,dependency_id,morph_id,head_id,
         sentence_id,token_digest,representation)=row
        if (representation!=2 or
            any(type(x)!=int or x<1 for x in (token_id,sentence_id)) or
            type(start)!=int or type(end)!=int or
            start<previous_end or start<0 or end<=start or end>len(source_text)):
            raise ValueError("invalid source-ordered numeric token/span/representation")
        if any(v is not None and (type(v)!=int or v<1) for v in
               (pos_id,dependency_id,morph_id,head_id)):
            raise ValueError("malformed SLR parser symbol/head ID")
        if pos_id is None or dependency_id is None or head_id is None:
            raise ValueError("declared parser POS/dependency/head capability missing")
        _bytes32(token_digest,"original token digest")
        if token_id in token_by_id:
            raise ValueError("duplicate original SLR token occurrence")
        token_by_id[token_id]=sentence_id
        tokens.append(dict(token_id=token_id,start_char=start,end_char=end,
                           pos_symbol_id=pos_id,dependency_id=dependency_id,
                           morph_set_id=morph_id,head_token_id=head_id))
        previous_end=end
    for token in tokens:
        head=token["head_token_id"]
        if head not in token_by_id or token_by_id[head]!=token_by_id[token["token_id"]]:
            raise ValueError("head must be committed within same original sentence")
    parser_contract_sha=_hash_canonical(dict(domain=CONTRACT_DOMAIN,
        parser_contract_ref=contract,model_name=model_name,
        model_version=model_version))
    parser_receipt_sha=_hash_canonical(dict(domain=DOC_RECEIPT_DOMAIN,
        run_ref=run_ref,document_ref=document_ref,source_sha256=digest.hex(),
        parser_contract_sha256=parser_contract_sha,
        partition_receipts=partition_receipts))
    return dict(schema_version=SCHEMA,document_id=document_ref,split=split,
        source_text=source_text,source_sha256=digest.hex(),
        parser_contract_sha256=parser_contract_sha,
        parser_receipt_sha256=parser_receipt_sha,
        visibility="full_context",slr_tokens=tokens,
        slr_source_ref=source_ref,slr_run_ref=run_ref,
        slr_parser_contract_ref=contract,slr_parser_model_name=model_name,
        slr_parser_model_version=model_version,
        slr_partition_receipts=partition_receipts,
        world_resolution_deferred=True,
        parser_observation_is_semantic_authority=False,
        cross_document_identity_closed=False)


def query_leech_grammar_observation(
    *, database_url: str, run_ref: str, document_ref: str,
    source_text: str, split: str,
) -> dict[str, Any]:
    """Read one snapshot of SLR PostgreSQL truth (caller owns source text)."""
    from src.storage.postgres.spacy_parser_model import connect
    conn=connect(database_url)
    try:
        with conn.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            def read(sql,params):
                cursor.execute(sql,params)
                return tuple(cursor.fetchall())
            args=(run_ref,document_ref)
            source=read(SOURCE_SQL,args)
            # Full validation before following the source revision into
            # partition rows; a second revision is explicitly rejected.
            if len(source)!=1:
                raise ValueError("ambiguous original source occurrence")
            coverage=read(COVERAGE_SQL,args)
            partitions=read(PARTITION_SQL,(*args,source[0][0]))
            tokens=read(TOKEN_SQL,args)
            return build_leech_grammar_observation(
                run_ref=run_ref,document_ref=document_ref,split=split,
                source_text=source_text,source_rows=source,
                coverage_rows=coverage,partition_rows=partitions,
                token_rows=tokens)
    finally:
        conn.close()
