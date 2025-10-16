"""SensibLaw Streamlit operations console."""

from __future__ import annotations

import json
import re
import sys
import tempfile
from dataclasses import asdict, dataclass, is_dataclass
from datetime import date
from enum import Enum
from html import escape
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import streamlit as st
import streamlit.components.v1 as components

try:  # Optional dependency for tabular display
    import pandas as pd
except Exception:  # pragma: no cover - pandas is optional at runtime
    pd = None  # type: ignore[assignment]

try:  # Optional dependency for graph rendering
    from graphviz import Digraph
except Exception:  # pragma: no cover - graphviz is optional at runtime
    Digraph = None  # type: ignore[assignment]

# Ensure the project source tree is importable when running ``streamlit run``.
ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.api.routes import (  # noqa: E402  - imported after path adjustment
    HTTPException,
    execute_tests,
    fetch_case_treatment,
    fetch_provision_atoms,
    generate_subgraph,
    _graph as ROUTES_GRAPH,
)
from src.api.sample_routes import api_provision, api_subgraph, api_treatment  # noqa: E402
from src.concepts.cloud import build_cloud as advanced_cloud  # noqa: E402
from src.distinguish.engine import compare_story_to_case  # noqa: E402
from src.distinguish.loader import load_case_silhouette  # noqa: E402
from src.frame.compiler import compile_frame  # noqa: E402
from src.glossary.service import lookup as glossary_lookup  # noqa: E402
from src.graph.models import EdgeType, GraphEdge, GraphNode, NodeType  # noqa: E402
from src.harm.index import compute_harm  # noqa: E402
from src.ingestion.frl import fetch_acts  # noqa: E402
from src.models.document import Document, DocumentTOCEntry  # noqa: E402
from src.models.provision import Atom, Provision  # noqa: E402
from src.pipeline import build_cloud, match_concepts, normalise  # noqa: E402
from src.pdf_ingest import process_pdf  # noqa: E402
from src.receipts.build import build_receipt  # noqa: E402
from src.receipts.verify import verify_receipt  # noqa: E402
from src.rules import Rule  # noqa: E402
from src.rules.extractor import extract_rules  # noqa: E402
from src.rules.reasoner import check_rules  # noqa: E402
from src.storage.versioned_store import VersionedStore  # noqa: E402
from src.tests.templates import TEMPLATE_REGISTRY  # noqa: E402
from src.text.similarity import simhash  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers and constants
# ---------------------------------------------------------------------------

SAMPLE_CASES: Dict[str, str] = {"GLJ Permanent Stay": "glj"}
SAMPLE_STORY_FACTS = {
    "facts": {
        "delay": True,
        "abuse_of_process": True,
        "fair_trial_possible": False,
    }
}
SAMPLE_FRL_PAYLOAD = {
    "results": [
        {
            "id": "Act1",
            "title": "Sample Act",
            "sections": [
                {
                    "number": "1",
                    "title": "Definitions",
                    "body": '"Dog" means a domesticated animal.',
                },
                {
                    "number": "2",
                    "title": "Care",
                    "body": "A person must care for their dog. See section 1.",
                },
            ],
        }
    ]
}
SAMPLE_GRAPH_CASES = {
    "Case#Mabo1992": {
        "title": "Mabo v Queensland (No 2)",
        "court": "HCA",
        "consent_required": False,
    },
    "Case#Wik1996": {
        "title": "Wik Peoples v Queensland",
        "court": "HCA",
        "consent_required": False,
    },
    "Case#Ward2002": {
        "title": "Western Australia v Ward",
        "court": "HCA",
        "consent_required": True,
        "cultural_flags": ["sacred_information"],
    },
}
SAMPLE_GRAPH_EDGES = [
    (
        "Case#Mabo1992",
        "Case#Wik1996",
        "followed",
        3.0,
    ),
    (
        "Case#Mabo1992",
        "Case#Ward2002",
        "distinguished",
        1.0,
    ),
    (
        "Case#Wik1996",
        "Case#Ward2002",
        "followed",
        2.0,
    ),
]
SAMPLE_CASE_TREATMENT_METADATA = {
    "followed": {"court": "HCA"},
    "distinguished": {"court": "FCA"},
}
DEFAULT_DB_NAME = "sensiblaw_documents.sqlite"


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _write_bytes(path: Path, data: bytes) -> Path:
    _ensure_parent(path)
    path.write_bytes(data)
    return path


def _json_default(value: Any) -> Any:
    """Provide JSON-serialisation fallbacks for complex objects."""

    if isinstance(value, Enum):
        return value.value
    if isinstance(value, date):
        return value.isoformat()
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serialisable")


def _download_json(
    label: str, payload: Any, filename: str, *, key: Optional[str] = None
) -> None:
    st.download_button(
        label,
        json.dumps(payload, indent=2, ensure_ascii=False, default=_json_default),
        file_name=filename,
        mime="application/json",
        key=key,
    )


def _normalise_anchor_key(value: Optional[str]) -> Optional[str]:
    """Return a slug suitable for anchor lookup."""

    if not value:
        return None
    slug = re.sub(r"[^0-9a-zA-Z]+", "-", value).strip("-").lower()
    return slug or None


def _collect_provisions(
    provisions: List[Provision],
) -> Tuple[List[Tuple[Provision, str]], Dict[str, str]]:
    """Assign anchor IDs to provisions and build lookup keys."""

    anchors: List[Tuple[Provision, str]] = []
    anchor_lookup: Dict[str, str] = {}
    used_anchors: Set[str] = set()

    def register(key: Optional[str], anchor: str) -> None:
        normalised = _normalise_anchor_key(key)
        if normalised and normalised not in anchor_lookup:
            anchor_lookup[normalised] = anchor

    counter = 0

    def ensure_unique(slug: str) -> str:
        candidate = slug
        suffix = 2
        while candidate in used_anchors:
            candidate = f"{slug}-{suffix}"
            suffix += 1
        used_anchors.add(candidate)
        return candidate

    def derive_anchor(node: Provision, fallback: str) -> str:
        candidates = [
            node.stable_id,
            node.identifier,
            node.heading,
            f"{node.identifier}-{node.heading}"
            if node.identifier and node.heading
            else None,
        ]
        for candidate in candidates:
            slug = _normalise_anchor_key(candidate) if candidate else None
            if slug:
                return ensure_unique(slug)
        return ensure_unique(fallback)

    def walk(node: Provision) -> None:
        nonlocal counter
        counter += 1
        fallback = f"segment-{counter}"
        anchor = derive_anchor(node, fallback)
        anchors.append((node, anchor))
        register(node.identifier, anchor)
        register(node.heading, anchor)
        register(node.stable_id, anchor)
        if node.toc_id is not None:
            register(str(node.toc_id), anchor)
            register(f"toc-{node.toc_id}", anchor)
        if node.identifier and node.heading:
            register(f"{node.identifier} {node.heading}", anchor)
        for child in node.children:
            walk(child)

    for provision in provisions:
        walk(provision)
    return anchors, anchor_lookup


@dataclass
class _AtomAnnotation:
    """Internal representation of a highlight span for a provision."""

    identifier: str
    text: str
    label: str
    detail_json: str
    used: bool = False


def _format_atom_label(atom: Atom, index: int) -> str:
    """Return a human-readable label for an ``Atom``."""

    candidates = [atom.role, atom.type, atom.party]
    for candidate in candidates:
        if candidate:
            cleaned = str(candidate).strip()
            if cleaned:
                return cleaned.replace("_", " ")
    return f"Atom {index}"


def _build_atom_annotations(provision: Provision) -> List[_AtomAnnotation]:
    """Prepare highlight annotations for ``provision`` body text."""

    provision.ensure_rule_atoms()
    atoms = [
        (index, atom)
        for index, atom in enumerate(provision.flatten_rule_atoms(), start=1)
        if atom.text and atom.text.strip()
    ]
    if not atoms:
        return []

    # Highlight shorter fragments first to reduce overlap with broader spans.
    atoms.sort(key=lambda item: len(item[1].text.strip()))

    annotations: List[_AtomAnnotation] = []
    for display_index, (atom_index, atom) in enumerate(atoms, start=1):
        snippet = atom.text.strip()
        if not snippet:
            continue
        label_source = _format_atom_label(atom, atom_index)
        label = label_source
        detail_json = json.dumps(atom.to_dict(), indent=2, ensure_ascii=False)
        annotations.append(
            _AtomAnnotation(
                identifier=f"atom-span-{display_index}",
                text=snippet,
                label=label,
                detail_json=detail_json,
            )
        )
    return annotations


