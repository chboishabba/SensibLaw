"""PDF ingestion utilities producing :class:`Document` objects."""

import argparse
import json
import logging
import re
import sys
from datetime import date
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from pdfminer.high_level import extract_text

from .culture.overlay import get_default_overlay
from .glossary.service import lookup as lookup_gloss
from .ingestion.cache import HTTPCache
from .models.document import Document, DocumentMetadata, Provision
from .models.provision import Atom
from .rules import UNKNOWN_PARTY
from .rules.extractor import extract_rules
from .storage.versioned_store import VersionedStore


logger = logging.getLogger(__name__)

_CULTURAL_OVERLAY = get_default_overlay()


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


def extract_pdf_text(pdf_path: Path) -> List[dict]:
    """Extract text and headings from a PDF, returning pages with numbers."""

    raw = extract_text(str(pdf_path)) or ""
    pages: List[dict] = []
    for i, page_text in enumerate(raw.split("\f"), start=1):
        lines = [
            re.sub(r"\s+", " ", line).strip()
            for line in page_text.splitlines()
            if line.strip()
        ]
        if not lines:
            continue
        heading = lines[0]
        body = " ".join(lines[1:]) if len(lines) > 1 else ""
        pages.append({"page": i, "heading": heading, "text": body})
    return pages


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


def _normalize_principle_text(text: Optional[str]) -> Optional[str]:
    """Collapse whitespace and trim structural numbering from ``text``."""

    if not text:
        return None
    normalized = re.sub(r"\s+", " ", text).strip()
    normalized = _PRINCIPLE_LEADING_NUMBERS.sub("", normalized)
    normalized = _PRINCIPLE_LEADING_ENUM.sub("", normalized)
    return normalized or None


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


def _rules_to_atoms(rules) -> List[Atom]:
    atoms: List[Atom] = []
    module_lookup_gloss = getattr(sys.modules.get(__name__), "lookup_gloss", lookup_gloss)
    for r in rules:
        actor = getattr(r, "actor", None)
        party = getattr(r, "party", None) or UNKNOWN_PARTY
        who_text = getattr(r, "who_text", None) or actor or None
        conditions = getattr(r, "conditions", None)
        scope = getattr(r, "scope", None)

        text_parts = [
            getattr(r, "actor", None),
            getattr(r, "modality", None),
            getattr(r, "action", None),
        ]
        if conditions:
            text_parts.append(conditions)
        if scope:
            text_parts.append(scope)
        text = " ".join(part.strip() for part in text_parts if part).strip() or None
        text = _normalize_principle_text(text)

        atoms.append(
            Atom(
                type="rule",
                role="principle",
                party=party,
                who=party,
                who_text=who_text,
                conditions=conditions,
                text=text,
                gloss=who_text or actor or None,
            )
        )

        for role, fragments in (getattr(r, "elements", None) or {}).items():
            for fragment in fragments:
                if not fragment:
                    continue
                gloss_entry = module_lookup_gloss(fragment)
                gloss_text = who_text or fragment
                gloss_metadata = None
                if gloss_entry:
                    gloss_text = gloss_entry.text
                    if gloss_entry.metadata is not None:
                        gloss_metadata = dict(gloss_entry.metadata)
                atoms.append(
                    Atom(
                        type="element",
                        role=role,
                        party=party,
                        who=party,
                        who_text=who_text,
                        conditions=conditions if role == "circumstance" else None,
                        text=fragment,
                        gloss=gloss_text,
                        gloss_metadata=gloss_metadata,
                    )
                )
        if party == UNKNOWN_PARTY:
            atoms.append(
                Atom(
                    type="lint",
                    role="unknown_party",
                    text=f"Unclassified actor: {actor}".strip(),
                    party=UNKNOWN_PARTY,
                    who=UNKNOWN_PARTY,
                    who_text=who_text or actor or None,
                    gloss=who_text or actor or None,
                )
            )
    return atoms


