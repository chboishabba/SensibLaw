"""PDF ingestion utilities producing :class:`Document` objects."""

import argparse
import json
import sqlite3
import calendar
import hashlib
import json
import logging
import re
import sys
from collections import deque
from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Set, Tuple

from pdfminer.high_level import extract_pages
from pdfminer.layout import LTAnno, LTChar, LTTextContainer
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser
from pdfminer.pdftypes import resolve1
from urllib.parse import parse_qs, unquote, urlparse

from src.culture.overlay import get_default_overlay
from src.glossary.linker import GlossaryLinker
from src.glossary.service import lookup as lookup_gloss
from src.ingestion.cache import HTTPCache
from src.models.document import Document, DocumentMetadata, DocumentTOCEntry
from src.models.provision import (
    Atom,
    GlossaryLink,
    Provision,
    RuleAtom,
    RuleElement,
    RuleLint,
    RuleReference,
    _build_family_key,
)
from src.models.text_span import TextSpan
from src.rules import UNKNOWN_PARTY
from src.rules.extractor import extract_rules
from src.nlp.taxonomy import Modality
from src import logic_tree
from src.pipeline import normalise
from src.storage.core import Storage
from src.storage.versioned_store import VersionedStore
from src.text.citations import CaseCitation, parse_case_citation


logger = logging.getLogger(__name__)

_CULTURAL_OVERLAY = get_default_overlay()
# Default SQLite target when callers do not provide one. Kept relative so it
# stays inside the repo unless explicitly overridden.
_DEFAULT_DB_PATH = Path("data/corpus/ingest.sqlite")


_QUOTE_CHARS = "\"'“”‘’"
_TOC_PREFIX_RE = re.compile(
    r"^(?P<type>Part|Division|Subdivision|Section)\b", re.IGNORECASE
)
_TOC_LINE_RE = re.compile(
    r"^(?P<type>Part|Division|Subdivision|Section)\s+(?P<content>.+?)\s*(?P<page>\d+)$",
    re.IGNORECASE,
)
_TOC_PAGE_NUMBER_RE = re.compile(r"^\d+$")
_TOC_SECTION_IDENTIFIER_RE = re.compile(r"^\d+[A-Z]*$")
_TOC_DOT_LEADER_RE = re.compile(r"[.·⋅•●∙]{2,}")
_BODY_DOT_LEADER_RE = re.compile(r"(?:\s*[.·⋅•●∙]){3,}")
_TOC_TRAILING_PAGE_REF_RE = re.compile(r"(?:\s*(?:Page\b)?\s*\d+)\s*$", re.IGNORECASE)
_TOC_TRAILING_PAGE_WORD_RE = re.compile(r"\bPage\b\s*$", re.IGNORECASE)
_TOC_TRAILING_DOT_LEADER_BLOCK_RE = re.compile(r"(?:[.·⋅•●∙]\s*)+$")
_TOC_TITLE_SPLIT_RE = re.compile(r"\s*[-–—:]\s*")
_SIMPLE_SECTION_HEADING_RE = re.compile(
    r"^(?:Part|Division|Subdivision|Section)\s+\d+[A-Za-z0-9]*$",
    re.IGNORECASE,
)
_DEFINITION_START_RE = re.compile(
    r"^\s*(?P<term>[\"“][^\"”]+[\"”]|'[^']+')\s+"
    r"(?P<verb>means|includes)\s+(?P<definition>.+)$",
    re.IGNORECASE,
)
_DEFINITION_START_INLINE_RE = re.compile(
    r"(?P<term>[\"“][^\"”]+[\"”]|'[^']+')\s+(?P<verb>means|includes)\s+",
    re.IGNORECASE,
)
_DEFINITION_HEADING_RE = re.compile(
    r"\b(definitions?|interpretation|defined terms)\b",
    re.IGNORECASE,
)
_SCOPE_NODE_TYPES = {"part", "division", "section"}

_CURRENT_AS_AT_RE = re.compile(
    r"\bcurrent\s+as\s+at\s+(?P<day>\d{1,2})(?:st|nd|rd|th)?\s+"
    r"(?P<month>[A-Za-z]+)\s+(?P<year>\d{4})\b",
    re.IGNORECASE,
)
_YEAR_ONLY_RE = re.compile(r"^\s*(?P<year>\d{4})\s*$")
_MONTH_LOOKUP = {
    name.lower(): index
    for index, name in enumerate(calendar.month_name)
    if name
}
_MONTH_LOOKUP.update(
    {
        name.lower(): index
        for index, name in enumerate(calendar.month_abbr)
        if name
    }
)
_MONTH_LOOKUP.setdefault("sept", 9)


def _normalise_term_key(term: str) -> str:
    return " ".join(term.strip().split()).lower()


def _normalise_definition_key(definition: str) -> str:
    return " ".join(definition.strip().split()).lower()


def _strip_quotes(value: str) -> str:
    return value.strip().strip(_QUOTE_CHARS)


