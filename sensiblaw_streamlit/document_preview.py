"""Document preview helpers for the SensibLaw Streamlit console."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from html import escape
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import streamlit.components.v1 as components

from src.models.document import Document, DocumentTOCEntry
from src.models.provision import Atom, Provision, RuleAtom


_TOC_TRAILING_PAGE_REF_RE = re.compile(r"(?:\s*(?:Page\b)?\s*\d+)\s*$", re.IGNORECASE)
_TOC_TRAILING_PAGE_WORD_RE = re.compile(r"\bPage\b\s*$", re.IGNORECASE)
_TOC_TRAILING_DOT_BLOCK_RE = re.compile(r"(?:[.·⋅•●∙]\s*)+$")

_TOC_NODE_PREFIXES = {
    "part": "Part",
    "division": "Division",
    "subdivision": "Subdivision",
    "section": "Section",
    "subsection": "Subsection",
    "paragraph": "Paragraph",
}


def _clean_toc_text(value: Optional[str]) -> Optional[str]:
    if not value:
        return None

    cleaned = re.sub(r"\s+", " ", value).strip()
    if not cleaned:
        return None

    page_artifacts = any(ch in ".·⋅•●∙" for ch in value) or "page" in value.lower()
    if page_artifacts:
        cleaned = _TOC_TRAILING_PAGE_REF_RE.sub("", cleaned)
    cleaned = _TOC_TRAILING_PAGE_WORD_RE.sub("", cleaned)
    cleaned = _TOC_TRAILING_DOT_BLOCK_RE.sub("", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or None


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
        # Prefer stable identifiers to keep anchors predictable across renders.
        for candidate in (
            node.stable_id,
            node.identifier,
            node.heading,
        ):
            normalised = _normalise_anchor_key(candidate)
            if normalised:
                return ensure_unique(normalised)
        # Prefer stable identifiers when available so anchors remain stable across
        # renders. Fall back to identifiers or headings before using the positional
        # segment identifier.
        candidates: List[Optional[str]] = [
            node.stable_id,
            node.identifier,
            node.heading,
        ]
        for candidate in candidates:
            slug = _normalise_anchor_key(candidate)
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


def _format_toc_identifier(entry: DocumentTOCEntry) -> Optional[str]:
    identifier = entry.identifier.strip() if entry.identifier else None
    node_type = entry.node_type.strip().lower() if entry.node_type else None
    prefix = _TOC_NODE_PREFIXES.get(node_type) if node_type else None

    if prefix and identifier:
        return f"{prefix} {identifier}"
    if identifier:
        return identifier
    if prefix:
        return prefix
    return None


def _format_toc_label(entry: DocumentTOCEntry) -> str:
    parts: List[str] = []
    identifier = _format_toc_identifier(entry)
    title = _clean_toc_text(entry.title)
    if identifier:
        parts.append(escape(identifier))
    if title:
        parts.append(escape(title))
    if not parts:
        fallback = entry.node_type or "Entry"
        parts.append(escape(fallback))
    return " ".join(parts)


def _format_toc_page(entry: DocumentTOCEntry) -> Optional[str]:
    if entry.page_number is None:
        return None
    return f"p. {entry.page_number}"


@dataclass
class _AtomAnnotation:
    """Internal representation of a highlight span for a provision."""

    identifier: str
    text: str
    label: str
    detail_json: str
    kind: str = "atom"
    used: bool = False


@dataclass
class DocumentActorSummary:
    """Aggregate view of actors referenced across rule atoms."""

    actor: str
    occurrences: int
    modalities: List[str]
    actions: List[str]
    sections: List[str]
    aliases: List[str]


@dataclass
class _ActorAccumulator:
    """Internal accumulator capturing actor level aggregates."""

    canonical: str
    occurrences: int = 0
    forms: Counter[str] = field(default_factory=Counter)
    modalities: Set[str] = field(default_factory=set)
    actions: Set[str] = field(default_factory=set)
    sections: List[str] = field(default_factory=list)


def _normalise_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _extract_actor_label(rule_atom: RuleAtom) -> Optional[str]:
    """Return the best available label describing the rule actor."""

    for attr in ("actor", "party", "who_text", "who"):
        raw = getattr(rule_atom, attr, None)
        if isinstance(raw, str):
            cleaned = _normalise_whitespace(raw)
            if cleaned:
                return cleaned
    return None


def _format_provision_reference(provision: Provision) -> Optional[str]:
    """Build a short reference string for the provision context."""

    parts: List[str] = []
    if provision.identifier and provision.identifier.strip():
        parts.append(_normalise_whitespace(provision.identifier))
    if provision.heading and provision.heading.strip():
        parts.append(_normalise_whitespace(provision.heading))
    if parts:
        return " – ".join(parts)
    if provision.node_type:
        return provision.node_type
    return None


def _iter_provision_tree(provisions: Iterable[Provision]) -> Iterable[Provision]:
    """Yield all provisions in a depth-first traversal order."""

    stack: List[Provision] = list(provisions)[::-1]
    while stack:
        node = stack.pop()
        yield node
        if node.children:
            stack.extend(reversed(node.children))


def collect_document_actor_summary(
    document: Document,
    *,
    max_section_samples: int = 5,
    max_action_samples: int = 5,
) -> List[DocumentActorSummary]:
    """Collate actor references across the document's rule atoms."""

    actors: Dict[str, _ActorAccumulator] = {}

    for provision in _iter_provision_tree(document.provisions):
        provision.ensure_rule_atoms()
        section_label = _format_provision_reference(provision)
        for rule_atom in provision.rule_atoms:
            actor_label = _extract_actor_label(rule_atom)
            if not actor_label:
                continue
            key = actor_label.casefold()
            accumulator = actors.get(key)
            if accumulator is None:
                accumulator = _ActorAccumulator(canonical=actor_label)
                actors[key] = accumulator

            accumulator.occurrences += 1
            accumulator.forms[actor_label] += 1

            if rule_atom.modality and rule_atom.modality.strip():
                accumulator.modalities.add(_normalise_whitespace(rule_atom.modality))

            if rule_atom.action and rule_atom.action.strip():
                if len(accumulator.actions) < max_action_samples:
                    accumulator.actions.add(_normalise_whitespace(rule_atom.action))

            if (
                section_label
                and section_label not in accumulator.sections
                and len(accumulator.sections) < max_section_samples
            ):
                accumulator.sections.append(section_label)

    summaries: List[DocumentActorSummary] = []
    for accumulator in actors.values():
        canonical = accumulator.canonical
        if accumulator.forms:
            canonical = accumulator.forms.most_common(1)[0][0]
        aliases = sorted(form for form in accumulator.forms.keys() if form != canonical)
        summaries.append(
            DocumentActorSummary(
                actor=canonical,
                occurrences=accumulator.occurrences,
                modalities=sorted(accumulator.modalities),
                actions=sorted(accumulator.actions),
                sections=list(accumulator.sections),
                aliases=aliases,
            )
        )

    summaries.sort(key=lambda item: (-item.occurrences, item.actor))
    return summaries


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
    annotations: List[_AtomAnnotation] = []

    if atoms:
        # Highlight shorter fragments first to reduce overlap with broader spans.
        atoms.sort(key=lambda item: len(item[1].text.strip()))
        next_display_index = 1
        for atom_index, atom in atoms:
            snippet = atom.text.strip()
            if not snippet:
                continue
            label_source = _format_atom_label(atom, atom_index)
            detail_json = json.dumps(atom.to_dict(), indent=2, ensure_ascii=False)
            annotations.append(
                _AtomAnnotation(
                    identifier=f"atom-span-{next_display_index}",
                    text=snippet,
                    label=label_source,
                    detail_json=detail_json,
                    kind=(atom.type or "atom"),
                )
            )
            next_display_index += 1
    else:
        next_display_index = 1

    seen_citations: set[Tuple[str, Optional[str], Optional[str]]] = set()

    for rule_index, rule_atom in enumerate(provision.rule_atoms, start=1):
        source_id = rule_atom.stable_id or f"rule-{rule_index}"
        for ref in rule_atom.references:
            snippet = (ref.citation_text or ref.to_legacy_text()).strip()
            if not snippet:
                continue
            key = (snippet.lower(), source_id, None)
            if key in seen_citations:
                continue
            seen_citations.add(key)
            detail_payload = {
                "atom_type": "citation",
                "text": snippet,
                "references": [ref.to_dict()],
                "source_rule": source_id,
            }
            annotations.append(
                _AtomAnnotation(
                    identifier=f"atom-span-{next_display_index}",
                    text=snippet,
                    label=f"Citation: {snippet}",
                    detail_json=json.dumps(
                        detail_payload, indent=2, ensure_ascii=False
                    ),
                    kind="citation",
                )
            )
            next_display_index += 1

        for element_index, element in enumerate(rule_atom.elements, start=1):
            element_refs = getattr(element, "references", []) or []
            element_label = element.role or f"element-{element_index}"
            for ref in element_refs:
                snippet = (ref.citation_text or ref.to_legacy_text()).strip()
                if not snippet:
                    continue
                key = (snippet.lower(), source_id, element_label)
                if key in seen_citations:
                    continue
                seen_citations.add(key)
                detail_payload = {
                    "atom_type": "citation",
                    "text": snippet,
                    "references": [ref.to_dict()],
                    "source_rule": source_id,
                    "source_element": element_label,
                }
                annotations.append(
                    _AtomAnnotation(
                        identifier=f"atom-span-{next_display_index}",
                        text=snippet,
                        label=f"Citation: {snippet}",
                        detail_json=json.dumps(
                            detail_payload, indent=2, ensure_ascii=False
                        ),
                        kind="citation",
                    )
                )
                next_display_index += 1

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


