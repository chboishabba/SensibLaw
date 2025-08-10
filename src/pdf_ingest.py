import argparse
import json
import re
from pathlib import Path

from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer


def extract_pdf_text(pdf_path: Path):
    """Extract normalized text from a PDF, keeping page numbers and headings."""
    pages = []
    for page_num, page_layout in enumerate(extract_pages(pdf_path), start=1):
        text_chunks = []
        for element in page_layout:
            if isinstance(element, LTTextContainer):
                text_chunks.append(element.get_text())
        raw_text = "".join(text_chunks)
        lines = [
            re.sub(r"\s+", " ", line).strip()
            for line in raw_text.splitlines()
            if line.strip()
        ]
        normalized = "\n".join(lines)
        pages.append({"page": page_num, "text": normalized})
    return pages


def build_metadata(pdf_path: Path, pages):
    """Create metadata wrapper for extracted pages."""
    return {
        "source": pdf_path.name,
        "page_count": len(pages),
        "pages": pages,
    }


def save_json(data, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Extract text from a PDF and save as JSON"
    )
    parser.add_argument("pdf", type=Path, help="Path to PDF file")
    parser.add_argument("-o", "--output", type=Path, help="Output JSON path")
    args = parser.parse_args()

    pages = extract_pdf_text(args.pdf)
    data = build_metadata(args.pdf, pages)
    output = args.output or Path("data/pdfs") / (args.pdf.stem + ".json")
    save_json(data, output)


if __name__ == "__main__":
    main()