def _clone_metadata(metadata: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if metadata is None:
        return None
    return dict(metadata)


def _compute_document_checksum(body: str) -> str:
    """Return a deterministic checksum for the provided document body."""

    return hashlib.sha256(body.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class GlossaryRecord:
    id: int
    term: str
    definition: str
    metadata: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class Glyph:
    page: int
    x0: float
    y0: float
    x1: float
    y1: float
    char: str


@dataclass(frozen=True)
class PdfLink:
    page: int
    rect: Tuple[float, float, float, float]
    uri: Optional[str] = None
    text: Optional[str] = None


class GlossaryRegistry:
    """Manage glossary entries backed by :class:`Storage`."""

    def __init__(self, storage: Optional[Storage] = None):
        self._storage = storage or Storage(":memory:")
        self._owns_storage = storage is None
        self._cache_by_term: Dict[str, GlossaryRecord] = {}
        self._cache_by_definition: Dict[str, GlossaryRecord] = {}

    def close(self) -> None:
        if self._owns_storage and self._storage is not None:
            self._storage.close()
            self._storage = None

    def _ensure_storage(self) -> Storage:
        if self._storage is None:
            raise RuntimeError("GlossaryRegistry has been closed")
        return self._storage

    def _cache_record(self, record: GlossaryRecord) -> GlossaryRecord:
        term_key = _normalise_term_key(record.term)
        definition_key = _normalise_definition_key(record.definition)
        self._cache_by_term[term_key] = record
        if definition_key:
            self._cache_by_definition[definition_key] = record
        return record

    def _record_from_entry(self, entry) -> GlossaryRecord:
        return self._cache_record(
            GlossaryRecord(
                id=entry.id or 0,
                term=entry.term,
                definition=entry.definition,
                metadata=_clone_metadata(entry.metadata),
            )
        )

    def register_definition(
        self,
        term: str,
        definition: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[GlossaryRecord]:
        term = term.strip()
        definition = definition.strip()
        if not term or not definition:
            return None

        metadata_copy = _clone_metadata(metadata)
        term_key = _normalise_term_key(term)
        definition_key = _normalise_definition_key(definition)

        cached = self._cache_by_term.get(term_key)
        if cached and _normalise_definition_key(cached.definition) == definition_key:
            if metadata_copy is not None and cached.metadata != metadata_copy:
                cached = GlossaryRecord(
                    id=cached.id,
                    term=cached.term,
                    definition=cached.definition,
                    metadata=metadata_copy,
                )
                self._cache_record(cached)
            return cached

        storage = self._ensure_storage()
        entry = storage.get_glossary_entry_by_term(term)
        if entry is None:
            entry_id = storage.insert_glossary_entry(term, definition, metadata_copy)
            entry = storage.get_glossary_entry(entry_id)
        else:
            stored_definition_key = _normalise_definition_key(entry.definition)
            desired_metadata = (
                metadata_copy
                if metadata_copy is not None
                else _clone_metadata(entry.metadata)
            )
            if stored_definition_key != definition_key or (
                metadata_copy is not None
                and _clone_metadata(entry.metadata) != metadata_copy
            ):
                storage.update_glossary_entry(
                    entry.id,
                    term=entry.term,
                    definition=definition,
                    metadata=desired_metadata,
                )
                entry = storage.get_glossary_entry(entry.id)

        if entry is None:
            return None

        return self._record_from_entry(entry)

    def resolve(self, term: Optional[str]) -> Optional[GlossaryRecord]:
        if not term:
            return None
        term_key = _normalise_term_key(term)
        cached = self._cache_by_term.get(term_key)
        if cached:
            return cached
        entry = self._ensure_storage().get_glossary_entry_by_term(term)
        if entry is None:
            return None
        return self._record_from_entry(entry)

    def resolve_by_definition(
        self, definition: Optional[str]
    ) -> Optional[GlossaryRecord]:
        if not definition:
            return None
        definition_key = _normalise_definition_key(definition)
        cached = self._cache_by_definition.get(definition_key)
        if cached:
            return cached
        entry = self._ensure_storage().find_glossary_entry_by_definition(definition)
        if entry is None:
            return None
        return self._record_from_entry(entry)


def _finalise_definition(parts: List[str]) -> str:
    joined = " ".join(part.strip().rstrip(";") for part in parts if part.strip())
    return re.sub(r"\s+", " ", joined).strip()


def _split_definition_line(raw_line: str) -> List[str]:
    matches = list(_DEFINITION_START_INLINE_RE.finditer(raw_line))
    if len(matches) <= 1:
        return [raw_line]

    segments: List[str] = []
    first_start = matches[0].start()
    prefix = raw_line[:first_start].strip()
    if prefix:
        segments.append(prefix)

    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(raw_line)
        segment = raw_line[start:end].strip()
        if segment:
            segments.append(segment)

    return segments or [raw_line]


def _extract_definition_entries(text: str) -> Dict[str, str]:
    entries: Dict[str, str] = {}
    current_term: Optional[str] = None
    collected: List[str] = []

    for raw_line in text.splitlines():
        for segment in _split_definition_line(raw_line):
            line = segment.strip()
            if not line:
                if current_term and collected:
                    entries[current_term] = _finalise_definition(collected)
                current_term = None
                collected = []
                continue

            cleaned = _PRINCIPLE_LEADING_NUMBERS.sub("", line)
            cleaned = _PRINCIPLE_LEADING_ENUM.sub("", cleaned)
            match = _DEFINITION_START_RE.match(cleaned)
            if match:
                if current_term and collected:
                    entries[current_term] = _finalise_definition(collected)
                current_term = _strip_quotes(match.group("term"))
                collected = [match.group("definition").strip()]
                continue

            if current_term:
                collected.append(cleaned)

    if current_term and collected:
        entries[current_term] = _finalise_definition(collected)

    return entries


_DEFAULT_GLOSSARY_REGISTRY = GlossaryRegistry()


def _is_definition_heading(heading: Optional[str]) -> bool:
    if not heading:
        return False
    return bool(_DEFINITION_HEADING_RE.search(heading))


def _iter_provisions_with_ancestors(
    provisions: List[Provision],
    ancestors: Optional[List[Provision]] = None,
):
    if ancestors is None:
        ancestors = []
    for provision in provisions:
        yield provision, list(ancestors)
        if provision.children:
            ancestors.append(provision)
            yield from _iter_provisions_with_ancestors(provision.children, ancestors)
            ancestors.pop()


def _collect_definition_text(provision: Provision) -> str:
    parts: List[str] = []
    if provision.heading:
        parts.append(provision.heading)
    if provision.text:
        parts.append(provision.text)
    for child in provision.children:
        child_text = _collect_definition_text(child)
        if not child_text:
            continue
        if child.identifier:
            parts.append(f"{child.identifier} {child_text}".strip())
        else:
            parts.append(child_text)
    return "\n".join(part for part in parts if part.strip()).strip()


def _build_scope_entries(
    ancestors: List[Provision], provision: Provision
) -> List[Dict[str, Optional[str]]]:
    scope_entries: List[Dict[str, Optional[str]]] = []
    for node in ancestors:
        if node.node_type in _SCOPE_NODE_TYPES:
            scope_entries.append(
                {
                    "node_type": node.node_type,
                    "identifier": node.identifier,
                    "heading": node.heading,
                }
            )
    if provision.node_type in _SCOPE_NODE_TYPES:
        scope_entries.append(
            {
                "node_type": provision.node_type,
                "identifier": provision.identifier,
                "heading": provision.heading,
            }
        )
    return scope_entries


def _register_definition_provisions(
    provisions: List[Provision],
    registry: GlossaryRegistry,
) -> bool:
    if not provisions:
        return False

    registered = False
    for provision, ancestors in _iter_provisions_with_ancestors(provisions):
        if provision.node_type != "section" or not _is_definition_heading(
            provision.heading
        ):
            continue

        definition_text = _collect_definition_text(provision)
        if not definition_text:
            continue

        entries = _extract_definition_entries(definition_text)
        if not entries:
            continue

        scope_entries = _build_scope_entries(ancestors, provision)
        metadata: Optional[Dict[str, Any]] = None
        if scope_entries:
            metadata = {"scope": [dict(entry) for entry in scope_entries]}

        for term, definition in entries.items():
            registry.register_definition(term, definition, metadata)
            registered = True

    return registered


def _resolve_definition_roots(body: str, fallback: List[Provision]) -> List[Provision]:
    if not _has_section_parser():
        return fallback
    try:  # pragma: no cover - defensive guard around optional dependency
        nodes = section_parser.parse_sections(body)  # type: ignore[attr-defined]
    except Exception:
        return fallback
    structured = _build_provisions_from_nodes(nodes or [])
    return structured or fallback


# ``section_parser`` is optional – tests may monkeypatch it. If it's not
# available, a trivial fallback is used which treats the entire body as a single
# provision.
try:  # pragma: no cover - executed conditionally
    from .ingestion import section_parser as _ingestion_section_parser  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    _ingestion_section_parser = None  # type: ignore
    _SECTION_PARSER_OPTIONAL_IMPORT_FAILED = True
else:  # pragma: no cover - only executed when optional import succeeds
    _SECTION_PARSER_OPTIONAL_IMPORT_FAILED = False

try:  # pragma: no cover - executed conditionally
    from . import section_parser as _root_section_parser  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    _root_section_parser = None  # type: ignore
    _ROOT_SECTION_PARSER_IMPORT_FAILED = True
else:  # pragma: no cover - only executed when import succeeds
    _ROOT_SECTION_PARSER_IMPORT_FAILED = False

section_parser = _root_section_parser or _ingestion_section_parser  # type: ignore


def _clean_page_line(line: str) -> Optional[str]:
    """Normalise whitespace and remove dotted leader artifacts from ``line``."""

    collapsed = re.sub(r"\s+", " ", line).strip()
    if not collapsed:
        return None

    cleaned = _BODY_DOT_LEADER_RE.sub(" ", collapsed)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or None


def _extract_pdf_links(data: bytes) -> Dict[int, List[PdfLink]]:
    """Extract hyperlink annotations keyed by page number."""

    links: Dict[int, List[PdfLink]] = {}
    try:
        with BytesIO(data) as buffer:
            parser = PDFParser(buffer)
            document = PDFDocument(parser)
            parser.set_document(document)
            for page_number, page in enumerate(PDFPage.create_pages(document), start=1):
                annotations = getattr(page, "annots", None)
                if not annotations:
                    continue
                resolved = resolve1(annotations)
                if not resolved:
                    continue
                for annotation_ref in resolved:
                    annotation = resolve1(annotation_ref)
                    if not isinstance(annotation, dict):
                        continue
                    subtype = annotation.get("Subtype")
                    if subtype is not None and str(subtype) != "/Link":
                        continue
                    rect = resolve1(annotation.get("Rect"))
                    if not rect or len(rect) != 4:
                        continue
                    action = annotation.get("A") or annotation.get("PA")
                    uri: Optional[str] = None
                    if action:
                        resolved_action = resolve1(action)
                        if isinstance(resolved_action, dict):
                            uri_obj = resolved_action.get("URI") or resolved_action.get("uri")
                            if uri_obj:
                                uri = str(resolve1(uri_obj))
                    if not uri:
                        continue
                    x0, y0, x1, y1 = [float(v) for v in rect]
                    links.setdefault(page_number, []).append(
                        PdfLink(page=page_number, rect=(x0, y0, x1, y1), uri=uri)
                    )
    except Exception:
        return {}
    return links


def _collect_glyphs_from_layout(layout) -> List[Glyph]:
    """Collect glyphs (characters) with bounding boxes from a pdfminer layout."""

    glyphs: List[Glyph] = []

    def _walk(element) -> None:
        if isinstance(element, LTChar):
            glyphs.append(
                Glyph(
                    page=getattr(element, "pageid", getattr(layout, "pageid", 0)),
                    x0=float(element.x0),
                    y0=float(element.y0),
                    x1=float(element.x1),
                    y1=float(element.y1),
                    char=element.get_text(),
                )
            )
            return
        if isinstance(element, LTAnno):
            return
        if isinstance(element, LTTextContainer):
            for child in element:
                _walk(child)
            return
        for child in getattr(element, "_objs", []):
            _walk(child)

    _walk(layout)
    return glyphs


def _rects_intersect(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> bool:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return not (ax1 <= bx0 or bx1 <= ax0 or ay1 <= by0 or by1 <= ay0)


def _extract_link_text(rect: Tuple[float, float, float, float], glyphs: List[Glyph]) -> Optional[str]:
    """Best-effort extraction of visible text within a hyperlink rectangle."""

    inside = [
        glyph
        for glyph in glyphs
        if _rects_intersect(rect, (glyph.x0, glyph.y0, glyph.x1, glyph.y1))
    ]
    if not inside:
        return None
    inside.sort(key=lambda g: (-g.y0, g.x0))
    text = "".join(g.char for g in inside if g.char)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def extract_pdf_text(pdf_path: Path) -> Iterator[dict]:
    """Yield text and headings from ``pdf_path`` one page at a time."""

    data = pdf_path.read_bytes()
    links_by_page = _extract_pdf_links(data)
    with BytesIO(data) as pdf_file:
        for page_number, layout in enumerate(extract_pages(pdf_file), start=1):
            glyphs = _collect_glyphs_from_layout(layout)
            lines: List[str] = []
            for element in layout:
                get_text = getattr(element, "get_text", None)
                if not callable(get_text):
                    continue
                text = get_text()
                if not text:
                    continue
                for raw_line in text.splitlines():
                    cleaned_line = _clean_page_line(raw_line)
                    if cleaned_line:
                        lines.append(cleaned_line)

            if not lines:
                continue

            heading = lines[0]
            body_lines = lines[1:]
            body = " ".join(body_lines) if body_lines else ""
            page_links = []
            for link in links_by_page.get(page_number, []):
                link_text = _extract_link_text(link.rect, glyphs)
                page_links.append(
                    {
                        "uri": link.uri,
                        "rect": link.rect,
                        "text": link_text,
                        "page": link.page,
                    }
                )
            yield {
                "page": page_number,
                "heading": heading,
                "text": body,
                "lines": lines,
                "links": page_links,
            }


def _normalise_toc_candidate(parts: List[str]) -> str:
    joined = " ".join(parts)
    joined = _TOC_DOT_LEADER_RE.sub(" ", joined)
    return re.sub(r"\s+", " ", joined).strip()


def _has_significant_dot_leader(value: str) -> bool:
    match = _TOC_TRAILING_DOT_LEADER_BLOCK_RE.search(value)
    if not match:
        return False
    stripped = match.group(0).replace(" ", "")
    return len(stripped) >= 3


def _looks_like_simple_heading(value: str) -> bool:
    return bool(_SIMPLE_SECTION_HEADING_RE.match(value))


def _clean_toc_title_segment(title_part: Optional[str]) -> Optional[str]:
    if not title_part:
        return None

    cleaned = re.sub(r"\s+", " ", title_part).strip()
    if not cleaned:
        return None

    has_dotted_leader_page_ref = bool(re.search(r"[.·⋅•●∙]{2,}\s*\d+\s*$", title_part))
    has_explicit_page_word = bool(
        re.search(r"\bPage\s*\d+\s*$", cleaned, re.IGNORECASE)
    )

    if has_dotted_leader_page_ref or has_explicit_page_word:
        cleaned = _TOC_TRAILING_PAGE_REF_RE.sub("", cleaned)
    cleaned = _TOC_TRAILING_PAGE_WORD_RE.sub("", cleaned)
    cleaned = _TOC_TRAILING_DOT_LEADER_BLOCK_RE.sub("", cleaned)
    cleaned = _TOC_DOT_LEADER_RE.sub(" ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or None


def _split_toc_identifier(content: str) -> Tuple[Optional[str], Optional[str]]:
    content = content.strip()
    if not content:
        return None, None

    split = _TOC_TITLE_SPLIT_RE.split(content, maxsplit=1)
    if len(split) == 2 and split[1].strip():
        identifier_part, title_part = split
    else:
        pieces = content.split(" ", 1)
        identifier_part = pieces[0]
        title_part = pieces[1] if len(pieces) > 1 else None

    identifier = identifier_part.strip().rstrip(".") or None
    title = _clean_toc_title_segment(title_part) if title_part else None
    return identifier, title


_TOC_SKIP_LINE_PATTERNS = [
    re.compile(r"^Page\s+\d+$", re.IGNORECASE),
    re.compile(r"^Current as at ", re.IGNORECASE),
    re.compile(r"^Authorised by the Parliamentary Counsel", re.IGNORECASE),
]
_TOC_SKIP_LINE_TEXT = {
    "Contents",
    "Dictionary",
    "Queensland",
    "Summary Offences Act 2005",
}

_KNOWN_JURISDICTIONS = {
    "australia",
    "commonwealth of australia",
    "commonwealth",
    "new south wales",
    "victoria",
    "queensland",
    "south australia",
    "western australia",
    "tasmania",
    "northern territory",
    "australian capital territory",
    "state of queensland",
    "state of victoria",
    "state of new south wales",
    "state of south australia",
    "state of western australia",
    "state of tasmania",
    "territory of the northern territory",
    "territory of the australian capital territory",
}

_SINGLE_WORD_JURISDICTIONS = {
    "australia",
    "commonwealth",
    "queensland",
    "victoria",
    "tasmania",
}

_LOWERCASE_JURISDICTION_FILLERS = {"of", "the", "and"}

_TITLE_KEYWORD_RE = re.compile(
    r"\b(Act|Regulation|Regulations|Rule|Rules|Bill|Ordinance|Order|Law)\b",
    re.IGNORECASE,
)

_DATE_LINE_PATTERNS = [
    re.compile(
        r"\bCurrent as at (?P<day>\d{1,2})(?:st|nd|rd|th)? (?P<month>[A-Za-z]+) (?P<year>\d{4})",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bReprinted as in force on (?P<day>\d{1,2})(?:st|nd|rd|th)? (?P<month>[A-Za-z]+) (?P<year>\d{4})",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bAs at (?P<day>\d{1,2})(?:st|nd|rd|th)? (?P<month>[A-Za-z]+) (?P<year>\d{4})",
        re.IGNORECASE,
    ),
]

_STANDALONE_YEAR_RE = re.compile(r"^(?P<year>\d{4})$")


def _should_join_toc_line(previous: str, current: str) -> bool:
    if not previous or not current:
        return False
    if current.lower() == "page":
        return False
    if _TOC_PREFIX_RE.match(current):
        return False
    if _TOC_SECTION_IDENTIFIER_RE.match(current):
        return False
    if _TOC_PAGE_NUMBER_RE.match(current):
        return False
    return bool(current and current[0].islower())


def _collect_toc_tokens(pages: List[dict]) -> List[str]:
    tokens: List[str] = []
    for page in pages:
        for raw_line in _page_lines_for_toc(page):
            normalised = re.sub(r"\s+", " ", str(raw_line)).strip()
            if not normalised:
                continue
            if set(normalised) <= {"-"}:
                continue
            if not re.search(r"[\w]", normalised):
                continue
            if normalised in _TOC_SKIP_LINE_TEXT:
                continue
            if any(pattern.match(normalised) for pattern in _TOC_SKIP_LINE_PATTERNS):
                continue
            tokens.append(normalised)

    combined: List[str] = []
    for token in tokens:
        if combined and _should_join_toc_line(combined[-1], token):
            combined[-1] = f"{combined[-1]} {token}".strip()
        else:
            combined.append(token)
    return combined


def _parse_multi_column_toc(pages: List[dict]) -> List[DocumentTOCEntry]:
    tokens = _collect_toc_tokens(pages)
    if not tokens:
        return []

    flat_entries: List[DocumentTOCEntry] = []
    pending_section_ids: deque[str] = deque()
    pending_page_entries: deque[DocumentTOCEntry] = deque()
    page_numbers: deque[int] = deque()
    pending_title_entry: Optional[DocumentTOCEntry] = None
    collecting_pages = False
    last_token_was_title = False
    page_column_active = False
    prefer_identifiers = False
    page_number_stream = False

    def assign_pages() -> None:
        while page_numbers and pending_page_entries:
            entry = pending_page_entries[0]
            entry.page_number = page_numbers.popleft()
            pending_page_entries.popleft()

    for token in tokens:
        lowered = token.lower()
        if lowered == "page":
            collecting_pages = True
            page_column_active = True
            last_token_was_title = False
            prefer_identifiers = False
            page_number_stream = True
            continue

        if collecting_pages and _TOC_PAGE_NUMBER_RE.match(token):
            try:
                page_numbers.append(int(token))
            except ValueError:
                pass
            else:
                assign_pages()
            prefer_identifiers = False
            last_token_was_title = True
            page_number_stream = True
            continue

        if collecting_pages:
            collecting_pages = False

        if (
            _TOC_PAGE_NUMBER_RE.match(token)
            and page_column_active
            and (pending_page_entries or page_number_stream)
            and not prefer_identifiers
        ):
            try:
                page_numbers.append(int(token))
            except ValueError:
                pass
            else:
                assign_pages()
            prefer_identifiers = False
            last_token_was_title = True
            page_number_stream = True
            continue

        normalised_token = _normalise_toc_candidate([token])
        line_match = _TOC_LINE_RE.match(normalised_token)
        if line_match:
            node_type = line_match.group("type").lower()
            content = line_match.group("content").strip()
            page_str = line_match.group("page")
            try:
                page_number = int(page_str)
            except ValueError:
                page_number = None
            identifier, title = _split_toc_identifier(content)
            entry = DocumentTOCEntry(
                node_type=node_type,
                identifier=identifier,
                title=title,
                page_number=page_number,
            )
            flat_entries.append(entry)
            if node_type == "section" and page_number is None:
                pending_page_entries.append(entry)
            pending_title_entry = entry if title is None else None
            assign_pages()
            last_token_was_title = bool(title)
            prefer_identifiers = True
            page_number_stream = False
            continue

        prefix_match = _TOC_PREFIX_RE.match(token)
        if prefix_match:
            node_type = prefix_match.group("type").lower()
            remainder = token[prefix_match.end() :].strip()
            identifier, title = _split_toc_identifier(remainder)
            entry = DocumentTOCEntry(
                node_type=node_type,
                identifier=identifier,
                title=title,
                page_number=None,
            )
            flat_entries.append(entry)
            if node_type == "section":
                pending_page_entries.append(entry)
            pending_title_entry = entry if title is None else None
            assign_pages()
            last_token_was_title = bool(title)
            prefer_identifiers = True
            page_number_stream = False
            continue

        if pending_title_entry is not None:
            if (
                _TOC_SECTION_IDENTIFIER_RE.match(token)
                and pending_title_entry.node_type != "section"
            ):
                pending_title_entry = None
                prefer_identifiers = True
                page_number_stream = False
            else:
                pending_title_entry.title = _clean_toc_title_segment(token)
                pending_title_entry = None
                assign_pages()
                last_token_was_title = True
                prefer_identifiers = True
                page_number_stream = False
                continue

        if _TOC_SECTION_IDENTIFIER_RE.match(token):
            pending_section_ids.append(token)
            last_token_was_title = False
            prefer_identifiers = True
            page_number_stream = False
            continue

        if pending_section_ids:
            identifier = pending_section_ids.popleft()
            entry = DocumentTOCEntry(
                node_type="section",
                identifier=identifier,
                title=_clean_toc_title_segment(token),
                page_number=None,
            )
            flat_entries.append(entry)
            pending_page_entries.append(entry)
            assign_pages()
            last_token_was_title = True
            prefer_identifiers = bool(pending_section_ids)
            page_number_stream = False
            continue

    assign_pages()
    return flat_entries


def _parse_toc_page(lines: List[str]) -> List[DocumentTOCEntry]:
    entries: List[DocumentTOCEntry] = []
    buffer: List[str] = []

    for raw_line in lines:
        cleaned = re.sub(r"\s+", " ", raw_line).strip()
        if not cleaned:
            continue

        candidate_parts = buffer + [cleaned] if buffer else [cleaned]
        normalised = _normalise_toc_candidate(candidate_parts)
        match = _TOC_LINE_RE.match(normalised)
        if match:
            node_type = match.group("type").lower()
            content = match.group("content").strip()
            page_str = match.group("page")
            try:
                page_number = int(page_str)
            except ValueError:
                page_number = None
            identifier, title = _split_toc_identifier(content)
            entries.append(
                DocumentTOCEntry(
                    node_type=node_type,
                    identifier=identifier,
                    title=title,
                    page_number=page_number,
                )
            )
            buffer = []
            continue

        if buffer:
            buffer.append(cleaned)
            continue

        if _TOC_PREFIX_RE.match(cleaned):
            buffer = [cleaned]

    return entries


def _page_lines_for_toc(page: Dict[str, Any]) -> List[str]:
    lines = page.get("lines")
    if isinstance(lines, list):
        return [str(line) for line in lines]

    collected: List[str] = []
    heading = page.get("heading")
    if heading:
        collected.append(str(heading))
    text = page.get("text")
    if text:
        collected.extend(str(text).splitlines())
    return collected


_JURISDICTION_STOP_WORDS = {
    "act",
    "acts",
    "law",
    "laws",
    "regulation",
    "regulations",
    "ordinance",
    "ordinances",
    "code",
    "codes",
    "bill",
    "bills",
}


def _looks_like_jurisdiction_banner(line: str) -> bool:
    """Return ``True`` when ``line`` resembles a jurisdiction banner."""

    if not line:
        return False

    if any(char.isdigit() for char in line):
        return False

    cleaned = re.sub(r"[^A-Za-z\s'-]", " ", line).strip()
    if not cleaned:
        return False

    words = [word for word in cleaned.split() if word]
    if not words:
        return False

    if len(words) > 6:
        return False

    lower_words = {word.lower() for word in words}
    if lower_words & _JURISDICTION_STOP_WORDS:
        return False

    letters = [char for char in cleaned if char.isalpha()]
    if not letters:
        return False

    uppercase_ratio = sum(1 for char in letters if char.isupper()) / len(letters)
    if uppercase_ratio >= 0.6:
        return True

    if all(word[0].isupper() and word[1:].islower() for word in words if len(word) > 1):
        return True

    return False


def _infer_cover_metadata(pages: List[dict]) -> Tuple[Optional[str], Optional[str]]:
    """Infer jurisdiction and title from the first page cover banner."""

    if not pages:
        return None, None

    first_page = pages[0]
    raw_lines: Iterable[str]
    if isinstance(first_page.get("lines"), list):
        raw_lines = first_page.get("lines", [])  # type: ignore[assignment]
    else:
        raw_lines = _page_lines_for_toc(first_page)

    lines = [str(line).strip() for line in raw_lines if str(line).strip()]
    if not lines:
        return None, None

    for index, line in enumerate(lines):
        if not _looks_like_jurisdiction_banner(line):
            continue

        jurisdiction = line
        for candidate in lines[index + 1 :]:
            title_candidate = candidate.strip()
            if not title_candidate or title_candidate == jurisdiction:
                continue
            return jurisdiction, title_candidate

        return jurisdiction, None

    return None, None
def _flatten_toc_entries(entries: List[DocumentTOCEntry]) -> Iterable[DocumentTOCEntry]:
    for entry in entries:
        yield entry
        if entry.children:
            yield from _flatten_toc_entries(entry.children)


def _normalise_lookup_value(value: str) -> Optional[str]:
    normalised = re.sub(r"\s+", " ", value).strip().lower()
    return normalised or None


_TOC_TRAILING_PAGE_TOKEN_RE = re.compile(r"(?:\s*(?:page)?\s*\d+)+\s*$", re.IGNORECASE)
_TOC_IDENTIFIER_ONLY_RE = re.compile(r"^[A-Za-z0-9]+$")


def _build_toc_lookup(entries: List[DocumentTOCEntry]) -> Tuple[Set[str], Set[str]]:
    """Return lookup tables for matching TOC headings and identifiers."""

    heading_lookup: Set[str] = set()
    identifier_lookup: Set[str] = set()

    for entry in _flatten_toc_entries(entries):
        variants: List[str] = []
        parts: List[str] = []
        if entry.node_type:
            parts.append(entry.node_type)
        if entry.identifier:
            parts.append(entry.identifier)
        if entry.title:
            parts.append(entry.title)
        if parts:
            variants.append(" ".join(parts))
        if entry.node_type and entry.identifier:
            variants.append(f"{entry.node_type} {entry.identifier}")
        if entry.identifier and entry.title:
            variants.append(f"{entry.identifier} {entry.title}")
        if entry.node_type and entry.title:
            variants.append(f"{entry.node_type} {entry.title}")
        if entry.title:
            variants.append(entry.title)
        if entry.identifier:
            identifier_lookup.add(entry.identifier.strip().lower())

        for variant in variants:
            normalised = _normalise_lookup_value(variant)
            if normalised:
                heading_lookup.add(normalised)

    return heading_lookup, identifier_lookup


def _normalise_line_for_lookup(line: str) -> Optional[str]:
    cleaned = " ".join(line.split())
    cleaned = _TOC_TRAILING_PAGE_TOKEN_RE.sub("", cleaned)
    cleaned = _TOC_DOT_LEADER_RE.sub(" ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return None
    return cleaned.lower()


def _is_probable_toc_page(
    lines: Sequence[str],
    heading_lookup: Set[str],
    identifier_lookup: Set[str],
) -> bool:
    if not lines:
        return False

    contents_hits = 0
    heading_hits = 0
    identifier_hits = 0

    for raw in lines:
        lowered = raw.strip().lower()
        if "contents" in lowered:
            contents_hits += 1

        normalised = _normalise_line_for_lookup(raw)
        if not normalised:
            continue
        if normalised in heading_lookup:
            heading_hits += 1
            continue
        if (
            normalised in identifier_lookup
            and _TOC_IDENTIFIER_ONLY_RE.match(raw.strip())
        ):
            identifier_hits += 1

    total_hits = heading_hits + identifier_hits
    if contents_hits and total_hits >= 3:
        return True
    if not contents_hits:
        return False
    if total_hits >= 5:
        return True
    return False


def _filter_pages_with_toc(pages: List[dict], toc_entries: List[DocumentTOCEntry]) -> List[dict]:
    if not toc_entries:
        return pages

    heading_lookup, identifier_lookup = _build_toc_lookup(toc_entries)
    if not heading_lookup and not identifier_lookup:
        return pages

    filtered: List[dict] = []
    for page in pages:
        lines = _page_lines_for_toc(page)
        if _is_probable_toc_page(lines, heading_lookup, identifier_lookup):
            continue
        filtered.append(page)
    return filtered or pages


def parse_table_of_contents(pages: List[dict]) -> List[DocumentTOCEntry]:
    """Parse table-of-contents pages into a hierarchical structure."""

    flat_entries = _parse_multi_column_toc(pages)
    if not flat_entries:
        for page in pages:
            lines = _page_lines_for_toc(page)
            parsed = _parse_toc_page(lines)
            if len(parsed) >= 2:
                flat_entries.extend(parsed)

    if not flat_entries:
        return []

    hierarchy_order = {
        "part": 0,
        "division": 1,
        "subdivision": 2,
        "section": 3,
    }
    root_entries: List[DocumentTOCEntry] = []
    stack: List[Tuple[int, DocumentTOCEntry]] = []

    for entry in flat_entries:
        level = hierarchy_order.get(entry.node_type or "", len(hierarchy_order))
        while stack and stack[-1][0] >= level:
            stack.pop()
        if stack:
            stack[-1][1].children.append(entry)
        else:
            root_entries.append(entry)
        stack.append((level, entry))

    _propagate_toc_page_numbers(root_entries)
    return root_entries


def _flatten_toc_entries(entries: Iterable[DocumentTOCEntry]) -> Iterable[DocumentTOCEntry]:
    for entry in entries:
        yield entry
        if entry.children:
            yield from _flatten_toc_entries(entry.children)


def _collect_toc_heading_candidates(
    entries: Iterable[DocumentTOCEntry],
) -> Set[str]:
    candidates: Set[str] = set()

    for entry in _flatten_toc_entries(entries):
        if entry.title:
            candidates.add(entry.title)
            if entry.identifier:
                candidates.add(f"{entry.identifier} {entry.title}")
        if entry.identifier:
            candidates.add(entry.identifier)

    return {candidate for candidate in candidates if candidate}


def _is_table_of_contents_page(page: Dict[str, Any]) -> bool:
    heading = str(page.get("heading") or "").strip()
    if heading and _CONTENTS_MARKER_RE.search(heading):
        return True

    lines = _page_lines_for_toc(page)
    if not lines:
        return False

    for raw_line in lines[:3]:
        if _CONTENTS_MARKER_RE.search(str(raw_line)):
            return True

    parsed = _parse_toc_page(lines)
    if len(parsed) >= 2:
        return True

    toc_like = 0
    page_ref_like = 0
    for raw_line in lines:
        normalised = _normalise_toc_candidate([str(raw_line)])
        if _TOC_LINE_RE.match(normalised) or _TOC_PREFIX_RE.match(normalised):
            toc_like += 1
        if _TOC_TRAILING_PAGE_REF_RE.search(normalised) or _has_significant_dot_leader(normalised):
            page_ref_like += 1

    return toc_like >= 2 and page_ref_like >= 1


def _propagate_toc_page_numbers(entries: List[DocumentTOCEntry]) -> None:
    """Fill missing page numbers from descendant entries."""

    def walk(entry: DocumentTOCEntry) -> Optional[int]:
        child_pages: List[int] = []
        for child in entry.children:
            child_page = walk(child)
            if child_page is not None:
                child_pages.append(child_page)
        if entry.page_number is not None:
            return entry.page_number
        if child_pages:
            page = min(child_pages)
            entry.page_number = page
            return page
        return None

    for entry in entries:
        walk(entry)


def build_metadata(pdf_path: Path, pages: List[dict]) -> dict:
    """Create metadata wrapper for extracted pages."""

    return {
        "source": pdf_path.name,
        "page_count": len(pages),
        "pages": pages,
    }


def save_json(pages: List[dict], output_path: Path, source: Path) -> None:
    """Save extracted pages as JSON."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "source": str(source),
        "page_count": len(pages),
        "pages": pages,
    }
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def download_pdf(url: str, cache: HTTPCache, dest: Path) -> Path:
    """Download a PDF using :class:`HTTPCache` and save to ``dest``."""

    dest.write_bytes(cache.fetch(url))
    return dest


_PRINCIPLE_LEADING_NUMBERS = re.compile(r"^(?:\d+(?:\.\d+)?\s+){2,}")
_PRINCIPLE_LEADING_ENUM = re.compile(r"^(?:\([a-z0-9]+\)\s+)+", re.IGNORECASE)

_CITATION_NEUTRAL_RE = re.compile(r"\[\d{4}\]")
_CITATION_WORD_RE = re.compile(r"\bv\.?\b", re.IGNORECASE)
_CASE_NAME_RE = re.compile(r"[A-Z][A-Za-z0-9.'()& -]+? v [A-Z][A-Za-z0-9.'()& -]+")
_YEAR_TOKEN_RE = re.compile(r"^\(\d{4}\)$")
_SECTION_ID_PATTERN = re.compile(r"^\d+[A-Za-z]*(?:\([^)]+\))*$")

_MODALITY_DISPLAY = {
    Modality.MUST: "must",
    Modality.MUST_NOT: "must not",
    Modality.MAY: "may",
    Modality.MAY_NOT: "may not",
    Modality.SHALL: "shall",
    Modality.SHALL_NOT: "shall not",
}

_FRONT_MISLEADING_TITLES = {"sticker label signal", "case name"}
_JURISDICTION_EXCLUDE_TOKENS = {
    "appl",
    "applied",
    "foll",
    "followed",
    "citation",
    "year",
    "case",
    "name",
    "sticker",
    "label",
    "signal",
}
_FRONT_CITATION_START = {"citation", "citation year"}


def _normalize_principle_text(text: Optional[str]) -> Optional[str]:
    """Collapse whitespace and trim structural numbering from ``text``."""

    if not text:
        return None
    normalized = re.sub(r"\s+", " ", text).strip()
    normalized = _PRINCIPLE_LEADING_NUMBERS.sub("", normalized)
    normalized = _PRINCIPLE_LEADING_ENUM.sub("", normalized)
    return normalized or None


def _display_modality(value: Optional[str]) -> Optional[str]:
    """Convert a modality identifier to human-readable text."""

    if not value:
        return None
    modality = Modality.normalise(value)
    if modality is None:
        return value
    return _MODALITY_DISPLAY.get(modality, value)


def _looks_like_citation(candidate: str) -> bool:
    candidate = " ".join(candidate.strip().split())
    if not candidate:
        return False
    lower = candidate.lower()
    if _CITATION_NEUTRAL_RE.search(candidate):
        return True
    if _CITATION_WORD_RE.search(lower):
        return True
    if lower.startswith("in re ") or lower.startswith("re "):
        return True
    if " ex parte " in lower:
        return True
    return False


def _strip_inline_citations(
    value: Optional[str],
) -> Tuple[Optional[str], List[RuleReference]]:
    """Remove inline parenthetical citations, returning cleaned text and refs."""

    if value is None:
        return None, []

    text = str(value)
    if not text.strip():
        return None, []

    references: List[RuleReference] = []
    spans: List[Tuple[int, int]] = []
    depth = 0
    start_index: Optional[int] = None

    for index, char in enumerate(text):
        if char == "(":
            if depth == 0:
                start_index = index
            depth += 1
        elif char == ")" and depth > 0:
            depth -= 1
            if depth == 0 and start_index is not None:
                end = index + 1
                chunk = text[start_index:end]
                body = chunk[1:-1].strip()
                if _looks_like_citation(body):
                    citation = parse_case_citation(body)
                    references.append(citation.to_rule_reference())
                    spans.append((start_index, end))
                start_index = None

    if not spans:
        cleaned = re.sub(r"\s+", " ", text).strip()
        return (cleaned or None), references

    parts: List[str] = []
    cursor = 0
    for start, end in spans:
        parts.append(text[cursor:start])
        cursor = end
    parts.append(text[cursor:])

    cleaned = re.sub(r"\s+", " ", "".join(parts)).strip()
    cleaned = cleaned.rstrip(" ,.;:") if spans else cleaned
    cleaned = cleaned.strip()
    return (cleaned or None), references


def _dedupe_principles(values: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    unique: List[str] = []
    for value in values:
        normalised = _normalize_principle_text(value)
        if not normalised:
            continue
        key = normalised.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(normalised)
    return unique


def _span_source_for_document(metadata: DocumentMetadata) -> str:
    return metadata.canonical_id or metadata.citation or "unknown"


def _find_text_span(body: str, fragment: Optional[str]) -> Optional[Tuple[int, int]]:
    if not body or not fragment:
        return None
    needle = fragment.strip()
    if not needle:
        return None
    idx = body.find(needle)
    if idx != -1:
        return (idx, idx + len(needle))
    # Fallback: normalize whitespace for deterministic matching.
    normal_body = re.sub(r"\s+", " ", body)
    normal_fragment = re.sub(r"\s+", " ", needle)
    idx = normal_body.find(normal_fragment)
    if idx == -1:
        return None
    # Approximate mapping back to original string.
    prefix = normal_body[:idx]
    cursor = 0
    for token in prefix.split(" "):
        if not token:
            continue
        token_idx = body.find(token, cursor)
        if token_idx == -1:
            break
        cursor = token_idx + len(token)
    start = cursor
    end = start + len(normal_fragment)
    return (start, end)


def _rules_to_atoms(
    rules,
    *,
    glossary_registry: Optional[GlossaryRegistry] = None,
    document_body: Optional[str] = None,
    span_source: Optional[str] = None,
) -> List[RuleAtom]:
    rule_atoms: List[RuleAtom] = []
    module_lookup_gloss = getattr(
        sys.modules.get(__name__), "lookup_gloss", lookup_gloss
    )
    registry = (
        glossary_registry if glossary_registry is not None else GlossaryRegistry()
    )
    linker = GlossaryLinker(registry)
    for r in rules:
        actor = getattr(r, "actor", None)
        party = getattr(r, "party", None) or UNKNOWN_PARTY
        who_text = getattr(r, "who_text", None) or actor or None
        modality = getattr(r, "modality", None)
        modality_display = _display_modality(modality)

        action_raw = getattr(r, "action", None)
        action, action_refs = _strip_inline_citations(action_raw)
        conditions_raw = getattr(r, "conditions", None)
        conditions, condition_refs = _strip_inline_citations(conditions_raw)
        scope_raw = getattr(r, "scope", None)
        scope, scope_refs = _strip_inline_citations(scope_raw)

        text_parts = [actor, modality_display or modality, action]
        if conditions:
            text_parts.append(conditions)
        if scope:
            text_parts.append(scope)
        text_combined = " ".join(part.strip() for part in text_parts if part).strip() or None
        text, text_refs = _strip_inline_citations(text_combined)
        text = _normalize_principle_text(text)

        rule_references: List[RuleReference] = []
        rule_references.extend(text_refs)
        rule_references.extend(action_refs)
        rule_references.extend(condition_refs)
        rule_references.extend(scope_refs)

        subject_link = linker.link(
            candidates=(who_text, actor, party),
            fallback_text=who_text or actor or None,
        )

        rule_span = _find_text_span(document_body or "", text or text_combined)
        rule_text_span = (
            TextSpan(
                revision_id=span_source or "unknown",
                start_char=rule_span[0],
                end_char=rule_span[1],
            )
            if rule_span
            else None
        )
        if text and rule_text_span is None and span_source and span_source != "unknown":
            logger.warning(
                "missing TextSpan for rule atom text: %s", (text[:80] or "").strip()
            )
        rule_atom = RuleAtom(
            atom_type="rule",
            role="principle",
            party=party,
            who=party,
            who_text=who_text,
            actor=actor,
            modality=modality,
            action=action,
            conditions=conditions,
            scope=scope,
            text=text,
            subject_link=subject_link,
            references=rule_references,
            text_span=rule_text_span,
            span_status="ok" if rule_text_span else "missing_span",
        )

        rule_atom.subject = Atom(
            type=rule_atom.atom_type,
            role=rule_atom.role,
            party=rule_atom.party,
            who=rule_atom.who,
            who_text=rule_atom.who_text,
            conditions=rule_atom.conditions,
            text=rule_atom.text,
            glossary=subject_link,
        )

        for role, fragments in (getattr(r, "elements", None) or {}).items():
            for fragment in fragments:
                if not fragment:
                    continue
                cleaned_fragment, fragment_refs = _strip_inline_citations(fragment)
                if not cleaned_fragment:
                    continue
                gloss_entry = module_lookup_gloss(cleaned_fragment)
                element_link = linker.link(
                    candidates=(cleaned_fragment, who_text, actor),
                    glossary_entry=gloss_entry,
                    fallback_text=who_text or cleaned_fragment,
                )
                if element_link is None:
                    element_link = GlossaryLink(text=who_text or cleaned_fragment)
                element_span = _find_text_span(document_body or "", cleaned_fragment)
                element_text_span = (
                    TextSpan(
                        revision_id=span_source or "unknown",
                        start_char=element_span[0],
                        end_char=element_span[1],
                    )
                    if element_span
                    else None
                )
                if cleaned_fragment and element_text_span is None and span_source and span_source != "unknown":
                    logger.warning(
                        "missing TextSpan for rule element: %s",
                        (cleaned_fragment[:80] or "").strip(),
                    )
                rule_atom.elements.append(
                    RuleElement(
                        role=role,
                        text=cleaned_fragment,
                        conditions=conditions if role == "circumstance" else None,
                        glossary=element_link,
                        references=fragment_refs,
                        atom_type="element",
                        text_span=element_text_span,
                        span_status="ok" if element_text_span else "missing_span",
                    )
                )
        for reference in rule_references:
            reference_link = linker.link(
                candidates=(
                    reference.citation_text,
                    reference.work,
                    reference.section,
                ),
                fallback_text=reference.citation_text or reference.work,
            )
            if reference_link is not None:
                reference.glossary = reference_link
        if party == UNKNOWN_PARTY:
            rule_atom.lints.append(
                RuleLint(
                    code="unknown_party",
                    message=f"Unclassified actor: {actor}".strip(),
                    atom_type="lint",
                )
            )
        rule_atoms.append(rule_atom)

    return rule_atoms


def _build_provision_from_node(node) -> Provision:
    raw_text = getattr(node, "text", "") or ""
    text_parts: List[str] = []
    if raw_text:
        text_parts.append(raw_text)
    else:
        for child in getattr(node, "children", []):
            child_text = getattr(child, "text", "") or ""
            if not child_text.strip():
                continue
            identifier = getattr(child, "identifier", None)
            fragment = f"{identifier} {child_text}".strip() if identifier else child_text
            text_parts.append(fragment)

    rendered_text = "\n".join(part for part in text_parts if part).strip()

    provision = Provision(
        text=rendered_text,
        identifier=getattr(node, "identifier", None),
        heading=getattr(node, "heading", None),
        node_type=getattr(node, "node_type", None),
        rule_tokens=dict(getattr(node, "rule_tokens", {})),
        references=list(getattr(node, "references", [])),
    )
    provision.children = [
        _build_provision_from_node(child) for child in getattr(node, "children", [])
    ]
    return provision


def _build_provisions_from_nodes(nodes) -> List[Provision]:
    return [_build_provision_from_node(node) for node in nodes]


def _collect_section_provisions(provision: Provision, bucket: List[Provision]) -> None:
    if provision.node_type == "section":
        bucket.append(provision)
    for child in provision.children:
        _collect_section_provisions(child, bucket)


_CONTENTS_MARKER_RE = re.compile(r"\bcontents\b", re.IGNORECASE)
_SECTION_HEADING_RE = re.compile(
    r"(?m)^(?P<identifier>\d+[A-Za-z0-9]*)\s+(?P<heading>(?!\d)[^\n]+)"
)


def _iter_section_provisions(provisions: List[Provision]):
    """Yield every section provision from a list of provisions."""

    for provision in provisions:
        if provision.node_type == "section":
            yield provision
        if provision.children:
            yield from _iter_section_provisions(provision.children)


def _has_section_parser() -> bool:
    return bool(section_parser and hasattr(section_parser, "parse_sections"))


def _normalise_heading_key(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    cleaned = _TOC_TRAILING_PAGE_REF_RE.sub("", value)
    cleaned = _TOC_TRAILING_PAGE_WORD_RE.sub("", cleaned)
    cleaned = _TOC_TRAILING_DOT_LEADER_BLOCK_RE.sub("", cleaned)
    cleaned = _TOC_DOT_LEADER_RE.sub(" ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned.lower() or None


def _fallback_parse_sections(
    text: str, toc_headings: Optional[Iterable[str]] = None
) -> List[Provision]:
    matches = list(_SECTION_HEADING_RE.finditer(text))
    if not matches:
        return [Provision(text=text)]

    sections: List[Provision] = []
    prefix = text[: matches[0].start()].strip()
    attach_prefix = _should_attach_prefix(prefix)

    toc_heading_keys: Set[str] = set()
    if toc_headings:
        for heading in toc_headings:
            normalised = _normalise_heading_key(heading)
            if normalised:
                toc_heading_keys.add(normalised)

    def body_looks_like_toc(content: str) -> bool:
        if not content.strip():
            return True

        lines = [line.strip() for line in content.splitlines() if line.strip()]
        if not lines:
            return True

        toc_like = 0
        for line in lines:
            normalised = _normalise_toc_candidate([line])
            if _looks_like_simple_heading(normalised):
                continue
            if _TOC_LINE_RE.match(normalised) or _TOC_PREFIX_RE.match(normalised):
                toc_like += 1
                continue
            if (
                _TOC_TRAILING_PAGE_REF_RE.search(normalised)
                or _TOC_TRAILING_PAGE_WORD_RE.search(normalised)
                or _has_significant_dot_leader(normalised)
            ):
                toc_like += 1

        return toc_like >= len(lines)

    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[start:end].strip()

        identifier = match.group("identifier").strip()
        heading = match.group("heading").strip()

        heading_key = _normalise_heading_key(heading)
        heading_has_page_ref = bool(
            _TOC_TRAILING_PAGE_REF_RE.search(heading)
            or _TOC_TRAILING_PAGE_WORD_RE.search(heading)
            or _has_significant_dot_leader(heading)
        )
        is_toc_heading = heading_key is not None and heading_key in toc_heading_keys
        if heading_has_page_ref or (is_toc_heading and body_looks_like_toc(body)):
            continue

        parts: List[str] = []
        if index == 0 and attach_prefix:
            parts.append(prefix)
        parts.append(heading)
        if body:
            parts.append(body)

        section_text = "\n".join(parts).strip()
        sections.append(
            Provision(
                text=section_text,
                identifier=identifier or None,
                heading=heading or None,
                node_type="section",
            )
        )

    return sections


def _strip_leading_table_of_contents(text: str) -> str:
    lines = text.splitlines()
    stripped_lines: List[str] = []
    skipping = True

    for line in lines:
        raw = line.rstrip()
        cleaned = raw.strip()
        if skipping:
            if not cleaned:
                continue
            normalised = _normalise_toc_candidate([cleaned]) if cleaned else ""
            if _looks_like_simple_heading(normalised):
                stripped_lines.append(line)
                skipping = False
                continue
            looks_like_toc = bool(
                _CONTENTS_MARKER_RE.search(normalised)
                or _TOC_LINE_RE.match(normalised)
                or _TOC_TRAILING_PAGE_REF_RE.search(normalised)
                or _TOC_TRAILING_PAGE_WORD_RE.search(normalised)
                or _has_significant_dot_leader(normalised)
            )
            if looks_like_toc:
                continue
            skipping = False

        if not skipping:
            stripped_lines.append(line)

    return "\n".join(stripped_lines).lstrip("\n")


def _strip_embedded_table_of_contents(text: str) -> str:
    lines = []

    for line in text.splitlines():
        raw = line.rstrip()
        cleaned = raw.strip()
        if not cleaned:
            lines.append(line)
            continue

        normalised = _normalise_toc_candidate([cleaned])
        if _looks_like_simple_heading(normalised):
            lines.append(line)
            continue
        has_page_marker = bool(
            _TOC_TRAILING_PAGE_REF_RE.search(normalised)
            or _TOC_TRAILING_PAGE_WORD_RE.search(normalised)
        )
        has_dot_leader_block = _has_significant_dot_leader(normalised)
        dot_leader_match = _TOC_TRAILING_DOT_LEADER_BLOCK_RE.search(normalised)
        has_dot_leader = bool(
            dot_leader_match and len(dot_leader_match.group(0).strip()) > 1
        )
        looks_like_toc = bool(
            _CONTENTS_MARKER_RE.search(normalised)
            or _TOC_LINE_RE.match(normalised)
            or has_page_marker
            or (
                has_dot_leader_block
                and has_dot_leader
                and any(char.isdigit() for char in normalised)
            )
        )
        if looks_like_toc:
            continue

        lines.append(line)

    return "\n".join(lines)


def parse_sections(
    text: str, *, toc_headings: Optional[Iterable[str]] = None
) -> List[Provision]:
    """Split ``text`` into individual section provisions."""

    cleaned_text = _strip_leading_table_of_contents(text)
    cleaned_text = _strip_embedded_table_of_contents(cleaned_text)

    if not cleaned_text.strip():
        return []

    parser_available = _has_section_parser()
    if parser_available:
        try:
            nodes = section_parser.parse_sections(cleaned_text)  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - defensive guard
            nodes = []
        structured = _build_provisions_from_nodes(nodes or [])
        sections = list(_iter_section_provisions(structured))
        if sections:
            return sections
        if structured:
            return structured

    logger.debug(
        "Falling back to regex-based section parsing (section_parser_available=%s, "
        "optional_import_failed=%s, root_import_failed=%s)",
        parser_available,
        _SECTION_PARSER_OPTIONAL_IMPORT_FAILED,
        _ROOT_SECTION_PARSER_IMPORT_FAILED,
        extra={
            "section_parser_available": parser_available,
            "section_parser_optional_import_failed": _SECTION_PARSER_OPTIONAL_IMPORT_FAILED,
            "root_section_parser_import_failed": _ROOT_SECTION_PARSER_IMPORT_FAILED,
        },
    )

    return _fallback_parse_sections(cleaned_text, toc_headings=toc_headings)


def _looks_like_capitalised_word(word: str) -> bool:
    if not word:
        return False
    if len(word) == 1:
        return word.isalpha() and word.isupper()
    return word[0].isupper() and word[1:].islower()


def _looks_like_jurisdiction_line(line: str) -> bool:
    if not line:
        return False
    stripped = line.strip()
    if not stripped:
        return False
    if any(char.isdigit() for char in stripped):
        return False
    if re.search(r"[,;:]", stripped):
        return False

    tokens = stripped.lower().split()
    if any(token in _JURISDICTION_EXCLUDE_TOKENS for token in tokens):
        return False

    lowered = stripped.lower()
    if lowered in _KNOWN_JURISDICTIONS:
        return True

    if len(tokens) == 1:
        return lowered in _SINGLE_WORD_JURISDICTIONS or stripped.isupper()

    if len(tokens) > 6:
        return False

    for token in tokens:
        lowered_token = token.lower()
        if lowered_token in _LOWERCASE_JURISDICTION_FILLERS:
            continue
        if not _looks_like_capitalised_word(token):
            return False

    return True


def _looks_like_title_line(line: str) -> bool:
    if not line:
        return False
    return bool(_TITLE_KEYWORD_RE.search(line))


def _infer_cover_metadata(pages: List[dict]) -> Tuple[Optional[str], Optional[str]]:
    if not pages:
        return None, None

    raw_lines = pages[0].get("lines") or []
    lines = [str(line).strip() for line in raw_lines if str(line).strip()]
    if not lines:
        return None, None

    jurisdiction: Optional[str] = None
    title: Optional[str] = None

    for index, line in enumerate(lines[:10]):
        if title is None and _looks_like_title_line(line):
            title = line
            if index >= 1 and jurisdiction is None:
                potential = lines[index - 1]
                if _looks_like_jurisdiction_line(potential):
                    jurisdiction = potential
            continue

        if jurisdiction is None and _looks_like_jurisdiction_line(line):
            jurisdiction = line

    return jurisdiction, title


def _parse_day_month_year(day: str, month: str, year: str) -> Optional[date]:
    composed = f"{day} {month} {year}"
    for fmt in ("%d %B %Y", "%d %b %Y"):
        try:
            return datetime.strptime(composed, fmt).date()
        except ValueError:
            continue
    return None


def _extract_document_date_from_lines(lines: Iterable[str]) -> Optional[date]:
    for line in lines:
        stripped = str(line).strip()
        if not stripped:
            continue
        tokens = stripped.lower().split()
        if any(token in _JURISDICTION_EXCLUDE_TOKENS for token in tokens):
            continue
        for pattern in _DATE_LINE_PATTERNS:
            match = pattern.search(stripped)
            if match:
                parsed = _parse_day_month_year(
                    match.group("day"), match.group("month"), match.group("year")
                )
                if parsed:
                    return parsed

        cleaned = stripped.strip(" .")
        standalone = _STANDALONE_YEAR_RE.fullmatch(cleaned)
        if standalone:
            year_value = int(standalone.group("year"))
            if 1000 <= year_value <= 3000:
                return date(year_value, 1, 1)

    return None


def _compute_document_checksum(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _determine_document_title(
    pages: List[dict],
    source: Path,
    provided_title: Optional[str],
    inferred_title: Optional[str] = None,
) -> Optional[str]:
    """Return a best-effort title for the document."""

    if provided_title:
        candidate = provided_title.strip()
        if candidate:
            return candidate

    if inferred_title:
        candidate = inferred_title.strip()
        lowered = candidate.lower()
        if candidate and lowered not in _FRONT_MISLEADING_TITLES:
            tokens = set(lowered.split())
            if not tokens.intersection(_JURISDICTION_EXCLUDE_TOKENS):
                return candidate

    for page in pages:
        heading = str(page.get("heading") or "").strip()
        if heading:
            lowered = heading.lower()
            if lowered not in _FRONT_MISLEADING_TITLES:
                return heading

    def _title_from_filename() -> Optional[str]:
        stem = source.stem.replace("_", " ").strip()
        stem = re.sub(r"(?i)\\.pdf$", "", stem)
        stem = stem.strip()
        if not stem:
            return None
        # Drop a leading year and court code if present.
        stem = re.sub(r"^\\d{3,4}\\s+[A-Z]{2,}\\s+", "", stem)
        return stem or None

    filename_title = _title_from_filename()
    if filename_title:
        return filename_title

    if inferred_title:
        candidate = inferred_title.strip()
        lowered = candidate.lower()
        if candidate and lowered not in _FRONT_MISLEADING_TITLES:
            return candidate

    fallback = source.stem.replace("_", " ").strip()
    return fallback or None


def _normalize_month_key(value: str) -> Optional[int]:
    key = value.strip().lower().rstrip(".,")
    if not key:
        return None
    if key not in _MONTH_LOOKUP and key.endswith("s"):
        key = key[:-1]
    return _MONTH_LOOKUP.get(key)


def _extract_document_date(pages: List[dict]) -> Optional[date]:
    if not pages:
        return None

    first_page = pages[0] or {}
    raw_lines = first_page.get("lines")
    candidate_lines: List[str] = []
    if isinstance(raw_lines, list):
        for line in raw_lines:
            text = str(line).strip()
            if text:
                candidate_lines.append(text)

    if not candidate_lines:
        heading = first_page.get("heading")
        if heading:
            heading_text = str(heading).strip()
            if heading_text:
                candidate_lines.append(heading_text)
        text = first_page.get("text")
        if text:
            for raw_line in str(text).splitlines():
                line_text = raw_line.strip()
                if line_text:
                    candidate_lines.append(line_text)

    return _extract_document_date_from_lines(candidate_lines)


def _extract_case_names_from_lines(lines: List[str]) -> List[str]:
    """Collect case names from the first page lines."""

    names: List[str] = []
    buffer: List[str] = []

    def flush() -> None:
        nonlocal buffer
        if buffer:
            candidate = " ".join(buffer).strip()
            candidate = re.split(
                r"(?i)\b(?:followed|applied|considered|considere d)\b", candidate
            )[0].strip()
            match = _CASE_NAME_RE.search(candidate)
            if match:
                names.append(match.group(0).strip())
        buffer = []

    for line in lines:
        lower = line.lower()
        if lower.startswith(("appl", "applied", "foll", "followed", "cons")):
            flush()
            continue
        if " v " in lower or lower.endswith(" v") or lower.startswith("v "):
            if buffer:
                flush()
            buffer.append(line)
            continue
        if buffer:
            buffer.append(line)
    flush()
    deduped: List[str] = []
    seen: set[str] = set()
    for name in names:
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(name)
    return deduped


def _extract_case_citations_from_tokens(tokens: List[str]) -> List[CaseCitation]:
    """Rebuild case citation strings from tokenised table columns."""

    citations: List[str] = []
    buffer: List[str] = []
    stop_tokens = {"fca", "fca –", "federal", "court", "nt", "followed", "followed", "foil", "discd", "discussed"}
    for token in tokens:
        if _YEAR_TOKEN_RE.match(token.strip()):
            if buffer:
                citations.append(" ".join(buffer))
                buffer = []
            buffer.append(token)
            continue
        lowered = token.strip().lower()
        if buffer and lowered in stop_tokens:
            citations.append(" ".join(buffer))
            buffer = []
            continue
        if buffer:
            buffer.append(token)
    if buffer:
        citations.append(" ".join(buffer))

    parsed: List[CaseCitation] = []
    seen: set[str] = set()
    for text in citations:
        citation = parse_case_citation(text)
        key = citation.raw or text
        if key in seen:
            continue
        seen.add(key)
        parsed.append(citation)
    return parsed


def _case_citation_to_reference(
    citation: CaseCitation, *, case_name: Optional[str] = None
) -> RuleReference:
    work = case_name or citation.case_name or citation.work_text()
    section = citation.reported_citation or citation.neutral_citation
    return RuleReference(
        work=work,
        section=section,
        pinpoint=citation.pinpoint,
        citation_text=citation.raw or section,
    )


_SECTION_INTRO_TOKENS = {"sec", "sec.", "section", "sections", "s", "ss", "secs", "secs."}
_SECTION_JOINERS = {"and", "or"}
_REFERENCE_BOUNDARY_TOKENS = {".", ";", ":"}
_ACT_NAME_NOISE_PREFIXES = {"see"}
_DEICTIC_ACT_MARKER = "__DEICTIC_ACT__"
_DEICTIC_ACT_TOKENS = {
    "the act",
    "that act",
    "this act",
    "the nt act",
    "the nsw nt act",
    "the nta",
}
_ACT_ANCHOR_RE = re.compile(
    r"(?P<anchor>[A-Za-z][A-Za-z0-9 .,&()\\-]*?(?:Act|Constitution)(?:\\s+\\d{4}(?:-\\d{4})?)?)",
    re.IGNORECASE,
)


def _merge_provenance(
    original: Optional[Dict[str, Any]],
    clause_id: Optional[str],
    pages: Optional[List[int]],
    anchor_used: Optional[str],
) -> Optional[Dict[str, Any]]:
    """Combine provenance hints without affecting behaviour."""
    prov: Dict[str, Any] = {}
    if original:
        prov.update(original)
    if clause_id is not None:
        prov.setdefault("clause_id", clause_id)
    if pages:
        prov.setdefault("pages", list(pages))
    if anchor_used is not None:
        prov.setdefault("anchor_used", anchor_used)
    return prov or None


def _token_text_for_reference(token: Any) -> str:
    return getattr(token, "text", None) or str(token)


def _token_slice_to_text(
    source_text: str, tokens: Sequence[Any], start: int, end: int
) -> Optional[str]:
    if not tokens or start >= len(tokens) or start >= end:
        return None
    start_offset = getattr(tokens[start], "idx", None)
    end_offset = getattr(tokens[end - 1], "idx", None)
    last_text = _token_text_for_reference(tokens[end - 1])
    if start_offset is not None and end_offset is not None and last_text:
        end_offset = end_offset + len(last_text)
        snippet = source_text[start_offset:end_offset]
        cleaned = " ".join(snippet.split())
        return cleaned or None
    joined = " ".join(_token_text_for_reference(tok) for tok in tokens[start:end]).strip()
    return joined or None


def _iter_clause_spans(tree: logic_tree.LogicTree, token_count: int) -> List[Tuple[int, int]]:
    def _collect(target_types: Set[logic_tree.NodeType]) -> List[Tuple[int, int]]:
        buckets: List[Tuple[int, int]] = []
        for node in getattr(tree, "nodes", []):
            if getattr(node, "node_type", None) in target_types and getattr(node, "span", None):
                start, end = node.span  # type: ignore[misc]
                buckets.append((int(start), int(end)))
        return buckets

    spans: List[Tuple[int, int]] = _collect({logic_tree.NodeType.REFERENCE})
    if not spans:
        spans = _collect({logic_tree.NodeType.MODAL})
    if not spans:
        spans = _collect({logic_tree.NodeType.CLAUSE})
    if not spans:
        spans.append((0, token_count))
    if len(spans) > 1:
        # Boundaries inside abbreviations (e.g. "sec.") can fragment clause spans,
        # so fall back to scanning the whole token stream when spans are fragmented.
        return [(0, token_count)]
    spans.sort(key=lambda span: span[0])
    return spans


def _normalise_section_identifier(section_tokens: Sequence[Any]) -> Optional[str]:
    if not section_tokens:
        return None
    raw = "".join(_token_text_for_reference(tok) for tok in section_tokens)
    raw = raw.strip().strip(" ,.;:")
    raw = raw.replace(" ", "")
    if not raw:
        return None
    if not _SECTION_ID_PATTERN.match(raw):
        return None
    return raw


def _collect_section_identifiers(
    tokens: Sequence[Any], start: int, end: int
) -> Tuple[List[str], int]:
    sections: List[str] = []
    current: List[Any] = []
    idx = start
    while idx < end:
        raw = _token_text_for_reference(tokens[idx])
        lower = raw.lower()
        if not current and raw in {".", "-"}:
            idx += 1
            continue
        if lower == "of":
            if current:
                section = _normalise_section_identifier(current)
                if section:
                    sections.append(section)
            return sections, idx
        if lower in _SECTION_INTRO_TOKENS:
            if current:
                section = _normalise_section_identifier(current)
                if section:
                    sections.append(section)
            return sections, idx
        if lower in _SECTION_JOINERS or raw in {","}:
            if current:
                section = _normalise_section_identifier(current)
                if section:
                    sections.append(section)
                current = []
            idx += 1
            continue
        if raw in _REFERENCE_BOUNDARY_TOKENS:
            if current:
                section = _normalise_section_identifier(current)
                if section:
                    sections.append(section)
            return sections, idx
        current.append(tokens[idx])
        idx += 1
    if current:
        section = _normalise_section_identifier(current)
        if section:
            sections.append(section)
    return sections, idx


def _looks_like_next_section(tokens: Sequence[Any], start: int, end: int) -> bool:
    for idx in range(start, min(end, start + 3)):
        raw = _token_text_for_reference(tokens[idx]).lower().rstrip(".")
        if raw in _SECTION_INTRO_TOKENS:
            return True
    return False


def _collect_act_tokens(tokens: Sequence[Any], start: int, end: int) -> Tuple[List[Any], int]:
    act_tokens: List[Any] = []
    idx = start
    anchor_seen = False
    allowed_after_anchor = {"-", "–", "—", "(", ")", "[", "]", "of", "no"}
    while idx < end:
        raw = _token_text_for_reference(tokens[idx])
        lower = raw.lower()
        if lower in _SECTION_INTRO_TOKENS or raw in _REFERENCE_BOUNDARY_TOKENS or raw == ",":
            break
        if lower == "and" and _looks_like_next_section(tokens, idx + 1, end):
            break
        if anchor_seen:
            if (
                raw.isdigit()
                or re.match(r"\d{2,4}", raw)
                or lower in allowed_after_anchor
                or raw in {"-", "–", "—"}
            ):
                act_tokens.append(tokens[idx])
                idx += 1
                continue
            break
        act_tokens.append(tokens[idx])
        if "act" in lower or "constitution" in lower:
            anchor_seen = True
        idx += 1
    while act_tokens and not _token_text_for_reference(act_tokens[-1]).strip():
        act_tokens.pop()
    return act_tokens, idx


def _clean_act_name(act_tokens: Sequence[Any]) -> Optional[str]:
    if not act_tokens:
        return None
    parts = [_token_text_for_reference(tok).strip() for tok in act_tokens]
    parts = [part for part in parts if part]
    if not parts:
        return None
    year_tokens = [part for part in parts if re.fullmatch(r"\d{4}", part)]
    text = " ".join(parts)
    for prefix in _ACT_NAME_NOISE_PREFIXES:
        if text.lower().startswith(prefix + " "):
            text = text[len(prefix) + 1 :].strip(" ,.;:")
            break
    text = re.sub(r"\s+", " ", text).strip(" ,.;:-")
    lowered = text.lower()
    if lowered in _DEICTIC_ACT_TOKENS or any(
        lowered.startswith(token + " ") for token in _DEICTIC_ACT_TOKENS
    ):
        return _DEICTIC_ACT_MARKER
    anchor_match = None
    for match in _ACT_ANCHOR_RE.finditer(text):
        anchor_match = match
    if anchor_match is not None:
        text = text[anchor_match.start() : anchor_match.end()].strip(" ,.;:-")
    tokens = text.split()
    anchor_index = None
    for idx, token in enumerate(tokens):
        if "act" in token.lower() or "constitution" in token.lower():
            anchor_index = idx
    if anchor_index is not None:
        start = max(0, anchor_index - 5)
        end = anchor_index + 1
        while end < len(tokens):
            cleaned = tokens[end].strip("()[]")
            if re.fullmatch(r"\d{2,4}", cleaned) or cleaned in {"-", "–", "—"}:
                end += 1
                continue
            break
        tokens = tokens[start:end]
    while tokens and (
        re.fullmatch(r"[()\\[\\]\\d.-]+", tokens[0])
        or re.fullmatch(r"[ivxlcdmIVXLCDM]{1,3}", tokens[0])
    ):
        tokens = tokens[1:]
    text = " ".join(tokens)
    text = re.sub(r"^[^A-Za-z]+", "", text)
    text = re.sub(r"\s+", " ", text).strip(" ,.;:-")
    if year_tokens and not re.search(r"\b\d{4}\b", text):
        text = f"{text} {year_tokens[0]}".strip()
    if not text:
        return None
    if not re.search(r"\b(act|constitution)\b", text, re.IGNORECASE):
        return None
    if len(text) > 120:
        return None
    return text


def _extract_clause_statutory_references(
    tokens: Sequence[Any],
    span: Tuple[int, int],
    source_text: str,
    *,
    source_label: Optional[str] = None,
    clause_id: Optional[str] = None,
) -> List[RuleReference]:
    references: List[RuleReference] = []
    start, end = span
    idx = start
    last_anchor: Optional[str] = None
    while idx < end:
        token_text = _token_text_for_reference(tokens[idx]).lower().rstrip(".")
        if token_text in _SECTION_INTRO_TOKENS:
            sections, cursor = _collect_section_identifiers(tokens, idx + 1, end)
            if not sections:
                idx += 1
                continue
            if cursor >= end or _token_text_for_reference(tokens[cursor]).lower() != "of":
                idx = cursor
                continue
            act_tokens, after_act = _collect_act_tokens(tokens, cursor + 1, end)
            act_name = _clean_act_name(act_tokens)
            if not act_name:
                idx = after_act
                continue
            if act_name == _DEICTIC_ACT_MARKER:
                if not last_anchor:
                    idx = after_act
                    continue
                act_name = last_anchor
            else:
                last_anchor = act_name
            citation_text = _token_slice_to_text(source_text, tokens, idx, after_act)
            for pinpoint in sections:
                references.append(
                    RuleReference(
                        work=act_name,
                        section="section",
                        pinpoint=pinpoint,
                        citation_text=citation_text,
                        source=source_label,
                        provenance={"clause_id": clause_id} if clause_id else None,
                    )
                )
            idx = after_act
            continue
        idx += 1
    return references


def _canonicalize_work_text(work: Optional[str]) -> Optional[str]:
    if not work:
        return None
    original = work
    year_in_original: Optional[str] = None
    year_match = re.search(r"\b\d{4}(?:-\d{4})?\b", original)
    if year_match:
        year_in_original = year_match.group(0)
    work = re.sub(r"\s+", " ", work).strip(" ,.;:-")
    lowered = work.lower()
    if re.search(r"\b(this|that|the)\s+act\b", lowered):
        return _DEICTIC_ACT_MARKER
    if lowered in _DEICTIC_ACT_TOKENS or any(
        lowered.startswith(token + " ") for token in _DEICTIC_ACT_TOKENS
    ):
        return _DEICTIC_ACT_MARKER
    anchor_match = None
    for match in _ACT_ANCHOR_RE.finditer(work):
        anchor_match = match
    if anchor_match is not None:
        work = anchor_match.group("anchor").strip(" ,.;:-")
    tokens = work.split()
    anchor_index = None
    for idx, token in enumerate(tokens):
        if "act" in token.lower() or "constitution" in token.lower():
            anchor_index = idx
    if anchor_index is not None:
        start = max(0, anchor_index - 5)
        end = anchor_index + 1
        while end < len(tokens):
            cleaned = tokens[end].strip("()[]")
            if re.fullmatch(r"\d{2,4}", cleaned) or cleaned in {"-", "–", "—"}:
                end += 1
                continue
            break
        tokens = tokens[start:end]
    while tokens and tokens[0].lower() in {"of", "the", "this", "that", "a", "an"}:
        tokens = tokens[1:]
    while tokens and (
        re.fullmatch(r"[()\[\]\d.-]+", tokens[0])
        or re.fullmatch(r"[ivxlcdmIVXLCDM]{1,3}", tokens[0])
    ):
        tokens = tokens[1:]
    work = " ".join(tokens)
    work = re.sub(r"^[^A-Za-z]+", "", work)
    work = re.sub(r"\s+", " ", work).strip(" ,.;:-")
    if not work:
        return None
    if not re.search(r"\b(act|constitution)\b", work, re.IGNORECASE):
        return None
    if year_in_original and year_in_original not in work:
        work = f"{work} {year_in_original}".strip()
    if len(work) > 120:
        return None
    return work.lower()


def _canonicalize_references(
    references: List[RuleReference],
    *,
    preferred_sources: Optional[Sequence[str]] = None,
    anchor_core_merge: bool = False,
    clause_id: Optional[str] = None,
    pages: Optional[List[int]] = None,
    anchor_used: Optional[str] = None,
) -> List[RuleReference]:
    canonical: List[RuleReference] = []
    last_anchor: Optional[str] = None
    for ref in references:
        canonical_work = _canonicalize_work_text(ref.work)
        if canonical_work == _DEICTIC_ACT_MARKER:
            if not last_anchor:
                continue
            canonical_work = last_anchor
        elif canonical_work:
            last_anchor = canonical_work
        else:
            continue
        canonical.append(
            RuleReference(
                work=canonical_work,
                section=ref.section,
                pinpoint=ref.pinpoint,
                citation_text=ref.citation_text,
                source=ref.source,
                uri=ref.uri,
                provenance=_merge_provenance(ref.provenance, clause_id, pages, anchor_used),
                glossary=ref.glossary,
                identity_hash=ref.identity_hash,
                family_key=ref.family_key,
                year=ref.year,
                jurisdiction_hint=ref.jurisdiction_hint,
            )
        )

    deduped: List[RuleReference] = []
    seen: Dict[Tuple[Optional[str], Optional[str], Optional[str]], RuleReference] = {}

    def _source_rank(source: Optional[str]) -> int:
        if not preferred_sources:
            return 0
        try:
            return preferred_sources.index(source)  # type: ignore[arg-type]
        except Exception:
            return len(preferred_sources)

    def _anchor_family_key(value: Optional[str]) -> Optional[str]:
        return _build_family_key(value)

    if anchor_core_merge and canonical:
        link_present = any(ref.source == "link" and ref.work for ref in canonical)
        if not link_present:
            def _anchor_score(value: RuleReference) -> Tuple[int, int, int, str]:
                work_text = value.work or ""
                has_year = 1 if re.search(r"\b\d{4}(?:-\d{4})?\b", work_text) else 0
                clean_start = 1 if re.match(r"^[A-Za-z]", work_text) else 0
                return (has_year, clean_start, len(work_text), work_text)

            anchor_core_ref: Optional[RuleReference] = None
            for ref in sorted(canonical, key=_anchor_score, reverse=True):
                if ref.work:
                    anchor_core_ref = ref
                    break

            anchor_core_work = anchor_core_ref.work if anchor_core_ref else None
            anchor_core_family = _anchor_family_key(anchor_core_work) if anchor_core_work else None

            rewritten: List[RuleReference] = []
            for ref in canonical:
                if ref.source == "link":
                    rewritten.append(ref)
                    continue
                if ref.work == _DEICTIC_ACT_MARKER:
                    if anchor_core_work:
                        ref = RuleReference(
                            work=anchor_core_work,
                            section=ref.section,
                            pinpoint=ref.pinpoint,
                            citation_text=ref.citation_text,
                            source=ref.source,
                            uri=ref.uri,
                            provenance=ref.provenance,
                            identity_hash=ref.identity_hash,
                            family_key=ref.family_key,
                            year=ref.year,
                            jurisdiction_hint=ref.jurisdiction_hint,
                            glossary=ref.glossary,
                        )
                    else:
                        continue
                elif anchor_core_family:
                    family_key = _anchor_family_key(ref.work)
                    if family_key and (
                        family_key == anchor_core_family
                        or anchor_core_family.endswith(family_key)
                        or family_key in anchor_core_family
                    ):
                        ref = RuleReference(
                            work=anchor_core_work,
                            section=ref.section,
                            pinpoint=ref.pinpoint,
                            citation_text=ref.citation_text,
                            source=ref.source,
                            uri=ref.uri,
                            provenance=ref.provenance,
                            identity_hash=ref.identity_hash,
                            family_key=ref.family_key,
                            year=ref.year,
                            jurisdiction_hint=ref.jurisdiction_hint,
                            glossary=ref.glossary,
                        )
                rewritten.append(ref)
            canonical = rewritten

    for ref in canonical:
        key = (
            ref.work.lower() if ref.work else None,
            ref.section.lower() if ref.section else None,
            ref.pinpoint.lower() if ref.pinpoint else None,
        )
        existing = seen.get(key)
        if existing is None or _source_rank(ref.source) < _source_rank(existing.source):
            seen[key] = ref

    for ref in seen.values():
        deduped.append(ref.compute_identity())
    return deduped


def _extract_statutory_references_from_logic_tree(
    text: str, *, source_id: str, source_label: Optional[str] = None
) -> List[RuleReference]:
    if not text.strip():
        return []
    try:
        normalized = normalise(text)
    except Exception:
        return []
    tokens = list(normalized.tokens)
    if not tokens:
        return []
    try:
        tree = logic_tree.build(tokens, source_id=source_id)
        clause_spans = _iter_clause_spans(tree, len(tokens))
    except Exception:
        clause_spans = [(0, len(tokens))]
    references: List[RuleReference] = []
    for idx, span in enumerate(clause_spans):
        clause_id = f"{source_id}-clause-{idx}"
        clause_refs = _extract_clause_statutory_references(
            tokens, span, str(normalized), source_label=source_label, clause_id=clause_id
        )
        references.extend(
            _canonicalize_references(
                clause_refs,
                anchor_core_merge=True,
                clause_id=clause_id,
                anchor_used=source_label,
            )
        )
    return _canonicalize_references(
        references, preferred_sources=("link", None), anchor_used=source_label
    )


def _parse_work_from_uri(uri: str) -> Optional[str]:
    parsed = urlparse(uri)
    path_tail = unquote(parsed.path.split("/")[-1])
    path_tail = re.sub(r"\.[A-Za-z0-9]+$", "", path_tail)
    path_tail = path_tail.replace("_", " ").replace("-", " ")
    work = _canonicalize_work_text(path_tail)
    if work:
        return work
    for values in parse_qs(parsed.query).values():
        for value in values:
            candidate = _canonicalize_work_text(unquote(value).replace("_", " "))
            if candidate:
                return candidate
    return None


def _parse_section_from_uri(uri: str) -> Optional[str]:
    parsed = urlparse(uri)
    candidates: List[str] = []
    if parsed.fragment:
        candidates.append(parsed.fragment)
    if parsed.query:
        candidates.append(parsed.query)
    if parsed.path:
        candidates.extend(parsed.path.split("/"))
    for candidate in candidates:
        candidate = candidate.replace("_", " ")
        match = re.search(
            r"(?:sec(?:tion)?|s)\s*[:=/\-]?\s*(?P<section>[0-9A-Za-z()]+)",
            candidate,
            re.IGNORECASE,
        )
        if match:
            section = match.group("section")
            return re.sub(r"\s+", "", section)
        simple = re.search(r"^(?P<section>\d+[A-Za-z]*(?:\([^)]+\))*)$", candidate)
        if simple:
            return simple.group("section")
    return None


def _extract_hyperlink_references(
    pages: List[dict], *, source_id: str
) -> List[RuleReference]:
    references: List[RuleReference] = []
    for page in pages:
        link_page = page.get("page")
        for link in page.get("links") or []:
            anchor_text = str(link.get("text") or "").strip()
            uri = link.get("uri")
            anchor_refs: List[RuleReference] = []
            if anchor_text:
                anchor_refs.extend(
                    _extract_statutory_references_from_logic_tree(
                        anchor_text, source_id=source_id, source_label="link"
                    )
                )
                if not anchor_refs:
                    work = _canonicalize_work_text(anchor_text)
                    if work:
                        anchor_refs.append(
                            RuleReference(
                                work=work,
                                citation_text=anchor_text,
                                source="link",
                                uri=uri,
                                provenance={"pages": [link_page], "anchor_used": "link"},
                            )
                        )
            work_from_uri = _parse_work_from_uri(uri) if uri else None
            section_from_uri = _parse_section_from_uri(uri) if uri else None
            uri_refs: List[RuleReference] = []
            if work_from_uri:
                uri_refs.append(
                    RuleReference(
                        work=work_from_uri,
                        section="section" if section_from_uri else None,
                        pinpoint=section_from_uri,
                        citation_text=anchor_text or uri,
                        source="link",
                        uri=uri,
                        provenance={"pages": [link_page], "anchor_used": "link"},
                    )
                )
            if uri_refs:
                references.extend(uri_refs)
                for ref in anchor_refs:
                    if ref.section or ref.pinpoint:
                        references.append(ref)
            else:
                references.extend(anchor_refs)
    return _canonicalize_references(
        references,
        preferred_sources=("link",),
        pages=[p.get("page") for p in pages if p.get("page") is not None],
        anchor_used="link",
    )


def _extract_front_page_references(pages: List[dict]) -> List[RuleReference]:
    """Derive case references from the front-page citation table."""

    if not pages:
        return []
    lines = pages[0].get("lines") or []
    if not isinstance(lines, list) or not lines:
        return []

    lower_lines = [str(line).strip().lower() for line in lines if str(line).strip()]
    split_index = None
    for idx, line in enumerate(lower_lines):
        if any(line.startswith(prefix) for prefix in _FRONT_CITATION_START):
            split_index = idx
            break

    if split_index is None:
        return []

    case_names = _extract_case_names_from_lines(lines[:split_index])
    citation_tokens = [str(token).strip() for token in lines[split_index + 1 :] if str(token).strip()]
    citations = _extract_case_citations_from_tokens(citation_tokens)

    references: List[RuleReference] = []
    for idx, citation in enumerate(citations):
        paired_name = case_names[idx] if idx < len(case_names) else None
        ref = _case_citation_to_reference(citation, case_name=paired_name)
        ref.provenance = {"pages": [1], "anchor_used": "front_page"}
        references.append(ref)

    return references


def build_document(
    pages: List[dict],
    source: Path,
    jurisdiction: Optional[str] = None,
    citation: Optional[str] = None,
    title: Optional[str] = None,
    cultural_flags: Optional[List[str]] = None,
    document_date: Optional[date] = None,
    glossary_registry: Optional[GlossaryRegistry] = None,
) -> Document:
    """Create a :class:`Document` from extracted pages.

    Args:
        pages: Extracted page payloads including headings and text.
        source: Path to the original PDF used for provenance.
        jurisdiction: Optional jurisdiction metadata supplied by the caller.
        citation: Optional citation metadata supplied by the caller.
        title: Optional document title to prefer over inferred headings.
        cultural_flags: Any cultural sensitivity flags to attach to metadata.
        glossary_registry: Glossary registry for definition lookups.
    """

    inferred_jurisdiction, inferred_title = _infer_cover_metadata(pages)
    first_page_lines = pages[0].get("lines") if pages else None
    inferred_date = _extract_document_date_from_lines(first_page_lines or [])

    full_body_parts = [
        f"{str(page.get('heading') or '')}\n{str(page.get('text') or '')}".strip()
        for page in pages
        if str(page.get("heading") or "").strip()
        or str(page.get("text") or "").strip()
    ]
    full_body = "\n\n".join(full_body_parts).strip()
    detected_date = _extract_document_date(pages)

    toc_entries = parse_table_of_contents(pages)
    toc_heading_candidates = _collect_toc_heading_candidates(toc_entries)

    non_toc_pages = [page for page in pages if not _is_table_of_contents_page(page)]
    body_pages = _filter_pages_with_toc(non_toc_pages, toc_entries)
    if not body_pages:
        body_pages = non_toc_pages or pages

    section_body_parts = [
        f"{str(page.get('heading') or '')}\n{str(page.get('text') or '')}".strip()
        for page in body_pages
        if str(page.get("heading") or "").strip()
        or str(page.get("text") or "").strip()
    ]
    section_body = "\n\n".join(section_body_parts).strip()

    body = section_body or full_body
    checksum = _compute_document_checksum(body)

    resolved_title = _determine_document_title(
        pages, source, title, inferred_title=inferred_title
    )
    resolved_jurisdiction = jurisdiction or inferred_jurisdiction or ""
    resolved_date = (
        detected_date
        or document_date
        or inferred_date
        or date.today()
    )
    if not resolved_jurisdiction:
        stem_upper = source.stem.upper()
        if " HCA " in f" {stem_upper} " or stem_upper.startswith("HCA ") or " HCA" in stem_upper:
            resolved_jurisdiction = "HCA"

    metadata = DocumentMetadata(
        jurisdiction=resolved_jurisdiction,
        citation=citation or "",
        date=resolved_date,
        title=resolved_title,
        cultural_flags=cultural_flags,
        provenance=str(source),
        checksum=checksum,
    )

    registry = glossary_registry or _DEFAULT_GLOSSARY_REGISTRY

    provisions = parse_sections(section_body or "", toc_headings=toc_heading_candidates)
    front_page_refs = _extract_front_page_references(pages)
    statute_refs = _extract_statutory_references_from_logic_tree(
        body, source_id=source.stem
    )
    link_refs = _extract_hyperlink_references(pages, source_id=source.stem)
    statute_refs = _canonicalize_references(
        link_refs + statute_refs,
        preferred_sources=("link", None),
        pages=[p.get("page") for p in pages if p.get("page") is not None],
        anchor_used="body",
    )
    extra_refs = front_page_refs + statute_refs

    definitions = _extract_definition_entries(body)
    structured_for_definitions: Optional[List[Provision]] = None
    if not provisions:
        parser_available = _has_section_parser()
        if parser_available:
            try:
                nodes = section_parser.parse_sections(section_body)  # type: ignore[attr-defined]
            except Exception:  # pragma: no cover - defensive guard
                nodes = []
            structured = _build_provisions_from_nodes(nodes or [])
            if structured:
                structured_for_definitions = structured
            sections = list(_iter_section_provisions(structured))
            if sections:
                provisions = sections
            elif structured:
                provisions = structured

        if not provisions:
            logger.debug(
                "Section parsing yielded no provisions after structured fallback "
                "(section_parser_available=%s, optional_import_failed=%s, "
                "root_import_failed=%s, body_length=%s)",
                parser_available,
                _SECTION_PARSER_OPTIONAL_IMPORT_FAILED,
                _ROOT_SECTION_PARSER_IMPORT_FAILED,
                len(section_body),
                extra={
                    "section_parser_available": parser_available,
                    "section_parser_optional_import_failed": _SECTION_PARSER_OPTIONAL_IMPORT_FAILED,
                    "root_section_parser_import_failed": _ROOT_SECTION_PARSER_IMPORT_FAILED,
                    "body_length": len(section_body),
                },
            )

    needs_structured_definitions = not provisions or any(
        getattr(prov, "node_type", None) == "section"
        and _is_definition_heading(getattr(prov, "heading", None))
        for prov in provisions
    )

    if structured_for_definitions is None:
        if needs_structured_definitions:
            structured_for_definitions = _resolve_definition_roots(body, provisions)
        else:
            structured_for_definitions = provisions

    registered_with_scope = _register_definition_provisions(
        structured_for_definitions, registry
    )

    if not registered_with_scope:
        for term, definition in definitions.items():
            registry.register_definition(term, definition)

    for prov in provisions:
        prov.ensure_rule_atoms()
        rules = extract_rules(prov.text)
        rule_atoms = _rules_to_atoms(
            rules,
            glossary_registry=registry,
            document_body=body,
            span_source=_span_source_for_document(metadata),
        )
        prov.rule_atoms.extend(rule_atoms)
        prov.sync_legacy_atoms()
        existing = _dedupe_principles(prov.principles)
        prov.principles = existing
        rule_principles = _dedupe_principles(
            atom.text for atom in prov.atoms if atom.type == "rule" and atom.text
        )
        merged = _dedupe_principles([*existing, *rule_principles])
        prov.principles = merged
        if prov is provisions[0] and extra_refs:
            seen_refs: set[tuple[Optional[str], Optional[str], Optional[str], Optional[str], Optional[int]]] = set(
                tuple(ref) if isinstance(ref, (list, tuple)) else ()
                for ref in prov.references
            )
            for ref in extra_refs:
                serialised = (
                    ref.work,
                    ref.section,
                    ref.pinpoint,
                    ref.citation_text,
                    ref.glossary_id,
                )
                if serialised in seen_refs:
                    continue
                seen_refs.add(serialised)
                prov.references.append(serialised)

    document = Document(
        metadata=metadata,
        body=body,
        provisions=provisions,
        toc_entries=toc_entries,
    )
    _CULTURAL_OVERLAY.apply(document)
    return document


def save_document(doc: Document, output_path: Path) -> None:
    """Persist a document to disk as JSON."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        f.write(doc.to_json())


def iter_process_pdf(
    pdf: Path,
    output: Optional[Path] = None,
    jurisdiction: Optional[str] = None,
    citation: Optional[str] = None,
    title: Optional[str] = None,
    cultural_flags: Optional[List[str]] = None,
    document_date: Optional[date] = None,
    db_path: Optional[Path] = None,
    doc_id: Optional[int] = None,
    context_overlays: Optional[List[dict]] = None,
    break_after_chars: Optional[int] = None,
) -> Iterator[Tuple[str, Dict[str, Any]]]:
    """Yield progress updates for :func:`process_pdf` steps.

    Each iteration yields a ``(stage, payload)`` tuple describing the work that has
    just completed. Callers can advance the generator manually to "step" through the
    ingestion pipeline.
    """

    if doc_id is not None and db_path is None:
        raise ValueError("A database path must be provided when specifying --doc-id")

    storage: Optional[Storage] = None
    registry: Optional[GlossaryRegistry] = None
    doc: Optional[Document] = None
    try:
        if db_path:
            db_path.parent.mkdir(parents=True, exist_ok=True)
            storage = Storage(db_path)
        registry = GlossaryRegistry(storage)
        char_threshold = break_after_chars if break_after_chars and break_after_chars > 0 else None
        pages: List[dict] = []
        char_count = 0
        breakpoint_triggered = False
        for page in extract_pdf_text(pdf):
            pages.append(page)
            body_text = str(page.get("text") or "")
            heading_text = str(page.get("heading") or "")
            char_count += len(body_text) + len(heading_text)
            if char_threshold is not None and not breakpoint_triggered and char_count >= char_threshold:
                breakpoint_triggered = True
                yield (
                    "extraction",
                    {
                        "pages": list(pages),
                        "char_count": char_count,
                        "complete": False,
                        "breakpoint": char_threshold,
                    },
                )

        yield (
            "extraction",
            {
                "pages": list(pages),
                "char_count": char_count,
                "complete": True,
                "breakpoint": char_threshold,
            },
        )

        doc = build_document(
            pages,
            pdf,
            jurisdiction,
            citation,
            title,
            cultural_flags,
            document_date=document_date,
            glossary_registry=registry,
        )
        from src.text.compression_stats import compute_compression_stats

        doc.metadata.compression_stats = compute_compression_stats(doc.body).to_dict()
        yield ("build", {"document": doc})
    finally:
        if registry is not None:
            registry.close()
        if storage is not None:
            storage.close()

    if doc is None:
        raise RuntimeError("PDF ingestion failed to build a document")

    out = output or Path("data/pdfs") / (pdf.stem + ".json")
    stored_doc_id: Optional[int] = None
    if db_path:
        store = VersionedStore(db_path)
        try:
            actual_doc_id = doc_id if doc_id is not None else store.generate_id()
            if not doc.metadata.canonical_id:
                doc.metadata.canonical_id = str(actual_doc_id)
            store.validate_revision_payload(doc)
            store.add_revision(actual_doc_id, doc, doc.metadata.date)
            stored_doc_id = actual_doc_id
            yield ("persist", {"stored_doc_id": stored_doc_id, "document": doc})
        finally:
            store.close()

    if db_path and context_overlays:
        from sensiblaw.db import MigrationRunner
        from sensiblaw.ingest.context_overlays import ingest_context_fields

        connection = sqlite3.connect(db_path)
        try:
            MigrationRunner(connection).apply_all()
            ingest_context_fields(connection, context_overlays)
            yield ("context_overlays", {"count": len(context_overlays)})
        finally:
            connection.close()

    save_document(doc, out)
    yield (
        "save",
        {"document": doc, "stored_doc_id": stored_doc_id, "output_path": out},
    )


def process_pdf(
    pdf: Path,
    output: Optional[Path] = None,
    jurisdiction: Optional[str] = None,
    citation: Optional[str] = None,
    title: Optional[str] = None,
    cultural_flags: Optional[List[str]] = None,
    document_date: Optional[date] = None,
    db_path: Optional[Path] = None,
    doc_id: Optional[int] = None,
    context_overlays: Optional[List[dict]] = None,
) -> Tuple[Document, Optional[int]]:
    """Extract text, parse sections, run rule extraction and persist."""

    result_doc: Optional[Document] = None
    stored_doc_id: Optional[int] = None
    for stage, payload in iter_process_pdf(
        pdf,
        output=output,
        jurisdiction=jurisdiction,
        citation=citation,
        title=title,
        cultural_flags=cultural_flags,
        document_date=document_date,
        db_path=db_path,
        doc_id=doc_id,
        context_overlays=context_overlays,
    ):
        if stage == "build":
            result_doc = payload.get("document")
        elif stage == "persist":
            stored_doc_id = payload.get("stored_doc_id")
            result_doc = payload.get("document") or result_doc
        elif stage == "save":
            result_doc = payload.get("document") or result_doc
            stored_doc_id = payload.get("stored_doc_id", stored_doc_id)

    if result_doc is None:
        raise RuntimeError("PDF ingestion did not yield a document")

    return result_doc, stored_doc_id


def _load_context_overlays(path: Path) -> List[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        overlays = payload.get("overlays", [])
    else:
        overlays = payload
    if not isinstance(overlays, list):
        raise ValueError("Context overlays must be a list or {overlays:[...]} object")
    return [dict(item) for item in overlays]


def main() -> None:
    """Command line entry point."""

    parser = argparse.ArgumentParser(
        description="Extract rules from a PDF and save as a Document"
    )
    parser.add_argument("pdf", type=Path, help="Path to PDF file")
    parser.add_argument("-o", "--output", type=Path, help="Output JSON path")
    parser.add_argument("--jurisdiction", help="Jurisdiction metadata")
    parser.add_argument("--citation", help="Citation metadata")
    parser.add_argument("--title", help="Title metadata")
    parser.add_argument(
        "--cultural-flags", nargs="*", help="List of cultural sensitivity flags"
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=_DEFAULT_DB_PATH,
        help=(
            "Optional SQLite path for versioned storage. "
            "Defaults to data/corpus/ingest.sqlite; pass '' to skip DB persistence."
        ),
    )
    parser.add_argument(
        "--context-overlays",
        type=Path,
        help="Optional JSON file containing context overlay records to store.",
    )
    args = parser.parse_args()

    context_overlays = None
    if args.context_overlays:
        context_overlays = _load_context_overlays(args.context_overlays)

    doc, _ = process_pdf(
        args.pdf,
        output=args.output,
        jurisdiction=args.jurisdiction,
        citation=args.citation,
        title=args.title,
        cultural_flags=args.cultural_flags,
        db_path=args.db_path,
        context_overlays=context_overlays,
    )
    print(doc.to_json())


if __name__ == "__main__":  # pragma: no cover
    main()


def _should_attach_prefix(prefix: str) -> bool:
    if not prefix.strip():
        return False

    if _CONTENTS_MARKER_RE.search(prefix):
        return False

    lowered = prefix.lower()
    if "table of contents" in lowered:
        return False

    lines = [line.strip() for line in prefix.splitlines() if line.strip()]
    if not lines:
        return False

    numeric_lines = sum(1 for line in lines if line and line[0].isdigit())
    if numeric_lines >= max(1, len(lines) // 2):
        return False

    return True