_DOT_LEADER_PATTERN = re.compile(r"(?:\s*[.\u00b7]\s*){4,}")


def _normalise_provision_line(line: str) -> str:
    """Collapse noisy leader dots that pollute rendered provisions."""

    if not line:
        return ""

    cleaned = _DOT_LEADER_PATTERN.sub(" ", line)
    return cleaned.strip()


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
        kind_attr = escape(annotation.kind, quote=True)
        highlight_text = escape(matched_text)
        identifier_attr = escape(annotation.identifier, quote=True)
        parts.append(
            "<mark class='atom-span' tabindex='0' role='button' "
            f"id='{identifier_attr}' "
            f"aria-label='{label_attr}' title='{label_attr}' "
            f"data-atom-id='{identifier_attr}' "
            f"data-label='{label_attr}' data-kind='{kind_attr}' "
            f"data-detail='{detail_attr}' "
            f"data-highlight-id='{identifier_attr}'>{highlight_text}</mark>"
        )
        cursor = end
    if cursor < len(line):
        parts.append(escape(line[cursor:]))
    return "".join(parts)


def _render_toc(
    entries: List[DocumentTOCEntry],
    lookup: Dict[str, str],
    provision_by_anchor: Optional[Dict[str, Provision]] = None,
) -> str:
    """Render nested table-of-contents entries as HTML."""

    if not entries:
        return "<p class='toc-empty'>No table of contents entries detected.</p>"

    resolved_anchors: Dict[int, Optional[str]] = {}

    def resolve_anchor(entry: DocumentTOCEntry) -> Optional[str]:
        """Locate the best provision anchor for ``entry``."""

        entry_key = id(entry)
        if entry_key in resolved_anchors:
            return resolved_anchors[entry_key]

        identifier = entry.identifier.strip() if entry.identifier else None
        title = _clean_toc_text(entry.title)
        formatted_identifier = _format_toc_identifier(entry)

        candidates: List[str] = []

        if identifier:
            candidates.append(identifier)
            candidates.append(f"toc-{identifier}")

        if title:
            candidates.append(title)

        if formatted_identifier:
            candidates.append(formatted_identifier)

        if identifier and title:
            candidates.append(f"{identifier} {title}")

        if formatted_identifier and title:
            candidates.append(f"{formatted_identifier} {title}")

        if title:
            split_match = re.match(r"^([A-Za-z0-9().-]+)\s+(.*)$", title)
            if split_match:
                remainder = split_match.group(2)
                if remainder:
                    candidates.append(remainder)
                    if identifier:
                        candidates.append(f"{identifier} {remainder}")
                    if formatted_identifier:
                        candidates.append(f"{formatted_identifier} {remainder}")

            for separator in (" - ", " – ", " — "):
                if separator in title:
                    left, right = title.split(separator, 1)
                    if left.strip():
                        candidates.append(left.strip())
                    if right.strip():
                        candidates.append(right.strip())

        seen: Set[str] = set()
        anchor: Optional[str] = None
        for candidate in candidates:
            normalised = _normalise_anchor_key(candidate)
            if not normalised or normalised in seen:
                continue
            seen.add(normalised)
            if normalised in lookup:
                anchor = lookup[normalised]
                break

        if not anchor:
            for child in entry.children:
                anchor = resolve_anchor(child)
                if anchor:
                    break

        resolved_anchors[entry_key] = anchor
        return anchor

    def render_nodes(nodes: List[DocumentTOCEntry], depth: int = 0) -> str:
        items: List[str] = []
        for entry in nodes:
            label = _format_toc_label(entry)
            anchor = resolve_anchor(entry)
            page_text = _format_toc_page(entry)
            page_html = (
                f"<span class='toc-page'>{escape(page_text)}</span>"
                if page_text
                else ""
            )
            child_html = (
                render_nodes(entry.children, depth + 1) if entry.children else ""
            )
            depth_attr = f" data-depth='{depth}' style='--toc-depth:{depth}'"
            type_attr = (
                f" data-node-type='{escape(entry.node_type, quote=True)}'"
                if entry.node_type
                else ""
            )
            page_attr = (
                f" data-page='{escape(str(entry.page_number), quote=True)}'"
                if entry.page_number is not None
                else ""
            )
            if anchor:
                stable_attr = ""
                if provision_by_anchor:
                    provision = provision_by_anchor.get(anchor)
                    stable_id = getattr(provision, "stable_id", None)
                    if stable_id:
                        stable_attr = (
                            f" data-stable-id='{escape(stable_id, quote=True)}'"
                            f" title='Stable ID: {escape(stable_id)}'"
                        )
                link_html = (
                    f"<a class='toc-entry' href='#{anchor}'{stable_attr}>"
                    f"<span class='toc-label'>{label}</span>{page_html}"
                    "</a>"
                )
                item = f"<li{depth_attr}{type_attr}{page_attr}>{link_html}{child_html}</li>"
            else:
                content = (
                    f"<span class='toc-entry'><span class='toc-label'>{label}</span>"
                    f"{page_html}</span>"
                )
                item = (
                    f"<li{depth_attr}{type_attr}{page_attr}>{content}{child_html}</li>"
                )
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