def _find_in_line(
    line: str,
    snippet: str,
    occupied: List[Tuple[int, int]],
    *,
    case_insensitive: bool = False,
) -> Optional[Tuple[int, int, str]]:
    """Locate ``snippet`` within ``line`` avoiding occupied ranges."""

    if not snippet:
        return None

    haystack = line.lower() if case_insensitive else line
    needle = snippet.lower() if case_insensitive else snippet
    start = 0
    while start <= len(haystack):
        index = haystack.find(needle, start)
        if index == -1:
            break
        end = index + len(needle)
        if all(end <= s or index >= e for s, e in occupied):
            return index, end, line[index:end]
        start = index + 1
    return None


def _highlight_line(line: str, annotations: List[_AtomAnnotation]) -> str:
    """Render ``line`` with inline ``Atom`` annotations."""

    if not line:
        return ""

    matches: List[Tuple[int, int, _AtomAnnotation, str]] = []
    occupied: List[Tuple[int, int]] = []
    for annotation in annotations:
        if annotation.used:
            continue
        snippet = annotation.text
        if not snippet:
            continue
        result = _find_in_line(line, snippet, occupied)
        if result is None:
            result = _find_in_line(line, snippet, occupied, case_insensitive=True)
        if result is None:
            continue
        start, end, matched_text = result
        annotation.used = True
        occupied.append((start, end))
        matches.append((start, end, annotation, matched_text))

    if not matches:
        return escape(line)

    matches.sort(key=lambda item: item[0])
    cursor = 0
    parts: List[str] = []
    for start, end, annotation, matched_text in matches:
        if start > cursor:
            parts.append(escape(line[cursor:start]))
        label_attr = escape(annotation.label, quote=True)
        detail_attr = escape(annotation.detail_json, quote=True)
        highlight_text = escape(matched_text)
        parts.append(
            "<mark class='atom-span' tabindex='0' role='button' "
            f"aria-label='{label_attr}' title='{label_attr}' "
            f"data-atom-id='{annotation.identifier}' "
            f"data-label='{label_attr}' data-detail='{detail_attr}'>{highlight_text}</mark>"
        )
        cursor = end
    if cursor < len(line):
        parts.append(escape(line[cursor:]))
    return "".join(parts)


def _render_toc(entries: List[DocumentTOCEntry], lookup: Dict[str, str]) -> str:
    """Render nested table-of-contents entries as HTML."""

    if not entries:
        return "<p class='toc-empty'>No table of contents entries detected.</p>"

    def render_nodes(nodes: List[DocumentTOCEntry], depth: int = 0) -> str:
        items: List[str] = []
        for entry in nodes:
            label_parts: List[str] = []
            if entry.identifier:
                label_parts.append(escape(entry.identifier))
            if entry.title:
                label_parts.append(escape(entry.title))
            label = " ".join(label_parts) or escape(entry.node_type or "Entry")
            anchor: Optional[str] = None
            for key in (
                entry.identifier,
                entry.title,
                f"{entry.identifier} {entry.title}"
                if entry.identifier and entry.title
                else None,
                f"toc-{entry.identifier}" if entry.identifier else None,
            ):
                normalised = _normalise_anchor_key(key) if key else None
                if normalised and normalised in lookup:
                    anchor = lookup[normalised]
                    break
            child_html = (
                render_nodes(entry.children, depth + 1) if entry.children else ""
            )
            depth_attr = f" data-depth='{depth}' style='--toc-depth:{depth}'"
            if anchor:
                item = (
                    f"<li{depth_attr}><a href='#{anchor}'>{label}</a>{child_html}</li>"
                )
            else:
                item = f"<li{depth_attr}>{label}{child_html}</li>"
            items.append(item)
        return f"<ul>{''.join(items)}</ul>"

    return f"<nav class='toc-tree'>{render_nodes(entries)}</nav>"


def _atom_text_candidates(atom: Any) -> List[str]:
    """Return candidate text snippets that describe an atom."""

    candidates: List[str] = []
    text = getattr(atom, "text", None)
    if isinstance(text, str) and text.strip():
        candidates.append(text)

    subject = getattr(atom, "subject", None)
    subject_text = getattr(subject, "text", None) if subject else None
    if isinstance(subject_text, str) and subject_text.strip():
        candidates.append(subject_text)

    for element in getattr(atom, "elements", []) or []:
        element_text = getattr(element, "text", None)
        if isinstance(element_text, str) and element_text.strip():
            candidates.append(element_text)

    seen: Dict[str, None] = {}
    for value in candidates:
        normalised = value.strip()
        if normalised and normalised not in seen:
            seen[normalised] = None
    return list(seen.keys())


def _find_span_for_snippet(
    text: str, snippet: str, occupied: List[Tuple[int, int]]
) -> Optional[Tuple[int, int]]:
    """Locate ``snippet`` within ``text`` while avoiding duplicates."""

    snippet = snippet.strip()
    if not text or not snippet:
        return None

    parts = [re.escape(part) for part in snippet.split() if part]
    if not parts:
        return None

    pattern = re.compile(r"\\s+".join(parts), re.IGNORECASE)
    for match in pattern.finditer(text):
        start, end = match.span()
        if all(end <= s or start >= e for s, e in occupied):
            occupied.append((start, end))
            return start, end
    return None


def _locate_atom_span(
    text: str, atom: Any, occupied: List[Tuple[int, int]]
) -> Optional[Tuple[int, int]]:
    """Best-effort span lookup for an atom within provision text."""

    candidates = sorted(_atom_text_candidates(atom), key=len, reverse=True)
    for candidate in candidates:
        span = _find_span_for_snippet(text, candidate, occupied)
        if span is not None:
            return span
    return None


def _build_atom_anchor_id(
    provision_anchor: str, atom: Any, index: int
) -> Optional[str]:
    """Construct a stable anchor identifier for an atom badge."""

    candidates: List[str] = []
    stable_id = getattr(atom, "stable_id", None)
    if stable_id:
        candidates.append(str(stable_id))

    toc_id = getattr(atom, "toc_id", None)
    if toc_id is not None:
        candidates.append(f"{provision_anchor}-toc-{toc_id}-atom-{index}")

    candidates.append(f"{provision_anchor}-atom-{index}")

    for candidate in candidates:
        normalised = _normalise_anchor_key(candidate)
        if normalised:
            return f"atom-{normalised}"

    fallback = _normalise_anchor_key(f"{provision_anchor}-atom-{index}")
    if fallback:
        return f"atom-{fallback}"
    return None


def _render_atom_badges(provision: Provision, provision_anchor: str) -> str:
    """Render interactive rule atom badges for a provision."""

    if not provision.rule_atoms:
        return ""

    badges: List[str] = []
    occupied_spans: List[Tuple[int, int]] = []
    provision_text = provision.text

    for index, atom in enumerate(provision.rule_atoms, start=1):
        detail_dict = atom.to_dict()

        anchor_id = _build_atom_anchor_id(provision_anchor, atom, index)
        if anchor_id:
            detail_dict.setdefault("anchor", anchor_id)

        span = _locate_atom_span(provision_text, atom, occupied_spans)
        span_attrs: List[str] = []
        if span is not None:
            span_start, span_end = span
            detail_dict.setdefault("span_start", span_start)
            detail_dict.setdefault("span_end", span_end)
            span_attrs.append(f"data-span-start='{span_start}'")
            span_attrs.append(f"data-span-end='{span_end}'")

        detail_json = json.dumps(detail_dict, indent=2, ensure_ascii=False)
        detail_attr = escape(detail_json, quote=True)
        label_source = atom.atom_type or atom.role or f"Atom {index}"
        label = escape(label_source)
        badges.append(
            (
                "<span class='atom-badge' tabindex='0' role='button' "
                f"aria-label='{label}' title='{label}' data-label='{label}' "
                f"data-detail='{detail_attr}'>{label}</span>"
            )
        )

        attributes = [
            "class='atom-badge'",
            "tabindex='0'",
            f"data-label='{label}'",
            f"data-detail='{detail_attr}'",
        ]

        if anchor_id:
            attributes.append(f"id='{anchor_id}'")
            span_attrs.append(f"data-anchor-id='{anchor_id}'")

        attributes.extend(span_attrs)

        badges.append(f"<span {' '.join(attributes)}>{label}</span>")

    return (
        "<div class='atom-badges'><strong>Atoms:</strong> "
        + " ".join(badges)
        + "</div>"
    )


