from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Iterable

from src.nlp.spacy_adapter import parse
from src.ontology.entity_bridge import lookup_bridge_alias
from src.reporting.structure_report import TextUnit


_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "he",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "this",
    "to",
    "was",
    "were",
    "with",
    "you",
    "your",
}

_CONTENT_POS = {"NOUN", "PROPN", "ADJ"}


@dataclass(frozen=True, slots=True)
class TermMention:
    term: str
    surface: str
    pos: str
    dep: str
    sentence_text: str
    unit_id: str
    source_id: str
    token_index: int
    head_index: int
    sentence_tokens: tuple[dict, ...]


def _is_candidate_token(token: dict) -> bool:
    text = str(token.get("text") or "").strip()
    if not text:
        return False
    if len(text) < 3 and not text.isupper():
        return False
    if text.casefold() in _STOPWORDS:
        return False
    if not any(ch.isalpha() for ch in text):
        return False
    pos = str(token.get("pos") or "")
    return pos in _CONTENT_POS or text[:1].isupper()


def _term_key(token: dict) -> str:
    lemma = str(token.get("lemma") or "").strip().casefold()
    text = str(token.get("text") or "").strip().casefold()
    value = lemma or text
    return value.replace("’", "'")


def _trim(text: str, limit: int = 180) -> str:
    return text.replace("\n", " ").strip()[:limit]


def _load_mentions(units: Iterable[TextUnit]) -> tuple[list[TermMention], bool]:
    mentions: list[TermMention] = []
    saw_dep = False
    for unit in units:
        parsed = parse(unit.text)
        for sent in parsed.get("sents", []):
            sentence_tokens = tuple(sent.get("tokens", []))
            for idx, token in enumerate(sentence_tokens):
                if not _is_candidate_token(token):
                    continue
                dep = str(token.get("dep") or "")
                if dep:
                    saw_dep = True
                mentions.append(
                    TermMention(
                        term=_term_key(token),
                        surface=str(token.get("text") or ""),
                        pos=str(token.get("pos") or ""),
                        dep=dep,
                        sentence_text=str(sent.get("text") or ""),
                        unit_id=unit.unit_id,
                        source_id=unit.source_id,
                        token_index=idx,
                        head_index=max(0, idx if dep in {"ROOT", ""} else idx - 1),
                        sentence_tokens=sentence_tokens,
                    )
                )
    return mentions, saw_dep


def _top_terms(mentions: list[TermMention], top_k: int) -> list[str]:
    counts: Counter[str] = Counter()
    unit_sets: dict[str, set[str]] = defaultdict(set)
    for mention in mentions:
        counts[mention.term] += 1
        unit_sets[mention.term].add(mention.unit_id)
    ranked = sorted(
        counts,
        key=lambda term: (-counts[term], -len(unit_sets[term]), term),
    )
    return ranked[:top_k]


def build_relation_neighborhood_report(
    units: Iterable[TextUnit],
    *,
    top_k: int = 8,
    top_n_neighbors: int = 8,
    conn: sqlite3.Connection | None = None,
    db_path: str | Path | None = None,
    slice_name: str | None = None,
) -> dict:
    unit_list = [unit for unit in units if unit.text.strip()]
    mentions, saw_dep = _load_mentions(unit_list)
    top_terms = _top_terms(mentions, top_k)
    mention_by_term: dict[str, list[TermMention]] = defaultdict(list)
    for mention in mentions:
        if mention.term in top_terms:
            mention_by_term[mention.term].append(mention)

    out_terms: list[dict] = []
    for term in top_terms:
        term_mentions = mention_by_term[term]
        unit_ids = {m.unit_id for m in term_mentions}
        source_ids = {m.source_id for m in term_mentions}
        surfaces = Counter(m.surface for m in term_mentions)
        dependency_neighbors: Counter[tuple[str, str]] = Counter()
        cooccurring_terms: Counter[str] = Counter()
        sentence_examples: list[dict[str, str]] = []
        bridge_hits: dict[tuple[str, str], dict] = {}
        seen_example_units: set[str] = set()

        for mention in term_mentions:
            sentence_term_set = {
                _term_key(tok)
                for tok in mention.sentence_tokens
                if _is_candidate_token(tok) and _term_key(tok) != term
            }
            for neighbor in sentence_term_set:
                cooccurring_terms[neighbor] += 1
            idx = mention.token_index
            tokens = mention.sentence_tokens
            if idx > 0 and _is_candidate_token(tokens[idx - 1]):
                dependency_neighbors[(_term_key(tokens[idx - 1]), "adjacent_prev")] += 1
            if idx + 1 < len(tokens) and _is_candidate_token(tokens[idx + 1]):
                dependency_neighbors[(_term_key(tokens[idx + 1]), "adjacent_next")] += 1
            if mention.unit_id not in seen_example_units:
                sentence_examples.append({"unit_id": mention.unit_id, "snippet": _trim(mention.sentence_text)})
                seen_example_units.add(mention.unit_id)
            for alias in {mention.surface, term, mention.surface.casefold()}:
                for link in lookup_bridge_alias(alias, conn=conn, db_path=db_path, slice_name=slice_name):
                    bridge_hits[(link.provider, link.external_id)] = {
                        "canonical_ref": link.canonical_ref,
                        "canonical_kind": link.canonical_kind,
                        "curie": link.curie,
                        "matched_alias": link.matched_alias,
                        "slice_name": link.slice_name,
                    }

        out_terms.append(
            {
                "term": term,
                "top_surface": surfaces.most_common(1)[0][0] if surfaces else term,
                "count": len(term_mentions),
                "unit_count": len(unit_ids),
                "source_count": len(source_ids),
                "top_dependency_neighbors": [
                    {"term": neighbor, "relation": relation, "count": count}
                    for (neighbor, relation), count in dependency_neighbors.most_common(top_n_neighbors)
                ],
                "top_cooccurring_terms": [
                    {"term": neighbor, "count": count}
                    for neighbor, count in cooccurring_terms.most_common(top_n_neighbors)
                ],
                "bridge_matches": sorted(bridge_hits.values(), key=lambda row: (row["canonical_kind"], row["canonical_ref"], row["curie"])),
                "examples": sentence_examples[:3],
            }
        )

    global_topics = Counter()
    for row in out_terms:
        for neighbor in row["top_cooccurring_terms"]:
            global_topics[neighbor["term"]] += int(neighbor["count"])

    return {
        "unit_count": len(unit_list),
        "term_count": len(mentions),
        "top_k": top_k,
        "top_n_neighbors": top_n_neighbors,
        "dependency_mode": "parser_evidence" if saw_dep else "cooccurrence_only",
        "top_terms": out_terms,
        "top_topic_interconnects": [
            {"term": term, "count": count}
            for term, count in global_topics.most_common(top_n_neighbors)
        ],
    }
