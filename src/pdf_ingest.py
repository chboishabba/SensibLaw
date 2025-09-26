"""PDF ingestion utilities producing :class:`Document` objects."""

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from pdfminer.high_level import extract_text

from .culture.overlay import get_default_overlay
from .glossary.service import lookup as lookup_gloss
from .ingestion.cache import HTTPCache
from .models.document import Document, DocumentMetadata, Provision
from .models.provision import Atom, RuleAtom, RuleElement, RuleLint
from .rules import UNKNOWN_PARTY
from .rules.extractor import extract_rules
from .storage.core import Storage
from .storage.versioned_store import VersionedStore


logger = logging.getLogger(__name__)

_CULTURAL_OVERLAY = get_default_overlay()


_QUOTE_CHARS = "\"'“”‘’"
_DEFINITION_START_RE = re.compile(
    r"^\s*(?P<term>[\"“][^\"”]+[\"”]|'[^']+')\s+"
    r"(?P<verb>means|includes)\s+(?P<definition>.+)$",
    re.IGNORECASE,
)


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


def _extract_definition_entries(text: str) -> Dict[str, str]:
    entries: Dict[str, str] = {}
    current_term: Optional[str] = None
    collected: List[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
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
            modality=getattr(r, "modality", None),
            action=getattr(r, "action", None),
            conditions=conditions,
            scope=scope,
            text=text,
            subject_gloss=subject_gloss,
            subject_gloss_metadata=subject_metadata,
            glossary_id=subject_glossary_id,
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
                gloss_entry = module_lookup_gloss(fragment)
                resolved_entry: Optional[GlossaryRecord] = None
                if registry is not None and gloss_entry:
                    resolved_entry = registry.register_definition(
                        gloss_entry.phrase,
                        gloss_entry.text,
                        gloss_entry.metadata,
                    )
                if registry is not None and resolved_entry is None:
                    resolved_entry = registry.resolve(fragment)

                gloss_text = who_text or fragment
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
                        text=fragment,
                        conditions=conditions if role == "circumstance" else None,
                        gloss=gloss_text,
                        gloss_metadata=gloss_metadata,
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
    glossary_registry: Optional[GlossaryRegistry] = None,
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

    registry = glossary_registry or _DEFAULT_GLOSSARY_REGISTRY

    definitions = _extract_definition_entries(body)
    for term, definition in definitions.items():
        registry.register_definition(term, definition)

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

    storage: Optional[Storage] = None
    registry: Optional[GlossaryRegistry] = None
    try:
        if db_path:
            storage = Storage(db_path)
        registry = GlossaryRegistry(storage)
        pages = extract_pdf_text(pdf)
        doc = build_document(
            pages,
            pdf,
            jurisdiction,
            citation,
            cultural_flags,
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