def _render_provision_section(provision: Provision, anchor: str) -> str:
    """Render a single provision, including text and atoms."""

    heading = escape(provision.heading) if provision.heading else "Provision"
    identifier = escape(provision.identifier) if provision.identifier else ""
    metadata_parts = []
    if identifier:
        metadata_parts.append(f"<span class='provision-identifier'>{identifier}</span>")
    if provision.toc_id is not None:
        metadata_parts.append(
            f"<span class='provision-toc'>TOC ID {escape(str(provision.toc_id))}</span>"
        )
    if provision.cultural_flags:
        flags = ", ".join(escape(flag) for flag in provision.cultural_flags)
        metadata_parts.append(f"<span class='provision-flags'>{flags}</span>")

    metadata_html = (
        "<div class='provision-meta'>" + " • ".join(metadata_parts) + "</div>"
        if metadata_parts
        else ""
    )

    annotations = _build_atom_annotations(provision)
    paragraphs: List[str] = []
    for raw_line in provision.text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        highlighted = _highlight_line(stripped, annotations)
        paragraphs.append(f"<p>{highlighted}</p>")
    stable_attr = (
        f" data-stable-id='{escape(provision.stable_id, quote=True)}'"
        if provision.stable_id
        else ""
    )
    section_id = f"section-{anchor}"
    heading_html = (
        f"<h4><span class='heading-anchor' id='{anchor}'>{heading}</span></h4>"
    )
    atom_html = _render_atom_badges(provision, anchor)
    return (
        f"<section class='provision-section' id='{section_id}' data-anchor='{anchor}'{stable_attr}>"
        f"{heading_html}{metadata_html}{''.join(paragraphs)}{atom_html}</section>"
    )


