from __future__ import annotations

from typing import Any, Iterable, Mapping


SEMANTIC_MEMORY_INDEX_SCHEMA_VERSION = "sl.semantic_memory_index.v0_1"
SEMANTIC_MEMORY_QUERY_SCHEMA_VERSION = "sl.semantic_memory_query.v0_1"

_QUESTION_WORDS = {
    "where",
    "else",
    "in",
    "my",
    "notes",
    "note",
    "do",
    "did",
    "i",
    "we",
    "talk",
    "about",
    "mention",
    "mentions",
    "mentioned",
    "actually",
    "see",
    "saw",
    "seen",
    "the",
    "a",
    "an",
    "of",
    "to",
    "for",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _key(value: Any) -> str:
    return " ".join(_text(value).casefold().split())


def _phrase_forms(value: str) -> set[str]:
    normalized = _key(value)
    if not normalized:
        return set()
    forms = {normalized}
    if normalized.endswith("s") and len(normalized) > 3:
        forms.add(normalized[:-1])
    else:
        forms.add(f"{normalized}s")
    return forms


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _grounding_rows(grounding_catalog: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    rows: dict[str, list[dict[str, Any]]] = {}
    raw_rows = grounding_catalog.get("groundings")
    if not isinstance(raw_rows, Mapping):
        raw_rows = grounding_catalog
    for phrase, raw in raw_rows.items():
        if str(phrase).startswith("_"):
            continue
        normalized = _key(phrase)
        candidates = [_dict(item) for item in _list(raw)]
        if normalized and candidates:
            rows[normalized] = candidates
    return rows


def _topic_rows(candidate: Mapping[str, Any]) -> list[dict[str, Any]]:
    topics: list[dict[str, Any]] = []
    grounded_node = candidate.get("grounded_node") or candidate.get("qid") or candidate.get("id")
    if grounded_node:
        topics.append(
            {
                "topic_id": str(grounded_node),
                "topic_label": _text(candidate.get("grounded_label") or candidate.get("label") or grounded_node),
                "ontology_path": [
                    _text(candidate.get("grounded_label") or candidate.get("label") or grounded_node)
                ],
                "relation_path": [],
                "topic_depth": 0,
            }
        )
    for index, raw_topic in enumerate(_list(candidate.get("topic_closure"))):
        if isinstance(raw_topic, Mapping):
            topic_id = raw_topic.get("topic_id") or raw_topic.get("id") or raw_topic.get("qid")
            if not topic_id:
                continue
            topics.append(
                {
                    "topic_id": str(topic_id),
                    "topic_label": _text(raw_topic.get("topic_label") or raw_topic.get("label") or topic_id),
                    "ontology_path": [
                        _text(item) for item in _list(raw_topic.get("ontology_path")) if _text(item)
                    ],
                    "relation_path": [
                        _text(item) for item in _list(raw_topic.get("relation_path")) if _text(item)
                    ],
                    "topic_depth": int(raw_topic.get("topic_depth", index + 1) or 0),
                }
            )
            continue
        if raw_topic:
            topics.append(
                {
                    "topic_id": str(raw_topic),
                    "topic_label": str(raw_topic),
                    "ontology_path": [str(raw_topic)],
                    "relation_path": [],
                    "topic_depth": index + 1,
                }
            )
    return topics


def _iter_segments(document: Mapping[str, Any]) -> Iterable[dict[str, Any]]:
    raw_segments = document.get("segments")
    if isinstance(raw_segments, list) and raw_segments:
        for index, raw_segment in enumerate(raw_segments):
            if isinstance(raw_segment, Mapping):
                segment = dict(raw_segment)
                segment.setdefault("segment_id", f"{document.get('doc_id', 'doc')}:s{index + 1}")
                segment.setdefault("text", document.get("raw_text") or document.get("text") or "")
                yield segment
        return
    yield {
        "segment_id": f"{document.get('doc_id', 'doc')}:s1",
        "text": document.get("raw_text") or document.get("text") or "",
        "atoms": document.get("atoms", []),
    }


def _atom_mentions(atom: Mapping[str, Any]) -> set[str]:
    mentions: set[str] = set()
    for raw_value in _list(atom.get("spans")):
        if raw_value:
            mentions.add(_key(raw_value))
    roles = atom.get("roles")
    if isinstance(roles, Mapping):
        for raw_value in roles.values():
            if isinstance(raw_value, Mapping):
                value = raw_value.get("text") or raw_value.get("value") or raw_value.get("span")
                if value:
                    mentions.add(_key(value))
            elif raw_value:
                mentions.add(_key(raw_value))
    return {mention for mention in mentions if mention}


def _segment_mentions(segment: Mapping[str, Any]) -> set[str]:
    mentions = {_key(segment.get("text"))}
    for atom in _list(segment.get("atoms")):
        if isinstance(atom, Mapping):
            mentions.update(_atom_mentions(atom))
    return {mention for mention in mentions if mention}


def _wrapper_state(
    *,
    candidate: Mapping[str, Any],
    segment: Mapping[str, Any],
    document: Mapping[str, Any],
    atoms: list[dict[str, Any]],
) -> str:
    raw = candidate.get("wrapper_state") or segment.get("wrapper_state") or document.get("wrapper_state")
    if raw:
        return _text(raw)
    for atom in atoms:
        raw_atom_wrapper = atom.get("wrapper_state") or atom.get("wrapper")
        if raw_atom_wrapper:
            return _text(raw_atom_wrapper)
    return "asserted_personal_observation"


def _phrase_in_mentions(phrase: str, mentions: Iterable[str]) -> bool:
    for mention in mentions:
        for form in _phrase_forms(phrase):
            if form and (form == mention or form in mention):
                return True
    return False


def build_semantic_memory_index(
    *,
    documents: Iterable[Mapping[str, Any]],
    grounding_catalog: Mapping[str, Any],
    ontology_snapshot_id: str,
) -> dict[str, Any]:
    """Build a deterministic semantic-memory index from supplied groundings.

    The helper is intentionally not an entity linker. It consumes packet-supplied
    grounding rows and ontology closure paths, then records explainable note
    matches against grounded topics.
    """

    catalog = _grounding_rows(grounding_catalog)
    records: list[dict[str, Any]] = []
    by_topic: dict[str, list[str]] = {}
    for document in documents:
        doc_id = _text(document.get("doc_id")) or f"doc_{len(records) + 1}"
        for segment in _iter_segments(document):
            segment_text = _text(segment.get("text"))
            mentions = _segment_mentions(segment)
            atoms = [_dict(atom) for atom in _list(segment.get("atoms")) if isinstance(atom, Mapping)]
            for phrase, candidates in catalog.items():
                if not _phrase_in_mentions(phrase, mentions):
                    continue
                for candidate in candidates:
                    topics = _topic_rows(candidate)
                    if not topics:
                        continue
                    record_id = f"smr:{len(records) + 1}"
                    topic_ids = [topic["topic_id"] for topic in topics]
                    record = {
                        "record_id": record_id,
                        "doc_id": doc_id,
                        "segment_id": _text(segment.get("segment_id")),
                        "snippet": segment_text,
                        "raw_span": phrase,
                        "grounded_node": _text(candidate.get("grounded_node") or candidate.get("qid") or candidate.get("id")),
                        "grounded_node_label": _text(
                            candidate.get("grounded_label") or candidate.get("label") or candidate.get("grounded_node")
                        ),
                        "grounding_residual": _text(candidate.get("grounding_residual") or "partial_grounding"),
                        "wrapper_state": _wrapper_state(
                            candidate=candidate,
                            segment=segment,
                            document=document,
                            atoms=atoms,
                        ),
                        "qualifier_state": _dict(candidate.get("qualifier_state")),
                        "atom_context": atoms,
                        "topics": topics,
                        "topic_ids": topic_ids,
                        "ontology_snapshot_id": ontology_snapshot_id,
                        "provenance": _dict(document.get("provenance")),
                    }
                    records.append(record)
                    for topic_id in topic_ids:
                        by_topic.setdefault(topic_id, []).append(record_id)
    return {
        "schema_version": SEMANTIC_MEMORY_INDEX_SCHEMA_VERSION,
        "ontology_snapshot_id": ontology_snapshot_id,
        "record_count": len(records),
        "records": records,
        "indexes": {
            "topic_index": {topic_id: sorted(record_ids) for topic_id, record_ids in sorted(by_topic.items())},
        },
        "authority_boundary": {
            "private_memory_index": True,
            "public_wikidata_claim": False,
            "no_belief_inference": True,
            "groundings_are_packet_supplied": True,
        },
    }


def _query_terms(query: str) -> set[str]:
    return {
        term
        for term in re_split_words(query)
        if term and term not in _QUESTION_WORDS
    }


def re_split_words(text: str) -> list[str]:
    return [part for part in _key(text).replace("?", " ").replace(".", " ").split() if part]


def _ground_query(query: str, grounding_catalog: Mapping[str, Any]) -> list[dict[str, Any]]:
    catalog = _grounding_rows(grounding_catalog)
    terms = _query_terms(query)
    rows: list[dict[str, Any]] = []
    for phrase, candidates in catalog.items():
        if phrase in _key(query) or _phrase_forms(phrase) & terms:
            for candidate in candidates:
                rows.extend(_topic_rows(candidate))
    if rows:
        return rows
    for record_term in terms:
        for phrase, candidates in catalog.items():
            if record_term in _phrase_forms(phrase):
                for candidate in candidates:
                    rows.extend(_topic_rows(candidate))
    return rows


def retrieve_semantic_memory(
    *,
    query: str,
    memory_index: Mapping[str, Any],
    grounding_catalog: Mapping[str, Any],
    require_wrapper_state: str | None = None,
) -> dict[str, Any]:
    query_topics = _ground_query(query, grounding_catalog)
    query_topic_ids = {topic["topic_id"] for topic in query_topics}
    matches: list[dict[str, Any]] = []
    for raw_record in memory_index.get("records", []):
        if not isinstance(raw_record, Mapping):
            continue
        record = dict(raw_record)
        if require_wrapper_state and record.get("wrapper_state") != require_wrapper_state:
            continue
        if query_topic_ids and not (query_topic_ids & set(record.get("topic_ids", []))):
            continue
        if not query_topic_ids:
            query_key = _key(query)
            if query_key not in _key(record.get("snippet")):
                continue
        shared_topics = sorted(query_topic_ids & set(record.get("topic_ids", [])))
        explanation_paths = [
            {
                "matched_span": record.get("raw_span"),
                "grounded_as": record.get("grounded_node_label"),
                "topic_id": topic.get("topic_id"),
                "topic_label": topic.get("topic_label"),
                "ontology_path": topic.get("ontology_path", []),
                "relation_path": topic.get("relation_path", []),
            }
            for topic in record.get("topics", [])
            if not shared_topics or topic.get("topic_id") in shared_topics
        ]
        matches.append(
            {
                "doc_id": record.get("doc_id"),
                "segment_id": record.get("segment_id"),
                "snippet": record.get("snippet"),
                "matched_span": record.get("raw_span"),
                "grounded_node": record.get("grounded_node"),
                "grounding_residual": record.get("grounding_residual"),
                "wrapper_state": record.get("wrapper_state"),
                "atom_context": record.get("atom_context", []),
                "explanation_paths": explanation_paths,
            }
        )
    return {
        "schema_version": SEMANTIC_MEMORY_QUERY_SCHEMA_VERSION,
        "query": query,
        "query_topics": query_topics,
        "match_count": len(matches),
        "matches": matches,
        "authority_boundary": {
            "private_memory_retrieval": True,
            "public_wikidata_claim": False,
            "no_belief_inference": True,
        },
    }


__all__ = [
    "SEMANTIC_MEMORY_INDEX_SCHEMA_VERSION",
    "SEMANTIC_MEMORY_QUERY_SCHEMA_VERSION",
    "build_semantic_memory_index",
    "retrieve_semantic_memory",
]
