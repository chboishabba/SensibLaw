from __future__ import annotations

import re
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Set, Tuple

from src.logic_tree import LogicTree, Node, NodeType, build, CONDITION_TRIGGERS, EXCEPTION_TRIGGERS
from src.models.document import Document
from src.models.provision import RuleReference
from src.pipeline import build_logic_tree, normalise, tokenise
from src.reference_identity import iter_references_from_document, normalize_for_identity


@dataclass(frozen=True)
class ConditionAtom:
    """Clause-local condition/exception marker."""

    type: str  # if | unless | except | subject | provided | when | where | until | upon
    span: Tuple[int, int] | None
    clause_id: str


@dataclass(frozen=True)
class ActorAtom:
    """Clause-local actor/role bound to an obligation."""

    text: str
    normalized: str
    span: Tuple[int, int] | None
    clause_id: str


@dataclass(frozen=True)
class ActionAtom:
    """Clause-local action (verb head/phrase) bound to an obligation."""

    text: str
    normalized: str
    span: Tuple[int, int] | None
    clause_id: str


@dataclass(frozen=True)
class ObjectAtom:
    """Clause-local object (acted-upon phrase) bound to an obligation."""

    text: str
    normalized: str
    span: Tuple[int, int] | None
    clause_id: str


@dataclass(frozen=True)
class ScopeAtom:
    """Clause-local scope attachment (time/place/context)."""

    category: str  # time | place | context
    text: str
    normalized: str
    span: Tuple[int, int] | None
    clause_id: str


@dataclass(frozen=True)
class LifecycleTrigger:
    """Explicit activation or termination trigger."""

    kind: str  # activation | termination
    text: str
    normalized: str
    span: Tuple[int, int] | None
    clause_id: str


@dataclass(frozen=True)
class ObligationAtom:
    type: str  # obligation | permission | prohibition | exclusion
    modality: str
    clause_id: str
    actor: Optional[ActorAtom]
    action: Optional[ActionAtom]
    obj: Optional[ObjectAtom]
    reference_identities: Set[str]
    conditions: List[ConditionAtom]
    scopes: List[ScopeAtom]
    lifecycle: List[LifecycleTrigger]
    span: Tuple[int, int] | None
    provenance: Optional[dict] = None


def condition_to_dict(cond: ConditionAtom) -> dict:
    return {
        "type": cond.type,
        "span": list(cond.span) if cond.span else None,
        "clause_id": cond.clause_id,
    }


def actor_to_dict(actor: ActorAtom | None) -> Optional[dict]:
    if actor is None:
        return None
    return {
        "text": actor.text,
        "normalized": actor.normalized,
        "span": list(actor.span) if actor.span else None,
        "clause_id": actor.clause_id,
    }


def action_to_dict(action: ActionAtom | None) -> Optional[dict]:
    if action is None:
        return None
    return {
        "text": action.text,
        "normalized": action.normalized,
        "span": list(action.span) if action.span else None,
        "clause_id": action.clause_id,
    }


def object_to_dict(obj: ObjectAtom | None) -> Optional[dict]:
    if obj is None:
        return None
    return {
        "text": obj.text,
        "normalized": obj.normalized,
        "span": list(obj.span) if obj.span else None,
        "clause_id": obj.clause_id,
    }


def scope_to_dict(scope: ScopeAtom) -> dict:
    return {
        "category": scope.category,
        "text": scope.text,
        "normalized": scope.normalized,
        "span": list(scope.span) if scope.span else None,
        "clause_id": scope.clause_id,
    }


def lifecycle_to_dict(trigger: LifecycleTrigger) -> dict:
    return {
        "kind": trigger.kind,
        "text": trigger.text,
        "normalized": trigger.normalized,
        "span": list(trigger.span) if trigger.span else None,
        "clause_id": trigger.clause_id,
    }


def obligation_to_dict(ob: ObligationAtom) -> dict:
    return {
        "type": ob.type,
        "modality": ob.modality,
        "clause_id": ob.clause_id,
        "actor": actor_to_dict(ob.actor),
        "action": action_to_dict(ob.action),
        "object": object_to_dict(ob.obj),
        "reference_identities": sorted(ob.reference_identities),
        "conditions": [condition_to_dict(c) for c in ob.conditions],
        "scopes": [scope_to_dict(s) for s in ob.scopes],
        "lifecycle": [lifecycle_to_dict(lc) for lc in ob.lifecycle],
        "span": list(ob.span) if ob.span else None,
        "provenance": ob.provenance,
    }