def build_document_preview_html(document: Document) -> str:
    """Generate HTML preview for a processed document."""

    provision_sections, lookup = _collect_provisions(document.provisions)
    toc_html = _render_toc(document.toc_entries, lookup)

    if provision_sections:
        sections_html = "".join(
            _render_provision_section(provision, anchor)
            for provision, anchor in provision_sections
        )
    else:
        sections_html = "<p class='no-provisions'>No provisions were extracted.</p>"

    stylesheet = """
<style>
.document-preview {
    font-family: var(--font, "Source Sans Pro", sans-serif);
    display: flex;
    flex-direction: column;
    gap: 1rem;
}
.document-preview .document-columns {
    display: grid;
    grid-template-columns: minmax(200px, 260px) 1fr minmax(220px, 280px);
    gap: 1.5rem;
    align-items: start;
}
.document-preview nav.toc-tree ul {
    list-style: none;
    margin: 0;
    padding-left: 0;
}
.document-preview nav.toc-tree li {
    margin-bottom: 0.35rem;
}
.document-preview nav.toc-tree li[data-depth] > a {
    display: inline-flex;
    align-items: center;
    padding-left: calc(var(--toc-depth, 0) * 0.75rem);
    position: relative;
}
.document-preview nav.toc-tree li[data-depth='0'] > a {
    font-weight: 600;
}
.document-preview nav.toc-tree a {
    color: #11567f;
    text-decoration: none;
}
.document-preview nav.toc-tree a.active {
    font-weight: 600;
    color: #0b3a56;
    position: relative;
}
.document-preview nav.toc-tree a.active::before {
    content: '';
    position: absolute;
    left: -0.5rem;
    top: 50%;
    transform: translateY(-50%);
    width: 0.25rem;
    height: 0.25rem;
    border-radius: 50%;
    background-color: currentColor;
}
.document-preview nav.toc-tree a:hover,
.document-preview nav.toc-tree a:focus {
    text-decoration: underline;
}
.document-preview nav.toc-tree a.active {
    font-weight: 600;
    color: #0b3f63;
}
.document-preview .heading-anchor {
    display: inline-block;
    scroll-margin-top: 0.75rem;
}
.document-preview .content-column {
    max-height: 720px;
    overflow-y: auto;
    padding-right: 0.5rem;
    scroll-behavior: smooth;
}
.document-preview .provision-section {
    padding: 0.75rem 1rem;
    margin-bottom: 1rem;
    border: 1px solid #d9d9d9;
    border-radius: 0.5rem;
    background-color: #fff;
}
.document-preview .provision-section h4 {
    margin-top: 0;
    margin-bottom: 0.25rem;
}
.document-preview .provision-meta {
    font-size: 0.85rem;
    color: #555;
    margin-bottom: 0.75rem;
}
.document-preview .provision-meta span {
    background-color: #f2f6fa;
    padding: 0.1rem 0.35rem;
    border-radius: 999px;
}
.document-preview .atom-badges {
    margin-top: 0.75rem;
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    align-items: center;
}
.document-preview .atom-badge {
    display: inline-flex;
    align-items: center;
    padding: 0.2rem 0.55rem;
    border-radius: 999px;
    background-color: #ffe6c7;
    color: #8a4f0f;
    font-size: 0.85rem;
    cursor: pointer;
    border: 1px solid rgba(138, 79, 15, 0.2);
}
.document-preview .atom-badge[data-active='true'] {
    background-color: #ffd59a;
    border-color: #ff9d2e;
    color: #5a3608;
    box-shadow: 0 0 0 2px rgba(255, 157, 46, 0.25);
}
.document-preview .atom-badge:focus {
    outline: 2px solid #ff9d2e;
    outline-offset: 2px;
}
.document-preview .atom-badge:hover {
    background-color: #ffd59a;
}
.document-preview .atom-span {
    background-color: #fff3bf;
    padding: 0 0.15rem;
    border-radius: 0.25rem;
    cursor: pointer;
    color: inherit;
    transition: background-color 0.2s ease, box-shadow 0.2s ease;
}
.document-preview .atom-span:hover,
.document-preview .atom-span:focus {
    background-color: #ffe066;
    box-shadow: 0 0 0 2px rgba(255, 157, 46, 0.35);
    outline: none;
}
.document-preview .atom-span[data-active='true'] {
    background-color: #ffd43b;
    box-shadow: 0 0 0 2px rgba(255, 157, 46, 0.5);
}
.document-preview .detail-column {
    border: 1px solid #d9d9d9;
    border-radius: 0.5rem;
    padding: 0.75rem 1rem;
    background: #f4f7fb;
    max-height: 720px;
    overflow-y: auto;
}
.document-preview .detail-column pre {
    background: #fff;
    border: 1px solid #ececec;
    border-radius: 0.5rem;
    padding: 0.5rem 0.75rem;
    white-space: pre-wrap;
    word-break: break-word;
}
.document-preview .detail-column .detail-placeholder {
    margin: 0;
    color: #4b5563;
}
.document-preview .rule-card {
    background: #fff;
    border: 1px solid #e5e7eb;
    border-radius: 0.75rem;
    padding: 1rem 1.25rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
}
.document-preview .rule-card__title {
    margin: 0;
    font-size: 1.05rem;
    color: #0f172a;
}
.document-preview .rule-card__meta {
    margin: 0;
    font-size: 0.8rem;
    color: #6b7280;
}
.document-preview .rule-card__sentence {
    margin: 0;
    padding: 0.75rem 0.9rem;
    border-left: 4px solid #2563eb;
    background: #eff6ff;
    border-radius: 0.5rem;
    font-weight: 600;
    color: #1e3a8a;
}
.document-preview .rule-card__fields {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 0.35rem 0.9rem;
    margin: 0;
}
.document-preview .rule-card__fields dt {
    font-weight: 600;
    color: #374151;
}
.document-preview .rule-card__fields dd {
    margin: 0;
    color: #1f2937;
}
.document-preview .rule-card__section {
    border-top: 1px solid #e5e7eb;
    padding-top: 0.75rem;
    margin-top: 0.25rem;
}
.document-preview .rule-card__section h4 {
    margin: 0 0 0.4rem 0;
    font-size: 0.95rem;
    color: #0f172a;
}
.document-preview .rule-card__list {
    margin: 0;
    padding-left: 1.1rem;
    color: #1f2937;
}
.document-preview .rule-card__list li {
    margin-bottom: 0.25rem;
}
.document-preview .rule-card__tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
}
.document-preview .rule-card__tag {
    display: inline-flex;
    align-items: center;
    padding: 0.2rem 0.6rem;
    border-radius: 999px;
    background: #e0e7ff;
    color: #3730a3;
    font-size: 0.75rem;
}
.document-preview .rule-card__subsection {
    margin-bottom: 0.75rem;
}
.document-preview .rule-card__subsection:last-child {
    margin-bottom: 0;
}
.document-preview .rule-card__empty {
    margin: 0;
    color: #6b7280;
    font-style: italic;
}
.document-preview .toc-empty,
.document-preview .no-provisions {
    font-style: italic;
    color: #555;
}
@media (max-width: 1024px) {
    .document-preview .document-columns {
        grid-template-columns: 1fr;
    }
    .document-preview .content-column,
    .document-preview .detail-column {
        max-height: none;
    }
}
</style>
"""

    script = """
<script>
(function() {
    const previewRoot = document.querySelector('.document-preview');
    if (!previewRoot) {
        return;
    }

    const contentColumn = previewRoot.querySelector('.content-column');
    const headingAnchors = contentColumn
        ? Array.from(contentColumn.querySelectorAll('.heading-anchor'))
        : [];
    const tocLinks = Array.from(
        previewRoot.querySelectorAll('nav.toc-tree a[href^="#"]')
    );
    const tocLinkById = new Map();
    let activeAnchorId = null;

    function setActiveLink(anchorId) {
        if (activeAnchorId === anchorId) {
            return;
        }
        if (activeAnchorId) {
            const previous = tocLinkById.get(activeAnchorId);
            if (previous) {
                previous.classList.remove('active');
            }
        }
        activeAnchorId = anchorId || null;
        if (!anchorId) {
            return;
        }
        const next = tocLinkById.get(anchorId);
        if (next) {
            next.classList.add('active');
        }
    }

    function scrollToAnchor(anchorId) {
        if (!contentColumn) {
            return;
        }
        const target = document.getElementById(anchorId);
        if (!target) {
            return;
        }
        const containerRect = contentColumn.getBoundingClientRect();
        const targetRect = target.getBoundingClientRect();
        const offset = targetRect.top - containerRect.top + contentColumn.scrollTop - 8;
        contentColumn.scrollTo({
            top: Math.max(offset, 0),
            behavior: 'smooth'
        });
    }

    function updateActiveFromScroll() {
        if (!contentColumn || !headingAnchors.length) {
            return;
        }
        const containerRect = contentColumn.getBoundingClientRect();
        let candidate = null;
        for (const anchor of headingAnchors) {
            const delta = anchor.getBoundingClientRect().top - containerRect.top;
            if (delta >= -16) {
                candidate = anchor.id;
                break;
            }
        }
        if (!candidate && headingAnchors.length) {
            const last = headingAnchors[headingAnchors.length - 1];
            if (last.getBoundingClientRect().top <= containerRect.bottom) {
                candidate = last.id;
            }
        }
        if (candidate) {
            setActiveLink(candidate);
        }
    }

    tocLinks.forEach(function(link) {
        const href = link.getAttribute('href');
        if (!href || !href.startsWith('#')) {
            return;
        }
        const anchorId = href.slice(1);
        tocLinkById.set(anchorId, link);
        link.addEventListener('click', function(event) {
            if (!contentColumn) {
                return;
            }
            event.preventDefault();
            scrollToAnchor(anchorId);
            setActiveLink(anchorId);
        });
    });

    if (contentColumn) {
        const handleScroll = function() {
            window.requestAnimationFrame(updateActiveFromScroll);
        };
        contentColumn.addEventListener('scroll', handleScroll);
        updateActiveFromScroll();
    }

    const initialHash = window.location.hash ? window.location.hash.slice(1) : '';
    if (initialHash && tocLinkById.has(initialHash)) {
        setTimeout(function() {
            scrollToAnchor(initialHash);
            setActiveLink(initialHash);
        }, 0);
    } else if (headingAnchors.length) {
        setActiveLink(headingAnchors[0].id);
    }

    const badges = Array.from(document.querySelectorAll('.atom-badge'));
    const spans = Array.from(document.querySelectorAll('.atom-span'));
    const detailColumn = document.getElementById('atom-detail-panel');
    const tocLinks = Array.from(
        document.querySelectorAll('.toc-tree a[href^="#"]')
    );
    const contentColumn = document.querySelector('.content-column');

    if (!detailColumn) {
        return;
    }
    function createFieldList(fieldDefs, source) {
        const dl = document.createElement('dl');
        dl.className = 'rule-card__fields';
        fieldDefs.forEach(([key, display]) => {
            const value = source ? source[key] : undefined;
            if (value === null || value === undefined) {
                return;
            }
            let textValue;
            if (Array.isArray(value)) {
                textValue = value
                    .map((entry) => {
                        if (entry === null || entry === undefined) {
                            return '';
                        }
                        if (typeof entry === 'object') {
                            return '';
                        }
                        return String(entry).trim();
                    })
                    .filter(Boolean)
                    .join(', ');
            } else if (typeof value === 'object') {
                return;
            } else {
                textValue = String(value).trim();
            }
            if (!textValue) {
                return;
            }
            const dt = document.createElement('dt');
            dt.textContent = display;
            const dd = document.createElement('dd');
            dd.textContent = textValue;
            dl.appendChild(dt);
            dl.appendChild(dd);
        });
        return dl.childElementCount ? dl : null;
    }

    function createMetadataTags(metadata) {
        if (!metadata || typeof metadata !== 'object') {
            return null;
        }
        const entries = Object.entries(metadata).filter(([, value]) => value !== null && value !== undefined && value !== '');
        if (!entries.length) {
            return null;
        }
        const container = document.createElement('div');
        container.className = 'rule-card__tags';
        entries.forEach(([key, value]) => {
            const span = document.createElement('span');
            span.className = 'rule-card__tag';
            if (Array.isArray(value)) {
                const filtered = value
                    .filter((item) => item !== null && item !== undefined && item !== '')
                    .map((item) => String(item));
                span.textContent = filtered.length ? `${key}: ${filtered.join(', ')}` : key;
            } else if (typeof value === 'object') {
                span.textContent = `${key}`;
            } else if (value === true) {
                span.textContent = key;
            } else {
                span.textContent = `${key}: ${value}`;
            }
            container.appendChild(span);
        });
        return container;
    }

    function renderDetail(label, detailText) {
        let parsed = detailText;
        if (typeof detailText === 'string' && detailText.trim() !== '') {
            try {
                parsed = JSON.parse(detailText);
            } catch (error) {
                parsed = detailText;
            }
        }
        detailColumn.innerHTML = '';
        const title = document.createElement('h3');
        title.textContent = label || 'Atom details';
        detailColumn.appendChild(title);
        if (parsed === null || parsed === undefined || parsed === '') {
            const paragraph = document.createElement('p');
            paragraph.textContent = 'No structured details available.';
            detailColumn.appendChild(paragraph);
            return;
        }
        if (typeof parsed === 'string') {
        const panelHeading = document.createElement('h3');
        panelHeading.textContent = 'Atom details';
        detailColumn.appendChild(panelHeading);
        if (typeof parsed === 'string' || !parsed || typeof parsed !== 'object') {
            const paragraph = document.createElement('p');
            paragraph.className = 'rule-card__empty';
            paragraph.textContent = typeof parsed === 'string' ? parsed : 'No additional details available.';
            detailColumn.appendChild(paragraph);
            return;
        }

        const card = document.createElement('article');
        card.className = 'rule-card';

        const title = document.createElement('h3');
        title.className = 'rule-card__title';
        title.textContent = label || 'Selected atom';
        card.appendChild(title);

        const metaParts = [];
        if (parsed.toc_id !== null && parsed.toc_id !== undefined) {
            metaParts.push(`TOC ${parsed.toc_id}`);
        }
        if (parsed.stable_id) {
            metaParts.push(`#${parsed.stable_id}`);
        }
        if (parsed.atom_type && parsed.atom_type !== 'rule') {
            metaParts.push(String(parsed.atom_type));
        }
        if (metaParts.length) {
            const meta = document.createElement('p');
            meta.className = 'rule-card__meta';
            meta.textContent = metaParts.join(' • ');
            card.appendChild(meta);
        }

        const sentenceText = parsed.text || (parsed.subject && parsed.subject.text) || '';
        if (sentenceText) {
            const sentence = document.createElement('p');
            sentence.className = 'rule-card__sentence';
            sentence.textContent = sentenceText;
            card.appendChild(sentence);
        }

        const primaryFields = [
            ['party', 'Party'],
            ['role', 'Role'],
            ['actor', 'Actor'],
            ['modality', 'Modality'],
            ['action', 'Action'],
            ['conditions', 'Conditions'],
            ['scope', 'Scope'],
            ['who', 'Who'],
            ['who_text', 'Who text'],
            ['subject_gloss', 'Subject gloss'],
        ];
        const fieldList = createFieldList(primaryFields, parsed);
        if (fieldList) {
            card.appendChild(fieldList);
        }

        const subjectSection = parsed.subject && typeof parsed.subject === 'object'
            ? createFieldList(
                  [
                      ['type', 'Type'],
                      ['role', 'Role'],
                      ['party', 'Party'],
                      ['who', 'Who'],
                      ['who_text', 'Who text'],
                      ['conditions', 'Conditions'],
                      ['text', 'Text'],
                      ['gloss', 'Gloss'],
                  ],
                  parsed.subject,
              )
            : null;
        if (subjectSection) {
            const section = document.createElement('section');
            section.className = 'rule-card__section';
            const heading = document.createElement('h4');
            heading.textContent = 'Subject';
            section.appendChild(heading);
            section.appendChild(subjectSection);
            if (parsed.subject && parsed.subject.gloss_metadata) {
                const tags = createMetadataTags(parsed.subject.gloss_metadata);
                if (tags) {
                    section.appendChild(tags);
                }
            }
            card.appendChild(section);
        }

        if (parsed.subject_gloss_metadata) {
            const tags = createMetadataTags(parsed.subject_gloss_metadata);
            if (tags) {
                const section = document.createElement('section');
                section.className = 'rule-card__section';
                const heading = document.createElement('h4');
                heading.textContent = 'Subject metadata';
                section.appendChild(heading);
                section.appendChild(tags);
                card.appendChild(section);
            }
        }

        if (Array.isArray(parsed.elements) && parsed.elements.length) {
            const section = document.createElement('section');
            section.className = 'rule-card__section';
            const heading = document.createElement('h4');
            heading.textContent = 'Elements';
            section.appendChild(heading);
            parsed.elements.forEach((element, index) => {
                if (!element || typeof element !== 'object') {
                    return;
                }
                const elementFields = createFieldList(
                    [
                        ['role', 'Role'],
                        ['text', 'Text'],
                        ['conditions', 'Conditions'],
                        ['gloss', 'Gloss'],
                    ],
                    element,
                );
                if (!elementFields) {
                    return;
                }
                const wrapper = document.createElement('div');
                wrapper.className = 'rule-card__subsection';
                if (parsed.elements.length > 1) {
                    const subheading = document.createElement('h5');
                    subheading.textContent = `Element ${index + 1}`;
                    subheading.style.margin = '0 0 0.3rem 0';
                    subheading.style.fontSize = '0.85rem';
                    subheading.style.color = '#1f2937';
                    wrapper.appendChild(subheading);
                }
                wrapper.appendChild(elementFields);
                if (element.gloss_metadata) {
                    const tags = createMetadataTags(element.gloss_metadata);
                    if (tags) {
                        wrapper.appendChild(tags);
                    }
                }
                if (Array.isArray(element.references) && element.references.length) {
                    const refList = document.createElement('ul');
                    refList.className = 'rule-card__list';
                    element.references.forEach((ref) => {
                        if (!ref || typeof ref !== 'object') {
                            return;
                        }
                        const parts = [];
                        if (ref.work) parts.push(ref.work);
                        if (ref.section) parts.push(`s ${ref.section}`);
                        if (ref.pinpoint) parts.push(ref.pinpoint);
                        if (ref.citation_text) parts.push(ref.citation_text);
                        if (!parts.length) {
                            return;
                        }
                        const li = document.createElement('li');
                        li.textContent = parts.join(', ');
                        refList.appendChild(li);
                    });
                    if (refList.childElementCount) {
                        const refsHeading = document.createElement('h6');
                        refsHeading.textContent = 'References';
                        refsHeading.style.margin = '0.5rem 0 0.2rem 0';
                        refsHeading.style.fontSize = '0.75rem';
                        refsHeading.style.textTransform = 'uppercase';
                        refsHeading.style.letterSpacing = '0.05em';
                        refsHeading.style.color = '#6b7280';
                        wrapper.appendChild(refsHeading);
                        wrapper.appendChild(refList);
                    }
                }
                section.appendChild(wrapper);
            });
            card.appendChild(section);
        }

        if (Array.isArray(parsed.references) && parsed.references.length) {
            const section = document.createElement('section');
            section.className = 'rule-card__section';
            const heading = document.createElement('h4');
            heading.textContent = 'References';
            section.appendChild(heading);
            const list = document.createElement('ul');
            list.className = 'rule-card__list';
            parsed.references.forEach((ref) => {
                if (!ref || typeof ref !== 'object') {
                    return;
                }
                const parts = [];
                if (ref.work) parts.push(ref.work);
                if (ref.section) parts.push(`s ${ref.section}`);
                if (ref.pinpoint) parts.push(ref.pinpoint);
                if (ref.citation_text) parts.push(ref.citation_text);
                if (!parts.length) {
                    return;
                }
                const li = document.createElement('li');
                li.textContent = parts.join(', ');
                list.appendChild(li);
            });
            if (list.childElementCount) {
                section.appendChild(list);
                card.appendChild(section);
            }
        }

        if (Array.isArray(parsed.lints) && parsed.lints.length) {
            const section = document.createElement('section');
            section.className = 'rule-card__section';
            const heading = document.createElement('h4');
            heading.textContent = 'Extraction notes';
            section.appendChild(heading);
            const list = document.createElement('ul');
            list.className = 'rule-card__list';
            parsed.lints.forEach((lint) => {
                if (!lint || typeof lint !== 'object') {
                    return;
                }
                const parts = [];
                if (lint.code) parts.push(lint.code);
                if (lint.message) parts.push(lint.message);
                const li = document.createElement('li');
                li.textContent = parts.join(' — ');
                list.appendChild(li);
            });
            if (list.childElementCount) {
                section.appendChild(list);
                card.appendChild(section);
            }
        }

        if (!card.childElementCount) {
            const placeholder = document.createElement('p');
            placeholder.className = 'rule-card__empty';
            placeholder.textContent = 'No additional details available.';
            detailColumn.appendChild(placeholder);
            return;
        }

        detailColumn.appendChild(card);
    }
    function setActive(label) {
        const allTargets = badges.concat(spans);
        allTargets.forEach(function(node) {
            if (label && node.getAttribute('data-label') === label) {
                node.setAttribute('data-active', 'true');
            } else {
                node.removeAttribute('data-active');
            }
        });
    }
    function activate(element) {
        if (!element) {
            return;
        }
        const label = element.getAttribute('data-label');
        const detail = element.getAttribute('data-detail');
        setActive(label);
        renderDetail(label, detail);
    }
    const initial = badges[0] || spans[0] || null;
    if (initial) {
        activate(initial);
    }
    function attachInteractiveHandlers(element) {
        element.addEventListener('click', function(event) {
            event.preventDefault();
            activate(element);
        });
        element.addEventListener('keypress', function(event) {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                activate(element);
            }
        });
    }
    badges.forEach(function(badge) {
        attachInteractiveHandlers(badge);
    });
    spans.forEach(function(span) {
        attachInteractiveHandlers(span);
        span.addEventListener('mouseenter', function() {
            activate(span);
        });
        span.addEventListener('focus', function() {
            activate(span);
        });
    });

    if (!tocLinks.length || !contentColumn) {
        return;
    }

    const linkById = new Map();
    tocLinks.forEach(function(link) {
        const targetId = link.getAttribute('href').slice(1);
        if (targetId) {
            linkById.set(targetId, link);
        }
    });

    const observedSections = Array.from(linkById.keys())
        .map(function(id) {
            return document.getElementById(id);
        })
        .filter(function(section) {
            return section instanceof HTMLElement;
        });

    if (!observedSections.length) {
        return;
    }

    let activeLink = null;
    const visibleSections = new Map();

    function setActiveLink(link) {
        if (activeLink === link) {
            return;
        }
        if (activeLink) {
            activeLink.classList.remove('active');
        }
        activeLink = link;
        if (activeLink) {
            activeLink.classList.add('active');
        }
    }

    const observer = new IntersectionObserver(
        function(entries) {
            entries.forEach(function(entry) {
                const id = entry.target.getAttribute('id');
                if (!id) {
                    return;
                }
                if (entry.isIntersecting) {
                    visibleSections.set(id, entry.intersectionRatio);
                } else {
                    visibleSections.delete(id);
                }
            });

            let bestId = null;
            let bestRatio = 0;
            visibleSections.forEach(function(ratio, id) {
                if (ratio > bestRatio) {
                    bestRatio = ratio;
                    bestId = id;
                }
            });

            if (!bestId && observedSections.length) {
                bestId = observedSections[0].getAttribute('id');
            }

            if (!bestId) {
                setActiveLink(null);
                return;
            }

            const link = linkById.get(bestId);
            if (link) {
                setActiveLink(link);
            }
        },
        {
            root: contentColumn,
            threshold: [0.1, 0.25, 0.5, 0.75],
            rootMargin: '0px 0px -40% 0px'
        }
    );

    observedSections.forEach(function(section) {
        observer.observe(section);
    });

    const firstLink = linkById.get(observedSections[0].getAttribute('id'));
    if (firstLink) {
        setActiveLink(firstLink);
    }
})();
</script>
"""

    return (
        f"{stylesheet}"
        "<div class='document-preview'>"
        "<div class='document-columns'>"
        "<div class='toc-column'>"
        "<h3>Table of contents</h3>"
        f"{toc_html}"
        "</div>"
        "<div class='content-column'>"
        f"{sections_html}"
        "</div>"
        "<div class='detail-column' id='atom-detail-panel'>"
        "<h3>Atom details</h3>"
        "<p class='detail-placeholder'>Select an atom badge to explore the structured rule.</p>"
        "</div>"
        "</div>"
        "</div>"
        f"{script}"
    )


