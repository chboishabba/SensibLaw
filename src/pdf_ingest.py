import argparse
import json
import re
from pathlib import Path

from pdfminer.high_level import extract_text

from .ingestion.cache import HTTPCache


def extract_pdf_text(pdf_path: Path):
    """Extract text and headings from a PDF, returning pages with numbers."""
    raw = extract_text(str(pdf_path)) or ""
    pages = []
    for i, page_text in enumerate(raw.split("\f"), start=1):
        lines = [re.sub(r"\s+", " ", line).strip() for line in page_text.splitlines() if line.strip()]
        if not lines:
            continue
        heading = lines[0]
        body = " ".join(lines[1:]) if len(lines) > 1 else ""
        pages.append({"page": i, "heading": heading, "text": body})
    return pages


def save_json(pages, output_path: Path, source: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "source": str(source),
        "page_count": len(pages),
        "pages": pages,
    }
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def download_pdf(url: str, cache: HTTPCache, dest: Path) -> Path:
    """Download a PDF using :class:`HTTPCache` and save to ``dest``.

    The helper allows PDF ingestion to reuse the same caching logic and delay
    configuration as other network fetchers.
    """

    dest.write_bytes(cache.fetch(url))
    return dest


def main():
    parser = argparse.ArgumentParser(description="Extract text from a PDF and save as JSON")
    parser.add_argument("pdf", type=Path, help="Path to PDF file")
    parser.add_argument("-o", "--output", type=Path, help="Output JSON path")
    args = parser.parse_args()

    output = args.output or Path("data/pdfs") / (args.pdf.stem + ".json")
    pages = extract_pdf_text(args.pdf)
    save_json(pages, output, args.pdf)


if __name__ == "__main__":
    main()