_MODAL_PATTERNS: Sequence[Tuple[Tuple[str, ...], str, str]] = (
    (("does", "not", "apply"), "exclusion", "does not apply"),
    (("do", "not", "apply"), "exclusion", "do not apply"),
    (("not", "apply"), "exclusion", "not apply"),
    (("does", "not", "affect"), "exclusion", "does not affect"),
    (("except", "that"), "exclusion", "except that"),
    (("must", "not"), "prohibition", "must not"),
    (("shall", "not"), "prohibition", "shall not"),
    (("may", "not"), "prohibition", "may not"),
    (("must",), "obligation", "must"),
    (("shall",), "obligation", "shall"),
    (("required",), "obligation", "required"),
    (("is", "required", "to"), "obligation", "is required to"),
    (("is", "to"), "obligation", "is to"),
    (("may",), "permission", "may"),
)


def _normalise_token_text(token_text: str) -> str:
    return re.sub(r"[.,;:]+$", "", token_text.lower()).strip()


def _find_modality(tokens: List[str]) -> Optional[Tuple[str, str, int, int]]:
    if not tokens:
        return None
    normalised = [_normalise_token_text(t) for t in tokens]
    for idx in range(len(normalised)):
        for pattern, kind, surface in _MODAL_PATTERNS:
            plen = len(pattern)
            if idx + plen > len(normalised):
                continue
            window = tuple(normalised[idx : idx + plen])
            if window == pattern:
                return kind, surface, idx, plen
    return None


def _find_conditions(tokens: List[str]) -> List[str]:
    conditions: List[str] = []
    triggers = CONDITION_TRIGGERS | EXCEPTION_TRIGGERS
    for tok in tokens:
        norm = _normalise_token_text(tok)
        if norm in triggers and norm not in conditions:
            conditions.append(norm)
    return conditions


def _condition_atoms(
    tokens: List[str], span: Tuple[int, int] | None, clause_id: str
) -> List[ConditionAtom]:
    cond_types = _find_conditions(tokens)
    return [ConditionAtom(type=c, span=span, clause_id=clause_id) for c in cond_types]


def _extract_actor(
    tokens: List[str],
    clause_span: Tuple[int, int] | None,
    clause_id: str,
    modality_start_idx: int,
) -> Optional[ActorAtom]:
    if clause_span is None:
        return None
    if modality_start_idx <= 0:
        return None
    actor_tokens = tokens[:modality_start_idx]
    # strip leading numbering/paren tokens (e.g., "1.", "(a)")
    cleaned: List[str] = []
    for tok in actor_tokens:
        norm = _normalise_token_text(tok)
        if not norm:
            continue
        if norm.isdigit():
            continue
        if all(ch in {"(", ")", "."} for ch in norm):
            continue
        if re.fullmatch(r"[a-z]|\([a-z]\)", norm):
            continue
        cleaned.append(tok)
    actor_tokens = cleaned or actor_tokens
    actor_text = " ".join(actor_tokens).strip()
    if not actor_text:
        return None
    normalized_tokens = [_normalise_token_text(t) for t in actor_tokens]
    normalized = " ".join(t for t in normalized_tokens if t)
    if not normalized:
        return None
    span = (clause_span[0], clause_span[0] + modality_start_idx)
    return ActorAtom(text=actor_text, normalized=normalized, span=span, clause_id=clause_id)


def _extract_action_object(
    tokens: List[str],
    clause_span: Tuple[int, int] | None,
    clause_id: str,
    modal_start_idx: int,
    modal_len: int,
) -> tuple[Optional[ActionAtom], Optional[ObjectAtom]]:
    if clause_span is None:
        return None, None
    after_start = modal_start_idx + modal_len
    if after_start >= len(tokens):
        return None, None
    remainder = tokens[after_start:]
    # drop leading "to" for constructions like "is required to"
    if remainder and _normalise_token_text(remainder[0]) == "to":
        remainder = remainder[1:]
        after_start += 1
    if not remainder:
        return None, None
    norm_tokens = [_normalise_token_text(t) for t in remainder]
    action_norm = norm_tokens[0]
    action_text = remainder[0]
    action_span = (clause_span[0] + after_start, clause_span[0] + after_start + 1)
    obj_tokens = remainder[1:]
    boundary_prepositions = {"on", "in", "within", "during", "while", "until", "upon", "when"}
    for idx, tok in enumerate(obj_tokens):
        if _normalise_token_text(tok) in boundary_prepositions:
            obj_tokens = obj_tokens[:idx]
            break
    obj_norm_tokens = [_normalise_token_text(t) for t in obj_tokens if _normalise_token_text(t)]
    if obj_tokens and obj_norm_tokens:
        obj_text = " ".join(obj_tokens).strip()
        obj_norm = " ".join(obj_norm_tokens)
        obj_span = (action_span[1], action_span[1] + len(obj_tokens))
        obj_atom = ObjectAtom(text=obj_text, normalized=obj_norm, span=obj_span, clause_id=clause_id)
    else:
        obj_atom = None
    action_atom = ActionAtom(text=action_text, normalized=action_norm, span=action_span, clause_id=clause_id)
    return action_atom, obj_atom


