"""Representative normalized operator closure rules for backend parity benchmarks.

This lane is deliberately separate from the production operator composer.  It exercises
modality/polarity, condition, exception, and transition closure over one immutable sentence
job, producing the same content-addressed proposals through a Python handler or Zelph rule
execution.  Equality here qualifies a backend for further measurement; it does not promote
it into production or confer semantic authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from src.pnf.factor_proposals import FactorProposal
from src.pnf.streaming_fixed_point import SolverJob
from src.policy.carriers.canonical import canonical_sha256


NORMALIZED_OPERATOR_CONTRACT = "normalized-operator-closure:v0_1"
NORMALIZED_OPERATOR_RULE_SET_REVISION = "v0_1"

_MODAL = {
    "must": ("obligation", "normative.obligation"),
    "shall": ("obligation", "normative.obligation"),
    "may": ("permission_candidate", "normative.permission_candidate"),
}
_CONDITIONS = {"if", "when", "provided", "providing"}
_EXCEPTIONS = {"unless", "except", "excluding"}
_TRANSITIONS = {
    "commence": "legal.commencement",
    "begin": "legal.commencement_candidate",
    "repeal": "legal.repeal",
    "amend": "legal.amendment",
    "cease": "legal.cessation",
}


def _tokens(job: SolverJob) -> tuple[dict[str, Any], ...]:
    delta = job.input_payload.get("observation_delta") or {}
    return tuple(
        dict(row.get("token") or {})
        for row in delta.get("observations") or ()
        if str(row.get("observation_type") or "") == "parser.token"
    )


def _lemma(token: Mapping[str, Any]) -> str:
    return str(token.get("lemma") or token.get("text") or "").casefold()


def _candidate_node(identity: Mapping[str, Any]) -> str:
    return "candidate_" + canonical_sha256(identity)[:24]


@dataclass(frozen=True)
class OperatorCandidate:
    node: str
    proposal: FactorProposal
    kind: str
    polarity: str = "none"


def normalized_operator_candidates(job: SolverJob) -> tuple[OperatorCandidate, ...]:
    tokens = _tokens(job)
    by_index = {int(row.get("index", -1)): row for row in tokens}
    negative_heads = {
        int(row.get("head_index", -1))
        for row in tokens
        if _lemma(row) in {"not", "never"}
    }
    source_revision_ref = "source-revision:" + canonical_sha256(
        {
            "document_ref": job.owner_key.document_ref,
            "input_refs": list(job.input_refs),
            "rule_set_revision": NORMALIZED_OPERATOR_RULE_SET_REVISION,
        }
    )
    candidates: list[OperatorCandidate] = []

    def add(
        *,
        identity: Mapping[str, Any],
        factor_type: str,
        predicate_ref: str,
        kind: str,
        role_bindings: Mapping[str, str],
        qualifier_state: Mapping[str, Any],
        residuals: Sequence[str] = (),
        polarity: str = "none",
    ) -> None:
        node = _candidate_node(identity)
        proposal = FactorProposal(
            document_ref=job.owner_key.document_ref,
            source_revision_ref=source_revision_ref,
            factor_type_ref=factor_type,
            source_span_refs=(job.owner_key.scope_ref,),
            input_observation_refs=job.input_refs,
            dependency_factor_refs=(),
            structural_signature=f"signature:{kind}:benchmark:v1",
            role_bindings=dict(role_bindings),
            qualifier_state=dict(qualifier_state),
            producer_contract=NORMALIZED_OPERATOR_CONTRACT,
            declaration_revision=NORMALIZED_OPERATOR_RULE_SET_REVISION,
            candidate_payload={
                "candidate_node": node,
                "predicate_ref": predicate_ref,
                "benchmark_lane": True,
            },
            residuals=tuple(residuals),
        )
        candidates.append(
            OperatorCandidate(
                node=node,
                proposal=proposal,
                kind=kind,
                polarity=polarity,
            )
        )

    for token in tokens:
        lemma = _lemma(token)
        index = int(token.get("index", -1))
        head_index = int(token.get("head_index", -1))
        if lemma in _MODAL and str(token.get("dep") or "") in {"aux", "auxpass"}:
            modality, predicate_ref = _MODAL[lemma]
            polarity = "negative" if head_index in negative_heads else "positive"
            if modality == "obligation" and polarity == "negative":
                predicate_ref = "normative.prohibition"
            add(
                identity={"kind": "modal", "index": index, "head": head_index},
                factor_type="semantic.normative_relation",
                predicate_ref=predicate_ref,
                kind="modal",
                role_bindings={"conduct": f"parser-token:{head_index}"},
                qualifier_state={"modality": modality, "polarity": polarity},
                residuals=("normative_scope_unresolved",),
                polarity=polarity,
            )
        elif lemma in _CONDITIONS:
            add(
                identity={"kind": "condition", "index": index, "head": head_index},
                factor_type="semantic.legal_condition",
                predicate_ref="legal.activation_condition_candidate",
                kind="condition",
                role_bindings={"condition": f"parser-token:{head_index}"},
                qualifier_state={"marker": lemma, "scope_state": "candidate"},
                residuals=("condition_attachment_unresolved",),
            )
        elif lemma in _EXCEPTIONS:
            add(
                identity={"kind": "exception", "index": index, "head": head_index},
                factor_type="semantic.legal_exception",
                predicate_ref="legal.exception_candidate",
                kind="exception",
                role_bindings={"exception": f"parser-token:{head_index}"},
                qualifier_state={"marker": lemma, "scope_state": "candidate"},
                residuals=("exception_attachment_unresolved",),
            )
        elif lemma in _TRANSITIONS and str(token.get("pos") or "") in {"VERB", "AUX"}:
            add(
                identity={"kind": "transition", "index": index},
                factor_type="semantic.legal_transition",
                predicate_ref=_TRANSITIONS[lemma],
                kind="transition",
                role_bindings={"transition": f"parser-token:{index}"},
                qualifier_state={"effective_time_state": "unresolved"},
                residuals=("effective_time_unresolved",),
            )

    del by_index
    return tuple(sorted(candidates, key=lambda row: row.node))


def native_operator_proposals(job: SolverJob) -> tuple[FactorProposal, ...]:
    return tuple(row.proposal for row in normalized_operator_candidates(job))


class NormalizedOperatorZelphCodec:
    codec_ref = "zelph-codec:normalized-operator:v0_1"
    rule_set_revision = NORMALIZED_OPERATOR_RULE_SET_REVISION

    def encode_facts(self, job: SolverJob) -> str:
        lines: list[str] = []
        for candidate in normalized_operator_candidates(job):
            lines.extend(
                (
                    f'{candidate.node} "candidate kind" "{candidate.kind}"',
                    f'{candidate.node} "candidate polarity" "{candidate.polarity}"',
                    f'{candidate.node} "candidate ready" "true"',
                )
            )
        return "\n".join(lines)

    def rules_and_queries(self, job: SolverJob) -> str:
        del job
        return "\n".join(
            (
                '(C "candidate kind" "modal", C "candidate ready" "true") => (C "selected candidate" "true")',
                '(C "candidate kind" "condition", C "candidate ready" "true") => (C "selected candidate" "true")',
                '(C "candidate kind" "exception", C "candidate ready" "true") => (C "selected candidate" "true")',
                '(C "candidate kind" "transition", C "candidate ready" "true") => (C "selected candidate" "true")',
                'C "selected candidate" _value',
            )
        )

    def decode_proposals(
        self,
        job: SolverJob,
        triples: Sequence[Mapping[str, str]],
    ) -> Sequence[FactorProposal]:
        selected = {
            str(row.get("subject") or "")
            for row in triples
            if str(row.get("predicate") or "") == "selected candidate"
            and str(row.get("object") or "").strip('"') == "true"
        }
        return tuple(
            row.proposal
            for row in normalized_operator_candidates(job)
            if row.node in selected
        )


__all__ = [
    "NORMALIZED_OPERATOR_CONTRACT",
    "NORMALIZED_OPERATOR_RULE_SET_REVISION",
    "NormalizedOperatorZelphCodec",
    "OperatorCandidate",
    "native_operator_proposals",
    "normalized_operator_candidates",
]
