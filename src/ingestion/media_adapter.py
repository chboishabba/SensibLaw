from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import re
from typing import Any, Iterable, Mapping, Sequence


class MediaType(str, Enum):
    TEXT = "text"
    AUDIO = "audio"
    VIDEO = "video"
    IMAGE = "image"
    STRUCTURED = "structured"


class SegmentKind(str, Enum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    QUOTE = "quote"
    TABLE = "table"
    CODE_BLOCK = "code_block"
    DIVIDER = "divider"


class UnitKind(str, Enum):
    TEXT_RUN = "text_run"
    CODE_SPAN = "code_span"
    CITATION = "citation"
    LINK = "link"
    EMPHASIS = "emphasis"


@dataclass(frozen=True)
class CanonicalUnit:
    unit_id: str
    segment_id: str
    unit_kind: str
    text: str
    start_char: int
    end_char: int
    anchor_refs: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "segment_id": self.segment_id,
            "unit_kind": self.unit_kind,
            "text": self.text,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "anchor_refs": dict(self.anchor_refs),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class CanonicalSegment:
    segment_id: str
    text_id: str
    segment_kind: str
    text: str
    start_char: int
    end_char: int
    order_index: int
    units: tuple[CanonicalUnit, ...] = ()
    anchors: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "text_id": self.text_id,
            "segment_kind": self.segment_kind,
            "text": self.text,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "order_index": self.order_index,
            "units": [unit.to_dict() for unit in self.units],
            "anchors": dict(self.anchors),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class CanonicalText:
    text_id: str
    media_type: str
    text: str
    segments: tuple[CanonicalSegment, ...]
    provenance: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "text_id": self.text_id,
            "media_type": self.media_type,
            "text": self.text,
            "segments": [segment.to_dict() for segment in self.segments],
            "provenance": dict(self.provenance),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class ParsedEnvelope:
    envelope_id: str
    media_type: str
    canonical_text: CanonicalText
    parse_profile: str
    parsed_segments: tuple[CanonicalSegment, ...] = ()
    parsed_units: tuple[CanonicalUnit, ...] = ()
    segment_graph: Any | None = None
    ingest_receipt: dict[str, Any] = field(default_factory=dict)
    parse_receipt: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "envelope_id": self.envelope_id,
            "media_type": self.media_type,
            "canonical_text": self.canonical_text.to_dict(),
            "parse_profile": self.parse_profile,
            "parsed_segments": [segment.to_dict() for segment in self.parsed_segments],
            "parsed_units": [unit.to_dict() for unit in self.parsed_units],
            "segment_graph": (
                self.segment_graph.to_dict() if self.segment_graph is not None else None
            ),
            "ingest_receipt": dict(self.ingest_receipt),
            "parse_receipt": dict(self.parse_receipt),
            "warnings": list(self.warnings),
        }


class MediaAdapter(ABC):
    media_type: MediaType

    @abstractmethod
    def adapt(self, artifact: Any) -> CanonicalText:
        raise NotImplementedError


def _normalize_text(value: Any) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def _stable_id(*parts: Any) -> str:
    digest = hashlib.sha1(
        "|".join(str(part) for part in parts if part is not None).encode("utf-8")
    ).hexdigest()
    return digest[:12]


