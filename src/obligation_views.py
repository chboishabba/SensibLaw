from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from src.logic_tree import LogicTree, Node, NodeType
from src.obligations import (
    ActorAtom,
    ActionAtom,
    ConditionAtom,
    LifecycleTrigger,
    ObjectAtom,
    ObligationAtom,
    ScopeAtom,
    _normalise_token_text,
    obligation_to_dict,
)
from src.pipeline import normalise, tokenise, build_logic_tree

QUERY_SCHEMA_VERSION = "obligation.query.v1"
EXPLANATION_SCHEMA_VERSION = "obligation.explanation.v1"


def _is_numbering_token(token_norm: str) -> bool:
    if not token_norm:
        return False
    if token_norm.isdigit():
        return True
    if token_norm in {"(", ")", "."}:
        return True
    if re.fullmatch(r"\(?[a-z]\)?", token_norm):
        return True
    return False


def _clause_nodes(tree: LogicTree) -> List[Node]:
    clauses = [node for node in tree.nodes if node.node_type is NodeType.CLAUSE and node.span is not None]
    clauses.sort(key=lambda n: n.span[0] if n.span else 99_999_999)
    return clauses


def _source_prefix(obligation: ObligationAtom) -> str:
    if "-clause-" not in obligation.clause_id:
        return obligation.clause_id
    return obligation.clause_id.rsplit("-clause-", 1)[0]


def _build_clause_map(text: str, source_id: str) -> Dict[str, Tuple[Tuple[int, int], List[str]]]:
    normalized = normalise(text)
    tokens = tokenise(str(normalized))
    tree = build_logic_tree(tokens, source_id=source_id)
    clauses = _clause_nodes(tree)
    clause_map: Dict[str, Tuple[Tuple[int, int], List[str]]] = {}
    for idx, clause in enumerate(clauses):
        clause_id = f"{source_id}-clause-{idx}"
        span = clause.span or (0, 0)
        clause_tokens = tokens[span[0] : span[1]]
        clause_map[clause_id] = (span, [t.text if hasattr(t, "text") else str(t) for t in clause_tokens])
    return clause_map


def _content_positions(token_texts: Sequence[str]) -> List[Optional[int]]:
    positions: List[Optional[int]] = []
    counter = 0
    for tok in token_texts:
        norm = _normalise_token_text(tok)
        if _is_numbering_token(norm):
            positions.append(None)
        else:
            positions.append(counter)
            counter += 1
    return positions


def _content_span(abs_span: Tuple[int, int] | None, clause_span: Tuple[int, int], positions: Sequence[Optional[int]]) -> Tuple[int, int] | None:
    if abs_span is None:
        return None
    start, end = abs_span
    offset = clause_span[0]
    slice_positions = positions[start - offset : end - offset]
    numeric_positions = [p for p in slice_positions if p is not None]
    if not numeric_positions:
        return None
    return min(numeric_positions), max(numeric_positions) + 1


def _sort_list(items: Sequence, key_fn):
    return sorted(items, key=key_fn)


def _dedup_scopes(scope_dicts: List[dict]) -> List[dict]:
    # keep the shortest phrase per category to avoid window-inflated duplicates
    best: dict[str, dict] = {}
    for scope in scope_dicts:
        existing = best.get(scope["category"])
        if (
            existing is None
            or len(scope["normalized"]) < len(existing["normalized"])
            or (
                len(scope["normalized"]) == len(existing["normalized"])
                and scope["normalized"] < existing["normalized"]
            )
        ):
            best[scope["category"]] = scope
    return [scope for _, scope in sorted(best.items(), key=lambda kv: kv[0])]


def _dedup_by_key(entries: List[dict], key_fn) -> List[dict]:
    seen: set[Tuple] = set()
    out: List[dict] = []
    for entry in entries:
        key = key_fn(entry)
        if key in seen:
            continue
        seen.add(key)
        out.append(entry)
    return out


def _atom_dict(atom, clause_span, positions):
    if atom is None:
        return None
    return {
        "text": atom.text,
        "normalized": atom.normalized,
        "span": list(atom.span) if atom.span else None,
        "content_span": _content_span(atom.span, clause_span, positions) if atom.span else None,
        "clause_id": atom.clause_id,
    }


def _condition_dict(cond: ConditionAtom, clause_span, positions):
    return {
        "type": cond.type,
        "span": list(cond.span) if cond.span else None,
        "content_span": _content_span(cond.span, clause_span, positions) if cond.span else None,
        "clause_id": cond.clause_id,
    }


def _scope_dict(scope: ScopeAtom, clause_span, positions):
    return {
        "category": scope.category,
        "text": scope.text,
        "normalized": scope.normalized,
        "span": list(scope.span) if scope.span else None,
        "content_span": _content_span(scope.span, clause_span, positions) if scope.span else None,
        "clause_id": scope.clause_id,
    }


