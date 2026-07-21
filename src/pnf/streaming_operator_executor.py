"""Sentence-delta adapter for streaming generic operator composition.

The public parser may still return a complete document record, but this adapter exposes
that record as immutable sentence batches. Each complete sentence activates an
independent revision-bound operator-composition job. Jobs may execute concurrently and
stream proposal receipts back to the keyed document owner.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.language.operator_composition import (
    OPERATOR_COMPOSITION_CONTRACT,
    compose_operator_factors,
)
from src.pnf.factor_proposals import FactorProposal
from src.pnf.streaming_fixed_point import (
    CoverageNotice,
    ObservationDelta,
    PythonClosureExecutor,
    SolverJob,
    StreamingDeclaration,
    StreamingSemanticOwner,
    execute_ready_jobs,
)
from src.policy.carriers.canonical import canonical_sha256


STREAMING_OPERATOR_DECLARATION_REF = (
    "streaming-declaration:operator-composition:v0_1"
)
STREAMING_OPERATOR_ADAPTER_REF = (
    "parser-delta-adapter:operator-composition:v0_1"
)


def _observation_ref(
    document_ref: str,
    sentence_index: int,
    token: Mapping[str, Any],
) -> str:
    return "parser-observation:" + canonical_sha256(
        {
            "document_ref": document_ref,
            "sentence_index": sentence_index,
            "index": int(token.get("index", -1)),
            "start": int(token.get("start", 0)),
            "end": int(token.get("end", 0)),
            "lemma": str(token.get("lemma") or token.get("text") or ""),
            "dependency": str(token.get("dep") or ""),
            "head_index": int(token.get("head_index", -1)),
        }
    )


def parser_sentence_deltas(
    *,
    document_ref: str,
    parsed_document: Mapping[str, Any],
) -> tuple[ObservationDelta, ...]:
    """Project parser sentences into stable, complete semantic observation batches."""

    deltas: list[ObservationDelta] = []
    token_cursor = 0
    for sentence_index, sentence in enumerate(
        parsed_document.get("sents") or ()
    ):
        tokens = tuple(dict(row) for row in sentence.get("tokens") or ())
        if not tokens:
            continue
        observations: list[dict[str, Any]] = []
        observation_refs: list[str] = []
        for token in tokens:
            ref = _observation_ref(document_ref, sentence_index, token)
            observation_refs.append(ref)
            observations.append(
                {
                    "observation_ref": ref,
                    "observation_type": "parser.token",
                    "sentence_index": sentence_index,
                    "token": token,
                    "authority": "parser_observation_only",
                }
            )
        observation_refs = sorted(set(observation_refs))
        char_start = min(int(row.get("start", 0)) for row in tokens)
        char_end = max(int(row.get("end", char_start)) for row in tokens)
        scope_ref = f"document-sentence:{document_ref}:{sentence_index}"
        batch_ref = "parser-sentence-batch:" + canonical_sha256(
            {
                "document_ref": document_ref,
                "sentence_index": sentence_index,
                "observation_refs": observation_refs,
            }
        )
        deltas.append(
            ObservationDelta(
                document_ref=document_ref,
                batch_ref=batch_ref,
                scope_ref=scope_ref,
                sequence_no=sentence_index,
                parser_contract=str(
                    (parsed_document.get("parser_receipt") or {}).get(
                        "contract_ref"
                    )
                    or STREAMING_OPERATOR_ADAPTER_REF
                ),
                observation_refs=tuple(observation_refs),
                observations=tuple(observations),
                token_start=token_cursor,
                token_end=token_cursor + len(tokens),
                char_start=char_start,
                char_end=char_end,
                token_count=len(tokens),
                coverage_barrier="sentence",
                coverage_complete=True,
            )
        )
        token_cursor += len(tokens)
    return tuple(deltas)


def operator_streaming_declaration() -> StreamingDeclaration:
    return StreamingDeclaration(
        declaration_ref=STREAMING_OPERATOR_DECLARATION_REF,
        producer_ref=OPERATOR_COMPOSITION_CONTRACT,
        requires=("parser.token",),
        optional=(),
        emits=(
            "semantic.normative_relation",
            "semantic.legal_condition",
            "semantic.legal_exception",
            "semantic.legal_transition",
        ),
        scope_kind="sentence",
        coverage_barrier="sentence",
        affected_index="semantic.operator_composition",
        declaration_revision="v0_1",
        priority=40,
    )


def _proposal_from_factor(
    *,
    document_ref: str,
    factor: Mapping[str, Any],
    observation_refs: Sequence[str],
) -> FactorProposal:
    metadata = dict(factor.get("metadata") or {})
    alternatives = [
        dict(row)
        for row in factor.get("alternatives") or ()
        if isinstance(row, Mapping)
    ]
    provenance_refs = tuple(
        sorted(
            set(str(ref) for ref in metadata.get("provenance_refs") or ())
            | set(str(ref) for ref in observation_refs)
        )
    )
    return FactorProposal(
        document_ref=document_ref,
        source_revision_ref="source-revision:"
        + canonical_sha256(
            {
                "document_ref": document_ref,
                "observation_refs": sorted(set(observation_refs)),
            }
        ),
        factor_type_ref=str(factor.get("factor_type") or ""),
        source_span_refs=tuple(
            str(ref) for ref in metadata.get("provenance_refs") or ()
        ),
        input_observation_refs=tuple(
            sorted(set(str(ref) for ref in observation_refs))
        ),
        dependency_factor_refs=(),
        structural_signature=str(
            metadata.get("structural_signature_ref") or ""
        ),
        role_bindings=dict(metadata.get("role_bindings") or {}),
        qualifier_state=dict(metadata.get("qualifier_state") or {}),
        producer_contract=str(
            metadata.get("composition_contract_ref")
            or OPERATOR_COMPOSITION_CONTRACT
        ),
        declaration_revision="v0_1",
        candidate_payload={
            "source_factor_ref": str(factor.get("factor_ref") or ""),
            "predicate_ref": str(metadata.get("predicate_ref") or ""),
            "alternatives": alternatives,
            "provenance_refs": list(provenance_refs),
        },
        residuals=tuple(
            str(value) for value in factor.get("residuals") or ()
        ),
    )


def solve_operator_job(job: SolverJob) -> tuple[FactorProposal, ...]:
    """Pure closure handler for one complete sentence observation delta."""

    delta = dict(job.input_payload.get("observation_delta") or {})
    observations = tuple(delta.get("observations") or ())
    tokens = [
        dict(row.get("token") or {})
        for row in observations
        if str(row.get("observation_type") or "") == "parser.token"
    ]
    factors = compose_operator_factors(
        document_ref=job.owner_key.document_ref,
        parsed_document={
            "sents": [{"tokens": tokens}],
            "parser_receipt": {
                "source": "streaming_observation_delta",
                "reparsed": False,
            },
        },
    )
    return tuple(
        _proposal_from_factor(
            document_ref=job.owner_key.document_ref,
            factor=factor.to_dict(),
            observation_refs=job.input_refs,
        )
        for factor in factors
    )


def build_streaming_operator_state(
    *,
    document_ref: str,
    parsed_document: Mapping[str, Any],
    closure_workers: int = 2,
    partition_count: int = 1,
) -> StreamingSemanticOwner:
    """Run sentence jobs concurrently and return the converged keyed owner state."""

    owner = StreamingSemanticOwner(
        document_ref=document_ref,
        partition_count=partition_count,
    )
    declaration = operator_streaming_declaration()
    owner.register_declarations((declaration,))
    for delta in parser_sentence_deltas(
        document_ref=document_ref,
        parsed_document=parsed_document,
    ):
        owner.admit_observation_delta(delta)
    executor = PythonClosureExecutor(
        {STREAMING_OPERATOR_DECLARATION_REF: solve_operator_job}
    )
    execute_ready_jobs(owner, executor, workers=closure_workers)
    owner.reduce_dirty_groups()
    owner.admit_coverage_notice(
        CoverageNotice(
            document_ref=document_ref,
            scope_ref="document-global",
            barrier="document",
            state="complete",
            evidence_refs=tuple(
                delta.delta_ref for delta in owner.ledger.observation_deltas
            ),
        )
    )
    return owner


__all__ = [
    "STREAMING_OPERATOR_ADAPTER_REF",
    "STREAMING_OPERATOR_DECLARATION_REF",
    "build_streaming_operator_state",
    "operator_streaming_declaration",
    "parser_sentence_deltas",
    "solve_operator_job",
]