def _build_atom_highlight_lookup(
    provision: Provision, annotations: List[_AtomAnnotation]
) -> Dict[int, str]:
    """Map rule atom indices to highlight identifiers for scroll targets."""

    provision.ensure_rule_atoms()

    annotation_pool: Dict[str, List[_AtomAnnotation]] = {}
    for annotation in annotations:
        key = annotation.text.strip().lower()
        if not key:
            continue
        annotation_pool.setdefault(key, []).append(annotation)

    for candidates in annotation_pool.values():
        candidates.sort(key=lambda item: item.identifier)

    lookup: Dict[int, str] = {}
    for index, atom in enumerate(provision.rule_atoms, start=1):
        for candidate in _atom_text_candidates(atom):
            key = candidate.strip().lower()
            if not key:
                continue
            pool = annotation_pool.get(key)
            if not pool:
                continue
            annotation = pool.pop(0)
            lookup[index] = annotation.identifier
            break
    return lookup


def _render_atom_badges(
    provision: Provision,
    provision_anchor: str,
    highlight_lookup: Optional[Dict[int, str]] = None,
) -> str:
    """Render interactive rule atom badges for a provision."""

    if not provision.rule_atoms:
        return ""

    badges: List[str] = []
    occupied_spans: List[Tuple[int, int]] = []
    provision_text = provision.text or ""

    for index, atom in enumerate(provision.rule_atoms, start=1):
        detail_dict = atom.to_dict()
        anchor_id = _build_atom_anchor_id(provision_anchor, atom, index)
        if anchor_id:
            detail_dict.setdefault("anchor", anchor_id)

        span = _locate_atom_span(provision_text, atom, occupied_spans)
        if span is not None:
            span_start, span_end = span
            detail_dict.setdefault("span_start", span_start)
            detail_dict.setdefault("span_end", span_end)

        highlight_id = None
        if highlight_lookup is not None:
            highlight_id = highlight_lookup.get(index)
            if highlight_id:
                detail_dict.setdefault("highlight_id", highlight_id)

        label_text = atom.atom_type or _format_atom_label(atom, index)
        detail_json = json.dumps(detail_dict, indent=2, ensure_ascii=False)

        attributes: Dict[str, str] = {
            "class": "atom-badge",
            "tabindex": "0",
            "role": "button",
            "aria-label": label_text,
            "data-label": label_text,
            "data-detail": detail_json,
        }
        if anchor_id:
            attributes["id"] = anchor_id
        if highlight_id:
            attributes["data-highlight-id"] = highlight_id
        if span is not None:
            attributes["data-span-start"] = str(span_start)
            attributes["data-span-end"] = str(span_end)

        attr_html = " ".join(
            f"{key}='{escape(value, quote=True)}'" for key, value in attributes.items()
        )
        badges.append(f"<span {attr_html}>{escape(label_text)}</span>")

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
    highlight_lookup = _build_atom_highlight_lookup(provision, annotations)
    paragraphs: List[str] = []
    for raw_line in provision.text.splitlines():
        stripped = raw_line.strip()
        cleaned = _normalise_provision_line(stripped)
        if not cleaned:
            continue
        highlighted = _highlight_line(cleaned, annotations)
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
    atom_html = _render_atom_badges(provision, anchor, highlight_lookup)
    return (
        f"<section class='provision-section' id='{section_id}' data-anchor='{anchor}'{stable_attr}>"
        f"{heading_html}{metadata_html}{''.join(paragraphs)}{atom_html}</section>"
    )