def render_document_preview(document: Document) -> None:
    """Render a cleaned, hyperlinked preview for ``document``."""

    html_content = build_document_preview_html(document)
    components.html(html_content, height=900, scrolling=True)


def _render_table(records: Iterable[Dict[str, Any]], *, key: str) -> None:
    rows = list(records)
    if not rows:
        st.info("No data available for the current selection.")
        return
    if pd is not None:
        frame = pd.DataFrame(rows)
        st.dataframe(frame, use_container_width=True)
    else:  # pragma: no cover - pandas optional
        st.write(rows)
    _download_json(f"Download {key}", rows, f"{key}.json")


def _render_dot(dot: Optional[str], *, key: str) -> None:
    if not dot:
        return
    try:
        st.graphviz_chart(dot)
    except Exception as exc:  # pragma: no cover - graphviz optional
        st.warning(
            f"Graphviz rendering is unavailable ({exc}). Download the DOT file instead."
        )
    st.download_button(
        f"Download {key} DOT",
        dot,
        file_name=f"{key}.dot",
        mime="text/vnd.graphviz",
    )


def _build_knowledge_graph_dot(payload: Dict[str, Any]) -> Optional[str]:
    """Construct a Graphviz representation of a knowledge graph payload."""

    if Digraph is None:
        return None

    graph = Digraph("knowledge_graph", format="svg")
    graph.attr("graph", rankdir="LR", bgcolor="white")
    graph.attr("node", shape="ellipse", style="filled", fillcolor="white")

    node_type_styles = {
        "case": {"shape": "box", "fillcolor": "#E8F1FF"},
        "provision": {"shape": "oval", "fillcolor": "#F4F0FF"},
        "concept": {"shape": "hexagon", "fillcolor": "#FFF4E5"},
        "person": {"shape": "diamond", "fillcolor": "#EAF9F0"},
        "document": {"shape": "note", "fillcolor": "#FFFBEA"},
    }

    nodes = payload.get("nodes", []) or []
    edges = payload.get("edges", []) or []

    def _enum_value(value: Any) -> str:
        if hasattr(value, "value"):
            return str(value.value)
        if isinstance(value, str):
            return value.split(".")[-1].lower()
        return str(value)

    for node in nodes:
        identifier = node.get("identifier")
        if not identifier:
            continue

        node_type = _enum_value(node.get("type", ""))
        metadata = node.get("metadata") or {}
        title = metadata.get("title") or metadata.get("name") or identifier
        subtitle_parts = []
        for key in ("court", "year", "citation"):
            value = metadata.get(key)
            if value:
                subtitle_parts.append(str(value))
        if node.get("date") and not metadata.get("year"):
            subtitle_parts.append(str(node["date"]))
        if metadata.get("role"):
            subtitle_parts.append(str(metadata["role"]))

        label = title
        if subtitle_parts:
            label = f"{title}\n" + " | ".join(subtitle_parts)

        node_attrs = node_type_styles.get(node_type, {})
        if node.get("consent_required"):
            node_attrs = {
                **node_attrs,
                "fillcolor": "#FFE8E5",
                "style": "filled,dashed",
            }

        if metadata.get("cultural_flags") or node.get("cultural_flags"):
            node_attrs = {**node_attrs, "color": "#C94C4C", "penwidth": "2"}

        graph.node(identifier, label=label, **node_attrs)

    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        if not source or not target:
            continue

        edge_type = _enum_value(edge.get("type", ""))
        label = edge_type.replace("_", " ").title() if edge_type else ""
        weight = edge.get("weight")
        if isinstance(weight, (int, float)) and weight != 1:
            label = f"{label} ({weight:g})" if label else f"{weight:g}"

        color = "#1D4ED8"
        if edge_type in {"distinguishes", "rejects", "overrules"}:
            color = "#B91C1C"
        elif edge_type in {"follows", "applies", "considers"}:
            color = "#047857"

        edge_attrs: Dict[str, Any] = {"color": color}
        if label:
            edge_attrs["label"] = label

        graph.edge(source, target, **edge_attrs)

    return graph.source


