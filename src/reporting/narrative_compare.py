from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Iterable

from src.reporting.structure_report import TextUnit
from src.reporting.source_url import parse_source_url
from src.policy.provenance_packet_geometry import ensure_receipt_kinds, receipt_dict


@dataclass(frozen=True, slots=True)
class NarrativeSource:
    source_id: str
    title: str
    origin_url: str | None
    source_type: str
    text_units: tuple[TextUnit, ...]


_ATTRIBUTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("assert", re.compile(r"^(?P<speaker>[A-Z][A-Za-z][A-Za-z .'-]{1,80}?)\s+(?:said|says|argued|argues|submitted|submits|contended|contends)\s+that\s+(?P<claim>.+)$", re.IGNORECASE)),
    ("report", re.compile(r"^(?P<speaker>[A-Z][A-Za-z][A-Za-z .'-]{1,80}?)\s+(?:reported|reports)\s+that\s+(?P<claim>.+)$", re.IGNORECASE)),
    ("hold", re.compile(r"^(?P<speaker>(?:the\s+)?(?:court|majority(?:\s+in\s+[A-Z][A-Za-z .'-]+)?|judge|justices?)[A-Za-z .'-]*)\s+(?:held|holds)\s+that\s+(?P<claim>.+)$", re.IGNORECASE)),
    ("show", re.compile(r"^(?P<speaker>[A-Z][A-Za-z][A-Za-z .'-]{1,80}?)\s+(?:showed|shows)\s+that\s+(?P<claim>.+)$", re.IGNORECASE)),
)

_FACT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("happen_in", re.compile(r"^(?P<subject>.+?)\s+happened\s+in\s+(?P<object>.+)$", re.IGNORECASE)),
    ("approve_after", re.compile(r"^(?P<subject>.+?)\s+(?:was|were)\s+approved\s+after\s+(?P<object>.+)$", re.IGNORECASE)),
    ("begin_before", re.compile(r"^(?P<subject>.+?)\s+began\s+before\s+(?P<object>.+)$", re.IGNORECASE)),
    ("meet", re.compile(r"^(?P<subject>.+?)\s+met\s+(?P<object>.+)$", re.IGNORECASE)),
    ("block", re.compile(r"^(?P<subject>.+?)\s+blocked\s+(?P<object>.+)$", re.IGNORECASE)),
    ("contribute_to", re.compile(r"^(?P<subject>.+?)\s+contributed\s+to\s+(?P<object>.+)$", re.IGNORECASE)),
    ("delay", re.compile(r"^(?P<subject>.+?)\s+delayed\s+(?P<object>.+)$", re.IGNORECASE)),
    ("use", re.compile(r"^(?P<subject>.+?)\s+uses\s+(?P<object>.+)$", re.IGNORECASE)),
    ("support", re.compile(r"^(?P<subject>.+?)\s+supports\s+(?P<object>.+)$", re.IGNORECASE)),
    ("pass", re.compile(r"^(?P<subject>.+?)\s+passed\s+(?P<object>.+)$", re.IGNORECASE)),
    ("govern_in", re.compile(r"^(?P<subject>.+?)\s+govern(?:s)?\s+successfully\s+in\s+(?P<object>.+)$", re.IGNORECASE)),
)

_DISPUTE_PREDICATE_PAIRS = {
    ("approve_after", "begin_before"),
    ("begin_before", "approve_after"),
}

_CAUSAL_DISPUTE_PREDICATES = {"contribute_to", "delay"}
_STATEMENT_FAMILY_PREDICATES = {"claim_text"}
_GOVERNANCE_FAMILY_PREDICATES = {"support", "pass"}
_CAUSAL_LINK_KINDS = {"supports", "undermines"}
_ALLOWED_LINK_CONFIDENCE = {"high", "medium", "low", "abstain"}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().strip(".!?;:")).strip()


def _norm(value: str) -> str:
    text = _clean_text(value).casefold()
    text = re.sub(r"^(?:the|a|an)\s+", "", text)
    text = re.sub(r"\bprocess$", "", text).strip()
    return text


def _argument(role: str, value: str) -> dict[str, str]:
    return {"role": role, "value": value}