def build_document_preview_html(document: Document) -> str:
    """Generate HTML preview for a processed document."""

    provision_sections, lookup = _collect_provisions(document.provisions)
    provision_by_anchor = {
        anchor: provision for provision, anchor in provision_sections
    }
    toc_html = _render_toc(document.toc_entries, lookup, provision_by_anchor)

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
.document-preview nav.toc-tree li[data-depth] > .toc-entry {
    display: inline-flex;
    align-items: center;
    padding-left: calc(var(--toc-depth, 0) * 0.75rem);
    position: relative;
}
.document-preview nav.toc-tree li[data-depth='0'] > .toc-entry {
    font-weight: 600;
}
.document-preview nav.toc-tree .toc-entry {
    gap: 0.35rem;
}
.document-preview nav.toc-tree .toc-entry .toc-label {
    flex: 1 1 auto;
    min-width: 0;
}
.document-preview nav.toc-tree .toc-entry .toc-page {
    flex: 0 0 auto;
    font-size: 0.75rem;
    color: #36546b;
    background-color: rgba(17, 86, 127, 0.12);
    border-radius: 999px;
    padding: 0.1rem 0.4rem;
}
.document-preview nav.toc-tree li[data-depth] > .toc-entry:not(a) {
    color: #11567f;
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
.document-preview .atom-span[data-kind='citation'] {
    background-color: #d3f9d8;
    color: #14532d;
}
.document-preview .atom-span:hover,
.document-preview .atom-span:focus {
    background-color: #ffe066;
    box-shadow: 0 0 0 2px rgba(255, 157, 46, 0.35);
    outline: none;
}
.document-preview .atom-span[data-kind='citation']:hover,
.document-preview .atom-span[data-kind='citation']:focus {
    background-color: #b2f2bb;
    box-shadow: 0 0 0 2px rgba(34, 197, 94, 0.35);
}
.document-preview .atom-span[data-active='true'] {
    background-color: #ffd43b;
    box-shadow: 0 0 0 2px rgba(255, 157, 46, 0.5);
}
.document-preview .atom-span[data-kind='citation'][data-active='true'] {
    background-color: #8ce99a;
    box-shadow: 0 0 0 2px rgba(21, 128, 61, 0.5);
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

    const badges = Array.from(previewRoot.querySelectorAll('.atom-badge'));
    const spans = Array.from(previewRoot.querySelectorAll('.atom-span'));
    const detailColumn = previewRoot.querySelector('#atom-detail-panel');

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
        const entries = Object.entries(metadata || {})
            .map(([key, value]) => {
                if (value === null || value === undefined) {
                    return null;
                }
                if (Array.isArray(value)) {
                    const filtered = value
                        .map((item) => {
                            if (item === null || item === undefined) {
                                return '';
                            }
                            return String(item).trim();
                        })
                        .filter(Boolean);
                    if (!filtered.length) {
                        return null;
                    }
                    return [key, filtered.join(', ')];
                }
                if (typeof value === 'object') {
                    return null;
                }
                const text = String(value).trim();
                return text ? [key, text] : null;
            })
            .filter(Boolean);
        if (!entries.length) {
            return null;
        }
        const list = document.createElement('ul');
        list.className = 'rule-card__tags';
        entries.forEach(([key, value]) => {
            const item = document.createElement('li');
            item.className = 'rule-card__tag';
            item.textContent = `${key}: ${value}`;
            list.appendChild(item);
        });
        return list.childElementCount ? list : null;
    }

    function renderDetail(label, detail) {
        if (!detailColumn) {
            return;
        }
        detailColumn.innerHTML = '';
        const heading = document.createElement('h3');
        heading.className = 'rule-card__title';
        heading.textContent = label || 'Atom detail';
        detailColumn.appendChild(heading);

        if (!detail) {
            const placeholder = document.createElement('p');
            placeholder.className = 'rule-card__empty';
            placeholder.textContent = 'No detail available for this atom.';
            detailColumn.appendChild(placeholder);
            return;
        }

        let parsed;
        try {
            parsed = JSON.parse(detail);
        } catch (error) {
            const pre = document.createElement('pre');
            pre.textContent = detail;
            detailColumn.appendChild(pre);
            return;
        }

        const card = document.createElement('article');
        card.className = 'rule-card';

        if (parsed.stable_id) {
            const badge = document.createElement('div');
            badge.className = 'rule-card__badge';
            badge.textContent = `Stable ID: ${parsed.stable_id}`;
            card.appendChild(badge);
        }

        if (parsed.text) {
            const paragraph = document.createElement('p');
            paragraph.className = 'rule-card__body';
            paragraph.textContent = parsed.text;
            card.appendChild(paragraph);
        }

        if (parsed.sentence) {
            const sentence = document.createElement('p');
            sentence.className = 'rule-card__sentence';
            sentence.textContent = parsed.sentence;
            card.appendChild(sentence);
        }

        const fields = createFieldList(
            [
                ['role', 'Role'],
                ['atom_type', 'Type'],
                ['party', 'Party'],
                ['evaluation', 'Evaluation'],
            ],
            parsed,
        );
        if (fields) {
            card.appendChild(fields);
        }

        if (parsed.gloss_metadata) {
            const tags = createMetadataTags(parsed.gloss_metadata);
            if (tags) {
                const section = document.createElement('section');
                section.className = 'rule-card__section';
                const heading = document.createElement('h4');
                heading.textContent = 'Glossary metadata';
                section.appendChild(heading);
                section.appendChild(tags);
                card.appendChild(section);
            }
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

    function extractHighlightId(detail) {
        if (!detail) {
            return null;
        }
        try {
            const parsed = JSON.parse(detail);
            if (parsed && typeof parsed === 'object') {
                if (parsed.highlight_id) {
                    return String(parsed.highlight_id);
                }
                if (parsed.anchor) {
                    return String(parsed.anchor);
                }
            }
        } catch (error) {
            return null;
        }
        return null;
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
        const explicitTarget = element.getAttribute('data-highlight-id');
        const highlightId = explicitTarget || extractHighlightId(detail);
        if (highlightId) {
            scrollToAnchor(highlightId);
        }
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

    const observedSections = Array.from(tocLinkById.keys())
        .map(function(id) {
            return document.getElementById(id);
        })
        .filter(function(section) {
            return section instanceof HTMLElement;
        });

    if (!observedSections.length) {
        return;
    }

    const visibleSections = new Map();

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
                setActiveTocLink(null);
                return;
            }

            setActiveLink(bestId);
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

    const firstObservedId = observedSections[0].getAttribute('id');
    if (firstObservedId) {
        setActiveLink(firstObservedId);
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


__all__ = [
    "_collect_provisions",
    "_normalise_anchor_key",
    "_normalise_provision_line",
    "_render_toc",
    "collect_document_actor_summary",
    "DocumentActorSummary",
    "build_document_preview_html",
    "render_document_preview",
]