def _build_inline_text_unit(
    *,
    prefix: str,
    text_id: str,
    segment_id: str,
    text: str,
    start_char: int,
    end_char: int | None = None,
    order_index: int = 0,
    media_type: str = MediaType.TEXT.value,
    page: int | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> CanonicalUnit:
    actual_end_char = start_char + len(text) if end_char is None else end_char
    anchor_refs: dict[str, Any] = {
        "text_id": text_id,
        "segment_id": segment_id,
        "unit_id": f"{prefix}:unit:0",
        "start_char": start_char,
        "end_char": actual_end_char,
        "order_index": order_index,
        "media_type": media_type,
    }
    if page is not None:
        anchor_refs["page"] = page
    return CanonicalUnit(
        unit_id=f"{prefix}:unit:0",
        segment_id=segment_id,
        unit_kind=UnitKind.TEXT_RUN.value,
        text=text,
        start_char=start_char,
        end_char=actual_end_char,
        anchor_refs=anchor_refs,
        metadata=dict(metadata or {}),
    )


def adapt_text_content(
    text: str,
    *,
    provenance: Mapping[str, Any] | None = None,
    segment_kind: str = SegmentKind.PARAGRAPH.value,
    segment_prefix: str = "text",
) -> CanonicalText:
    normalized = _normalize_text(text)
    text_id = f"{segment_prefix}:text:{_stable_id(segment_prefix, normalized)}"
    if not normalized:
        return CanonicalText(
            text_id=text_id,
            media_type=MediaType.TEXT.value,
            text="",
            segments=(),
            provenance=dict(provenance or {}),
        )
    segment_id = f"{segment_prefix}:segment:0"
    unit = _build_inline_text_unit(
        prefix=segment_prefix,
        text_id=text_id,
        segment_id=segment_id,
        text=normalized,
        start_char=0,
        order_index=0,
        media_type=MediaType.TEXT.value,
    )
    segment = CanonicalSegment(
        segment_id=segment_id,
        text_id=text_id,
        segment_kind=segment_kind,
        text=normalized,
        start_char=0,
        end_char=len(normalized),
        order_index=0,
        units=(unit,),
        anchors={"char_range": [0, len(normalized)]},
    )
    return CanonicalText(
        text_id=text_id,
        media_type=MediaType.TEXT.value,
        text=normalized,
        segments=(segment,),
        provenance=dict(provenance or {}),
    )


class PdfPageMediaAdapter(MediaAdapter):
    media_type = MediaType.TEXT

    def __init__(self, *, source_artifact_ref: str, provenance: Mapping[str, Any] | None = None):
        self._source_artifact_ref = source_artifact_ref
        self._provenance = dict(provenance or {})

    def adapt(self, artifact: Sequence[Mapping[str, Any]]) -> CanonicalText:
        parts: list[str] = []
        segment_records: list[tuple[str, int, str, str, int, int]] = []
        offset = 0
        order_index = 0

        for page_index, page in enumerate(artifact, start=1):
            heading = _normalize_text(page.get("heading"))
            body = _normalize_text(page.get("text"))

            for segment_kind, text in (
                (SegmentKind.HEADING.value, heading),
                (SegmentKind.PARAGRAPH.value, body),
            ):
                if not text:
                    continue
                if parts:
                    parts.append("\n\n")
                    offset += 2
                start_char = offset
                parts.append(text)
                offset += len(text)
                segment_id = (
                    f"{self._source_artifact_ref}:page:{page_index}:segment:{order_index}"
                )
                segment_records.append(
                    (segment_id, page_index, segment_kind, text, start_char, offset)
                )
                order_index += 1

        canonical_text = "".join(parts)
        text_id = f"{self._source_artifact_ref}:text:{_stable_id(self._source_artifact_ref, canonical_text)}"
        segments: list[CanonicalSegment] = []
        for order_index, (
            segment_id,
            page_index,
            segment_kind,
            text,
            start_char,
            end_char,
        ) in enumerate(segment_records):
            unit = _build_inline_text_unit(
                prefix=segment_id,
                text_id=text_id,
                segment_id=segment_id,
                text=text,
                start_char=start_char,
                end_char=end_char,
                order_index=order_index,
                media_type=self.media_type.value,
                page=page_index,
                metadata={"page": page_index},
            )
            segments.append(
                CanonicalSegment(
                    segment_id=segment_id,
                    text_id=text_id,
                    segment_kind=segment_kind,
                    text=text,
                    start_char=start_char,
                    end_char=end_char,
                    order_index=order_index,
                    units=(unit,),
                    anchors={
                        "char_range": [start_char, end_char],
                        "page": page_index,
                    },
                    metadata={"page": page_index},
                )
            )

        return CanonicalText(
            text_id=text_id,
            media_type=self.media_type.value,
            text=canonical_text,
            segments=tuple(segments),
            provenance={
                **self._provenance,
                "adapter": "pdf_page_media_adapter",
                "source_artifact_ref": self._source_artifact_ref,
            },
        )


class TextDocumentMediaAdapter(MediaAdapter):
    media_type = MediaType.TEXT

    def __init__(
        self,
        *,
        source_artifact_ref: str = "text-document",
        provenance: Mapping[str, Any] | None = None,
    ):
        self._source_artifact_ref = source_artifact_ref
        self._provenance = dict(provenance or {})

    def adapt(self, artifact: Any) -> CanonicalText:
        if isinstance(artifact, Mapping):
            text = artifact.get("text") or artifact.get("body") or ""
            artifact_provenance = artifact.get("provenance")
            if isinstance(artifact_provenance, Mapping):
                provenance = {**self._provenance, **dict(artifact_provenance)}
            else:
                provenance = dict(self._provenance)
        else:
            text = artifact
            provenance = dict(self._provenance)

        return adapt_text_content(
            text,
            provenance={
                **provenance,
                "adapter": "text_document_media_adapter",
                "source_artifact_ref": self._source_artifact_ref,
            },
            segment_prefix=self._source_artifact_ref,
        )


_INLINE_UNIT_PATTERNS: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (re.compile(r"`([^`\n]+)`"), UnitKind.CODE_SPAN.value, "code"),
    (re.compile(r"\[([^\]]+)\]\(([^)]+)\)"), UnitKind.LINK.value, "link"),
    (re.compile(r"\b(?:[A-Z][A-Za-z]+ v\. [A-Z][A-Za-z]+|\[[0-9]{4}\] [A-Z]{2,}[A-Za-z0-9 ]*)\b"), UnitKind.CITATION.value, "citation"),
    (re.compile(r"(\*\*[^*\n]+\*\*|_[^_\n]+_)"), UnitKind.EMPHASIS.value, "emphasis"),
)


