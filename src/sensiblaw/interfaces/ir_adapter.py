from __future__ import annotations

"""Minimal parser-grounded IR layer above canonical parser output."""

import hashlib
from typing import Any

from .ir_types import (
    InteractionMode,
    InteractionProjectionReceipt,
    QueryEdge,
    QueryNode,
    QueryTree,
)
from .parser_adapter import (
    collect_canonical_operational_structure_occurrences,
    parse_canonical_text,
)


_AMBIENT_TOKENS = frozenset(
    {
        "hello",
        "hi",
        "hey",
        "yo",
        "there",
        "thanks",
        "thank",
        "cheers",
        "welcome",
        "goodbye",
        "bye",
    }
)
_IMPERATIVE_HEADS = frozenset(
    {
        "please",
        "tell",
        "say",
        "send",
        "give",
        "share",
        "help",
        "explain",
        "check",
        "run",
        "do",
        "greet",
        "message",
        "contact",
        "reply",
        "provide",
        "show",
        "list",
        "confirm",
    }
)
_QUESTION_WORDS = frozenset(
    {
        "who",
        "what",
        "when",
        "where",
        "why",
        "how",
        "which",
        "whom",
        "whose",
        "can",
        "could",
        "would",
        "will",
        "should",
        "is",
        "are",
        "am",
        "do",
        "does",
        "did",
        "have",
        "has",
    }
)
_DIRECT_ADDRESS_TOKENS = frozenset({"you", "your", "yours", "u", "team", "all", "everyone", "somebody", "someone"})


def _stable_id(prefix: str, *parts: object) -> str:
    seed = "|".join(str(part) for part in parts)
    return f"{prefix}:{hashlib.sha1(seed.encode('utf-8')).hexdigest()[:12]}"


def _token_text(token: dict[str, Any]) -> str:
    return str(token.get("text", ""))


def _sentence_features(sentence: dict[str, Any]) -> dict[str, Any]:
    text = str(sentence.get("text", ""))
    tokens = [token for token in sentence.get("tokens", ()) if _token_text(token).strip()]
    token_texts = [_token_text(token) for token in tokens]
    lower_texts = [value.casefold() for value in token_texts]
    non_punct = [value for value in token_texts if any(ch.isalnum() for ch in value)]
    first_lower = non_punct[0].casefold() if non_punct else ""

    has_question_mark = "?" in token_texts or text.rstrip().endswith("?")
    has_question_word = any(value in _QUESTION_WORDS for value in lower_texts[:2])
    has_please = "please" in lower_texts
    starts_with_imperative = first_lower in _IMPERATIVE_HEADS
    contains_direct_address = any(value in _DIRECT_ADDRESS_TOKENS for value in lower_texts)
    leading_vocative = False
    if tokens:
        first = tokens[0]
        second = tokens[1] if len(tokens) > 1 else None
        first_text = _token_text(first)
        second_text = _token_text(second) if second is not None else ""
        if first_text and first_text[:1].isupper() and second_text == ",":
            leading_vocative = True

    return {
        "has_question_mark": has_question_mark,
        "has_question_word": has_question_word,
        "has_please": has_please,
        "starts_with_imperative": starts_with_imperative,
        "contains_direct_address": contains_direct_address or leading_vocative,
        "token_count": len(tokens),
    }