def _seed_sample_graph() -> None:
    """Populate the FastAPI routes graph with demonstration data."""

    if ROUTES_GRAPH.nodes:
        return

    for identifier, meta in SAMPLE_GRAPH_CASES.items():
        ROUTES_GRAPH.add_node(
            GraphNode(
                type=NodeType.CASE,
                identifier=identifier,
                metadata={"title": meta["title"]},
                cultural_flags=meta.get("cultural_flags"),
                consent_required=meta.get("consent_required", False),
            )
        )

    for source, target, relation, weight in SAMPLE_GRAPH_EDGES:
        metadata = {
            "relation": relation,
            "court": SAMPLE_CASE_TREATMENT_METADATA.get(relation, {}).get(
                "court", "HCA"
            ),
        }
        edge = GraphEdge(
            type=EdgeType.CITES,
            source=source,
            target=target,
            metadata=metadata,
            weight=weight,
        )
        # Duplicate edges raise a ValueError; guard with try/except for idempotence.
        try:
            ROUTES_GRAPH.add_edge(edge)
        except ValueError:
            continue


# ---------------------------------------------------------------------------
# Streamlit page configuration
# ---------------------------------------------------------------------------

st.set_page_config(page_title="SensibLaw Console", layout="wide")
st.title("SensibLaw Operations Console")
st.caption(
    "Interact with SensibLaw services for document processing, concept mapping,"
    " knowledge graph exploration, and more."
)

# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


def render_documents_tab() -> None:
    st.subheader("Documents")
    st.write(
        "Ingest PDFs, persist revisions via the versioned store, and inspect historical snapshots."
    )

    default_store = st.session_state.get(
        "document_store_path",
        str(ROOT / "ui" / DEFAULT_DB_NAME),
    )
    store_path_input = st.text_input(
        "SQLite store path",
        value=default_store,
        help="Document revisions are persisted to this SQLite database.",
    )
    st.session_state["document_store_path"] = store_path_input
    db_path = Path(store_path_input).expanduser()
    _ensure_parent(db_path)

    with st.form("pdf_ingest_form"):
        st.markdown("### PDF ingestion")
        sample_pdf = None
        pdf_files = list(ROOT.glob("*.pdf"))
        if pdf_files:
            sample_pdf = st.selectbox(
                "Sample PDF", ["-- None --"] + [p.name for p in pdf_files], index=0
            )
        uploaded_pdf = st.file_uploader(
            "Upload PDF for processing", type=["pdf"], key="pdf_uploader"
        )
        jurisdiction = st.text_input("Jurisdiction", value="High Court of Australia")
        citation = st.text_input("Citation", value="[1992] HCA 23")
        cultural_flags = st.text_input("Cultural flags (comma separated)", value="")
        ingest = st.form_submit_button("Process PDF")

    if ingest:
        buffer = None
        source_name = None
        if uploaded_pdf is not None:
            buffer = uploaded_pdf.getvalue()
            source_name = uploaded_pdf.name
        elif sample_pdf and sample_pdf != "-- None --":
            buffer = (ROOT / sample_pdf).read_bytes()
            source_name = sample_pdf
        else:
            st.error("Please upload a PDF or choose a sample file.")

        if buffer:
            st.info(f"Processing {source_name} …")
            with st.spinner("Extracting text and rules"):
                tmp_dir = Path(tempfile.mkdtemp(prefix="sensiblaw_pdf_"))
                pdf_path = _write_bytes(
                    tmp_dir / (source_name or "document.pdf"), buffer
                )
                flags = [f.strip() for f in cultural_flags.split(",") if f.strip()]
                document, stored_id = process_pdf(
                    pdf_path,
                    jurisdiction=jurisdiction or None,
                    citation=citation or None,
                    cultural_flags=flags or None,
                    db_path=db_path,
                )
            st.success("PDF processed successfully.")
            st.markdown("### Document preview")
            render_document_preview(document)
            doc_payload = document.to_dict()
            if stored_id is not None:
                st.info(f"Stored as document ID {stored_id} in {db_path}")
                doc_payload["doc_id"] = stored_id
            st.session_state["last_document_payload"] = doc_payload
            st.session_state["expand_last_document"] = True

    last_document = st.session_state.get("last_document_payload")
    if last_document:
        expanded = st.session_state.pop("expand_last_document", False)
        with st.expander("Most recent document metadata and rules", expanded=expanded):
            st.json(last_document)
        _download_json(
            "Download document JSON",
            last_document,
            "document.json",
            key="download_document_json",
        )

    st.markdown("### Stored documents")
    document_rows: List[dict[str, Any]] = []
    load_error: Optional[str] = None
    store: Optional[VersionedStore] = None
    try:
        store = VersionedStore(db_path)
        document_rows = store.list_latest_documents()
    except Exception as exc:  # pragma: no cover - defensive UI feedback
        load_error = str(exc)
    finally:
        if store is not None:
            store.close()

    if load_error:
        st.error(f"Unable to load documents from the store: {load_error}")
    elif not document_rows:
        st.info("No documents have been ingested into the selected store yet.")
    else:
        summary_rows: List[dict[str, Any]] = []
        option_lookup: Dict[str, dict[str, Any]] = {}
        for entry in document_rows:
            metadata = entry["metadata"]
            label = f"{entry['doc_id']} · rev {entry['rev_id']} · {metadata.citation}"
            option_lookup[label] = entry
            summary_rows.append(
                {
                    "Document ID": entry["doc_id"],
                    "Revision": entry["rev_id"],
                    "Effective date": entry["effective_date"].isoformat(),
                    "Document date": metadata.date.isoformat(),
                    "Citation": metadata.citation,
                    "Jurisdiction": metadata.jurisdiction,
                }
            )

        if pd is not None:
            frame = pd.DataFrame(summary_rows).set_index("Document ID")
            st.dataframe(frame, use_container_width=True)
        else:  # pragma: no cover - pandas optional
            st.write(summary_rows)

        selection = st.selectbox(
            "Inspect stored document",
            ["-- Select document --"] + list(option_lookup.keys()),
            key="stored_document_selector",
        )
        if selection and selection != "-- Select document --":
            selected_entry = option_lookup[selection]
            metadata_dict = selected_entry["metadata"].to_dict()
            with st.expander(
                f"Document {selected_entry['doc_id']} metadata", expanded=True
            ):
                st.json(metadata_dict)
            _download_json(
                "Download metadata JSON",
                metadata_dict,
                f"document_{selected_entry['doc_id']}_metadata.json",
                key=f"download_metadata_{selected_entry['doc_id']}_{selected_entry['rev_id']}",
            )

            view_latest = st.button(
                "View latest revision",
                key=f"view_document_{selected_entry['doc_id']}",
            )
            if view_latest:
                with st.spinner("Loading document"):
                    latest_store = VersionedStore(db_path)
                    try:
                        latest = latest_store.snapshot(
                            int(selected_entry["doc_id"]),
                            selected_entry["effective_date"],
                        )
                    finally:
                        latest_store.close()
                if latest is None:
                    st.warning("No revision found for the selected document.")
                elif isinstance(latest, Document):
                    render_document_preview(latest)
                else:
                    st.json(latest)

    st.markdown("### Snapshot lookup")
    with st.form("snapshot_form"):
        doc_id = st.number_input("Document ID", min_value=1, step=1, value=1)
        as_at = st.date_input("Snapshot date", value=date.today())
        fetch = st.form_submit_button("Fetch snapshot")

    if fetch:
        with st.spinner("Loading document snapshot"):
            store = VersionedStore(db_path)
            try:
                snapshot = store.snapshot(int(doc_id), as_at)
            finally:
                store.close()
        if snapshot is None:
            st.warning("No revision found for the supplied ID and date.")
        else:
            payload = snapshot.to_dict() if isinstance(snapshot, Document) else snapshot
            with st.expander("Snapshot contents", expanded=True):
                st.json(payload)
            _download_json("Download snapshot JSON", payload, "snapshot.json")