def _proposition_signature(proposition: dict[str, Any]) -> str:
    predicate_key = str(proposition.get("predicate_key") or "")
    negation_kind = str((proposition.get("negation") or {}).get("kind") or "")
    args = proposition.get("arguments") or []
    norm_parts = []
    for arg in args:
        role = str(arg.get("role") or "")
        if role in {"speaker", "authority", "target_proposition"}:
            continue
        norm_parts.append(f"{role}={_norm(str(arg.get('value') or ''))}")
    return "|".join([predicate_key, negation_kind, *sorted(norm_parts)])


def _fact_signature(fact: dict[str, Any]) -> str:
    return "|".join(
        [
            str(fact.get("action") or ""),
            *sorted(_norm(subject) for subject in fact.get("subjects", [])),
            *sorted(_norm(obj) for obj in fact.get("objects", [])),
        ]
    )


def _extract_fact_proposition(
    *,
    source_id: str,
    event_id: str,
    proposition_index: int,
    claim_text: str,
    source_signal: str,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    cleaned = _clean_text(claim_text)
    for predicate_key, pattern in _FACT_PATTERNS:
        match = pattern.match(cleaned)
        if not match:
            continue
        subject = _clean_text(str(match.group("subject") or ""))
        obj = _clean_text(str(match.group("object") or ""))
        proposition_id = f"{event_id}:p{proposition_index}"
        proposition = {
            "proposition_id": proposition_id,
            "event_id": event_id,
            "source_id": source_id,
            "proposition_kind": "fact",
            "predicate_key": predicate_key,
            "anchor_text": cleaned,
            "arguments": [_argument("subject", subject), _argument("object", obj)],
            "receipts": [receipt_dict("source_signal", source_signal), receipt_dict("claim_text", cleaned)],
        }
        fact = {
            "fact_id": f"{event_id}:f{proposition_index}",
            "event_id": event_id,
            "source_id": source_id,
            "subjects": [subject],
            "action": predicate_key,
            "objects": [obj],
            "text": cleaned,
            "receipts": proposition["receipts"],
        }
        return proposition, fact
    proposition_id = f"{event_id}:p{proposition_index}"
    proposition = {
        "proposition_id": proposition_id,
        "event_id": event_id,
        "source_id": source_id,
        "proposition_kind": "statement",
        "predicate_key": "claim_text",
        "anchor_text": cleaned,
        "arguments": [_argument("content", cleaned)],
        "receipts": [receipt_dict("source_signal", source_signal), receipt_dict("claim_text", cleaned)],
    }
    return proposition, None


def _extract_claim_graph(
    *,
    source_id: str,
    event_id: str,
    text: str,
    propositions: list[dict[str, Any]],
    proposition_links: list[dict[str, Any]],
    facts: list[dict[str, Any]],
    corroboration_refs: list[dict[str, Any]],
    state: dict[str, int],
    source_signal: str,
    max_depth: int = 3,
) -> str:
    cleaned = _clean_text(text)
    if max_depth > 0:
        for link_kind, pattern in _ATTRIBUTION_PATTERNS:
            match = pattern.match(cleaned)
            if not match:
                continue
            speaker = _clean_text(str(match.group("speaker") or ""))
            claim = _clean_text(str(match.group("claim") or ""))
            target_proposition_id = _extract_claim_graph(
                source_id=source_id,
                event_id=event_id,
                text=claim,
                propositions=propositions,
                proposition_links=proposition_links,
                facts=facts,
                corroboration_refs=corroboration_refs,
                state=state,
                source_signal=f"attribution_{link_kind}",
                max_depth=max_depth - 1,
            )
            state["wrapper_index"] += 1
            wrapper_id = f"{event_id}:a{state['wrapper_index']}"
            wrapper_arguments = [
                _argument("speaker", speaker),
                _argument("target_proposition", target_proposition_id),
            ]
            if link_kind == "hold":
                wrapper_arguments.append(_argument("authority", speaker))
            wrapper = {
                "proposition_id": wrapper_id,
                "event_id": event_id,
                "source_id": source_id,
                "proposition_kind": "attribution",
                "predicate_key": link_kind,
                "anchor_text": cleaned,
                "arguments": wrapper_arguments,
                "receipts": [
                    receipt_dict("source_signal", f"wrapper_{link_kind}"),
                    receipt_dict("surface_text", cleaned),
                ],
            }
            propositions.append(wrapper)
            state["link_index"] += 1
            proposition_links.append(
                {
                    "link_id": f"{event_id}:l{state['link_index']}",
                    "event_id": event_id,
                    "source_id": source_id,
                    "source_proposition_id": wrapper_id,
                    "target_proposition_id": target_proposition_id,
                    "link_kind": "attributes_to",
                    "receipts": [receipt_dict("speaker", speaker), receipt_dict("wrapper_kind", link_kind)],
                }
            )
            if _norm(speaker) in {"court records", "records", "documents", "court record"}:
                corroboration_refs.append(
                    {
                        "event_id": event_id,
                        "ref_kind": "documentary_support",
                        "label": speaker,
                        "claim_text": claim,
                    }
                )
            return wrapper_id

    state["proposition_index"] += 1
    proposition, fact = _extract_fact_proposition(
        source_id=source_id,
        event_id=event_id,
        proposition_index=state["proposition_index"],
        claim_text=cleaned,
        source_signal=source_signal,
    )
    propositions.append(proposition)
    if fact is not None:
        facts.append(fact)
    return str(proposition["proposition_id"])


def build_narrative_validation_report(source: NarrativeSource) -> dict[str, Any]:
    propositions: list[dict[str, Any]] = []
    proposition_links: list[dict[str, Any]] = []
    facts: list[dict[str, Any]] = []
    abstentions: list[dict[str, Any]] = []
    corroboration_refs: list[dict[str, Any]] = []
    state = {"proposition_index": 0, "wrapper_index": 0, "link_index": 0}

    for unit in source.text_units:
        event_id = unit.unit_id
        text = _clean_text(unit.text)
        if not text:
            continue
        before_fact_count = len(facts)
        proposition_id = _extract_claim_graph(
            source_id=source.source_id,
            event_id=event_id,
            text=text,
            propositions=propositions,
            proposition_links=proposition_links,
            facts=facts,
            corroboration_refs=corroboration_refs,
            state=state,
            source_signal="direct_statement",
        )
        proposition = next((row for row in propositions if str(row.get("proposition_id")) == proposition_id), None)
        if len(facts) == before_fact_count and isinstance(proposition, dict) and str(proposition.get("proposition_kind")) == "statement":
            abstentions.append(
                {
                    "event_id": event_id,
                    "reason": "unstructured_claim_text",
                    "text": text,
                }
            )

    support_links, link_index = _derive_support_links(
        source_id=source.source_id,
        propositions=propositions,
        proposition_links=proposition_links,
        starting_link_index=state["link_index"],
    )
    proposition_links.extend(support_links)

    payload = {
        "source": {
            "source_id": source.source_id,
            "title": source.title,
            "origin_url": source.origin_url,
            "origin": parse_source_url(source.origin_url),
            "source_type": source.source_type,
        },
        "summary": {
            "unit_count": len(source.text_units),
            "fact_count": len(facts),
            "proposition_count": len(propositions),
            "proposition_link_count": len(proposition_links),
            "abstention_count": len(abstentions),
            "corroboration_ref_count": len(corroboration_refs),
        },
        "facts": facts,
        "propositions": propositions,
        "proposition_links": proposition_links,
        "abstentions": abstentions,
        "corroboration_refs": corroboration_refs,
    }
    ensure_claim_link_provenance_for_public_artifact(payload)
    return payload


def _index_propositions(report: dict[str, Any]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    by_signature: dict[str, list[dict[str, Any]]] = {}
    by_subject_object: dict[str, list[dict[str, Any]]] = {}
    for proposition in report.get("propositions", []):
        if str(proposition.get("proposition_kind")) == "attribution":
            continue
        signature = _proposition_signature(proposition)
        by_signature.setdefault(signature, []).append(proposition)
        args = {str(arg.get("role")): str(arg.get("value") or "") for arg in proposition.get("arguments", [])}
        subject = _norm(args.get("subject") or args.get("content") or "")
        obj = _norm(args.get("object") or "")
        key = f"{subject}|{obj}"
        by_subject_object.setdefault(key, []).append(proposition)
    return by_signature, by_subject_object


def _predicate_object_key(proposition: dict[str, Any]) -> str:
    args = {str(arg.get("role")): str(arg.get("value") or "") for arg in proposition.get("arguments", [])}
    return f"{str(proposition.get('predicate_key') or '')}|{_norm(args.get('object') or '')}"


def _comparison_subject_key(proposition: dict[str, Any]) -> str:
    args = _arguments_by_role(proposition)
    predicate = str(proposition.get("predicate_key") or "")
    subject = _norm(args.get("subject") or "")
    content = _norm(args.get("content") or "")
    if predicate == "claim_text" and "woolworths" in content:
        return "woolworths"
    if predicate in _GOVERNANCE_FAMILY_PREDICATES and subject in {"majority government", "minority government"}:
        return "government_formation"
    return _norm(args.get("subject") or args.get("content") or "")


def _comparison_outcome_family(proposition: dict[str, Any]) -> str:
    args = _arguments_by_role(proposition)
    predicate = str(proposition.get("predicate_key") or "")
    obj = _norm(args.get("object") or args.get("content") or "")
    if predicate in _CAUSAL_DISPUTE_PREDICATES:
        if "climate policy" in obj or "policy instability" in obj or "policy momentum" in obj:
            return "climate_policy_setback"
    if predicate == "claim_text" and "woolworths" in obj:
        if "direct grocery impacts" in obj or "direct cost pass-through" in obj:
            return "woolworths_direct_price_impact"
    if predicate in _GOVERNANCE_FAMILY_PREDICATES:
        if "climate policy" in obj or "carbon pricing" in obj:
            return "government_climate_policy_capacity"
    return obj


def _collect_attribution_summaries(report: dict[str, Any], proposition_id: str) -> list[str]:
    propositions = {str(row.get("proposition_id")): row for row in report.get("propositions", [])}
    incoming: dict[str, list[dict[str, Any]]] = {}
    for link in report.get("proposition_links", []):
        if str(link.get("link_kind")) != "attributes_to":
            continue
        incoming.setdefault(str(link.get("target_proposition_id")), []).append(link)
    out: list[str] = []
    visited: set[str] = set()

    def visit(target_id: str) -> None:
        for link in incoming.get(target_id, []):
            wrapper_id = str(link.get("source_proposition_id"))
            if wrapper_id in visited:
                continue
            visited.add(wrapper_id)
            wrapper = propositions.get(wrapper_id)
            if not isinstance(wrapper, dict):
                continue
            args = {str(arg.get("role")): str(arg.get("value") or "") for arg in wrapper.get("arguments", [])}
            out.append(f"{wrapper.get('predicate_key')}:{args.get('speaker','')}")
            visit(wrapper_id)

    visit(proposition_id)
    return sorted(set(out))


def _arguments_by_role(proposition: dict[str, Any]) -> dict[str, str]:
    return {str(arg.get("role")): str(arg.get("value") or "") for arg in proposition.get("arguments", [])}


def _derive_comparison_links(
    *,
    disputed_propositions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    comparison_links: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for index, row in enumerate(disputed_propositions, start=1):
        left = row.get("left") or {}
        right = row.get("right") or {}
        left_id = str(left.get("proposition_id") or "")
        right_id = str(right.get("proposition_id") or "")
        if not left_id or not right_id:
            continue
        left_predicate = str(left.get("predicate_key") or "")
        right_predicate = str(right.get("predicate_key") or "")
        left_args = _arguments_by_role(left)
        right_args = _arguments_by_role(right)
        shared_object = _norm(left_args.get("object") or "") and _norm(left_args.get("object") or "") == _norm(
            right_args.get("object") or ""
        )
        distinct_subjects = _norm(left_args.get("subject") or "") != _norm(right_args.get("subject") or "")
        same_outcome_family = _comparison_outcome_family(left) and _comparison_outcome_family(left) == _comparison_outcome_family(right)
        same_subject = _comparison_subject_key(left) and _comparison_subject_key(left) == _comparison_subject_key(right)
        same_predicate_conflicting_subjects = shared_object and distinct_subjects and (
            left_predicate == right_predicate or (left_predicate, right_predicate) in _DISPUTE_PREDICATE_PAIRS
        )
        same_subject_conflicting_outcome = (
            same_subject
            and same_outcome_family
            and left_predicate in _CAUSAL_DISPUTE_PREDICATES
            and right_predicate in _CAUSAL_DISPUTE_PREDICATES
            and left_predicate != right_predicate
        )
        same_statement_family_conflict = (
            same_subject
            and same_outcome_family
            and left_predicate in _STATEMENT_FAMILY_PREDICATES
            and right_predicate in _STATEMENT_FAMILY_PREDICATES
            and _proposition_signature(left) != _proposition_signature(right)
        )
        same_governance_family_conflict = (
            same_subject
            and same_outcome_family
            and left_predicate in _GOVERNANCE_FAMILY_PREDICATES
            and right_predicate in _GOVERNANCE_FAMILY_PREDICATES
            and _proposition_signature(left) != _proposition_signature(right)
        )
        comparison_basis = (
            "shared_subject_statement_family"
            if same_statement_family_conflict
            else "shared_subject_governance_family"
            if same_governance_family_conflict
            else "shared_subject_conflicting_outcome_family"
            if same_subject_conflicting_outcome
            else "shared_outcome_conflicting_cause_or_predicate"
        )
        confidence = (
            "high"
            if same_subject_conflicting_outcome
            else "medium"
            if same_statement_family_conflict or same_governance_family_conflict
            else "low"
        )
        counter_hypothesis_ref = f"counter_hypothesis:{left_predicate}_vs_{right_predicate}:{comparison_basis}"
        if (
            same_predicate_conflicting_subjects
            or same_subject_conflicting_outcome
            or same_statement_family_conflict
            or same_governance_family_conflict
        ):
            key = (left_id, right_id, "undermines")
            if key in seen:
                continue
            seen.add(key)
            comparison_links.append(
                {
                    "link_id": f"cmp:l{index}",
                    "link_kind": "undermines",
                    "link_type": "causal_dispute",
                    "confidence": confidence,
                    "counter_hypothesis_ref": counter_hypothesis_ref,
                    "left_proposition_id": left_id,
                    "right_proposition_id": right_id,
                    "receipts": [
                        receipt_dict("comparison_basis", comparison_basis),
                        receipt_dict("subject_object_key", str(row.get("subject_object_key") or "")),
                        receipt_dict("link_type", "causal_dispute"),
                        receipt_dict("confidence", confidence),
                        receipt_dict("counter_hypothesis_ref", counter_hypothesis_ref),
                    ],
                }
            )
    return comparison_links


def _derive_support_links(
    *,
    source_id: str,
    propositions: list[dict[str, Any]],
    proposition_links: list[dict[str, Any]],
    starting_link_index: int,
) -> tuple[list[dict[str, Any]], int]:
    links: list[dict[str, Any]] = []
    link_index = starting_link_index
    seen: set[tuple[str, str, str]] = set()

    factual = [row for row in propositions if str(row.get("proposition_kind")) == "fact"]
    by_signature: dict[str, list[dict[str, Any]]] = {}
    for row in factual:
        by_signature.setdefault(_proposition_signature(row), []).append(row)

    for row in factual:
        if str(row.get("predicate_key")) != "block":
            continue
        block_args = _arguments_by_role(row)
        block_subject = _norm(block_args.get("subject") or "")
        block_object = _norm(block_args.get("object") or "")
        for candidate in factual:
            if str(candidate.get("predicate_key")) != "contribute_to":
                continue
            candidate_args = _arguments_by_role(candidate)
            candidate_subject = _norm(candidate_args.get("subject") or "")
            if block_subject and block_subject in candidate_subject and block_object and block_object in candidate_subject:
                key = (str(row.get("proposition_id")), str(candidate.get("proposition_id")), "supports")
                if key in seen:
                    continue
                seen.add(key)
                link_index += 1
                counter_hypothesis_ref = (
                    f"counter_hypothesis:{_norm(candidate_args.get('subject') or '')}:"
                    "non_block_causal_explanation"
                )
                links.append(
                    {
                        "link_id": f"{candidate.get('event_id')}:s{link_index}",
                        "event_id": str(candidate.get("event_id") or row.get("event_id") or ""),
                        "source_id": source_id,
                        "source_proposition_id": str(row.get("proposition_id") or ""),
                        "target_proposition_id": str(candidate.get("proposition_id") or ""),
                        "link_kind": "supports",
                        "link_type": "causal_support",
                        "confidence": "medium",
                        "counter_hypothesis_ref": counter_hypothesis_ref,
                        "receipts": [
                            receipt_dict("support_basis", "block_subject_embeds_causal_subject"),
                            receipt_dict("support_source", str(row.get("predicate_key") or "")),
                            receipt_dict("link_type", "causal_support"),
                            receipt_dict("confidence", "medium"),
                            receipt_dict("counter_hypothesis_ref", counter_hypothesis_ref),
                        ],
                    }
                )

    attributed_by_id = {str(row.get("proposition_id")): row for row in propositions if str(row.get("proposition_kind")) == "attribution"}
    evidence_target_ids: set[str] = set()
    for link in proposition_links:
        if str(link.get("link_kind")) != "attributes_to":
            continue
        wrapper = attributed_by_id.get(str(link.get("source_proposition_id")))
        if not isinstance(wrapper, dict):
            continue
        wrapper_args = _arguments_by_role(wrapper)
        if _norm(wrapper_args.get("speaker") or "") in {"court records", "records", "court record"}:
            evidence_target_ids.add(str(link.get("target_proposition_id") or ""))

    for signature, rows in by_signature.items():
        evidence_rows = [row for row in rows if str(row.get("proposition_id") or "") in evidence_target_ids]
        non_evidence_fact_rows = [row for row in rows if str(row.get("proposition_id") or "") not in evidence_target_ids]
        if not evidence_rows or not non_evidence_fact_rows:
            continue
        for evidence_row in evidence_rows:
            for target_row in non_evidence_fact_rows:
                key = (str(evidence_row.get("proposition_id")), str(target_row.get("proposition_id")), "supports")
                if key in seen:
                    continue
                seen.add(key)
                link_index += 1
                counter_hypothesis_ref = (
                    f"counter_hypothesis:{_proposition_signature(target_row)}:"
                    "non_documentary_supporting_interpretation"
                )
                links.append(
                    {
                        "link_id": f"{target_row.get('event_id')}:s{link_index}",
                        "event_id": str(target_row.get("event_id") or evidence_row.get("event_id") or ""),
                        "source_id": source_id,
                        "source_proposition_id": str(evidence_row.get("proposition_id") or ""),
                        "target_proposition_id": str(target_row.get("proposition_id") or ""),
                        "link_kind": "supports",
                        "link_type": "causal_support",
                        "confidence": "high",
                        "counter_hypothesis_ref": counter_hypothesis_ref,
                        "receipts": [
                            receipt_dict("support_basis", "documentary_support_same_signature"),
                            receipt_dict("support_source", "court_records"),
                            receipt_dict("link_type", "causal_support"),
                            receipt_dict("confidence", "high"),
                            receipt_dict("counter_hypothesis_ref", counter_hypothesis_ref),
                        ],
                    }
                )

    return links, link_index


def build_narrative_comparison_report(left: NarrativeSource, right: NarrativeSource) -> dict[str, Any]:
    left_report = build_narrative_validation_report(left)
    right_report = build_narrative_validation_report(right)
    left_by_sig, left_by_subject_object = _index_propositions(left_report)
    right_by_sig, right_by_subject_object = _index_propositions(right_report)

    shared_propositions: list[dict[str, Any]] = []
    disputed_propositions: list[dict[str, Any]] = []
    source_only_propositions: dict[str, list[dict[str, Any]]] = {left.source_id: [], right.source_id: []}
    seen_shared = set()
    seen_disputed = set()

    for signature, left_rows in left_by_sig.items():
        right_rows = right_by_sig.get(signature, [])
        if not right_rows:
            continue
        key = (signature, left_rows[0]["proposition_id"], right_rows[0]["proposition_id"])
        if key in seen_shared:
            continue
        seen_shared.add(key)
        shared_propositions.append(
            {
                "signature": signature,
                "left": left_rows,
                "right": right_rows,
                "left_attributions": _collect_attribution_summaries(left_report, str(left_rows[0]["proposition_id"])),
                "right_attributions": _collect_attribution_summaries(right_report, str(right_rows[0]["proposition_id"])),
            }
        )

    for subject_object, left_rows in left_by_subject_object.items():
        right_rows = right_by_subject_object.get(subject_object, [])
        if not right_rows:
            continue
        for left_row in left_rows:
            for right_row in right_rows:
                if _proposition_signature(left_row) == _proposition_signature(right_row):
                    continue
                pair = (
                    str(left_row.get("predicate_key")),
                    str(right_row.get("predicate_key")),
                    subject_object,
                )
                reverse_pair = (
                    str(right_row.get("predicate_key")),
                    str(left_row.get("predicate_key")),
                    subject_object,
                )
                if pair in seen_disputed or reverse_pair in seen_disputed:
                    continue
                if (
                    pair[:2] not in _DISPUTE_PREDICATE_PAIRS
                    and str(left_row.get("predicate_key")) == str(right_row.get("predicate_key"))
                ):
                    continue
                seen_disputed.add(pair)
                disputed_propositions.append(
                    {
                        "subject_object_key": subject_object,
                        "left": left_row,
                        "right": right_row,
                    }
                )

    left_non_attr = [row for row in left_report.get("propositions", []) if str(row.get("proposition_kind")) != "attribution"]
    right_non_attr = [row for row in right_report.get("propositions", []) if str(row.get("proposition_kind")) != "attribution"]
    for left_row in left_non_attr:
        for right_row in right_non_attr:
            left_predicate = str(left_row.get("predicate_key") or "")
            right_predicate = str(right_row.get("predicate_key") or "")
            left_subject = _comparison_subject_key(left_row)
            right_subject = _comparison_subject_key(right_row)
            left_outcome_family = _comparison_outcome_family(left_row)
            right_outcome_family = _comparison_outcome_family(right_row)
            same_predicate_outcome = left_predicate == right_predicate and _predicate_object_key(left_row) == _predicate_object_key(right_row)
            same_causal_family = (
                left_predicate in _CAUSAL_DISPUTE_PREDICATES
                and right_predicate in _CAUSAL_DISPUTE_PREDICATES
                and left_subject
                and left_subject == right_subject
                and left_outcome_family
                and left_outcome_family == right_outcome_family
            )
            same_statement_family = (
                left_predicate in _STATEMENT_FAMILY_PREDICATES
                and right_predicate in _STATEMENT_FAMILY_PREDICATES
                and left_subject
                and left_subject == right_subject
                and left_outcome_family
                and left_outcome_family == right_outcome_family
            )
            same_governance_family = (
                left_predicate in _GOVERNANCE_FAMILY_PREDICATES
                and right_predicate in _GOVERNANCE_FAMILY_PREDICATES
                and left_subject
                and left_subject == right_subject
                and left_outcome_family
                and left_outcome_family == right_outcome_family
            )
            if not same_predicate_outcome and not same_causal_family and not same_statement_family and not same_governance_family:
                continue
            if _proposition_signature(left_row) == _proposition_signature(right_row):
                continue
            pair = (
                left_predicate,
                left_outcome_family or _predicate_object_key(left_row),
                _proposition_signature(left_row),
                _proposition_signature(right_row),
            )
            if pair in seen_disputed:
                continue
            seen_disputed.add(pair)
            disputed_propositions.append(
                {
                    "subject_object_key": _predicate_object_key(left_row),
                    "comparison_subject_key": left_subject,
                    "comparison_outcome_family": left_outcome_family,
                    "left": left_row,
                    "right": right_row,
                }
            )

    shared_signatures = {row["signature"] for row in shared_propositions}
    disputed_left_ids = {str(row["left"]["proposition_id"]) for row in disputed_propositions}
    disputed_right_ids = {str(row["right"]["proposition_id"]) for row in disputed_propositions}

    for proposition in left_report.get("propositions", []):
        if str(proposition.get("proposition_kind")) == "attribution":
            continue
        if _proposition_signature(proposition) in shared_signatures or str(proposition.get("proposition_id")) in disputed_left_ids:
            continue
        source_only_propositions[left.source_id].append(proposition)
    for proposition in right_report.get("propositions", []):
        if str(proposition.get("proposition_kind")) == "attribution":
            continue
        if _proposition_signature(proposition) in shared_signatures or str(proposition.get("proposition_id")) in disputed_right_ids:
            continue
        source_only_propositions[right.source_id].append(proposition)

    left_facts = {_fact_signature(row): row for row in left_report.get("facts", [])}
    right_facts = {_fact_signature(row): row for row in right_report.get("facts", [])}
    shared_facts = [
        {"signature": signature, "left": left_facts[signature], "right": right_facts[signature]}
        for signature in sorted(set(left_facts) & set(right_facts))
    ]
    disputed_facts = [
        {
            "left": row["left"],
            "right": row["right"],
        }
        for row in disputed_propositions
        if row["left"].get("proposition_kind") == "fact" and row["right"].get("proposition_kind") == "fact"
    ]

    link_differences = []
    for row in shared_propositions:
        if row["left_attributions"] != row["right_attributions"]:
            link_differences.append(
                {
                    "signature": row["signature"],
                    "left_attributions": row["left_attributions"],
                    "right_attributions": row["right_attributions"],
                }
            )

    comparison_links = _derive_comparison_links(disputed_propositions=disputed_propositions)

    abstentions = {
        left.source_id: left_report.get("abstentions", []),
        right.source_id: right_report.get("abstentions", []),
    }

    payload = {
        "fixture_id": f"{left.source_id}__vs__{right.source_id}",
        "sources": [left_report["source"], right_report["source"]],
        "reports": {
            left.source_id: left_report,
            right.source_id: right_report,
        },
        "summary": {
            "shared_proposition_count": len(shared_propositions),
            "disputed_proposition_count": len(disputed_propositions),
            "source_only_proposition_count": sum(len(rows) for rows in source_only_propositions.values()),
            "shared_fact_count": len(shared_facts),
            "disputed_fact_count": len(disputed_facts),
            "link_difference_count": len(link_differences),
            "comparison_link_count": len(comparison_links),
        },
        "shared_propositions": shared_propositions,
        "disputed_propositions": disputed_propositions,
        "source_only_propositions": source_only_propositions,
        "shared_facts": shared_facts,
        "disputed_facts": disputed_facts,
        "link_differences": link_differences,
        "comparison_links": comparison_links,
        "comparison_receipts": [
            {"kind": "comparison_mode", "value": "normalized_proposition_and_fact_signatures_v1"},
            {"kind": "fixture_ids", "value": f"{left.source_id},{right.source_id}"},
        ],
        "abstentions": abstentions,
        "corroboration_refs": {
            left.source_id: left_report.get("corroboration_refs", []),
            right.source_id: right_report.get("corroboration_refs", []),
        },
    }
    ensure_claim_link_provenance_for_public_artifact(payload)
    return payload


def _iter_causal_links(payload: dict[str, Any]) -> Iterable[tuple[dict[str, Any], str]]:
    for idx, link in enumerate(payload.get("proposition_links", []), start=1):
        if not isinstance(link, dict):
            continue
        if str(link.get("link_kind") or "") in _CAUSAL_LINK_KINDS:
            yield link, f"proposition_links[{idx}]"
    for idx, link in enumerate(payload.get("comparison_links", []), start=1):
        if not isinstance(link, dict):
            continue
        if str(link.get("link_kind") or "") in _CAUSAL_LINK_KINDS:
            yield link, f"comparison_links[{idx}]"
    reports = payload.get("reports")
    if isinstance(reports, dict):
        for report_key, report in reports.items():
            if not isinstance(report, dict):
                continue
            for idx, link in enumerate(report.get("proposition_links", []), start=1):
                if not isinstance(link, dict):
                    continue
                if str(link.get("link_kind") or "") in _CAUSAL_LINK_KINDS:
                    yield link, f"reports.{report_key}.proposition_links[{idx}]"


def ensure_claim_link_provenance_for_public_artifact(payload: dict[str, Any]) -> None:
    for link, location in _iter_causal_links(payload):
        link_kind = str(link.get("link_kind") or "")
        link_type = str(link.get("link_type") or "").strip()
        confidence = str(link.get("confidence") or "").strip()
        counter_hypothesis_ref = str(link.get("counter_hypothesis_ref") or "").strip()
        if not link_type:
            raise ValueError(f"{location} missing link_type for causal link_kind={link_kind}")
        if confidence not in _ALLOWED_LINK_CONFIDENCE:
            raise ValueError(
                f"{location} has invalid confidence={confidence!r} for causal link_kind={link_kind}"
            )
        if not counter_hypothesis_ref:
            raise ValueError(f"{location} missing counter_hypothesis_ref for causal link_kind={link_kind}")

        receipts = link.get("receipts") or []
        try:
            ensure_receipt_kinds(
                receipts,
                required_kinds=("link_type", "confidence", "counter_hypothesis_ref"),
            )
        except ValueError as exc:
            raise ValueError(f"{location} {exc}") from exc


def load_narrative_fixture(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _source_from_payload(payload: dict[str, Any]) -> NarrativeSource:
    units = tuple(
        TextUnit(
            unit_id=str(row.get("unit_id") or ""),
            source_id=str(payload.get("source_id") or ""),
            source_type=str(payload.get("source_type") or "text_file"),
            text=str(row.get("text") or ""),
        )
        for row in payload.get("text_units", [])
        if str(row.get("text") or "").strip()
    )
    return NarrativeSource(
        source_id=str(payload.get("source_id") or ""),
        title=str(payload.get("title") or payload.get("source_id") or ""),
        origin_url=str(payload.get("origin_url") or "") or None,
        source_type=str(payload.get("source_type") or "text_file"),
        text_units=units,
    )


def load_fixture_sources(path: str | Path) -> tuple[dict[str, Any], list[NarrativeSource]]:
    payload = load_narrative_fixture(path)
    sources = [_source_from_payload(row) for row in payload.get("sources", [])]
    return payload, sources