def _parse_inline_units(segment: CanonicalSegment) -> tuple[CanonicalUnit, ...]:
    text = segment.text
    if not text:
        return ()

    matches: list[tuple[int, int, str, dict[str, Any]]] = []
    for pattern, unit_kind, metadata_key in _INLINE_UNIT_PATTERNS:
        for match in pattern.finditer(text):
            metadata: dict[str, Any] = {}
            if metadata_key == "code":
                metadata["delimiter"] = "backtick"
            elif metadata_key == "link":
                metadata["label"] = match.group(1)
                metadata["target"] = match.group(2)
            elif metadata_key == "citation":
                metadata["pattern"] = "legal_or_reporter"
            elif metadata_key == "emphasis":
                metadata["marker"] = match.group(0)[:2] if match.group(0).startswith("**") else match.group(0)[:1]
            matches.append((match.start(), match.end(), unit_kind, metadata))

    matches.sort(key=lambda item: (item[0], -(item[1] - item[0])))

    units: list[CanonicalUnit] = []
    cursor = 0
    unit_index = 0
    for start, end, unit_kind, metadata in matches:
        if start < cursor:
            continue
        if start > cursor:
            raw_text = text[cursor:start]
            units.append(
                CanonicalUnit(
                    unit_id=f"{segment.segment_id}:unit:{unit_index}",
                    segment_id=segment.segment_id,
                    unit_kind=UnitKind.TEXT_RUN.value,
                    text=raw_text,
                    start_char=segment.start_char + cursor,
                    end_char=segment.start_char + start,
                    anchor_refs={},
                )
            )
            unit_index += 1
        units.append(
            CanonicalUnit(
                unit_id=f"{segment.segment_id}:unit:{unit_index}",
                segment_id=segment.segment_id,
                unit_kind=unit_kind,
                text=text[start:end],
                start_char=segment.start_char + start,
                end_char=segment.start_char + end,
                anchor_refs={},
                metadata=metadata,
            )
        )
        unit_index += 1
        cursor = end

    if cursor < len(text):
        units.append(
            CanonicalUnit(
                unit_id=f"{segment.segment_id}:unit:{unit_index}",
                segment_id=segment.segment_id,
                unit_kind=UnitKind.TEXT_RUN.value,
                text=text[cursor:],
                start_char=segment.start_char + cursor,
                end_char=segment.start_char + len(text),
                anchor_refs={},
            )
        )

    if not units:
        return segment.units
    page = segment.anchors.get("page")
    normalized_units: list[CanonicalUnit] = []
    for unit in units:
        anchor_refs: dict[str, Any] = {
            "text_id": segment.text_id,
            "segment_id": unit.segment_id,
            "unit_id": unit.unit_id,
            "start_char": unit.start_char,
            "end_char": unit.end_char,
            "order_index": segment.order_index,
            "media_type": MediaType.TEXT.value,
        }
        if page is not None:
            anchor_refs["page"] = page
        normalized_units.append(
            CanonicalUnit(
                unit_id=unit.unit_id,
                segment_id=unit.segment_id,
                unit_kind=unit.unit_kind,
                text=unit.text,
                start_char=unit.start_char,
                end_char=unit.end_char,
                anchor_refs=anchor_refs,
                metadata=unit.metadata,
            )
        )
    return tuple(normalized_units)


