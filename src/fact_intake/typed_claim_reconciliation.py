from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


TYPED_CLAIM_RECONCILIATION_VERSION = "sl.typed_claim_reconciliation.v0_1"

AFFIDAVIT_RELATION_TYPES: tuple[str, ...] = (
    "exact_support",
    "equivalent_support",
    "explicit_dispute",
    "implicit_dispute",
    "partial_overlap",
    "adjacent_event",
    "substitution",
    "procedural_nonanswer",
    "unrelated",
)
RELATION_ROOTS: tuple[str, ...] = (
    "supports",
    "invalidates",
    "non_resolving",
    "unanswered",
)
RELATION_BUCKETS: tuple[str, ...] = (
    "supported",
    "disputed",
    "partial_support",
    "adjacent_event",
    "substitution",
    "non_substantive_response",
    "missing",
)

_RELATION_BUCKET_BY_TYPE: dict[str, str] = {
    "exact_support": "supported",
    "equivalent_support": "supported",
    "explicit_dispute": "disputed",
    "implicit_dispute": "disputed",
    "partial_overlap": "partial_support",
    "adjacent_event": "adjacent_event",
    "substitution": "substitution",
    "procedural_nonanswer": "non_substantive_response",
    "unrelated": "missing",
}
_RELATION_ROOT_LEAF_BY_TYPE: dict[str, tuple[str, str]] = {
    "exact_support": ("supports", "exact_support"),
    "equivalent_support": ("supports", "equivalent_support"),
    "explicit_dispute": ("invalidates", "explicit_dispute"),
    "implicit_dispute": ("invalidates", "implicit_dispute"),
    "partial_overlap": ("supports", "partial_support"),
    "adjacent_event": ("non_resolving", "adjacent_event"),
    "substitution": ("non_resolving", "substitution"),
    "procedural_nonanswer": ("non_resolving", "non_substantive_response"),
    "unrelated": ("unanswered", "missing"),
}
_NEGATIVE_POLARITIES = {
    "negative",
    "not",
    "false",
    "denies",
    "deny",
    "disputes",
    "against",
}
_POSITIVE_POLARITIES = {
    "positive",
    "yes",
    "true",
    "supports",
    "for",
    "affirmed",
    "normal",
}


def normalize_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def normalize_token(value: Any) -> str:
    return normalize_text(value).casefold()


def normalize_polarity(value: Any) -> str:
    normalized = normalize_token(value)
    if normalized in _NEGATIVE_POLARITIES or normalized.startswith("not "):
        return "negative"
    if normalized in _POSITIVE_POLARITIES or not normalized:
        return "positive"
    return normalized