def build_query_tree(text: str) -> QueryTree:
    parsed = parse_canonical_text(text)
    structures = collect_canonical_operational_structure_occurrences(text)

    nodes: list[QueryNode] = []
    edges: list[QueryEdge] = []
    root_ids: list[str] = []

    sentence_nodes: list[QueryNode] = []
    token_node_ids: dict[int, str] = {}

    for sentence_index, sentence in enumerate(parsed.get("sents", ())):
        sentence_id = f"sentence:{sentence_index}"
        tokens = tuple(int(token["index"]) for token in sentence.get("tokens", ()))
        sentence_node = QueryNode(
            node_id=sentence_id,
            text=str(sentence.get("text", "")),
            span_start=int(sentence.get("start", 0)),
            span_end=int(sentence.get("end", 0)),
            kind="sentence",
            token_indices=tokens,
            features=_sentence_features(sentence),
        )
        nodes.append(sentence_node)
        sentence_nodes.append(sentence_node)
        root_ids.append(sentence_id)

        for token in sentence.get("tokens", ()):
            token_index = int(token["index"])
            token_id = f"token:{token_index}"
            token_node = QueryNode(
                node_id=token_id,
                text=_token_text(token),
                span_start=int(token["start"]),
                span_end=int(token["end"]),
                kind="token",
                token_indices=(token_index,),
                features={
                    "lemma": str(token.get("lemma", "")),
                    "pos": str(token.get("pos", "")),
                    "tag": str(token.get("tag", "")),
                    "dep": str(token.get("dep", "")),
                    "head_index": int(token.get("head_index", token_index)),
                    "head_text": str(token.get("head_text", "")),
                },
            )
            nodes.append(token_node)
            token_node_ids[token_index] = token_id
            edges.append(
                QueryEdge(
                    src_id=sentence_id,
                    dst_id=token_id,
                    kind="contains",
                    evidence_span=(token_node.span_start, token_node.span_end),
                )
            )

    for current, following in zip(sentence_nodes, sentence_nodes[1:]):
        edges.append(
            QueryEdge(
                src_id=current.node_id,
                dst_id=following.node_id,
                kind="follows",
                evidence_span=(current.span_end, following.span_start),
            )
        )

    for sentence_index, sentence in enumerate(parsed.get("sents", ())):
        sentence_id = f"sentence:{sentence_index}"
        by_index = {int(token["index"]): token for token in sentence.get("tokens", ())}
        for token in sentence.get("tokens", ()):
            head_index = int(token.get("head_index", token["index"]))
            token_index = int(token["index"])
            if head_index == token_index:
                continue
            head_token = by_index.get(head_index)
            if head_token is None:
                continue
            edges.append(
                QueryEdge(
                    src_id=token_node_ids[head_index],
                    dst_id=token_node_ids[token_index],
                    kind="depends_on",
                    evidence_span=(int(token["start"]), int(token["end"])),
                )
            )

    for structure_index, occurrence in enumerate(structures):
        structure_id = f"struct:{structure_index}"
        structure_node = QueryNode(
            node_id=structure_id,
            text=occurrence.text,
            span_start=occurrence.start_char,
            span_end=occurrence.end_char,
            kind="structure_marker",
            features={
                "kind": occurrence.kind,
                "norm_text": occurrence.norm_text,
                "flags": occurrence.flags,
            },
        )
        nodes.append(structure_node)
        for sentence_node in sentence_nodes:
            if structure_node.span_start >= sentence_node.span_start and structure_node.span_end <= sentence_node.span_end:
                edges.append(
                    QueryEdge(
                        src_id=sentence_node.node_id,
                        dst_id=structure_id,
                        kind="contains",
                        evidence_span=(structure_node.span_start, structure_node.span_end),
                    )
                )
                break
        else:
            root_ids.append(structure_id)

    deduped_roots = tuple(dict.fromkeys(root_ids))
    receipts = {
        "tree_version": "query_tree_v1",
        "parser": "parse_canonical_text",
        "structure_collector": "collect_canonical_operational_structure_occurrences",
        "sentence_count": str(len(sentence_nodes)),
        "structure_count": str(len(structures)),
    }
    return QueryTree(
        text=text,
        nodes=tuple(nodes),
        edges=tuple(edges),
        root_ids=deduped_roots,
        receipts=receipts,
    )


def _interaction_candidate(sentence_node: QueryNode) -> InteractionMode:
    features = sentence_node.features
    has_question = bool(features.get("has_question_mark")) or bool(features.get("has_question_word"))
    has_imperative = bool(features.get("has_please")) or bool(features.get("starts_with_imperative"))
    has_direct_address = bool(features.get("contains_direct_address"))

    if (has_question or has_imperative) and has_direct_address:
        return InteractionMode.DIRECTED_REQUEST
    if has_question:
        return InteractionMode.INTERROGATIVE
    if has_imperative:
        return InteractionMode.IMPERATIVE
    return InteractionMode.STATEMENT


def _is_ambient(query_tree: QueryTree) -> tuple[bool, tuple[str, ...]]:
    token_nodes = [node for node in query_tree.nodes if node.kind == "token" and any(ch.isalnum() for ch in node.text)]
    if not token_nodes:
        return False, ()
    lower_tokens = [node.text.casefold() for node in token_nodes]
    if all(token in _AMBIENT_TOKENS for token in lower_tokens):
        return True, tuple(node.node_id for node in token_nodes)
    return False, ()


def project_interaction_mode(query_tree: QueryTree) -> InteractionProjectionReceipt:
    ambient, ambient_nodes = _is_ambient(query_tree)
    if ambient:
        return InteractionProjectionReceipt(
            interaction_mode=InteractionMode.AMBIENT,
            supporting_node_ids=ambient_nodes,
        )

    sentence_nodes = [node for node in query_tree.nodes if node.kind == "sentence"]
    if not sentence_nodes:
        return InteractionProjectionReceipt(interaction_mode=InteractionMode.BOTTOM)

    scored: list[tuple[int, QueryNode, InteractionMode]] = []
    ranking = {
        InteractionMode.STATEMENT: 1,
        InteractionMode.INTERROGATIVE: 2,
        InteractionMode.IMPERATIVE: 3,
        InteractionMode.DIRECTED_REQUEST: 4,
    }
    for node in sentence_nodes:
        mode = _interaction_candidate(node)
        scored.append((ranking[mode], node, mode))

    _, winning_node, winning_mode = max(scored, key=lambda item: (item[0], item[1].span_end - item[1].span_start))
    signal_ids: list[str] = []
    for key, value in sorted(winning_node.features.items()):
        if value:
            signal_ids.append(_stable_id("signal", winning_node.node_id, key, value))

    return InteractionProjectionReceipt(
        interaction_mode=winning_mode,
        supporting_node_ids=(winning_node.node_id,),
        supporting_signal_ids=tuple(signal_ids),
    )


__all__ = [
    "InteractionMode",
    "InteractionProjectionReceipt",
    "QueryEdge",
    "QueryNode",
    "QueryTree",
    "build_query_tree",
    "project_interaction_mode",
]