def _inline_split_applied(
    parsed_segments: Sequence[CanonicalSegment],
    parsed_units: Sequence[CanonicalUnit],
) -> bool:
    original_units = tuple(unit for segment in parsed_segments for unit in segment.units)
    if len(original_units) != len(parsed_units):
        return True
    for original, parsed in zip(original_units, parsed_units):
        if (
            original.segment_id != parsed.segment_id
            or original.unit_kind != parsed.unit_kind
            or original.text != parsed.text
            or original.start_char != parsed.start_char
            or original.end_char != parsed.end_char
        ):
            return True
    return False


def parse_canonical_text(
    canonical_text: CanonicalText,
    *,
    parse_profile: str = "structural_parse",
    include_structure_graph: bool = False,
    ingest_receipt: Mapping[str, Any] | None = None,
) -> ParsedEnvelope:
    parsed_segments = canonical_text.segments
    parsed_units = tuple(
        unit for segment in parsed_segments for unit in _parse_inline_units(segment)
    )
    receipt = {
        "text_id": canonical_text.text_id,
        "media_type": canonical_text.media_type,
        **dict(ingest_receipt or {}),
    }
    segment_kind_counts: dict[str, int] = {}
    for segment in parsed_segments:
        segment_kind_counts[segment.segment_kind] = (
            segment_kind_counts.get(segment.segment_kind, 0) + 1
        )
    unit_kind_counts: dict[str, int] = {}
    for unit in parsed_units:
        unit_kind_counts[unit.unit_kind] = unit_kind_counts.get(unit.unit_kind, 0) + 1
    parse_receipt = {
        "parser_version": "canonical_text_parser_v1",
        "parse_profile": parse_profile,
        "segment_count": len(parsed_segments),
        "unit_count": len(parsed_units),
        "segment_kind_counts": segment_kind_counts,
        "unit_kind_counts": unit_kind_counts,
        "has_structure_graph": include_structure_graph,
        "warnings_count": len(canonical_text.warnings),
        "inline_split_applied": _inline_split_applied(parsed_segments, parsed_units),
        "anchor_normalization_applied": True,
    }
    parsed_envelope = ParsedEnvelope(
        envelope_id=f"{canonical_text.text_id}:envelope:{_stable_id(canonical_text.text_id, parse_profile)}",
        media_type=canonical_text.media_type,
        canonical_text=canonical_text,
        parse_profile=parse_profile,
        parsed_segments=parsed_segments,
        parsed_units=parsed_units,
        ingest_receipt=receipt,
        parse_receipt=parse_receipt,
        warnings=canonical_text.warnings,
    )
    if not include_structure_graph:
        return parsed_envelope

    from src.ingestion.structure_graph import build_segment_graph

    return ParsedEnvelope(
        envelope_id=parsed_envelope.envelope_id,
        media_type=parsed_envelope.media_type,
        canonical_text=parsed_envelope.canonical_text,
        parse_profile=parsed_envelope.parse_profile,
        parsed_segments=parsed_envelope.parsed_segments,
        parsed_units=parsed_envelope.parsed_units,
        segment_graph=build_segment_graph(parsed_envelope),
        ingest_receipt=parsed_envelope.ingest_receipt,
        parse_receipt={
            **parsed_envelope.parse_receipt,
            "has_structure_graph": True,
        },
        warnings=parsed_envelope.warnings,
    )


def build_parsed_envelope(canonical_text: CanonicalText) -> ParsedEnvelope:
    return parse_canonical_text(canonical_text)


__all__ = [
    "CanonicalSegment",
    "CanonicalText",
    "CanonicalUnit",
    "MediaAdapter",
    "MediaType",
    "ParsedEnvelope",
    "PdfPageMediaAdapter",
    "SegmentKind",
    "TextDocumentMediaAdapter",
    "UnitKind",
    "adapt_text_content",
    "build_parsed_envelope",
    "parse_canonical_text",
]