def normalize_proposition(
    *,
    subject: Any,
    predicate: Any,
    object: Any = None,
    polarity: Any = "positive",
    text: Any = None,
    context: Mapping[str, Any] | None = None,
    source: Any = None,
    sequence: Any = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    subject_text = normalize_text(subject)
    predicate_text = normalize_text(predicate)
    object_text = normalize_text(object)
    display_text = normalize_text(text) or " ".join(
        part for part in (subject_text, predicate_text, object_text) if part
    )
    return {
        "kind": "proposition",
        "subject": subject_text,
        "predicate": predicate_text,
        "object": object_text or None,
        "polarity": normalize_polarity(polarity),
        "text": display_text,
        "normalized": {
            "subject": normalize_token(subject_text),
            "predicate": normalize_token(predicate_text),
            "object": normalize_token(object_text),
            "text": normalize_token(display_text),
        },
        "context": dict(context or {}),
        "source": normalize_text(source) or None,
        "sequence": sequence,
        "metadata": dict(metadata or {}),
    }


def normalize_response_unit(
    *,
    text: Any,
    subject: Any = None,
    predicate: Any = None,
    object: Any = None,
    polarity: Any = "positive",
    response_role: Any = None,
    context: Mapping[str, Any] | None = None,
    source: Any = None,
    sequence: Any = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    record = normalize_proposition(
        subject=subject,
        predicate=predicate,
        object=object,
        polarity=polarity,
        text=text,
        context=context,
        source=source,
        sequence=sequence,
        metadata=metadata,
    )
    record["kind"] = "response_unit"
    record["response_role"] = normalize_token(response_role) or None
    return record


def normalize_object_type_claim(
    *,
    subject: Any,
    claimed_type: Any,
    context: Mapping[str, Any] | None = None,
    polarity: Any = "positive",
    source: Any = None,
    sequence: Any = None,
    witness_status: Any = None,
    review_status: Any = None,
    witness_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    subject_text = normalize_text(subject)
    claimed_type_text = normalize_text(claimed_type)
    context_dict = dict(context or {})
    witness_metadata_dict = dict(witness_metadata or {})
    inferred_witness_status = _infer_object_witness_status(
        context_dict,
        witness_metadata_dict,
    )
    final_witness_status = normalize_token(witness_status) or inferred_witness_status
    final_review_status = normalize_token(review_status) or _review_status_for_witness(
        final_witness_status
    )
    return {
        "kind": "object_type_claim",
        "subject": subject_text,
        "claimed_type": claimed_type_text,
        "polarity": normalize_polarity(polarity),
        "context": context_dict,
        "source": normalize_text(source) or None,
        "sequence": sequence,
        "witness_status": final_witness_status,
        "review_status": final_review_status,
        "promotion_state": _promotion_state(),
        "witness_metadata": witness_metadata_dict,
        "normalized": {
            "subject": normalize_token(subject_text),
            "claimed_type": normalize_token(claimed_type_text),
        },
    }


def normalize_wikidata_claim_row(
    *,
    subject: Any,
    property: Any = None,
    value: Any,
    qualifiers: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
    references: Sequence[Mapping[str, Any]] | None = None,
    rank: Any = "normal",
    deprecated: bool | None = None,
    source: Any = "wikidata",
    sequence: Any = None,
) -> dict[str, Any]:
    rank_text = normalize_token(rank) or "normal"
    is_deprecated = bool(deprecated) or rank_text == "deprecated"
    operational_status = "deprecated" if is_deprecated else rank_text
    evidence_state = "held_for_review" if is_deprecated else "observed"
    return {
        "kind": "wikidata_claim_row",
        "subject": normalize_text(subject),
        "property": normalize_text(property),
        "value": normalize_text(value),
        "qualifiers": _normalize_jsonish(qualifiers),
        "references": [dict(reference) for reference in references or ()],
        "rank": "deprecated" if is_deprecated else rank_text,
        "operational_status": operational_status,
        "evidence_state": evidence_state,
        "promotion_state": _promotion_state(),
        "truth_claimed": False,
        "truth_claimed_is_false": True,
        "live_edit_authority": False,
        "live_edit_authority_is_false": True,
        "source": normalize_text(source) or "wikidata",
        "sequence": sequence,
        "normalized": {
            "subject": normalize_token(subject),
            "property": normalize_token(property),
            "value": normalize_token(value),
        },
    }


def reduce_typed_relation(
    left: Mapping[str, Any],
    right: Mapping[str, Any] | None = None,
    *,
    relation_hint: str | None = None,
    explicit_exclusion_witness: bool = False,
    evidence_state: str = "observed",
) -> dict[str, Any]:
    if relation_hint:
        return build_typed_relation(
            relation_hint,
            left=left,
            right=right,
            evidence_state=evidence_state,
            relation_derivation="caller_hint",
            reason="Relation supplied by caller as evidence metadata.",
        )
    if right is None:
        return build_typed_relation(
            "unrelated",
            left=left,
            right=None,
            evidence_state=evidence_state,
            reason="No comparison unit was supplied.",
        )

    left_kind = str(left.get("kind") or "")
    right_kind = str(right.get("kind") or "")
    if _is_procedural_response(right):
        return build_typed_relation(
            "procedural_nonanswer",
            left=left,
            right=right,
            evidence_state=evidence_state,
            reason="The response is procedural or non-substantive evidence metadata.",
        )
    if left_kind == right_kind == "object_type_claim":
        return _reduce_object_type_claims(
            left,
            right,
            explicit_exclusion_witness=explicit_exclusion_witness,
            evidence_state=evidence_state,
        )
    if {left_kind, right_kind} <= {"proposition", "response_unit"}:
        return _reduce_proposition_like(left, right, evidence_state=evidence_state)
    return build_typed_relation(
        "unrelated",
        left=left,
        right=right,
        evidence_state=evidence_state,
        reason="The comparison units do not share a typed reconciliation surface.",
    )


def build_typed_relation(
    relation_type: str,
    *,
    left: Mapping[str, Any] | None = None,
    right: Mapping[str, Any] | None = None,
    evidence_state: str = "observed",
    relation_derivation: str = "derived",
    reason: str = "",
) -> dict[str, Any]:
    if relation_type not in _RELATION_BUCKET_BY_TYPE:
        raise ValueError(f"Unknown affidavit relation type: {relation_type}")
    relation_root, relation_leaf = _RELATION_ROOT_LEAF_BY_TYPE[relation_type]
    bucket = _RELATION_BUCKET_BY_TYPE[relation_type]
    return {
        "kind": "typed_relation",
        "schema": TYPED_CLAIM_RECONCILIATION_VERSION,
        "relation_type": relation_type,
        "relation_root": relation_root,
        "relation_leaf": relation_leaf,
        "bucket": bucket,
        "evidence_state": evidence_state,
        "relation_derivation": relation_derivation,
        "promotion_state": _promotion_state(),
        "left": _relation_ref(left),
        "right": _relation_ref(right),
        "explanation": {
            "classification": bucket,
            "reason": reason,
            "proof_promotion": "Relation/support classification is evidence metadata only.",
        },
    }


def _reduce_object_type_claims(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    *,
    explicit_exclusion_witness: bool,
    evidence_state: str,
) -> dict[str, Any]:
    same_subject = _normalized(left, "subject") == _normalized(right, "subject")
    same_type = _normalized(left, "claimed_type") == _normalized(right, "claimed_type")
    opposite_polarity = str(left.get("polarity")) != str(right.get("polarity"))
    if same_subject and same_type and opposite_polarity:
        return build_typed_relation(
            "explicit_dispute",
            left=left,
            right=right,
            evidence_state=evidence_state,
            reason="The object-type claims share subject and claimed type with opposite polarity.",
        )
    if same_subject and same_type:
        return build_typed_relation(
            "exact_support",
            left=left,
            right=right,
            evidence_state=evidence_state,
            reason="The object-type claims share subject, claimed type, and polarity.",
        )
    if same_subject and explicit_exclusion_witness:
        return build_typed_relation(
            "explicit_dispute",
            left=left,
            right=right,
            evidence_state=evidence_state,
            reason="An explicit exclusion witness marks these different positive types as incompatible.",
        )
    if same_subject:
        return build_typed_relation(
            "adjacent_event",
            left=left,
            right=right,
            evidence_state=evidence_state,
            reason="Different positive claimed types for the same subject are adjacent metadata, not contradiction.",
        )
    return build_typed_relation(
        "unrelated",
        left=left,
        right=right,
        evidence_state=evidence_state,
        reason="The object-type claims do not share a subject.",
    )


def _reduce_proposition_like(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    *,
    evidence_state: str,
) -> dict[str, Any]:
    same_subject = _normalized(left, "subject") and _normalized(left, "subject") == _normalized(
        right,
        "subject",
    )
    same_predicate = _normalized(left, "predicate") and _normalized(left, "predicate") == _normalized(
        right,
        "predicate",
    )
    same_object = _normalized(left, "object") == _normalized(right, "object")
    same_text = _normalized(left, "text") and _normalized(left, "text") == _normalized(right, "text")
    opposite_polarity = str(left.get("polarity")) != str(right.get("polarity"))
    if same_subject and same_predicate and same_object and opposite_polarity:
        return build_typed_relation(
            "explicit_dispute",
            left=left,
            right=right,
            evidence_state=evidence_state,
            reason="The proposition and response share subject/action/object with opposite polarity.",
        )
    if (same_text or (same_subject and same_predicate and same_object)) and not opposite_polarity:
        return build_typed_relation(
            "exact_support",
            left=left,
            right=right,
            evidence_state=evidence_state,
            reason="The proposition and response share the same typed content without proof promotion.",
        )
    if same_subject or same_predicate:
        return build_typed_relation(
            "partial_overlap",
            left=left,
            right=right,
            evidence_state=evidence_state,
            reason="The proposition and response overlap but do not resolve all typed dimensions.",
        )
    return build_typed_relation(
        "unrelated",
        left=left,
        right=right,
        evidence_state=evidence_state,
        reason="The proposition and response do not align on typed dimensions.",
    )


def _is_procedural_response(unit: Mapping[str, Any]) -> bool:
    return str(unit.get("response_role") or "") in {
        "procedural_frame",
        "procedural_nonanswer",
        "non_response",
        "restatement_only",
    }


def _promotion_state() -> dict[str, Any]:
    return {
        "promoted": False,
        "state": "not_promoted",
        "reason": "Evidence classification does not promote a proposition to proof.",
    }


def _infer_object_witness_status(
    context: Mapping[str, Any],
    witness_metadata: Mapping[str, Any],
) -> str:
    explicit_status = normalize_token(witness_metadata.get("witness_status"))
    if explicit_status:
        return explicit_status
    blocked = witness_metadata.get("blocked")
    if blocked is True or normalize_token(blocked) in {"true", "yes", "blocked"}:
        return "typing_blocked"
    has_context = any(
        normalize_text(context.get(key))
        for key in ("category", "bicategory", "typing_context", "context")
    )
    has_typing_rule = bool(
        normalize_text(context.get("typing_rule"))
        or normalize_text(witness_metadata.get("typing_rule"))
    )
    if has_context and has_typing_rule:
        return "typing_witnessed"
    if has_context:
        return "typing_witness_pending"
    return "typing_context_missing"


def _review_status_for_witness(witness_status: str) -> str:
    if witness_status == "typing_witnessed":
        return "reviewed_carrier"
    if witness_status == "typing_blocked":
        return "witness_blocked"
    return "witness_pending"


def _relation_ref(unit: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if unit is None:
        return None
    return {
        "kind": unit.get("kind"),
        "subject": unit.get("subject"),
        "predicate": unit.get("predicate"),
        "object": unit.get("object"),
        "claimed_type": unit.get("claimed_type"),
        "property": unit.get("property"),
        "value": unit.get("value"),
        "polarity": unit.get("polarity"),
        "source": unit.get("source"),
        "sequence": unit.get("sequence"),
    }


def _normalized(unit: Mapping[str, Any], key: str) -> str:
    normalized = unit.get("normalized")
    if isinstance(normalized, Mapping):
        return str(normalized.get(key) or "")
    return normalize_token(unit.get(key))


def _normalize_jsonish(value: Any) -> Any:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [dict(item) if isinstance(item, Mapping) else item for item in value]
    return value


__all__ = [
    "AFFIDAVIT_RELATION_TYPES",
    "RELATION_BUCKETS",
    "RELATION_ROOTS",
    "TYPED_CLAIM_RECONCILIATION_VERSION",
    "build_typed_relation",
    "normalize_object_type_claim",
    "normalize_polarity",
    "normalize_proposition",
    "normalize_response_unit",
    "normalize_text",
    "normalize_token",
    "normalize_wikidata_claim_row",
    "reduce_typed_relation",
]