def _phrase_category(phrase: str) -> Optional[str]:
    if phrase.startswith("within ") and any(unit in phrase for unit in ("day", "days", "hour", "hours", "month", "months", "year", "years")):
        return "time"
    if phrase.startswith("no later than "):
        return "time"
    if phrase in {"immediately", "at all times"}:
        return "time"
    if phrase in {"on the premises", "within the premises", "within the area", "in the area", "in the zone", "at the site", "on site"}:
        return "place"
    if phrase.startswith("during "):
        return "context"
    if phrase in {"during operations", "during business hours", "when requested", "when directed", "in an emergency"}:
        return "context"
    return None


def _extract_scopes(
    tokens: List[str], clause_span: Tuple[int, int] | None, clause_id: str
) -> List[ScopeAtom]:
    if clause_span is None:
        return []
    norm_tokens = [_normalise_token_text(t) for t in tokens]
    scopes: List[ScopeAtom] = []
    seen: set[tuple[str, int, int]] = set()
    for i in range(len(norm_tokens)):
        for j in range(i + 1, min(len(norm_tokens), i + 6) + 1):
            phrase = " ".join(norm_tokens[i:j]).strip()
            category = _phrase_category(phrase)
            if category is None:
                continue
            span = (clause_span[0] + i, clause_span[0] + j)
            key = (category, span[0], span[1])
            if key in seen:
                continue
            seen.add(key)
            scopes.append(
                ScopeAtom(
                    category=category,
                    text=" ".join(tokens[i:j]),
                    normalized=phrase,
                    span=span,
                    clause_id=clause_id,
                )
            )
    return scopes


def _extract_lifecycle(
    tokens: List[str], clause_span: Tuple[int, int] | None, clause_id: str
) -> List[LifecycleTrigger]:
    if clause_span is None:
        return []
    norm_tokens = [_normalise_token_text(t) for t in tokens]
    triggers: List[LifecycleTrigger] = []
    for idx, tok in enumerate(norm_tokens):
        # termination cues
        if tok in {"until", "ceases", "cease"}:
            end = min(len(tokens), idx + 4)
            phrase_tokens = tokens[idx:end]
            normalized = " ".join(norm_tokens[idx:end]).strip()
            span = (clause_span[0] + idx, clause_span[0] + end)
            triggers.append(
                LifecycleTrigger(
                    kind="termination",
                    text=" ".join(phrase_tokens),
                    normalized=normalized,
                    span=span,
                    clause_id=clause_id,
                )
            )
        # activation cues
        if tok in {"on", "upon", "when", "while", "once"}:
            end = min(len(tokens), idx + 3)
            phrase_tokens = tokens[idx:end]
            normalized = " ".join(norm_tokens[idx:end]).strip()
            span = (clause_span[0] + idx, clause_span[0] + end)
            triggers.append(
                LifecycleTrigger(
                    kind="activation",
                    text=" ".join(phrase_tokens),
                    normalized=normalized,
                    span=span,
                    clause_id=clause_id,
                )
            )
    return triggers


def _env_flag(name: str, default: bool = True) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return str(val).lower() not in ("0", "false", "no", "off", "")


ENABLE_ACTOR_BINDING_DEFAULT = _env_flag("OBLIGATIONS_ENABLE_ACTOR_BINDING", default=True)
ENABLE_ACTION_BINDING_DEFAULT = _env_flag("OBLIGATIONS_ENABLE_ACTION_BINDING", default=True)


def _clause_nodes(tree: LogicTree) -> List[Node]:
    clauses = [node for node in tree.nodes if node.node_type is NodeType.CLAUSE and node.span is not None]
    clauses.sort(key=lambda n: n.span[0] if n.span else 99_999_999)
    return clauses