# ---------------------------------------------------------------------------
# Text & Concepts
# ---------------------------------------------------------------------------


def render_text_concepts_tab() -> None:
    st.subheader("Text & Concepts")
    st.write(
        "Normalise text, surface concept matches, extract rules, and inspect ontology tagging outputs."
    )

    sample_story_path = ROOT / "examples" / "distinguish_glj" / "story.txt"
    sample_text = (
        sample_story_path.read_text(encoding="utf-8")
        if sample_story_path.exists()
        else ""
    )
    default_text = st.session_state.get("concept_input", sample_text)
    text = st.text_area("Input text", value=default_text, height=240)
    st.session_state["concept_input"] = text
    include_dot = st.checkbox("Include DOT exports", value=True)

    if st.button("Analyse text"):
        if not text.strip():
            st.error("Enter some text to analyse.")
            return
        with st.spinner("Running pipeline components"):
            normalised = normalise(text)
            concepts = match_concepts(normalised)
            cloud = build_cloud(concepts)
            advanced_notice: Optional[str] = None
            advanced: Dict[str, Any] = {}
            if ROUTES_GRAPH.nodes and concepts:
                hits: List[Tuple[str, Dict[str, Any]]] = [
                    (concept_id, {"keyword_exact": True}) for concept_id in concepts
                ]
                try:
                    advanced = advanced_cloud(hits, ROUTES_GRAPH)
                except Exception as exc:  # pragma: no cover - defensive UI feedback
                    advanced_notice = f"Unable to build advanced concept cloud: {exc}"
            elif not ROUTES_GRAPH.nodes:
                advanced_notice = "Load the knowledge graph data to enable advanced concept visualisations."
            rules = [r.__dict__ for r in extract_rules(text)]
            provision_payload = api_provision(text, dot=include_dot)
            concept_payload = api_subgraph(text, dot=include_dot)
            rule_payload = api_treatment(text, dot=include_dot)

        st.markdown("#### Normalised text")
        st.code(normalised)
        st.markdown("#### Concept matches")
        st.write(concepts)
        st.markdown("#### Concept cloud")
        if cloud:
            display = (
                pd.DataFrame(
                    {"concept": list(cloud.keys()), "count": list(cloud.values())}
                )
                if pd is not None
                else None
            )
            if display is not None:
                display = display.sort_values("count", ascending=False).set_index(
                    "concept"
                )
                st.bar_chart(display)
                st.dataframe(display, use_container_width=True)
            else:  # pragma: no cover - pandas optional
                st.write(cloud)
        else:
            st.info("No concepts matched the provided text.")
        _download_json("Download concept cloud", cloud, "concept_cloud.json")

        if include_dot:
            _render_dot(concept_payload.get("dot"), key="concept_cloud")

        st.markdown("#### Advanced cloud (concepts.cloud)")
        if advanced:
            st.write(advanced)
        elif advanced_notice:
            st.info(advanced_notice)
        else:
            st.info(
                "No advanced concept relationships available for the supplied text."
            )

        st.markdown("#### Extracted rules")
        _render_table(rules, key="rules")
        if include_dot:
            _render_dot(rule_payload.get("dot"), key="rules")

        st.markdown("#### Provision tagging")
        provision = provision_payload.get("provision", {})
        st.json(provision)
        if include_dot:
            _render_dot(provision_payload.get("dot"), key="provision")


# ---------------------------------------------------------------------------
# Knowledge Graph
# ---------------------------------------------------------------------------


def render_knowledge_graph_tab() -> None:
    st.subheader("Knowledge Graph")
    st.write(
        "Generate subgraphs, execute legal tests, inspect case treatments, and fetch provision atoms."
    )

    if st.button(
        "Load sample graph data", help="Populate the in-memory graph with demo cases"
    ):
        _seed_sample_graph()
        st.success("Sample graph seeded.")

    if not ROUTES_GRAPH.nodes:
        st.info(
            "The in-memory graph is empty. Load the sample dataset above or ingest"
            " your own nodes before running queries."
        )

    st.markdown("### Generate subgraph")
    with st.form("subgraph_form"):
        if ROUTES_GRAPH.nodes:
            seed_default = next(iter(ROUTES_GRAPH.nodes.keys()))
        else:
            seed_default = "Case#Mabo1992"
        seed = st.text_input("Seed node", value=seed_default)
        hops = st.slider("Maximum hops", min_value=1, max_value=5, value=2)
        consent = st.checkbox("Include consent gated nodes", value=False)
        submit = st.form_submit_button("Generate")

    if submit:
        try:
            with st.spinner("Generating subgraph"):
                payload = generate_subgraph(seed, hops, consent=consent)
        except HTTPException as exc:
            st.error(f"{exc.detail} (HTTP {exc.status_code})")
        else:
            st.success("Subgraph generated.")
            dot = _build_knowledge_graph_dot(payload)
            if dot:
                _render_dot(dot, key="knowledge_subgraph")
            else:
                st.info(
                    "Graphviz is not available. Install the optional dependency to see"
                    " the visualisation."
                )
            st.json(payload)
            _download_json("Download subgraph", payload, "subgraph.json")

    st.markdown("### Execute legal tests")
    template_ids = list(TEMPLATE_REGISTRY.keys())
    with st.form("tests_form"):
        selected_ids = st.multiselect(
            "Test templates", template_ids, default=template_ids[:1]
        )
        default_story = json.dumps(
            {"facts": {fid: True for fid in ("delay",)}}, indent=2
        )
        story_json = st.text_area(
            "Story facts JSON",
            value=st.session_state.get("story_json", default_story),
            height=160,
        )
        st.session_state["story_json"] = story_json
        tests_submit = st.form_submit_button("Run tests")

    if tests_submit:
        try:
            story_payload = json.loads(story_json or "{}")
        except json.JSONDecodeError as exc:
            st.error(f"Invalid JSON: {exc}")
        else:
            facts = story_payload.get("facts", story_payload)
            with st.spinner("Evaluating templates"):
                try:
                    result = execute_tests(selected_ids, facts)
                except HTTPException as exc:
                    st.error(f"{exc.detail} (HTTP {exc.status_code})")
                else:
                    st.json(result)
                    _download_json("Download test results", result, "tests.json")

    st.markdown("### Case treatment summary")
    with st.form("treatment_form"):
        case_id = st.text_input("Case identifier", value="Case#Mabo1992")
        treatment_submit = st.form_submit_button("Fetch treatment")

    if treatment_submit:
        try:
            with st.spinner("Fetching treatment"):
                data = fetch_case_treatment(case_id)
        except HTTPException as exc:
            st.error(f"{exc.detail} (HTTP {exc.status_code})")
        else:
            st.json(data)
            _render_table(data.get("treatments", []), key="treatments")

    st.markdown("### Provision atoms")
    with st.form("provision_form"):
        provision_id = st.text_input(
            "Provision identifier",
            value="Provision#NTA:s223",
        )
        provision_submit = st.form_submit_button("Fetch provision atoms")

    if provision_submit:
        try:
            with st.spinner("Retrieving provision atoms"):
                provision = fetch_provision_atoms(provision_id)
        except HTTPException as exc:
            st.error(f"{exc.detail} (HTTP {exc.status_code})")
        else:
            st.json(provision)
            _download_json(
                "Download provision atoms", provision, "provision_atoms.json"
            )


