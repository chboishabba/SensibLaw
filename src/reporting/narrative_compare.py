from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Iterable

from src.reporting.structure_report import TextUnit


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
    ("use", re.compile(r"^(?P<subject>.+?)\s+uses\s+(?P<object>.+)$", re.IGNORECASE)),
    ("support", re.compile(r"^(?P<subject>.+?)\s+supports\s+(?P<object>.+)$", re.IGNORECASE)),
    ("pass", re.compile(r"^(?P<subject>.+?)\s+passed\s+(?P<object>.+)$", re.IGNORECASE)),
    ("govern_in", re.compile(r"^(?P<subject>.+?)\s+govern(?:s)?\s+successfully\s+in\s+(?P<object>.+)$", re.IGNORECASE)),
)

_DISPUTE_PREDICATE_PAIRS = {
    ("approve_after", "begin_before"),
    ("begin_before", "approve_after"),
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().strip(".!?;:")).strip()


def _norm(value: str) -> str:
    text = _clean_text(value).casefold()
    text = re.sub(r"^(?:the|a|an)\s+", "", text)
    text = re.sub(r"\bprocess$", "", text).strip()
    return text


def _receipt(kind: str, value: str) -> dict[str, str]:
    return {"kind": kind, "value": value}


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
            "receipts": [_receipt("source_signal", source_signal), _receipt("claim_text", cleaned)],
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
        "receipts": [_receipt("source_signal", source_signal), _receipt("claim_text", cleaned)],
    }
    return proposition, None


def build_narrative_validation_report(source: NarrativeSource) -> dict[str, Any]:
    propositions: list[dict[str, Any]] = []
    proposition_links: list[dict[str, Any]] = []
    facts: list[dict[str, Any]] = []
    abstentions: list[dict[str, Any]] = []
    corroboration_refs: list[dict[str, Any]] = []
    proposition_index = 0
    link_index = 0

    for unit in source.text_units:
        event_id = unit.unit_id
        text = _clean_text(unit.text)
        if not text:
            continue
        matched_attribution = False
        for link_kind, pattern in _ATTRIBUTION_PATTERNS:
            match = pattern.match(text)
            if not match:
                continue
            matched_attribution = True
            speaker = _clean_text(str(match.group("speaker") or ""))
            claim = _clean_text(str(match.group("claim") or ""))
            proposition_index += 1
            inner_proposition, fact = _extract_fact_proposition(
                source_id=source.source_id,
                event_id=event_id,
                proposition_index=proposition_index,
                claim_text=claim,
                source_signal=f"attribution_{link_kind}",
            )
            propositions.append(inner_proposition)
            if fact is not None:
                facts.append(fact)
            wrapper_id = f"{event_id}:a{proposition_index}"
            wrapper = {
                "proposition_id": wrapper_id,
                "event_id": event_id,
                "source_id": source.source_id,
                "proposition_kind": "attribution",
                "predicate_key": link_kind,
                "anchor_text": text,
                "arguments": [
                    _argument("speaker", speaker),
                    _argument("target_proposition", inner_proposition["proposition_id"]),
                ],
                "receipts": [
                    _receipt("source_signal", f"wrapper_{link_kind}"),
                    _receipt("surface_text", text),
                ],
            }
            propositions.append(wrapper)
            link_index += 1
            proposition_links.append(
                {
                    "link_id": f"{event_id}:l{link_index}",
                    "event_id": event_id,
                    "source_id": source.source_id,
                    "source_proposition_id": wrapper_id,
                    "target_proposition_id": inner_proposition["proposition_id"],
                    "link_kind": "attributes_to",
                    "receipts": [_receipt("speaker", speaker), _receipt("wrapper_kind", link_kind)],
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
            break
        if matched_attribution:
            continue
        proposition_index += 1
        proposition, fact = _extract_fact_proposition(
            source_id=source.source_id,
            event_id=event_id,
            proposition_index=proposition_index,
            claim_text=text,
            source_signal="direct_statement",
        )
        propositions.append(proposition)
        if fact is not None:
            facts.append(fact)
        else:
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
        starting_link_index=link_index,
    )
    proposition_links.extend(support_links)

    return {
        "source": {
            "source_id": source.source_id,
            "title": source.title,
            "origin_url": source.origin_url,
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


def _collect_attribution_summaries(report: dict[str, Any], proposition_id: str) -> list[str]:
    propositions = {str(row.get("proposition_id")): row for row in report.get("propositions", [])}
    out: list[str] = []
    for link in report.get("proposition_links", []):
        if str(link.get("link_kind")) != "attributes_to":
            continue
        if str(link.get("target_proposition_id")) != proposition_id:
            continue
        wrapper = propositions.get(str(link.get("source_proposition_id")))
        if not isinstance(wrapper, dict):
            continue
        args = {str(arg.get("role")): str(arg.get("value") or "") for arg in wrapper.get("arguments", [])}
        out.append(f"{wrapper.get('predicate_key')}:{args.get('speaker','')}")
    return sorted(set(out))


def _arguments_by_role(proposition: dict[str, Any]) -> dict[str, str]:
    return {str(arg.get("role")): str(arg.get("value") or "") for arg in proposition.get("arguments", [])}


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
                links.append(
                    {
                        "link_id": f"{candidate.get('event_id')}:s{link_index}",
                        "event_id": str(candidate.get("event_id") or row.get("event_id") or ""),
                        "source_id": source_id,
                        "source_proposition_id": str(row.get("proposition_id") or ""),
                        "target_proposition_id": str(candidate.get("proposition_id") or ""),
                        "link_kind": "supports",
                        "receipts": [
                            _receipt("support_basis", "block_subject_embeds_causal_subject"),
                            _receipt("support_source", str(row.get("predicate_key") or "")),
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
                links.append(
                    {
                        "link_id": f"{target_row.get('event_id')}:s{link_index}",
                        "event_id": str(target_row.get("event_id") or evidence_row.get("event_id") or ""),
                        "source_id": source_id,
                        "source_proposition_id": str(evidence_row.get("proposition_id") or ""),
                        "target_proposition_id": str(target_row.get("proposition_id") or ""),
                        "link_kind": "supports",
                        "receipts": [
                            _receipt("support_basis", "documentary_support_same_signature"),
                            _receipt("support_source", "court_records"),
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
            if str(left_row.get("predicate_key")) != str(right_row.get("predicate_key")):
                continue
            if _predicate_object_key(left_row) != _predicate_object_key(right_row):
                continue
            if _proposition_signature(left_row) == _proposition_signature(right_row):
                continue
            pair = (
                str(left_row.get("predicate_key")),
                _predicate_object_key(left_row),
                _proposition_signature(left_row),
                _proposition_signature(right_row),
            )
            if pair in seen_disputed:
                continue
            seen_disputed.add(pair)
            disputed_propositions.append(
                {
                    "subject_object_key": _predicate_object_key(left_row),
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

    abstentions = {
        left.source_id: left_report.get("abstentions", []),
        right.source_id: right_report.get("abstentions", []),
    }

    return {
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
        },
        "shared_propositions": shared_propositions,
        "disputed_propositions": disputed_propositions,
        "source_only_propositions": source_only_propositions,
        "shared_facts": shared_facts,
        "disputed_facts": disputed_facts,
        "link_differences": link_differences,
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
