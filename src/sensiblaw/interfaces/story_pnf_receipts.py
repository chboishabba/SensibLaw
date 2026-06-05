from __future__ import annotations

"""Receipt-backed PredicatePNF emissions for suite-wide story evidence.

The helpers in this module are deliberately deterministic. They project
explicit row/text fields into evidence-only PNF atoms and compare those atoms
with the existing residual lattice; they do not promote facts, mutate tasks, or
claim truth authority.
"""

from collections import defaultdict
from collections.abc import Mapping, Sequence
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from src.text.residual_lattice import (
    PredicatePNF,
    QualifierState,
    TypedArg,
    WrapperState,
    meet_atom,
)


STORY_PNF_RECEIPTS_SCHEMA = "sl.story_pnf_receipts.v0_1"
CLASSIFICATION_DISCOVERY_LATTICE_SCHEMA = "sl.classification_discovery_lattice.v0_1"
AUTHORITY_BOUNDARY = "non-authoritative, receipt-backed, no promotion/mutation"
SUPPORTED_SOURCE_PROFILES = {
    "conversation_text",
    "story_event",
    "observer_capture",
    "execution_envelope",
    "fact_review_item",
    "handoff_entry",
}

_SENSITIVE_TEXT_KEYS = {
    "body",
    "content",
    "details",
    "message",
    "note",
    "notes",
    "ocr_text",
    "raw",
    "statement",
    "text",
    "transcript",
}
_STATUS_WORDS = {
    "hypothesis",
    "projection",
    "candidate",
    "commitment",
    "accepted",
    "promoted",
    "abstained",
    "unknown",
    "alleged",
    "denied",
    "observed",
    "ordered",
    "ruled",
    "sourced",
}
_COMMITMENT_WORDS = {
    "promise": "explicit_promise",
    "promised": "explicit_promise",
    "follow": "follow_needed",
    "blocker": "blocker",
    "blocked": "blocker",
    "done": "done",
    "undone": "undone",
    "superseded": "superseded",
}

_CLASSIFICATION_CLAIM_RE = re.compile(
    r"(?P<subject>[\w\-#:/]+)\s+(?:is|are|was|were)\s+(?:(?P<negation>not|isn't|weren't|wasn't|are not|was not)\s+)?"
    r"(?:a|an|the)\s+(?P<class_value>[^,.;:\\(\)!?\n]+)",
    re.IGNORECASE,
)
_CLASSIFICATION_CLASSIFIED_AS_RE = re.compile(
    r"(?P<subject>[\w\-#:/]+)\s+is\s+classified\s+as\s+(?:(?P<negation>not)\s+)?(?P<class_value>[^,.;:\\(\)!?\n]+)",
    re.IGNORECASE,
)
_KNOWN_WITNESS_RELATIONS: dict[str, str] = {
    "refines": "refinement_candidate",
    "refine": "refinement_candidate",
    "refinement_candidate": "refinement_candidate",
    "reclassifies": "reclassification_candidate",
    "reclassify": "reclassification_candidate",
    "reclassification_candidate": "reclassification_candidate",
    "alias": "alias_equivalent",
    "same_as": "alias_equivalent",
    "equivalent": "alias_equivalent",
    "cross_domain_gap": "cross_domain_gap",
    "unsupported_out_of_domain_candidate": "unsupported_out_of_domain_candidate",
    "unsupported": "unsupported_out_of_domain_candidate",
    "domain_exclusion": "exclusive_contradiction",
    "exclusive_contradiction": "exclusive_contradiction",
}

_CLASSIFICATION_RELATION_FORMALISM = {
    "relation_types": [
        "same",
        "equivalent",
        "refines",
        "reclassifies",
        "domain_gap",
        "excluded_by_witness",
        "unsupported_out_of_domain",
        "unknown",
    ],
    "relation_roots": ["supports", "invalidates", "non_resolving", "unanswered"],
    "relation_leaves": [
        "same",
        "alias_equivalent",
        "refinement_candidate",
        "reclassification_candidate",
        "cross_domain_gap",
        "exclusive_contradiction",
        "unsupported_out_of_domain_candidate",
        "unknown_class_relation",
    ],
    "basis_values": [
        "explicit_claim",
        "explicit_witness",
        "alias_witness",
        "residual_meet",
        "domain_heuristic",
        "sequence_adjacency",
        "unknown",
    ],
}


