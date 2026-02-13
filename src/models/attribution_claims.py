from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import re
from typing import Dict, List, Optional, Sequence


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _stable_id(prefix: str, *parts: str) -> str:
    norm_parts = [_normalize_text(p) for p in parts]
    payload = "|".join(norm_parts)
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{digest}"


class SourceEntityType(str, Enum):
    WIKIPEDIA_ARTICLE = "wikipedia_article"
    NEWS_ARTICLE = "news_article"
    GOVERNMENT_REPORT = "government_report"
    SPEECH = "speech"
    TRANSCRIPT = "transcript"
    COURT_OPINION = "court_opinion"
    DATASET = "dataset"


class AttributionType(str, Enum):
    DIRECT_STATEMENT = "direct_statement"
    REPORTED_STATEMENT = "reported_statement"
    INFERRED_STATEMENT = "inferred_statement"
    ANONYMOUS_SOURCE = "anonymous_source"
    EDITORIAL_SUMMARY = "editorial_summary"


class CertaintyLevel(str, Enum):
    EXPLICIT = "explicit"
    IMPLICIT = "implicit"
    INFERRED = "inferred"


class ExtractionMethod(str, Enum):
    DIRECT_QUOTE = "direct_quote"
    PARAPHRASE = "paraphrase"
    SUMMARY = "summary"
    STRUCTURED_TABLE = "structured_table"


@dataclass(frozen=True)
class SourceEntity:
    id: str
    type: SourceEntityType
    title: str
    publication_date: Optional[str] = None
    publisher: Optional[str] = None
    url: Optional[str] = None
    version_hash: Optional[str] = None


@dataclass(frozen=True)
class Attribution:
    id: str
    claim_id: str
    attributed_actor_id: str
    attribution_type: AttributionType
    source_entity_id: str
    reporting_actor_id: Optional[str] = None
    certainty_level: CertaintyLevel = CertaintyLevel.EXPLICIT
    extraction_method: ExtractionMethod = ExtractionMethod.SUMMARY
    parent_attribution_id: Optional[str] = None


@dataclass(frozen=True)
class ExtractionRecord:
    id: str
    source_entity_id: str
    parser_version: str
    extraction_timestamp: str
    confidence_score: Optional[float] = None


@dataclass(frozen=True)
class AttributionEdge:
    src: str
    predicate: str
    dst: str


def source_entity_id(
    entity_type: SourceEntityType,
    title: str,
    *,
    url: str = "",
    version_hash: str = "",
) -> str:
    return _stable_id("source", entity_type.value, title, url, version_hash)


def attribution_id(
    *,
    claim_id: str,
    attributed_actor_id: str,
    attribution_type: AttributionType,
    source_entity_id_value: str,
    reporting_actor_id: str = "",
) -> str:
    return _stable_id(
        "attr",
        claim_id,
        attributed_actor_id,
        attribution_type.value,
        source_entity_id_value,
        reporting_actor_id,
    )


def extraction_record_id(
    *,
    source_entity_id_value: str,
    parser_version: str,
    extraction_timestamp: str,
) -> str:
    return _stable_id("xrec", source_entity_id_value, parser_version, extraction_timestamp)


def validate_attribution_chain(attributions: Sequence[Attribution]) -> None:
    by_id: Dict[str, Attribution] = {a.id: a for a in attributions}
    for attr in attributions:
        parent = attr.parent_attribution_id
        if parent and parent not in by_id:
            raise ValueError(f"unknown parent_attribution_id: {parent}")

    # DFS cycle detection.
    color: Dict[str, int] = {}  # 0/None=unseen, 1=visiting, 2=done

    def visit(attr_id: str) -> None:
        state = color.get(attr_id, 0)
        if state == 1:
            raise ValueError(f"circular attribution chain at: {attr_id}")
        if state == 2:
            return
        color[attr_id] = 1
        parent = by_id[attr_id].parent_attribution_id
        if parent:
            visit(parent)
        color[attr_id] = 2

    for attr in attributions:
        visit(attr.id)


def authority_edges_for_attribution(attribution: Attribution) -> List[AttributionEdge]:
    node = f"attr:{attribution.id}"
    edges = [
        AttributionEdge(src=f"claim:{attribution.claim_id}", predicate="attributed_by", dst=node),
        AttributionEdge(
            src=node, predicate="attributed_actor", dst=f"actor:{attribution.attributed_actor_id}"
        ),
        AttributionEdge(src=node, predicate="source_entity", dst=f"source:{attribution.source_entity_id}"),
    ]
    if attribution.reporting_actor_id:
        edges.append(
            AttributionEdge(src=node, predicate="reporting_actor", dst=f"actor:{attribution.reporting_actor_id}")
        )
    if attribution.parent_attribution_id:
        edges.append(
            AttributionEdge(
                src=node,
                predicate="parent_attribution",
                dst=f"attr:{attribution.parent_attribution_id}",
            )
        )
    return edges


def authority_edges_for_extraction_record(record: ExtractionRecord) -> List[AttributionEdge]:
    node = f"xrec:{record.id}"
    return [
        AttributionEdge(src=node, predicate="source_entity", dst=f"source:{record.source_entity_id}"),
        AttributionEdge(src=node, predicate="parser_version", dst=f"parser:{record.parser_version}"),
        AttributionEdge(src=node, predicate="extracted_at", dst=f"time:{record.extraction_timestamp}"),
    ]


__all__ = [
    "Attribution",
    "AttributionEdge",
    "AttributionType",
    "CertaintyLevel",
    "ExtractionMethod",
    "ExtractionRecord",
    "SourceEntity",
    "SourceEntityType",
    "attribution_id",
    "authority_edges_for_attribution",
    "authority_edges_for_extraction_record",
    "extraction_record_id",
    "source_entity_id",
    "validate_attribution_chain",
]