def _source_id_for_document(doc: Document) -> str:
    if doc.metadata.canonical_id:
        return doc.metadata.canonical_id
    if doc.metadata.provenance:
        return Path(doc.metadata.provenance).stem
    return "document"


def _references_by_clause(references: Iterable[RuleReference]) -> dict[str, List[RuleReference]]:
    buckets: dict[str, List[RuleReference]] = {}
    for ref in references:
        clause_id = (ref.provenance or {}).get("clause_id")
        if clause_id:
            buckets.setdefault(clause_id, []).append(ref)
    return buckets


def extract_obligations_from_text(
    text: str,
    *,
    references: Iterable[RuleReference] = (),
    source_id: str = "document",
    enable_actor_binding: bool | None = None,
    enable_action_binding: bool | None = None,
) -> List[ObligationAtom]:
    normalized = normalise(text)
    tokens = tokenise(str(normalized))
    tree = build_logic_tree(tokens, source_id=source_id)
    clause_nodes = _clause_nodes(tree)
    refs_by_clause = _references_by_clause(references)

    obligations: List[ObligationAtom] = []
    for idx, clause in enumerate(clause_nodes):
        clause_id = f"{source_id}-clause-{idx}"
        clause_tokens = tokens[clause.span[0] : clause.span[1]] if clause.span else []
        token_texts = [t.text if hasattr(t, "text") else str(t) for t in clause_tokens]
        modality = _find_modality(token_texts)
        if modality is None:
            continue
        kind, surface, modal_start, modal_len = modality
        actor_enabled = ENABLE_ACTOR_BINDING_DEFAULT if enable_actor_binding is None else enable_actor_binding
        action_enabled = ENABLE_ACTION_BINDING_DEFAULT if enable_action_binding is None else enable_action_binding
        clause_refs = refs_by_clause.get(clause_id, [])
        ref_ids = {normalize_for_identity(ref).identity_hash for ref in clause_refs}
        actor = (
            _extract_actor(token_texts, clause.span, clause_id, modal_start) if actor_enabled else None
        )
        action_atom: Optional[ActionAtom]
        object_atom: Optional[ObjectAtom]
        if action_enabled:
            action_atom, object_atom = _extract_action_object(
                token_texts, clause.span, clause_id, modal_start, modal_len
            )
        else:
            action_atom, object_atom = None, None
        conditions = _condition_atoms(token_texts, clause.span, clause_id)
        scopes = _extract_scopes(token_texts, clause.span, clause_id)
        lifecycle = _extract_lifecycle(token_texts, clause.span, clause_id)
        provenance = _merge_clause_provenance(clause_refs)
        obligations.append(
            ObligationAtom(
                type=kind,
                modality=surface,
                clause_id=clause_id,
                actor=actor,
                action=action_atom,
                obj=object_atom,
                reference_identities=ref_ids,
                conditions=conditions,
                scopes=scopes,
                lifecycle=lifecycle,
                span=clause.span,
                provenance=provenance,
            )
        )
    return obligations


def extract_obligations_from_document(
    doc: Document, *, enable_actor_binding: bool | None = None, enable_action_binding: bool | None = None
) -> List[ObligationAtom]:
    source_id = _source_id_for_document(doc)
    references = iter_references_from_document(doc)
    return extract_obligations_from_text(
        doc.body,
        references=references,
        source_id=source_id,
        enable_actor_binding=enable_actor_binding,
        enable_action_binding=enable_action_binding,
    )


def _merge_clause_provenance(references: Sequence[RuleReference]) -> Optional[dict]:
    pages: Set[int] = set()
    anchor_used: Optional[str] = None
    for ref in references:
        prov = ref.provenance or {}
        pages.update(prov.get("pages", []) or [])
        if anchor_used is None:
            anchor_used = prov.get("anchor_used")
    prov_out: dict = {}
    if pages:
        prov_out["pages"] = sorted(pages)
    if anchor_used:
        prov_out["anchor_used"] = anchor_used
    if prov_out:
        prov_out.setdefault("source", "token")
    return prov_out or None


__all__ = [
    "ObligationAtom",
    "ConditionAtom",
    "ActorAtom",
    "ActionAtom",
    "ObjectAtom",
    "ScopeAtom",
    "LifecycleTrigger",
    "extract_obligations_from_text",
    "extract_obligations_from_document",
    "obligation_to_dict",
    "condition_to_dict",
    "actor_to_dict",
    "action_to_dict",
    "object_to_dict",
    "scope_to_dict",
    "lifecycle_to_dict",
]