def _lifecycle_dict(trigger: LifecycleTrigger, clause_span, positions):
    return {
        "kind": trigger.kind,
        "text": trigger.text,
        "normalized": trigger.normalized,
        "span": list(trigger.span) if trigger.span else None,
        "content_span": _content_span(trigger.span, clause_span, positions) if trigger.span else None,
        "clause_id": trigger.clause_id,
    }


def query_obligations(
    obligations: Iterable[ObligationAtom],
    *,
    actor: str | None = None,
    action: str | None = None,
    obj: str | None = None,
    scope_category: str | None = None,
    scope_text: str | None = None,
    lifecycle_kind: str | None = None,
    clause_id: str | None = None,
    modality: str | None = None,
    reference_id: str | None = None,
) -> List[ObligationAtom]:
    def _norm(val: Optional[str]) -> Optional[str]:
        return val.lower().strip() if val else None

    actor = _norm(actor)
    action = _norm(action)
    obj = _norm(obj)
    scope_category = _norm(scope_category)
    scope_text = _norm(scope_text)
    lifecycle_kind = _norm(lifecycle_kind)
    clause_id = clause_id.strip() if clause_id else None
    modality = _norm(modality)
    reference_id = reference_id.strip() if reference_id else None

    results: List[ObligationAtom] = []
    for ob in obligations:
        if actor and (ob.actor is None or ob.actor.normalized != actor):
            continue
        if action and (ob.action is None or ob.action.normalized != action):
            continue
        if obj and (ob.obj is None or ob.obj.normalized != obj):
            continue
        if clause_id and ob.clause_id != clause_id:
            continue
        if modality and ob.modality.lower() != modality:
            continue
        if reference_id and reference_id not in ob.reference_identities:
            continue
        if scope_category and not any(scope.category == scope_category for scope in ob.scopes):
            continue
        if scope_text and not any(scope.normalized == scope_text for scope in ob.scopes):
            continue
        if lifecycle_kind and not any(trigger.kind == lifecycle_kind for trigger in ob.lifecycle):
            continue
        results.append(ob)
    return results


def obligations_to_query_payload(obligations: Iterable[ObligationAtom]) -> dict:
    return {
        "version": QUERY_SCHEMA_VERSION,
        "results": [obligation_to_dict(ob) for ob in obligations],
    }


def build_explanations(text: str, obligations: Sequence[ObligationAtom], *, source_id: Optional[str] = None) -> List[dict]:
    if not obligations:
        return []
    prefix = source_id or _source_prefix(obligations[0])
    clause_map = _build_clause_map(text, prefix)

    explanations: List[dict] = []
    for ob in obligations:
        clause_span, clause_tokens = clause_map.get(ob.clause_id, ((0, 0), []))
        positions = _content_positions(clause_tokens)

        actor_dict = _atom_dict(ob.actor, clause_span, positions)
        action_dict = _atom_dict(ob.action, clause_span, positions)
        object_dict = _atom_dict(ob.obj, clause_span, positions)

        conditions = _sort_list(
            ob.conditions,
            key_fn=lambda c: (c.type, _content_span(c.span, clause_span, positions) or (99_999, 99_999)),
        )
        scopes = _sort_list(
            ob.scopes,
            key_fn=lambda s: (
                s.category,
                len(s.normalized),
                s.normalized,
                _content_span(s.span, clause_span, positions) or (99_999, 99_999),
            ),
        )
        lifecycle = _sort_list(
            ob.lifecycle,
            key_fn=lambda l: (l.kind, l.normalized, _content_span(l.span, clause_span, positions) or (99_999, 99_999)),
        )

        scope_dicts = _dedup_scopes(
            [_scope_dict(s, clause_span, positions) for s in scopes],
        )
        lifecycle_dicts = _dedup_by_key(
            [_lifecycle_dict(l, clause_span, positions) for l in lifecycle],
            key_fn=lambda l: (l["kind"], l["normalized"]),
        )

        explanations.append(
            {
                "clause_id": ob.clause_id,
                "type": ob.type,
                "modality": ob.modality,
                "source_span": list(ob.span) if ob.span else None,
                "atoms": {
                    "actor": actor_dict,
                    "action": action_dict,
                    "object": object_dict,
                    "conditions": [_condition_dict(c, clause_span, positions) for c in conditions],
                    "scopes": scope_dicts,
                    "lifecycle": lifecycle_dicts,
                },
                "reference_identities": sorted(ob.reference_identities),
            }
        )
    return explanations


def explanations_to_payload(explanations: Sequence[dict]) -> dict:
    return {
        "version": EXPLANATION_SCHEMA_VERSION,
        "explanations": list(explanations),
    }


__all__ = [
    "QUERY_SCHEMA_VERSION",
    "EXPLANATION_SCHEMA_VERSION",
    "query_obligations",
    "obligations_to_query_payload",
    "build_explanations",
    "explanations_to_payload",
]
