"""PDF ingestion utilities producing :class:`Document` objects."""

import argparse
import json
import re
from datetime import date
from pathlib import Path
from typing import List, Optional

from pdfminer.high_level import extract_text

from .ingestion.cache import HTTPCache
from .models.document import Document, DocumentMetadata, Provision
from .rules.extractor import extract_rules


# ``section_parser`` is optional – tests may monkeypatch it. If it's not
# available, a trivial fallback is used which treats the entire body as a single
# provision.
try:  # pragma: no cover - executed conditionally
    from . import section_parser  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    section_parser = None  # type: ignore


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


def _rules_to_strings(rules) -> List[str]:
    texts: List[str] = []
    for r in rules:
        t = f"{r.actor} {r.modality} {r.action}".strip()
        if r.conditions:
            t += f" {r.conditions}"
        if r.scope:
            t += f" {r.scope}"
        texts.append(t.strip())
    return texts


def _build_provision_from_node(node) -> Provision:
    provision = Provision(
        text=getattr(node, "text", ""),
        identifier=getattr(node, "identifier", None),
        heading=getattr(node, "heading", None),
        node_type=getattr(node, "node_type", None),
        rule_tokens=dict(getattr(node, "rule_tokens", {})),
    )
    provision.children = [
        _build_provision_from_node(child) for child in getattr(node, "children", [])
    ]
    return provision


def _build_provisions_from_nodes(nodes) -> List[Provision]:
    return [_build_provision_from_node(node) for node in nodes]


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

    if section_parser and hasattr(section_parser, "parse_sections"):
        structured = section_parser.parse_sections(body)  # type: ignore[attr-defined]
        provisions = _build_provisions_from_nodes(structured)
    else:  # Fallback: single provision containing entire body
        provisions = [Provision(text=body)]

    for prov in provisions:
        rules = extract_rules(prov.text)
        prov.principles.extend(_rules_to_strings(rules))

    return Document(metadata=metadata, body=body, provisions=provisions)


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
) -> Document:
    """Extract text, parse sections, run rule extraction and persist."""

    pages = extract_pdf_text(pdf)
    doc = build_document(pages, pdf, jurisdiction, citation, cultural_flags)
    out = output or Path("data/pdfs") / (pdf.stem + ".json")
    save_document(doc, out)
    return doc


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

    doc = process_pdf(
        args.pdf,
        output=args.output,
        jurisdiction=args.jurisdiction,
        citation=args.citation,
        cultural_flags=args.cultural_flags,
    )
    print(doc.to_json())


if __name__ == "__main__":  # pragma: no cover
    main()
