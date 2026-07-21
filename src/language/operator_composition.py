"""Generic parser-observation composition for modal and scoped PNF factors.

This module is part of the one shared parser-to-PNF spine.  It does not select a
legal source family and it does not decide applicability, violation, liability,
or legal truth.  It composes ordinary parser observations into candidate PNF
factors whose structure may later be projected into Legal IR.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.policy.algebra import Factor, TypedAlternative
from src.policy.carriers.canonical import canonical_sha256


OPERATOR_COMPOSITION_CONTRACT = "grammar:semantic:operator-composition:v0_1"

_MODAL_LEMMAS = {
    "must": ("obligation", "normative.obligation"),
    "shall": ("obligation", "normative.obligation"),
    "may": ("permission_candidate", "normative.permission_candidate"),
}
_CONDITION_MARKERS = {"if", "when", "provided", "providing"}
_EXCEPTION_MARKERS = {"unless", "except", "excluding"}
_TRANSITION_LEMMAS = {
    "commence": ("inactive", "active", "legal.commencement"),
    "begin": ("inactive", "active", "legal.commencement_candidate"),
    "repeal": ("active", "repealed", "legal.repeal"),
    "amend": ("prior_revision", "amended_revision", "legal.amendment"),
    "cease": ("active", "inactive", "legal.cessation"),
}


def _tokens(parsed_document: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for sentence_index, sentence in enumerate(parsed_document.get("sents") or ()):
        for token in sentence.get("tokens") or ():
            rows.append({**dict(token), "sentence_index": sentence_index})
    return tuple(rows)


def _token_ref(document_ref: str, token: Mapping[str, Any]) -> str:
    return "parser-token:" + canonical_sha256(
        {
            "document_ref": document_ref,
            "parser_index": int(token["index"]),
            "start": int(token["start"]),
            "end": int(token["end"]),
        }
    )


def _lemma(token: Mapping[str, Any]) -> str:
    return str(token.get("lemma") or token.get("text") or "").casefold()


def _children(
    token: Mapping[str, Any], sentence_tokens: Sequence[Mapping[str, Any]]
) -> tuple[Mapping[str, Any], ...]:
    index = int(token["index"])
    return tuple(row for row in sentence_tokens if int(row.get("head_index", -1)) == index)


def _subject_and_object(
    head: Mapping[str, Any], sentence_tokens: Sequence[Mapping[str, Any]]
) -> tuple[Mapping[str, Any] | None, Mapping[str, Any] | None]:
    children = _children(head, sentence_tokens)
    subject = next(
        (
            row
            for row in children
            if str(row.get("dep") or "") in {"nsubj", "nsubjpass", "csubj"}
        ),
        None,
    )
    object_row = next(
        (
            row
            for row in children
            if str(row.get("dep") or "")
            in {"obj", "dobj", "pobj", "attr", "oprd"}
        ),
        None,
    )
    return subject, object_row


def _new_factor(
    *,
    document_ref: str,
    sentence_index: int,
    factor_type: str,
    predicate_ref: str,
    signature_ref: str,
    role_bindings: Mapping[str, str],
    qualifier_state: Mapping[str, Any],
    provenance_refs: Sequence[str],
    residuals: Sequence[str],
    identity_payload: Mapping[str, Any],
) -> Factor[Any]:
    factor_ref = "factor:" + canonical_sha256(
        {
            "contract": OPERATOR_COMPOSITION_CONTRACT,
            "document_ref": document_ref,
            "sentence_index": sentence_index,
            "factor_type": factor_type,
            "identity": identity_payload,
        }
    )
    revision_ref = "factor-revision:" + canonical_sha256(
        {
            "factor_ref": factor_ref,
            "contract": OPERATOR_COMPOSITION_CONTRACT,
            "roles": dict(sorted(role_bindings.items())),
            "qualifiers": dict(qualifier_state),
        }
    )
    alternative = TypedAlternative(
        alternative_ref=f"{factor_ref}:candidate",
        value={
            "predicate_ref": predicate_ref,
            "role_bindings": dict(role_bindings),
            "qualifier_state": dict(qualifier_state),
        },
        type_ref=f"{factor_type}.candidate",
        derivation_refs=(OPERATOR_COMPOSITION_CONTRACT, *tuple(provenance_refs)),
    )
    return Factor(
        factor_ref=factor_ref,
        factor_type=factor_type,
        alternatives=(alternative,),
        residuals=tuple(sorted(set(str(value) for value in residuals))),
        closure_state="requires_external_resolution" if residuals else "locally_closed",
        metadata={
            "factor_revision_ref": revision_ref,
            "structural_signature_ref": signature_ref,
            "predicate_ref": predicate_ref,
            "role_bindings": dict(role_bindings),
            "qualifier_state": dict(qualifier_state),
            "wrapper_state": {
                "assertion_state": "source_observed",
                "authority_class": "unresolved",
            },
            "provenance_refs": tuple(provenance_refs),
            "composition_contract_ref": OPERATOR_COMPOSITION_CONTRACT,
        },
    )


def compose_operator_factors(
    *, document_ref: str, parsed_document: Mapping[str, Any]
) -> tuple[Factor[Any], ...]:
    """Compose candidate modal, scope, exception, and transition factors.

    Every input comes from the public parser observation stream.  The output is
    candidate PNF only; ambiguous modal senses and all legal applicability
    coordinates remain open.
    """

    all_tokens = _tokens(parsed_document)
    by_sentence: dict[int, list[Mapping[str, Any]]] = {}
    for token in all_tokens:
        by_sentence.setdefault(int(token["sentence_index"]), []).append(token)

    factors: list[Factor[Any]] = []
    for sentence_index, sentence_tokens in sorted(by_sentence.items()):
        token_by_index = {int(row["index"]): row for row in sentence_tokens}

        # Modal composition: auxiliary -> scoped predicate with polarity.
        for modal in sentence_tokens:
            modal_kind = _MODAL_LEMMAS.get(_lemma(modal))
            if modal_kind is None or str(modal.get("dep") or "") not in {"aux", "auxpass"}:
                continue
            head = token_by_index.get(int(modal.get("head_index", -1)))
            if head is None:
                continue
            subject, object_row = _subject_and_object(head, sentence_tokens)
            negation = next(
                (
                    row
                    for row in sentence_tokens
                    if _lemma(row) in {"not", "never"}
                    and int(row.get("head_index", -1))
                    in {int(head["index"]), int(modal["index"])}
                ),
                None,
            )
            modality, predicate_ref = modal_kind
            polarity = "negative" if negation is not None else "positive"
            if modality == "obligation" and polarity == "negative":
                predicate_ref = "normative.prohibition"
            role_bindings = {"conduct": _token_ref(document_ref, head)}
            if subject is not None:
                role_bindings["bearer"] = _token_ref(document_ref, subject)
            if object_row is not None:
                role_bindings["object"] = _token_ref(document_ref, object_row)
            provenance = [_token_ref(document_ref, modal), _token_ref(document_ref, head)]
            if negation is not None:
                provenance.append(_token_ref(document_ref, negation))
            residuals = [
                "jurisdiction_unresolved",
                "legal_time_unresolved",
                "normative_scope_unresolved",
            ]
            if modality == "permission_candidate":
                residuals.append("modal_sense_unresolved")
            if subject is None:
                residuals.append("norm_bearer_unresolved")
            factors.append(
                _new_factor(
                    document_ref=document_ref,
                    sentence_index=sentence_index,
                    factor_type="semantic.normative_relation",
                    predicate_ref=predicate_ref,
                    signature_ref="signature:normative-operation:v1",
                    role_bindings=role_bindings,
                    qualifier_state={"modality": modality, "polarity": polarity},
                    provenance_refs=provenance,
                    residuals=residuals,
                    identity_payload={
                        "modal": int(modal["index"]),
                        "head": int(head["index"]),
                        "polarity": polarity,
                    },
                )
            )

        # Conditions and exceptions are scoped clause relations, not conclusions.
        for marker in sentence_tokens:
            marker_lemma = _lemma(marker)
            if marker_lemma not in _CONDITION_MARKERS | _EXCEPTION_MARKERS:
                continue
            if str(marker.get("dep") or "") not in {"mark", "prep", "advmod"}:
                continue
            clause_head = token_by_index.get(int(marker.get("head_index", -1)))
            if clause_head is None:
                continue
            host = token_by_index.get(int(clause_head.get("head_index", -1)))
            factor_type = (
                "semantic.legal_exception"
                if marker_lemma in _EXCEPTION_MARKERS
                else "semantic.legal_condition"
            )
            predicate_ref = (
                "legal.exception_candidate"
                if factor_type == "semantic.legal_exception"
                else "legal.activation_condition_candidate"
            )
            role_name = "exception" if factor_type == "semantic.legal_exception" else "condition"
            role_bindings = {role_name: _token_ref(document_ref, clause_head)}
            if host is not None:
                role_bindings["host"] = _token_ref(document_ref, host)
            factors.append(
                _new_factor(
                    document_ref=document_ref,
                    sentence_index=sentence_index,
                    factor_type=factor_type,
                    predicate_ref=predicate_ref,
                    signature_ref=(
                        "signature:legal-exception:v1"
                        if factor_type == "semantic.legal_exception"
                        else "signature:legal-condition:v1"
                    ),
                    role_bindings=role_bindings,
                    qualifier_state={"marker": marker_lemma, "scope_state": "candidate"},
                    provenance_refs=(
                        _token_ref(document_ref, marker),
                        _token_ref(document_ref, clause_head),
                    ),
                    residuals=(
                        "exception_attachment_unresolved",
                        "exception_burden_unresolved",
                    )
                    if factor_type == "semantic.legal_exception"
                    else ("condition_attachment_unresolved",),
                    identity_payload={
                        "marker": int(marker["index"]),
                        "clause_head": int(clause_head["index"]),
                    },
                )
            )

        # Legal-object lifecycle transitions are state-transition candidates.
        for predicate in sentence_tokens:
            transition = _TRANSITION_LEMMAS.get(_lemma(predicate))
            if transition is None or str(predicate.get("pos") or "") not in {"VERB", "AUX"}:
                continue
            prior_state, next_state, predicate_ref = transition
            subject, object_row = _subject_and_object(predicate, sentence_tokens)
            legal_object = subject or object_row
            role_bindings = {"transition": _token_ref(document_ref, predicate)}
            if legal_object is not None:
                role_bindings["legal_object"] = _token_ref(document_ref, legal_object)
            factors.append(
                _new_factor(
                    document_ref=document_ref,
                    sentence_index=sentence_index,
                    factor_type="semantic.legal_transition",
                    predicate_ref=predicate_ref,
                    signature_ref="signature:legal-transition:v1",
                    role_bindings=role_bindings,
                    qualifier_state={
                        "prior_state": prior_state,
                        "next_state": next_state,
                        "effective_time_state": "unresolved",
                    },
                    provenance_refs=(_token_ref(document_ref, predicate),),
                    residuals=(
                        "legal_object_identity_unresolved",
                        "effective_time_unresolved",
                        "jurisdiction_unresolved",
                    ),
                    identity_payload={"predicate": int(predicate["index"]), "transition": transition},
                )
            )

    return tuple(sorted({row.factor_ref: row for row in factors}.values(), key=lambda row: row.factor_ref))


__all__ = ["OPERATOR_COMPOSITION_CONTRACT", "compose_operator_factors"]