def _build_provision_from_node(node) -> Provision:
    provision = Provision(
        text=getattr(node, "text", ""),
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


_SECTION_HEADING_RE = re.compile(
    r"(?m)^(?P<identifier>\d+[A-Za-z0-9]*)\s+(?P<heading>[^\n]+)"
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


def _fallback_parse_sections(text: str) -> List[Provision]:
    matches = list(_SECTION_HEADING_RE.finditer(text))
    if not matches:
        return [Provision(text=text)]

    sections: List[Provision] = []
    prefix = text[: matches[0].start()].strip()

    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[start:end].strip()

        identifier = match.group("identifier").strip()
        heading = match.group("heading").strip()

        parts: List[str] = []
        if index == 0 and prefix:
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


def parse_sections(text: str) -> List[Provision]:
    """Split ``text`` into individual section provisions."""

    if not text.strip():
        return []

    parser_available = _has_section_parser()
    if parser_available:
        try:
            nodes = section_parser.parse_sections(text)  # type: ignore[attr-defined]
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

    return _fallback_parse_sections(text)


def build_document(
    pages: List[dict],
    source: Path,
    jurisdiction: Optional[str] = None,
    citation: Optional[str] = None,
    cultural_flags: Optional[List[str]] = None,
) -> Document:
    """Create a :class:`Document` from extracted pages."""

    body = "\n\n".join(f"{p['heading']}\n{p['text']}".strip() for p in pages)
    metadata = DocumentMetadata(
        jurisdiction=jurisdiction or "",
        citation=citation or "",
        date=date.today(),
        cultural_flags=cultural_flags,
        provenance=str(source),
    )

    provisions = parse_sections(body)
    if not provisions:
        parser_available = _has_section_parser()
        if parser_available:
            try:
                nodes = section_parser.parse_sections(body)  # type: ignore[attr-defined]
            except Exception:  # pragma: no cover - defensive guard
                nodes = []
            structured = _build_provisions_from_nodes(nodes or [])
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
                len(body),
                extra={
                    "section_parser_available": parser_available,
                    "section_parser_optional_import_failed": _SECTION_PARSER_OPTIONAL_IMPORT_FAILED,
                    "root_section_parser_import_failed": _ROOT_SECTION_PARSER_IMPORT_FAILED,
                    "body_length": len(body),
                },
            )

    for prov in provisions:
        rules = extract_rules(prov.text)
        atoms = _rules_to_atoms(rules)
        prov.atoms.extend(atoms)
        existing = _dedupe_principles(prov.principles)
        prov.principles = existing
        rule_principles = _dedupe_principles(
            atom.text for atom in atoms if atom.type == "rule" and atom.text
        )
        merged = _dedupe_principles([*existing, *rule_principles])
        prov.principles = merged

    document = Document(metadata=metadata, body=body, provisions=provisions)
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
    cultural_flags: Optional[List[str]] = None,
    db_path: Optional[Path] = None,
    doc_id: Optional[int] = None,
) -> Tuple[Document, Optional[int]]:
    """Extract text, parse sections, run rule extraction and persist."""

    if doc_id is not None and db_path is None:
        raise ValueError("A database path must be provided when specifying --doc-id")

    pages = extract_pdf_text(pdf)
    doc = build_document(pages, pdf, jurisdiction, citation, cultural_flags)
    out = output or Path("data/pdfs") / (pdf.stem + ".json")

    stored_doc_id: Optional[int] = None
    if db_path:
        store = VersionedStore(db_path)
        try:
            actual_doc_id = doc_id if doc_id is not None else store.generate_id()
            if not doc.metadata.canonical_id:
                doc.metadata.canonical_id = str(actual_doc_id)
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
    parser.add_argument(
        "--cultural-flags", nargs="*", help="List of cultural sensitivity flags"
    )
    args = parser.parse_args()

    doc, _ = process_pdf(
        args.pdf,
        output=args.output,
        jurisdiction=args.jurisdiction,
        citation=args.citation,
        cultural_flags=args.cultural_flags,
    )
    print(doc.to_json())


if __name__ == "__main__":  # pragma: no cover
    main()