def collect_canonical_story_pnf_receipts(
    source: Any,
    *,
    source_profile: str,
    source_id: str | None = None,
    context: Mapping[str, Any] | None = None,
    class_relation_witnesses: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Collect suite-wide, receipt-backed PredicatePNF story evidence.

    The returned receipts are comparison evidence only. They are suitable for
    downstream support envelopes, review UX, exports, and archive persistence,
    but not for lane-specific promotion or mutation.
    """

    if source_profile not in SUPPORTED_SOURCE_PROFILES:
        raise ValueError(f"unsupported source_profile: {source_profile}")

    raw_context = context or {}
    context_payload = _clean_mapping(raw_context, sensitive=False)
    resolved_source_id = source_id or _stable_id("story-source", _minimized_source_payload(source))
    rows = _normalize_source_rows(source, source_profile=source_profile)
    context_payload = dict(context_payload)
    existing_witnesses = raw_context.get("class_relation_witnesses", ())
    merged_witnesses: list[Any] = []
    if isinstance(existing_witnesses, Sequence) and not isinstance(existing_witnesses, (str, bytes, bytearray)):
        merged_witnesses.extend(existing_witnesses)
    merged_witnesses.extend(class_relation_witnesses)
    context_payload["class_relation_witnesses"] = merged_witnesses
    diagnostics: list[dict[str, Any]] = []
    emissions: list[dict[str, Any]] = []

    context_atoms = _context_atoms(
        source_profile=source_profile,
        source_id=resolved_source_id,
        context=context_payload,
    )
    for atom in context_atoms:
        emissions.append(
            _emission_receipt(
                atom,
                source_profile=source_profile,
                source_id=resolved_source_id,
                row_ref="context",
                raw_row={},
                sensitive=source_profile == "handoff_entry",
            )
        )

    for index, row in enumerate(rows):
        row_ref = str(row.get("_row_ref") or row.get("id") or row.get("event_id") or f"row:{index}")
        row_atoms = _row_atoms(
            row,
            source_profile=source_profile,
            source_id=resolved_source_id,
            row_ref=row_ref,
        )
        if not row_atoms:
            diagnostics.append(
                {
                    "level": "warning",
                    "code": "no_story_pnf_emissions",
                    "row_ref": row_ref,
                    "profile": source_profile,
                }
            )
        for atom in row_atoms:
            emissions.append(
                _emission_receipt(
                    atom,
                    source_profile=source_profile,
                    source_id=resolved_source_id,
                    row_ref=row_ref,
                    raw_row=row,
                    sensitive=source_profile == "handoff_entry",
                )
            )

    residuals = _residual_receipts(emissions)
    residual_summary = {level: 0 for level in ("exact", "partial", "no_typed_meet", "contradiction")}
    for receipt in residuals:
        residual_summary[str(receipt["residual_level"])] += 1

    diagnostics.append(
        {
            "level": "info",
            "code": "authority_boundary",
            "detail": AUTHORITY_BOUNDARY,
        }
    )
    diagnostics.append(
        {
            "level": "info",
            "code": "story_pnf_counts",
            "source_rows": len(rows),
            "emission_receipts": len(emissions),
            "residual_receipts": len(residuals),
        }
    )

    payload: dict[str, Any] = {
        "schema": STORY_PNF_RECEIPTS_SCHEMA,
        "emission_receipts": emissions,
        "residual_receipts": residuals,
        "residual_summary": residual_summary,
        "diagnostics": diagnostics,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    classification_lattice = build_classification_discovery_lattice(
        emissions,
        class_relation_witnesses=context_payload.get("class_relation_witnesses", ()),
        context=context_payload,
    )
    if classification_lattice is not None:
        payload["classification_lattice"] = classification_lattice

    return payload


def _normalize_source_rows(source: Any, *, source_profile: str) -> list[dict[str, Any]]:
    if source_profile == "conversation_text" and isinstance(source, str):
        return _conversation_rows(source)
    if isinstance(source, Mapping):
        for key in ("rows", "events", "items", "captures", "entries", "utterances"):
            value = source.get(key)
            if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
                return [_row_mapping(item, index) for index, item in enumerate(value)]
        return [_row_mapping(source, 0)]
    if isinstance(source, Sequence) and not isinstance(source, (str, bytes, bytearray)):
        return [_row_mapping(item, index) for index, item in enumerate(source)]
    return [{"_row_ref": "row:0", "text": str(source)}]


def _conversation_rows(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, raw_line in enumerate(line.strip() for line in text.splitlines()):
        if not raw_line:
            continue
        actor = None
        content = raw_line
        match = re.match(r"^([^:]{1,64}):\s+(.*)$", raw_line)
        if match:
            actor = match.group(1).strip()
            content = match.group(2).strip()
        rows.append({"_row_ref": f"utterance:{index}", "actor": actor, "text": content, "medium": "conversation"})
    if not rows and text.strip():
        rows.append({"_row_ref": "utterance:0", "text": text.strip(), "medium": "conversation"})
    return rows


def _row_mapping(item: Any, index: int) -> dict[str, Any]:
    if isinstance(item, Mapping):
        row = {str(key): value for key, value in item.items()}
        row.setdefault("_row_ref", f"row:{index}")
        return row
    return {"_row_ref": f"row:{index}", "text": str(item)}


def _context_atoms(*, source_profile: str, source_id: str, context: Mapping[str, Any]) -> list[PredicatePNF]:
    atoms = [
        _atom(
            family="context/frame",
            name="source_class",
            roles={
                "source": source_id,
                "source_class": source_profile,
            },
            source_id=source_id,
            row_ref="context",
            status="context_frame",
        )
    ]
    for key in ("time", "medium", "audience", "role", "device", "session"):
        value = context.get(key)
        if value not in (None, ""):
            atoms.append(
                _atom(
                    family="context/frame",
                    name=key,
                    roles={"source": source_id, key: str(value)},
                    source_id=source_id,
                    row_ref="context",
                    status="context_frame",
                )
            )
    for key in ("scope", "boundary", "recipient_scope", "sync_policy"):
        value = context.get(key)
        if value not in (None, ""):
            atoms.append(
                _atom(
                    family="scope/boundary",
                    name=key,
                    roles={"source": source_id, key: str(value)},
                    source_id=source_id,
                    row_ref="context",
                    status="scope_boundary",
                )
            )
    return atoms


def _row_atoms(
    row: Mapping[str, Any],
    *,
    source_profile: str,
    source_id: str,
    row_ref: str,
) -> list[PredicatePNF]:
    atoms: list[PredicatePNF] = []
    actor = _first_text(row, "actor", "speaker", "user", "assignee", "runner", "reviewer", "recipient")
    action = _first_text(row, "action", "verb", "command", "result", "status")
    obj = _first_text(row, "object", "target", "task", "claim", "statement", "title", "window_title", "url")
    timestamp = _first_text(row, "timestamp", "time", "date", "started_at", "ended_at")
    text = _first_text(row, "text", "statement", "details", "note", "notes", "body", "ocr_text", "message", "excerpt")

    if actor or action or obj or timestamp:
        roles = {
            "event": row_ref,
            "actor": actor or "unknown_actor",
            "action": action or _profile_default_action(source_profile),
        }
        if obj:
            roles["object"] = obj
        if timestamp:
            roles["time"] = timestamp
        atoms.append(
            _atom(
                family="sequence/event",
                name=_sequence_name(source_profile),
                roles=roles,
                source_id=source_id,
                row_ref=row_ref,
                status="sequence_evidence",
            )
        )

    status = _status_value(row, text)
    if status:
        atoms.append(
            _atom(
                family="epistemic/status",
                name=status,
                roles={"item": row_ref, "status": status},
                source_id=source_id,
                row_ref=row_ref,
                status="epistemic_evidence",
            )
        )

    claim_mode = _claim_mode(row, text, source_profile)
    if claim_mode:
        roles = {"claim": row_ref, "mode": claim_mode}
        if actor:
            roles["actor"] = actor
        if obj or text:
            roles["object"] = obj or _digest_value(text)
        atoms.append(
            _atom(
                family="claim/assertion",
                name=claim_mode,
                roles=roles,
                source_id=source_id,
                row_ref=row_ref,
                status="assertion_evidence",
                polarity="negative" if claim_mode == "denied" else "positive",
            )
        )

    atoms.extend(
        _classification_type_atoms(
            row,
            source_id=source_id,
            row_ref=row_ref,
            text=text,
            default_subject=actor,
        )
    )

    lifecycle = _commitment_value(row, text)
    if lifecycle:
        atoms.append(
            _atom(
                family="commitment/lifecycle",
                name=lifecycle,
                roles={"item": obj or row_ref, "state": lifecycle},
                source_id=source_id,
                row_ref=row_ref,
                status="lifecycle_evidence",
            )
        )

    atoms.extend(_absence_atoms(row, source_profile=source_profile, source_id=source_id, row_ref=row_ref))
    atoms.extend(_scope_atoms(row, source_id=source_id, row_ref=row_ref))

    if source_profile == "handoff_entry":
        atoms.extend(_handoff_atoms(row, source_id=source_id, row_ref=row_ref))
    if source_profile in {"observer_capture", "story_event"}:
        atoms.extend(_observer_atoms(row, source_profile=source_profile, source_id=source_id, row_ref=row_ref))

    return atoms


def _classification_type_atoms(
    row: Mapping[str, Any],
    *,
    source_id: str,
    row_ref: str,
    text: str | None,
    default_subject: str | None,
) -> list[PredicatePNF]:
    claims = _extract_classification_claims(
        row,
        text=text,
        default_subject=default_subject,
    )
    atoms: list[PredicatePNF] = []
    for claim in claims:
        class_value = claim.get("class")
        subject = claim.get("subject")
        if not class_value or not subject:
            continue
        polarity = str(claim.get("polarity") or "positive")
        if polarity not in {"positive", "negative"}:
            polarity = "positive"
        roles = {
            "subject": subject,
            "class": class_value,
        }
        for optional_key in ("thread", "source", "authority"):
            value = claim.get(optional_key)
            if value not in (None, ""):
                roles[optional_key] = str(value)
        if claim.get("sequence") not in (None, ""):
            roles["sequence"] = str(claim["sequence"])

        atoms.append(
            _classification_atom(
                source_id=source_id,
                row_ref=row_ref,
                subject=subject,
                class_value=class_value,
                polarity=polarity,
                roles=roles,
            )
        )
    return atoms


def _extract_classification_claims(
    row: Mapping[str, Any],
    *,
    text: str | None,
    default_subject: str | None,
) -> list[dict[str, str]]:
    claims: list[dict[str, str]] = []
    default_subject = _normalize_subject(default_subject or _first_text(row, "subject", "agent", "speaker", "actor", "actor_id"))

    for value in _first_items(row, "class", "classification", "type", "theme", "classified_as"):
        if value is not None:
            claims.append(
                {
                    "subject": default_subject,
                    "class": _normalize_class_label(str(value)),
                    "polarity": "positive",
                    "thread": _first_text(row, "thread", "thread_id"),
                    "source": _first_text(row, "source", "source_id", "origin"),
                    "authority": _first_text(row, "authority", "authority_id"),
                    "sequence": _first_text(row, "sequence", "step"),
                }
            )

    for value in _first_items(row, "not_class", "not_classification", "not_classified_as", "excluded_class"):
        if value is not None:
            claims.append(
                {
                    "subject": default_subject,
                    "class": _normalize_class_label(str(value)),
                    "polarity": "negative",
                    "thread": _first_text(row, "thread", "thread_id"),
                    "source": _first_text(row, "source", "source_id", "origin"),
                    "authority": _first_text(row, "authority", "authority_id"),
                    "sequence": _first_text(row, "sequence", "step"),
                }
            )

    class_collections = row.get("classifications")
    if isinstance(class_collections, Sequence) and not isinstance(class_collections, (str, bytes, bytearray)):
        for entry in class_collections:
            if isinstance(entry, Mapping):
                subject = _normalize_subject(
                    str(entry.get("subject") or default_subject or "")
                )
                class_value = _normalize_class_label(str(entry.get("class") or entry.get("classification") or entry.get("type") or ""))
                polarity = str(entry.get("polarity") or "positive").lower()
                if class_value:
                    claims.append(
                        {
                            "subject": subject,
                            "class": class_value,
                            "polarity": "negative" if polarity.startswith("neg") else "positive",
                            "thread": _first_text(row, "thread", "thread_id",),
                            "source": _first_text(row, "source", "source_id", "origin"),
                            "authority": _first_text(row, "authority", "authority_id"),
                            "sequence": _first_text(row, "sequence", "step"),
                        }
                    )
            elif isinstance(entry, str):
                normalized_entry = _normalize_class_label(entry)
                if normalized_entry:
                    claims.append(
                        {
                            "subject": default_subject,
                            "class": normalized_entry,
                            "polarity": "positive",
                            "thread": _first_text(row, "thread", "thread_id"),
                            "source": _first_text(row, "source", "source_id", "origin"),
                            "authority": _first_text(row, "authority", "authority_id"),
                            "sequence": _first_text(row, "sequence", "step"),
                        }
                    )

    if text:
        lower_text = text.strip().lower()
        if "classified as" in lower_text:
            claims.extend(_claims_from_classification_pattern(text, _CLASSIFICATION_CLASSIFIED_AS_RE, default_subject))
        if " is " in lower_text:
            claims.extend(_claims_from_classification_pattern(text, _CLASSIFICATION_CLAIM_RE, default_subject))

    normalized_claims: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for claim in claims:
        subject = claim.get("subject")
        class_value = claim.get("class")
        polarity = claim.get("polarity", "positive")
        if not subject or not class_value:
            continue
        key = (subject, class_value, str(polarity))
        if key in seen:
            continue
        seen.add(key)
        normalized_claims.append(claim)
    return normalized_claims


def _first_items(row: Mapping[str, Any], *keys: str) -> list[Any]:
    values: list[Any] = []
    for key in keys:
        value = row.get(key)
        if value is not None:
            if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
                values.extend(list(value))
            else:
                values.append(value)
    return values


def _claims_from_classification_pattern(
    text: str,
    pattern: re.Pattern[str],
    default_subject: str | None,
) -> list[dict[str, str]]:
    claims: list[dict[str, str]] = []
    for match in pattern.finditer(text):
        raw_subject = _normalize_subject(str(match.group("subject") or default_subject or ""))
        if not raw_subject:
            continue
        class_value = _normalize_class_label(match.group("class_value"))
        if not class_value:
            continue
        polarity = "negative" if (match.group("negation") or "").strip() else "positive"
        claims.append(
            {
                "subject": raw_subject,
                "class": class_value,
                "polarity": polarity,
            }
        )
    return claims


def _classification_atom(
    *,
    source_id: str,
    row_ref: str,
    subject: str,
    class_value: str,
    polarity: str,
    roles: Mapping[str, str],
) -> PredicatePNF:
    predicate = "be/classify"
    structural_signature = f"classification:type:{class_value}"
    return PredicatePNF(
        predicate=predicate,
        structural_signature=structural_signature,
        roles={
            role: TypedArg(value=str(value), entity_type=role, provenance=(f"{source_id}:{row_ref}",))
            for role, value in roles.items()
            if value not in (None, "")
        },
        qualifiers=QualifierState(polarity=polarity),
        wrapper=WrapperState(status="classification-evidence", evidence_only=True),
        modifiers={"predicate_family": "classification/type"},
        provenance=(f"{source_id}:{row_ref}",),
        atom_id=_stable_id("classification", {"subject": subject, "class": class_value, "polarity": polarity}),
        domain="classification",
    )


def _normalize_class_label(value: str | None) -> str:
    if value is None:
        return ""
    text = str(value).strip().casefold()
    text = re.sub(r"^(?:a|an|the)\s+", "", text)
    text = re.sub(r"\s+", " ", text)
    text = text.strip(" \t\r\n")
    return text.strip(".,;:!?()")


def _normalize_subject(value: str | None) -> str:
    if value is None:
        return ""
    return str(value).strip().casefold()


def _get_classification_domains() -> tuple[tuple[str, str], ...]:
    return (
        ("dolphin", "biological_taxon"),
        ("morphism", "morphism"),
        ("j-invariant", "algebraic_geometry"),
        ("object", "math_general"),
    )


def _infer_class_domain(class_label: str) -> str:
    normalized = class_label.casefold()
    for marker, domain in _get_classification_domains():
        if marker in normalized:
            return domain
    return "general"


def _classification_claim_root(class_label: str) -> str:
    normalized = _normalize_class_label(class_label)
    if not normalized:
        return "unknown"
    base = re.sub(r"^\d+[\s\-_]*", "", normalized)
    if base and base != normalized:
        return base
    domain = _infer_class_domain(normalized)
    if domain != "general":
        return domain
    return normalized


def _classification_relation_metadata(status: str, *, edge_type: str) -> dict[str, str]:
    status = str(status or "unknown_class_relation")
    if status == "same":
        relation_type = "same"
        relation_root = "supports"
        relation_leaf = "same"
        basis = "explicit_claim" if edge_type in {"classified_as", "not_classified_as", "claim_root_leaf", "leaf_class_projection"} else "sequence_adjacency"
    elif status == "alias_equivalent":
        relation_type = "equivalent"
        relation_root = "supports"
        relation_leaf = "alias_equivalent"
        basis = "alias_witness"
    elif status == "refinement_candidate":
        relation_type = "refines"
        relation_root = "supports"
        relation_leaf = "refinement_candidate"
        basis = "explicit_witness"
    elif status == "reclassification_candidate":
        relation_type = "reclassifies"
        relation_root = "non_resolving"
        relation_leaf = "reclassification_candidate"
        basis = "explicit_witness"
    elif status == "exclusive_contradiction":
        relation_type = "excluded_by_witness"
        relation_root = "invalidates"
        relation_leaf = "exclusive_contradiction"
        basis = "explicit_witness"
    elif status == "cross_domain_gap":
        relation_type = "domain_gap"
        relation_root = "non_resolving"
        relation_leaf = "cross_domain_gap"
        basis = "domain_heuristic"
    elif status == "unsupported_out_of_domain_candidate":
        relation_type = "unsupported_out_of_domain"
        relation_root = "non_resolving"
        relation_leaf = "unsupported_out_of_domain_candidate"
        basis = "explicit_witness"
    else:
        relation_type = "unknown"
        relation_root = "unanswered"
        relation_leaf = "unknown_class_relation"
        basis = "unknown"
    if edge_type == "residual_support":
        basis = "residual_meet"
    return {
        "relation_type": relation_type,
        "relation_root": relation_root,
        "relation_leaf": relation_leaf,
        "relation_basis": basis,
    }


def build_classification_discovery_lattice(
    emission_receipts: Sequence[Mapping[str, Any]],
    *,
    class_relation_witnesses: Sequence[Mapping[str, Any]] | tuple[Mapping[str, Any], ...] = (),
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Build a downstream classification-discovery lattice payload.

    This payload wraps residual comparisons for classification atoms with explicit
    domain/class-relation metadata without modifying the core residual levels.
    """

    classification_claims = _collect_classification_claims_from_emissions(emission_receipts)
    if not classification_claims:
        return None

    witness_context = _coerce_class_relation_witnesses(class_relation_witnesses, context=context or {})
    aliases = _build_alias_mapping(classification_claims, witness_context)

    normalized_claims = [
        {
            "subject": _normalize_subject(claim["subject"]),
            "class": _canonical_class_alias(aliases, _normalize_class_label(claim["class"])),
            "polarity": claim["polarity"],
            "classification_claim_root": _classification_claim_root(
                _canonical_class_alias(aliases, _normalize_class_label(claim["class"]))
            ),
            "classification_leaf": _canonical_class_alias(aliases, _normalize_class_label(claim["class"])),
            "sequence": claim.get("sequence"),
            "thread": claim.get("thread"),
            "source": claim.get("source"),
            "authority": claim.get("authority"),
            "emission_id": claim["emission_id"],
            "atom": claim["atom"],
            "atom_id": claim.get("atom_id"),
        }
        for claim in classification_claims
        if claim.get("subject") and claim.get("class")
    ]

    subject_claims = defaultdict(list)
    for claim in normalized_claims:
        subject_claims[claim["subject"]].append(claim)

    for subject in subject_claims:
        subject_claims[subject].sort(
            key=lambda item: (
                item.get("sequence") is None,
                int(item.get("sequence")) if str(item.get("sequence") or "").isdigit() else item.get("sequence") or "",
                str(item.get("emission_id") or ""),
            )
        )

    nodes = []
    node_by_id: dict[str, dict[str, Any]] = {}
    edges = []

    def _add_node(node_id: str, kind: str, value: str) -> None:
        if node_id not in node_by_id:
            node = {"id": node_id, "kind": kind, "value": value}
            node_by_id[node_id] = node
            nodes.append(node)

    def _add_edge(
        *,
        source: str,
        target: str,
        kind: str,
        status: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        relation_metadata = _classification_relation_metadata(status, edge_type=kind)
        edge_payload: dict[str, Any] = {
            "id": _stable_id("class-edge", {"source": source, "target": target, "kind": kind, "status": status}),
            "source": source,
            "target": target,
            "type": kind,
            "status": status,
            **relation_metadata,
        }
        if metadata:
            if "relation_basis" in metadata:
                edge_payload["relation_basis"] = metadata["relation_basis"]
            edge_payload.update(metadata)
        edges.append(edge_payload)

    for witness in witness_context:
        witness_subject = _normalize_subject(witness.get("subject"))
        source_class = _canonical_class_alias(aliases, _normalize_class_label(witness.get("source_class", "")))
        target_class = _canonical_class_alias(aliases, _normalize_class_label(witness.get("target_class", "")))
        status = witness.get("status") or "unknown_class_relation"
        if not source_class or not target_class:
            continue
        if source_class == target_class:
            continue
        witness_id = _stable_id("class-witness", {
            "subject": witness_subject,
            "source_class": source_class,
            "target_class": target_class,
            "status": status,
        })
        _add_node(witness_id, "relation_witness", f"{source_class}->{target_class}:{status}")
        if witness_subject:
            witness_subject_node = f"subject:{witness_subject}"
            _add_node(witness_subject_node, "subject", witness_subject)
            _add_edge(
                source=witness_subject_node,
                target=witness_id,
                kind="witness_observation",
                status="same",
            )

    for subject in sorted(subject_claims):
        subject_node = _normalize_subject(subject)
        subject_id = f"subject:{subject_node}"
        _add_node(subject_id, "subject", subject_node)

        for claim in subject_claims[subject]:
            class_label = claim["class"]
            class_node = f"class:{class_label}"
            claim_root = claim["classification_claim_root"]
            claim_leaf = claim["classification_leaf"]
            root_node = f"classification_claim_root:{subject_node}:{claim_root}"
            leaf_node = f"classification_leaf:{subject_node}:{claim_leaf}"
            _add_node(class_node, "class", class_label)
            _add_node(root_node, "classification_claim_root", claim_root)
            _add_node(leaf_node, "classification_leaf", claim_leaf)
            _add_edge(
                source=root_node,
                target=leaf_node,
                kind="claim_root_leaf",
                status="same",
                metadata={
                    "subject": subject_node,
                    "classification_claim_root": claim_root,
                    "classification_leaf": claim_leaf,
                    "relation_basis": "explicit_claim",
                },
            )
            _add_edge(
                source=leaf_node,
                target=class_node,
                kind="leaf_class_projection",
                status="same",
                metadata={
                    "subject": subject_node,
                    "classification_claim_root": claim_root,
                    "classification_leaf": claim_leaf,
                    "relation_basis": "explicit_claim",
                },
            )
            role = "classified_as" if claim["polarity"] == "positive" else "not_classified_as"
            _add_edge(
                source=subject_id,
                target=class_node,
                kind=role,
                status="same",
                metadata={
                    "subject": subject_node,
                    "emission_id": claim["emission_id"],
                    "classification_claim_root": claim_root,
                    "classification_leaf": claim_leaf,
                    "relation_basis": "explicit_claim",
                },
            )
            if claim.get("thread"):
                thread_id = f"thread:{_normalize_subject(str(claim['thread']))}"
                _add_node(thread_id, "thread", str(claim["thread"]))
                _add_edge(
                    source=subject_id,
                    target=thread_id,
                    kind="class_thread",
                    status="same",
                )
            if claim.get("source"):
                source_id = f"source:{_normalize_subject(str(claim['source']))}"
                _add_node(source_id, "source", str(claim["source"]))
                _add_edge(
                    source=subject_id,
                    target=source_id,
                    kind="class_source",
                    status="same",
                )
            if claim.get("authority"):
                authority_id = f"authority:{_normalize_subject(str(claim['authority']))}"
                _add_node(authority_id, "authority", str(claim["authority"]))
                _add_edge(
                    source=subject_id,
                    target=authority_id,
                    kind="class_authority",
                    status="same",
                )

        claim_pairs = list(zip(subject_claims[subject], subject_claims[subject][1:]))
        for left, right in claim_pairs:
            relation = _class_pair_relation(
                left,
                right,
                witness_context,
                subject,
            )
            status = relation["status"]
            status = status or "same"
            _add_edge(
                source=f"class:{left['class']}",
                target=f"class:{right['class']}",
                kind="discovery_reclassification",
                status=status,
                metadata={
                    "subject": subject,
                    "left_emission_id": left["emission_id"],
                    "right_emission_id": right["emission_id"],
                    "left_classification_claim_root": left["classification_claim_root"],
                    "right_classification_claim_root": right["classification_claim_root"],
                    "left_classification_leaf": left["classification_leaf"],
                    "right_classification_leaf": right["classification_leaf"],
                    "relation_basis": relation["relation_basis"],
                },
            )
            if status in {"cross_domain_gap", "unsupported_out_of_domain_candidate", "exclusive_contradiction"}:
                _add_edge(
                    source=f"class:{left['class']}",
                    target=f"class:{right['class']}",
                    kind="needs_bridge",
                    status=status,
                    metadata={
                        "subject": subject,
                        "relation_basis": relation["relation_basis"],
                    },
                )

        class_pairs = _ordered_class_pairs([claim["class"] for claim in subject_claims[subject]])
        for left_class, right_class in class_pairs:
            left_claim = next(
                (
                    claim
                    for claim in subject_claims[subject]
                    if claim.get("class") == left_class
                ),
                None,
            )
            right_claim = next(
                (
                    claim
                    for claim in subject_claims[subject]
                    if claim.get("class") == right_class
                ),
                None,
            )
            if not left_claim or not right_claim:
                continue
            class_relation = _class_pair_relation(
                left_claim,
                right_claim,
                witness_context,
                subject,
            )
            _add_edge(
                source=f"class:{left_class}",
                target=f"class:{right_class}",
                kind="class_relation",
                status=class_relation["status"],
                metadata={
                    "subject": subject,
                    "left_classification_claim_root": left_claim["classification_claim_root"],
                    "right_classification_claim_root": right_claim["classification_claim_root"],
                    "left_classification_leaf": left_claim["classification_leaf"],
                    "right_classification_leaf": right_claim["classification_leaf"],
                    "relation_basis": class_relation["relation_basis"],
                },
            )

    residuals: list[dict[str, Any]] = []
    for subject, claims in subject_claims.items():
        sorted_claims = list(claims)
        for left, right in _pairwise(sorted_claims):
            left_atom = left["atom"]
            right_atom = right["atom"]
            if not isinstance(left_atom, Mapping) or not isinstance(right_atom, Mapping):
                continue
            residual = meet_atom(left_atom, right_atom)
            status = _residual_classification_status(left, right, residual, witness_context)
            relation = _classification_relation_metadata(status, edge_type="residual_support")
            residual_id = _stable_id(
                "class-residual",
                {
                    "left": left["emission_id"],
                    "right": right["emission_id"],
                    "status": status,
                },
            )
            residual_node_id = f"residual:{residual_id}"
            _add_node(
                residual_node_id,
                "residual_receipt",
                residual_id,
            )
            _add_edge(
                source=f"class:{left['class']}",
                target=residual_node_id,
                kind="residual_support",
                status=status,
                metadata={
                    "residual_id": residual_id,
                    "residual_level": str(residual.level.name).lower(),
                    "left_emission_id": left["emission_id"],
                    "right_emission_id": right["emission_id"],
                    "relation_basis": "residual_meet",
                },
            )
            _add_edge(
                source=residual_node_id,
                target=f"class:{right['class']}",
                kind="residual_support",
                status=status,
                metadata={
                    "residual_id": residual_id,
                    "residual_level": str(residual.level.name).lower(),
                    "left_emission_id": left["emission_id"],
                    "right_emission_id": right["emission_id"],
                    "relation_basis": "residual_meet",
                },
            )
            residuals.append(
                {
                    "id": residual_id,
                    "left_emission_id": left["emission_id"],
                    "right_emission_id": right["emission_id"],
                    "residual_level": str(residual.level.name).lower(),
                    "status": status,
                    **relation,
                    "relation_basis": "residual_meet",
                }
            )

    nodes.sort(key=lambda item: (item.get("kind"), item.get("value"), item.get("id")))
    edges.sort(key=lambda item: (item.get("type"), item.get("source"), item.get("target"), item.get("status")))

    return {
        "schema": CLASSIFICATION_DISCOVERY_LATTICE_SCHEMA,
        "relation_formalism": _CLASSIFICATION_RELATION_FORMALISM,
        "nodes": nodes,
        "edges": edges,
        "residual_receipts": residuals,
    }


def _collect_classification_claims_from_emissions(
    emission_receipts: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    for receipt in emission_receipts:
        emitted_atom = receipt.get("emitted_atom")
        if not isinstance(emitted_atom, Mapping):
            continue
        if emitted_atom.get("predicate") != "be/classify":
            continue
        structural_signature = str(emitted_atom.get("structural_signature") or "")
        if not structural_signature.startswith("classification:type:"):
            continue
        if emitted_atom.get("modifiers", {}).get("predicate_family") not in {"classification/type", "classification"}:
            continue
        roles = emitted_atom.get("roles")
        if not isinstance(roles, Mapping):
            continue
        subject = (
            _classification_role_value(roles.get("subject"))
            or _classification_role_value(roles.get("agent"))
        )
        class_value = (
            _classification_role_value(roles.get("class"))
            or _classification_role_value(roles.get("theme"))
            or _classification_role_value(roles.get("object"))
        )
        if not subject or not class_value:
            continue
        qualifiers = emitted_atom.get("qualifiers")
        polarity = "positive"
        if isinstance(qualifiers, Mapping):
            polarity = str(qualifiers.get("polarity") or "positive")
        claims.append(
            {
                "subject": subject,
                "class": _normalize_class_label(class_value),
                "polarity": polarity if polarity in {"positive", "negative"} else "positive",
                "sequence": _classification_role_value(roles.get("sequence")),
                "thread": _classification_role_value(roles.get("thread")),
                "source": _classification_role_value(roles.get("source")),
                "authority": _classification_role_value(roles.get("authority")),
                "emission_id": str(receipt.get("id") or _stable_id("fallback", emitted_atom)),
                "atom": emitted_atom,
                "atom_id": _classification_role_value(emitted_atom.get("atom_id")) or _classification_role_value(roles.get("subject")) or "",
            }
        )
    return claims


def _classification_role_value(value: Any) -> str:
    if isinstance(value, Mapping):
        raw = value.get("value")
        if raw is None:
            return ""
        return str(raw)
    if value is None:
        return ""
    return str(value)


def _coerce_class_relation_witnesses(
    witnesses: Sequence[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
    context: Mapping[str, Any] | None,
) -> list[dict[str, str]]:
    context = context or {}
    raw_witnesses = list(witnesses)
    context_witnesses = context.get("class_relation_witnesses")
    if isinstance(context_witnesses, Sequence) and not isinstance(context_witnesses, (str, bytes, bytearray)):
        raw_witnesses.extend([item for item in context_witnesses if isinstance(item, Mapping)])
    normalised: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for item in raw_witnesses:
        if not isinstance(item, Mapping):
            continue
        relation = str(item.get("relation") or item.get("status") or item.get("relation_status") or "").strip().lower()
        status = _KNOWN_WITNESS_RELATIONS.get(relation, "unknown_class_relation")
        strength = str(item.get("strength") or item.get("witness_strength") or "")
        if relation == "domain_exclusion":
            if strength.lower() in {"weak", "low", "possible"}:
                status = "unsupported_out_of_domain_candidate"
            else:
                status = "exclusive_contradiction"
        source_class = _normalize_class_label(
            str(
                item.get("from_class")
                or item.get("source_class")
                or item.get("left_class")
                or item.get("class_a")
                or item.get("from_domain")
                or item.get("source_domain")
                or ""
            )
        )
        target_class = _normalize_class_label(
            str(
                item.get("to_class")
                or item.get("target_class")
                or item.get("right_class")
                or item.get("class_b")
                or item.get("to_domain")
                or item.get("target_domain")
                or ""
            )
        )
        if not source_class:
            source_class = _infer_class_domain(
                str(
                    item.get("from_domain")
                    or item.get("source_domain")
                    or item.get("class_a_domain")
                    or ""
                )
            )
        if not target_class:
            target_class = _infer_class_domain(
                str(
                    item.get("to_domain")
                    or item.get("target_domain")
                    or item.get("class_b_domain")
                    or ""
                )
            )
        subject = _normalize_subject(str(item.get("subject") or ""))
        key = (subject, source_class, target_class, status)
        if key in seen:
            continue
        seen.add(key)
        normalised.append(
            {
                "subject": subject,
                "source_class": source_class,
                "target_class": target_class,
                "status": status,
                "relation": relation,
                "strength": strength,
            }
        )
    return normalised


def _class_signature_values(class_value: str) -> set[str]:
    normalized = _normalize_class_label(class_value)
    if not normalized:
        return set()
    base = re.sub(r"^\d+[\s\-_]*", "", normalized)
    signatures = {normalized}
    if base and base != normalized:
        signatures.add(base)
    domain = _infer_class_domain(normalized)
    if domain != "general":
        signatures.add(domain)
    return signatures


def _class_match_for_witness(
    class_value: str,
    witness_value: str,
) -> bool:
    normalized_class = _normalize_class_label(class_value)
    witness_normalized = _normalize_class_label(witness_value)
    if not normalized_class or not witness_normalized:
        return False
    signatures = _class_signature_values(normalized_class)
    return (
        normalized_class == witness_normalized
        or witness_normalized in signatures
        or _normalize_class_label(witness_normalized) in signatures
    )


def _build_alias_mapping(
    claims: Sequence[Mapping[str, Any]],
    witnesses: list[dict[str, str]],
) -> dict[str, str]:
    classes = sorted({_normalize_class_label(str(item.get("class") or "")) for item in claims if item.get("class")})
    parent = {class_value: class_value for class_value in classes}

    def find(value: str) -> str:
        root = value
        while parent[root] != root:
            root = parent[root]
        while parent[value] != value:
            value = parent[value]
            parent[value] = root
        return root

    def union(left: str, right: str) -> None:
        if not left or not right:
            return
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for witness in witnesses:
        if witness.get("status") != "alias_equivalent":
            continue
        union(witness.get("source_class", ""), witness.get("target_class", ""))

    canonical: dict[str, str] = {}
    for class_value in classes:
        canonical[class_value] = find(class_value)
    return canonical


def _canonical_class_alias(alias_map: Mapping[str, str], class_value: str) -> str:
    if not alias_map:
        return class_value
    return alias_map.get(class_value, class_value)


def _lookup_class_relation_witness(
    left_class: str,
    right_class: str,
    subject: str,
    witness_context: list[dict[str, str]],
) -> dict[str, str] | None:
    for witness in witness_context:
        witness_subject = witness.get("subject")
        if witness_subject and witness_subject != subject:
            continue
        source = witness.get("source_class", "")
        target = witness.get("target_class", "")
        if _class_match_for_witness(left_class, source) and _class_match_for_witness(right_class, target):
            return witness
        if _class_match_for_witness(right_class, source) and _class_match_for_witness(left_class, target):
            return witness
    return None


def _class_pair_relation(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    witness_context: list[dict[str, str]],
    subject: str,
) -> dict[str, str]:
    left_class = _normalize_class_label(str(left.get("class") or ""))
    right_class = _normalize_class_label(str(right.get("class") or ""))
    left_subject = _normalize_subject(str(left.get("subject") or ""))
    right_subject = _normalize_subject(str(right.get("subject") or ""))
    if left_subject and right_subject and left_subject == right_subject and left_class == right_class:
        left_polarity = str(left.get("polarity") or "positive")
        right_polarity = str(right.get("polarity") or "positive")
        if left_polarity == right_polarity:
            status = "same"
            metadata = _classification_relation_metadata(status, edge_type="class_relation")
            metadata["relation_basis"] = "explicit_claim"
            metadata["status"] = status
            return metadata
        status = "exclusive_contradiction"
        metadata = _classification_relation_metadata(status, edge_type="class_relation")
        metadata["relation_basis"] = "explicit_claim"
        metadata["status"] = status
        return metadata

    witness = _lookup_class_relation_witness(
        left_class=left_class,
        right_class=right_class,
        subject=subject,
        witness_context=witness_context,
    )
    if witness is not None:
        status = witness.get("status") or "unknown_class_relation"
        metadata = _classification_relation_metadata(status, edge_type="class_relation")
        if status == "alias_equivalent":
            metadata["relation_basis"] = "alias_witness"
        else:
            metadata["relation_basis"] = "explicit_witness"
        metadata["status"] = status
        return metadata

    if _infer_class_domain(left_class) != _infer_class_domain(right_class):
        status = "cross_domain_gap"
        metadata = _classification_relation_metadata(status, edge_type="class_relation")
        metadata["relation_basis"] = "domain_heuristic"
        metadata["status"] = status
        return metadata
    status = "unknown_class_relation"
    metadata = _classification_relation_metadata(status, edge_type="class_relation")
    metadata["status"] = status
    return metadata


def _class_pair_relation_status(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    witness_context: list[dict[str, str]],
    subject: str,
) -> str:
    return _class_pair_relation(left, right, witness_context, subject)["status"]


def _ordered_class_pairs(values: Sequence[str]) -> list[tuple[str, str]]:
    unique_classes: list[str] = []
    for value in values:
        normalized = _normalize_class_label(str(value))
        if normalized not in unique_classes:
            unique_classes.append(normalized)
    pairs: list[tuple[str, str]] = []
    for left_index, left in enumerate(unique_classes):
        for right in unique_classes[left_index + 1 :]:
            if left and right:
                pairs.append((left, right))
    return pairs


def _pairwise(values: Sequence[Mapping[str, Any]]) -> list[tuple[Mapping[str, Any], Mapping[str, Any]]]:
    return [
        (values[index], values[index + 1])
        for index in range(len(values) - 1)
    ]


def _residual_classification_status(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    residual,
    witness_context: list[dict[str, str]],
) -> str:
    if residual is not None and getattr(residual, "level", None) is not None:
        level_name = str(residual.level.name).lower()
    else:
        level_name = ""
    if level_name == "contradiction":
        if str(left.get("class")) == str(right.get("class")):
            return "exclusive_contradiction"
    if str(left.get("class")) == str(right.get("class")) and str(left.get("subject")) == str(right.get("subject")):
        if str(left.get("polarity", "positive")).lower() == str(right.get("polarity", "positive")).lower():
            return "same"
    return _class_pair_relation_status(left, right, witness_context, _normalize_subject(str(left.get("subject") or "")))


def render_classification_discovery_lattice_png(
    lattice_payload: Mapping[str, Any],
    output_path: str | Path,
) -> None:
    """Render a deterministic PNG visualisation of a classification lattice payload."""

    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt
    import networkx as nx

    nodes = lattice_payload.get("nodes", [])
    edges = lattice_payload.get("edges", [])
    if not isinstance(nodes, Sequence):
        nodes = []
    if not isinstance(edges, Sequence):
        edges = []

    graph = nx.DiGraph()
    for node in nodes:
        if not isinstance(node, Mapping):
            continue
        node_id = str(node.get("id"))
        if not node_id:
            continue
        graph.add_node(node_id, kind=str(node.get("kind") or "node"), value=str(node.get("value") or node_id))

    for edge in edges:
        if not isinstance(edge, Mapping):
            continue
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        if source and target and source in graph.nodes and target in graph.nodes:
            graph.add_edge(source, target, type=str(edge.get("type") or "relation"), status=str(edge.get("status") or "unknown"))

    if not graph.nodes:
        graph.add_node("empty")

    kind_colors = {
        "subject": "#2b6cb0",
        "class": "#2f855a",
        "thread": "#dd6b20",
        "source": "#6b46c1",
        "authority": "#b83280",
        "residual_receipt": "#718096",
        "relation_witness": "#319795",
        "bridge": "#b7791f",
    }

    positions = nx.spring_layout(graph, seed=17_606, k=0.9)
    plt.figure(figsize=(max(6, len(graph.nodes) * 0.7), max(4, len(graph.nodes) * 0.45)))
    node_colors = [kind_colors.get(graph.nodes[node].get("kind", "node"), "#2d3748") for node in graph.nodes]
    nx.draw_networkx_nodes(graph, positions, node_size=620, node_color=node_colors)
    nx.draw_networkx_labels(
        graph,
        positions,
        {
            node: str(graph.nodes[node].get("value") or node)
            for node in graph.nodes
        },
        font_size=8,
    )

    edge_colors = []
    for edge in graph.edges(data=True):
        status = str(edge[2].get("status") or "")
        if status == "exclusive_contradiction":
            edge_colors.append("#c53030")
        elif status == "same":
            edge_colors.append("#2f855a")
        elif status in {"cross_domain_gap", "unsupported_out_of_domain_candidate"}:
            edge_colors.append("#b7791f")
        else:
            edge_colors.append("#2b6cb0")

    nx.draw_networkx_edges(graph, positions, arrowstyle="-|>", arrowsize=12, edge_color=edge_colors)
    nx.draw_networkx_edge_labels(
        graph,
        positions,
        edge_labels={
            (source, target): f"{data.get('type')}/{data.get('status')}"
            for source, target, data in graph.edges(data=True)
        },
        font_size=6,
    )

    plt.axis("off")
    plt.tight_layout()
    plt.savefig(str(output_path), format="png")
    plt.close()


def _absence_atoms(
    row: Mapping[str, Any],
    *,
    source_profile: str,
    source_id: str,
    row_ref: str,
) -> list[PredicatePNF]:
    expected = {
        "story_event": ("timestamp", "actor"),
        "observer_capture": ("timestamp", "device", "session"),
        "execution_envelope": ("command", "status", "log"),
        "fact_review_item": ("source", "statement"),
        "handoff_entry": ("recipient", "scope"),
        "conversation_text": ("actor",),
    }.get(source_profile, ())
    atoms = []
    for field in expected:
        if _first_text(row, field) in (None, ""):
            atoms.append(
                _atom(
                    family="absence/gap",
                    name=f"missing_{field}",
                    roles={"item": row_ref, "missing": field},
                    source_id=source_id,
                    row_ref=row_ref,
                    status="gap_evidence",
                )
            )
    return atoms


def _scope_atoms(row: Mapping[str, Any], *, source_id: str, row_ref: str) -> list[PredicatePNF]:
    atoms = []
    for field in ("scope", "boundary", "privacy", "recipient_scope", "sync_policy"):
        value = _first_text(row, field)
        if value:
            atoms.append(
                _atom(
                    family="scope/boundary",
                    name=field,
                    roles={"item": row_ref, field: value},
                    source_id=source_id,
                    row_ref=row_ref,
                    status="scope_boundary",
                )
            )
    return atoms


def _handoff_atoms(row: Mapping[str, Any], *, source_id: str, row_ref: str) -> list[PredicatePNF]:
    atoms = []
    recipient = _first_text(row, "recipient", "recipient_profile", "to")
    if recipient:
        atoms.append(
            _atom(
                family="handoff/export",
                name="recipient_profile",
                roles={"entry": row_ref, "recipient": recipient},
                source_id=source_id,
                row_ref=row_ref,
                status="handoff_evidence",
            )
        )
    for field in ("redaction", "redaction_marker", "exclusion", "professional_note_boundary"):
        value = _first_text(row, field)
        if value:
            atoms.append(
                _atom(
                    family="handoff/export",
                    name=field,
                    roles={"entry": row_ref, field: value},
                    source_id=source_id,
                    row_ref=row_ref,
                    status="handoff_evidence",
                )
            )
    return atoms


def _observer_atoms(
    row: Mapping[str, Any],
    *,
    source_profile: str,
    source_id: str,
    row_ref: str,
) -> list[PredicatePNF]:
    roles = {"capture": row_ref, "source_class": source_profile}
    for field in ("device", "session", "window_title", "url", "app", "event_id"):
        value = _first_text(row, field)
        if value:
            roles[field] = value
    return [
        _atom(
            family="observer/evidence",
            name="capture",
            roles=roles,
            source_id=source_id,
            row_ref=row_ref,
            status="observer_only",
        )
    ]


def _atom(
    *,
    family: str,
    name: str,
    roles: Mapping[str, str],
    source_id: str,
    row_ref: str,
    status: str,
    polarity: str = "positive",
) -> PredicatePNF:
    predicate = f"{family}.{name}"
    normalized_roles = {
        role: TypedArg(value=str(value), entity_type=role, provenance=(f"{source_id}:{row_ref}",))
        for role, value in roles.items()
        if value not in (None, "")
    }
    return PredicatePNF(
        predicate=predicate,
        structural_signature=f"{family}:{name}",
        roles=normalized_roles,
        qualifiers=QualifierState(polarity=polarity),
        wrapper=WrapperState(status=status, evidence_only=True),
        modifiers={"predicate_family": family},
        provenance=(f"{source_id}:{row_ref}",),
        atom_id=_stable_id("story-pnf", {"predicate": predicate, "roles": {k: v.value for k, v in normalized_roles.items()}}),
        domain="story_pnf",
    )


def _emission_receipt(
    atom: PredicatePNF,
    *,
    source_profile: str,
    source_id: str,
    row_ref: str,
    raw_row: Mapping[str, Any],
    sensitive: bool,
) -> dict[str, Any]:
    emitted_atom = atom.to_dict()
    payload = {
        "source_profile": source_profile,
        "source_id": source_id,
        "row_ref": row_ref,
        "emitted_atom": emitted_atom,
    }
    return {
        "id": _stable_id("story-pnf-emission", payload),
        "schema": "sl.pnf_emission_receipt.v0_1",
        "status": "available",
        "parser_profile": f"sensiblaw.story_pnf.{source_profile}.v0_1",
        "reducer_profile": "sensiblaw.story_pnf_receipts.v0_1",
        "source_profile": source_profile,
        "source_id": source_id,
        "source_span": {
            "row_ref": row_ref,
            "minimized_row": _clean_mapping(raw_row, sensitive=sensitive),
        },
        "atom_id": atom.atom_id,
        "pnf_id": atom.atom_id,
        "predicate_family": atom.modifiers.get("predicate_family"),
        "emitted_atom": emitted_atom,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "receipt_ids": [],
    }


def _residual_receipts(emissions: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    receipts = []
    atoms = [(item, item.get("emitted_atom")) for item in emissions if isinstance(item.get("emitted_atom"), Mapping)]
    for left_index, (left_receipt, left_atom) in enumerate(atoms):
        for right_receipt, right_atom in atoms[left_index + 1 :]:
            residual = meet_atom(left_atom, right_atom)
            level = residual.level.name.lower()
            payload = {
                "left_emission_receipt_id": left_receipt.get("id"),
                "right_emission_receipt_id": right_receipt.get("id"),
                "residual_level": level,
                "residual": residual.to_dict(),
            }
            receipts.append(
                {
                    "id": _stable_id("story-pnf-residual", payload),
                    "schema": "sl.pnf_residual_receipt.v0_1",
                    "status": "available",
                    "left_atom_id": left_receipt.get("atom_id"),
                    "right_atom_id": right_receipt.get("atom_id"),
                    "left_emission_receipt_id": left_receipt.get("id"),
                    "right_emission_receipt_id": right_receipt.get("id"),
                    "residual_id": _stable_id("story-residual", payload),
                    "residual_level": level,
                    "relation": "story_pnf_comparison",
                    "predicate_family": _residual_family(left_receipt, right_receipt),
                    "payload": {
                        **payload,
                        "residual_computation_profile": "sensiblaw.story_pnf_receipts.v0_1",
                        "authority_boundary": AUTHORITY_BOUNDARY,
                    },
                    "receipt_ids": [],
                }
            )
    return receipts


def _residual_family(left: Mapping[str, Any], right: Mapping[str, Any]) -> str:
    left_family = str(left.get("predicate_family") or "")
    right_family = str(right.get("predicate_family") or "")
    if left_family == right_family:
        return left_family
    return "cross_family"


def _status_value(row: Mapping[str, Any], text: str | None) -> str | None:
    direct = _first_text(row, "epistemic_status", "status", "review_status", "claim_status")
    if direct:
        normalized = _tokenize_status(direct)
        if normalized in _STATUS_WORDS:
            return normalized
    lower = (text or "").lower()
    for word in sorted(_STATUS_WORDS):
        if re.search(rf"\b{re.escape(word)}\b", lower):
            return "accepted" if word == "promoted" else word
    return None


def _claim_mode(row: Mapping[str, Any], text: str | None, source_profile: str) -> str | None:
    direct = _first_text(row, "claim_mode", "assertion", "finding", "allegation_status")
    if direct:
        normalized = _tokenize_status(direct)
        if normalized in {"claimed", "denied", "alleged", "observed", "ordered", "ruled", "sourced"}:
            return normalized
    lower = " ".join(str(value).lower() for value in (direct, text, _first_text(row, "status")) if value)
    for mode in ("denied", "alleged", "observed", "ordered", "ruled", "sourced", "claimed"):
        if re.search(rf"\b{mode}\b", lower):
            return mode
    if source_profile == "fact_review_item" and (_first_text(row, "statement", "claim") or text):
        return "claimed"
    return None


def _commitment_value(row: Mapping[str, Any], text: str | None) -> str | None:
    direct = _first_text(row, "lifecycle", "lifecycle_state", "commitment", "task_state")
    lower = " ".join(str(value).lower() for value in (direct, text, _first_text(row, "status")) if value)
    for needle, value in _COMMITMENT_WORDS.items():
        if re.search(rf"\b{re.escape(needle)}\b", lower):
            return value
    return None


def _tokenize_status(value: str) -> str | None:
    token = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    if token in _STATUS_WORDS or token == "claimed":
        return token
    if token in {"accepted_promoted", "promoted"}:
        return "accepted"
    return token or None


def _first_text(row: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def _profile_default_action(source_profile: str) -> str:
    return {
        "observer_capture": "captured",
        "story_event": "recorded",
        "execution_envelope": "executed",
        "fact_review_item": "reviewed",
        "handoff_entry": "handed_off",
        "conversation_text": "uttered",
    }.get(source_profile, "observed")


def _sequence_name(source_profile: str) -> str:
    if source_profile == "execution_envelope":
        return "execution_run"
    if source_profile == "observer_capture":
        return "observer_capture"
    if source_profile == "story_event":
        return "story_event"
    return "event"


def _clean_mapping(row: Mapping[str, Any], *, sensitive: bool) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in sorted(row.items()):
        if key.startswith("_"):
            continue
        key_text = str(key)
        if sensitive and key_text.lower() in _SENSITIVE_TEXT_KEYS:
            cleaned[key_text] = _digest_payload(value)
        elif key_text.lower() in _SENSITIVE_TEXT_KEYS and isinstance(value, str) and len(value) > 240:
            cleaned[key_text] = _digest_payload(value)
        elif isinstance(value, (str, int, float, bool)) or value is None:
            cleaned[key_text] = value
        else:
            cleaned[key_text] = _digest_payload(value)
    return cleaned


def _minimized_source_payload(source: Any) -> dict[str, Any]:
    if isinstance(source, str):
        return {"type": "text", **_digest_payload(source)}
    if isinstance(source, Mapping):
        return {"type": "mapping", "keys": sorted(str(key) for key in source)}
    if isinstance(source, Sequence) and not isinstance(source, (str, bytes, bytearray)):
        return {"type": "sequence", "length": len(source)}
    return {"type": type(source).__name__, **_digest_payload(repr(source))}


def _digest_value(value: str | None) -> str:
    if value is None:
        return ""
    return _stable_id("text", value)


def _digest_payload(value: Any) -> dict[str, Any]:
    encoded = _json_bytes(value)
    return {"sha256": hashlib.sha256(encoded).hexdigest(), "bytes": len(encoded)}


def _stable_id(prefix: str, payload: Any) -> str:
    return f"{prefix}:{hashlib.sha256(_json_bytes(payload)).hexdigest()[:24]}"


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


__all__ = [
    "AUTHORITY_BOUNDARY",
    "STORY_PNF_RECEIPTS_SCHEMA",
    "CLASSIFICATION_DISCOVERY_LATTICE_SCHEMA",
    "SUPPORTED_SOURCE_PROFILES",
    "build_classification_discovery_lattice",
    "render_classification_discovery_lattice_png",
    "collect_canonical_story_pnf_receipts",
]