# ---------------------------------------------------------------------------
# Case Comparison
# ---------------------------------------------------------------------------


def render_case_comparison_tab() -> None:
    st.subheader("Case Comparison")
    st.write(
        "Load a base silhouette and compare story fact tags to highlight overlaps and gaps."
    )

    case_label = st.selectbox("Base case", list(SAMPLE_CASES.keys()))
    citation = SAMPLE_CASES[case_label]

    sample_story_json = json.dumps(SAMPLE_STORY_FACTS, indent=2)
    uploaded_story = st.file_uploader(
        "Upload story JSON (expects a {'facts': {...}} mapping)",
        type=["json"],
        key="story_upload",
    )
    if uploaded_story is not None:
        story_text = uploaded_story.read().decode("utf-8")
    else:
        story_text = st.text_area(
            "Story facts JSON",
            value=st.session_state.get("comparison_story", sample_story_json),
            height=200,
        )
    st.session_state["comparison_story"] = story_text

    if st.button("Compare story to case"):
        try:
            payload = json.loads(story_text or "{}")
        except json.JSONDecodeError as exc:
            st.error(f"Invalid JSON: {exc}")
            return
        story_tags = payload.get("facts", payload)
        with st.spinner("Loading silhouette and computing comparison"):
            try:
                silhouette = load_case_silhouette(citation)
            except Exception as exc:  # pragma: no cover - loader raises KeyError
                st.error(str(exc))
                return
            comparison = compare_story_to_case(story_tags, silhouette)
        st.success("Comparison complete.")
        st.json(comparison)
        _download_json("Download comparison", comparison, "case_comparison.json")

        overlaps = [
            {
                "id": item.get("id"),
                "paragraph": item.get("candidate", {}).get("paragraph"),
                "anchor": item.get("candidate", {}).get("anchor"),
            }
            for item in comparison.get("overlaps", [])
        ]
        missing = [
            {
                "id": item.get("id"),
                "anchor": item.get("candidate", {}).get("anchor"),
            }
            for item in comparison.get("missing", [])
        ]
        st.markdown("#### Overlaps")
        _render_table(overlaps, key="overlaps")
        st.markdown("#### Missing")
        _render_table(missing, key="missing")


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def render_utilities_tab() -> None:
    st.subheader("Utilities")
    st.write(
        "Quick access to glossary lookups, frame compilation, receipts, similarity fingerprints, FRL ingestion, rule checks, and harm scores."
    )

    st.markdown("### Glossary lookup")
    with st.form("glossary_form"):
        term = st.text_input("Term", value="permanent stay")
        lookup_submit = st.form_submit_button("Lookup")
    if lookup_submit:
        entry = glossary_lookup(term)
        if entry is None:
            st.warning("No glossary entry found.")
        else:
            st.json(
                {"phrase": entry.phrase, "text": entry.text, "metadata": entry.metadata}
            )

    st.markdown("### Frame compiler")
    with st.form("frame_form"):
        frame_source = st.text_area(
            "Frame definition", "actor must consider community impacts"
        )
        frame_submit = st.form_submit_button("Compile frame")
    if frame_submit:
        compiled = compile_frame(frame_source)
        st.code(compiled)

    st.markdown("### Receipts")
    with st.form("receipt_form"):
        receipt_input = st.text_area(
            "Receipt payload (JSON)",
            value=json.dumps({"actor": "court", "action": "issued order"}, indent=2),
            height=160,
        )
        receipt_submit = st.form_submit_button("Build & verify")
    if receipt_submit:
        try:
            payload = json.loads(receipt_input or "{}")
        except json.JSONDecodeError as exc:
            st.error(f"Invalid JSON: {exc}")
        else:
            built = build_receipt(payload)
            valid = verify_receipt(built)
            st.json({"receipt": built, "verified": valid})
            _download_json("Download receipt", built, "receipt.json")

    st.markdown("### Text similarity")
    with st.form("simhash_form"):
        simhash_text = st.text_area(
            "Text", "Sample text for simhash fingerprint", height=120
        )
        simhash_submit = st.form_submit_button("Compute simhash")
    if simhash_submit:
        fingerprint = simhash(simhash_text)
        st.code(fingerprint)

    st.markdown("### FRL ingestion")
    with st.form("frl_form"):
        frl_json = st.text_area(
            "FRL payload (JSON)",
            value=json.dumps(SAMPLE_FRL_PAYLOAD, indent=2),
            height=220,
        )
        frl_submit = st.form_submit_button("Build graph from payload")
    if frl_submit:
        try:
            data = json.loads(frl_json or "{}")
        except json.JSONDecodeError as exc:
            st.error(f"Invalid JSON: {exc}")
        else:
            with st.spinner("Constructing graph"):
                nodes, edges = fetch_acts("http://example.com", data=data)
            st.json({"nodes": nodes, "edges": edges})
            _download_json("Download FRL nodes", nodes, "frl_nodes.json")
            _download_json("Download FRL edges", edges, "frl_edges.json")

    st.markdown("### Rule consistency")
    with st.form("rules_form"):
        rules_json = st.text_area(
            "Rules (JSON list)",
            value=json.dumps(
                [
                    {"actor": "court", "modality": "must", "action": "hear the matter"},
                    {
                        "actor": "court",
                        "modality": "must not",
                        "action": "hear the matter",
                    },
                ],
                indent=2,
            ),
            height=200,
        )
        rules_submit = st.form_submit_button("Check rules")
    if rules_submit:
        try:
            rule_payload = json.loads(rules_json or "[]")
        except json.JSONDecodeError as exc:
            st.error(f"Invalid JSON: {exc}")
        else:
            rules = [Rule(**item) for item in rule_payload]
            issues = check_rules(rules)
            st.json({"issues": issues})

    st.markdown("### Harm scoring")
    with st.form("harm_form"):
        harm_story = st.text_area(
            "Story metrics (JSON)",
            value=json.dumps(
                {
                    "lost_evidence_items": 2,
                    "delay_months": 18,
                    "flags": ["vulnerable_witness"],
                },
                indent=2,
            ),
            height=200,
        )
        harm_submit = st.form_submit_button("Compute harm score")
    if harm_submit:
        try:
            story = json.loads(harm_story or "{}")
        except json.JSONDecodeError as exc:
            st.error(f"Invalid JSON: {exc}")
        else:
            score = compute_harm(story)
            st.json(score)
            _download_json("Download harm score", score, "harm_score.json")


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------


def main() -> None:
    documents_tab, text_tab, graph_tab, comparison_tab, utilities_tab = st.tabs(
        [
            "Documents",
            "Text & Concepts",
            "Knowledge Graph",
            "Case Comparison",
            "Utilities",
        ]
    )

    with documents_tab:
        render_documents_tab()
    with text_tab:
        render_text_concepts_tab()
    with graph_tab:
        render_knowledge_graph_tab()
    with comparison_tab:
        render_case_comparison_tab()
    with utilities_tab:
        render_utilities_tab()


if __name__ == "__main__":  # pragma: no cover - streamlit executes main
    main()
