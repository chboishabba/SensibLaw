"""PDF ingestion utilities producing :class:`Document` objects."""

import argparse
import calendar
import hashlib
import json
import logging
import re
import sys
from collections import deque
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Set, Tuple

from pdfminer.high_level import extract_pages

from src.culture.overlay import get_default_overlay
from src.glossary.service import lookup as lookup_gloss
from src.ingestion.cache import HTTPCache
from src.models.document import Document, DocumentMetadata, DocumentTOCEntry
from src.models.provision import (
    Atom,
    Provision,
    RuleAtom,
    RuleElement,
    RuleLint,
    RuleReference,
)
from src.rules import UNKNOWN_PARTY
from src.rules.extractor import extract_rules
from src.storage.core import Storage
from src.storage.versioned_store import VersionedStore
from src.text.citations import parse_case_citation


logger = logging.getLogger(__name__)

_CULTURAL_OVERLAY = get_default_overlay()


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


def extract_pdf_text(pdf_path: Path) -> Iterator[dict]:
    """Yield text and headings from ``pdf_path`` one page at a time."""

    with pdf_path.open("rb") as pdf_file:
        for page_number, layout in enumerate(extract_pages(pdf_file), start=1):
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
            yield {"page": page_number, "heading": heading, "text": body, "lines": lines}


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


def _normalize_principle_text(text: Optional[str]) -> Optional[str]:
    """Collapse whitespace and trim structural numbering from ``text``."""

    if not text:
        return None
    normalized = re.sub(r"\s+", " ", text).strip()
    normalized = _PRINCIPLE_LEADING_NUMBERS.sub("", normalized)
    normalized = _PRINCIPLE_LEADING_ENUM.sub("", normalized)
    return normalized or None


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


def _rules_to_atoms(
    rules, glossary_registry: Optional[GlossaryRegistry] = None
) -> List[RuleAtom]:
    rule_atoms: List[RuleAtom] = []
    module_lookup_gloss = getattr(
        sys.modules.get(__name__), "lookup_gloss", lookup_gloss
    )
    registry = (
        glossary_registry if glossary_registry is not None else GlossaryRegistry()
    )
    for r in rules:
        actor = getattr(r, "actor", None)
        party = getattr(r, "party", None) or UNKNOWN_PARTY
        who_text = getattr(r, "who_text", None) or actor or None
        modality = getattr(r, "modality", None)

        action_raw = getattr(r, "action", None)
        action, action_refs = _strip_inline_citations(action_raw)
        conditions_raw = getattr(r, "conditions", None)
        conditions, condition_refs = _strip_inline_citations(conditions_raw)
        scope_raw = getattr(r, "scope", None)
        scope, scope_refs = _strip_inline_citations(scope_raw)

        text_parts = [actor, modality, action]
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

        subject_gloss = who_text or actor or None
        subject_metadata: Optional[Dict[str, Any]] = None
        subject_glossary_id: Optional[int] = None
        if registry is not None:
            subject_entry: Optional[GlossaryRecord] = None
            for candidate in (who_text, actor, party):
                if candidate:
                    subject_entry = registry.resolve(candidate)
                    if subject_entry:
                        break
            if subject_entry:
                subject_gloss = subject_entry.definition
                subject_metadata = _clone_metadata(subject_entry.metadata)
                subject_glossary_id = subject_entry.id

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
            subject_gloss=subject_gloss,
            subject_gloss_metadata=subject_metadata,
            glossary_id=subject_glossary_id,
            references=rule_references,
        )

        rule_atom.subject = Atom(
            type=rule_atom.atom_type,
            role=rule_atom.role,
            party=rule_atom.party,
            who=rule_atom.who,
            who_text=rule_atom.who_text,
            conditions=rule_atom.conditions,
            text=rule_atom.text,
            gloss=rule_atom.subject_gloss,
            gloss_metadata=rule_atom.subject_gloss_metadata,
            glossary_id=rule_atom.glossary_id,
        )

        for role, fragments in (getattr(r, "elements", None) or {}).items():
            for fragment in fragments:
                if not fragment:
                    continue
                cleaned_fragment, fragment_refs = _strip_inline_citations(fragment)
                if not cleaned_fragment:
                    continue
                gloss_entry = module_lookup_gloss(cleaned_fragment)
                resolved_entry: Optional[GlossaryRecord] = None
                if registry is not None and gloss_entry:
                    resolved_entry = registry.register_definition(
                        gloss_entry.phrase,
                        gloss_entry.text,
                        gloss_entry.metadata,
                    )
                if registry is not None and resolved_entry is None:
                    resolved_entry = registry.resolve(cleaned_fragment)

                gloss_text = who_text or cleaned_fragment
                gloss_metadata = None
                glossary_id = None
                if resolved_entry:
                    gloss_text = resolved_entry.definition
                    gloss_metadata = _clone_metadata(resolved_entry.metadata)
                    glossary_id = resolved_entry.id
                elif gloss_entry:
                    gloss_text = gloss_entry.text
                    if gloss_entry.metadata is not None:
                        gloss_metadata = dict(gloss_entry.metadata)
                rule_atom.elements.append(
                    RuleElement(
                        role=role,
                        text=cleaned_fragment,
                        conditions=conditions if role == "circumstance" else None,
                        gloss=gloss_text,
                        gloss_metadata=gloss_metadata,
                        references=fragment_refs,
                        glossary_id=glossary_id,
                        atom_type="element",
                    )
                )
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

    lowered = stripped.lower()
    if lowered in _KNOWN_JURISDICTIONS:
        return True

    tokens = stripped.split()
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

    if inferred_title:
        candidate = inferred_title.strip()
        if candidate:
            return candidate

    if provided_title:
        candidate = provided_title.strip()
        if candidate:
            return candidate

    if inferred_title:
        candidate = inferred_title.strip()
        if candidate:
            return candidate

    for page in pages:
        heading = str(page.get("heading") or "").strip()
        if heading:
            return heading

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
        rule_atoms = _rules_to_atoms(rules, glossary_registry=registry)
        prov.rule_atoms.extend(rule_atoms)
        prov.sync_legacy_atoms()
        existing = _dedupe_principles(prov.principles)
        prov.principles = existing
        rule_principles = _dedupe_principles(
            atom.text for atom in prov.atoms if atom.type == "rule" and atom.text
        )
        merged = _dedupe_principles([*existing, *rule_principles])
        prov.principles = merged

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
) -> Tuple[Document, Optional[int]]:
    """Extract text, parse sections, run rule extraction and persist."""

    if doc_id is not None and db_path is None:
        raise ValueError("A database path must be provided when specifying --doc-id")

    storage: Optional[Storage] = None
    registry: Optional[GlossaryRegistry] = None
    try:
        if db_path:
            storage = Storage(db_path)
        registry = GlossaryRegistry(storage)
        pages = list(extract_pdf_text(pdf))
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
    finally:
        if registry is not None:
            registry.close()
        if storage is not None:
            storage.close()
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
        finally:
            store.close()

    save_document(doc, out)
    return doc, stored_doc_id


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
    args = parser.parse_args()

    doc, _ = process_pdf(
        args.pdf,
        output=args.output,
        jurisdiction=args.jurisdiction,
        citation=args.citation,
        title=args.title,
        cultural_flags=args.cultural_flags,
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
