import argparse
import json
import re
from pathlib import Path

import pdfplumber


def extract_pdf_text(pdf_path: Path):
    """Extract text from a PDF, returning list of pages with numbers."""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            text = re.sub(r"\s+", " ", text).strip()
            pages.append({"page": i, "text": text})
    return pages


def save_json(data, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Extract text from a PDF and save as JSON")
    parser.add_argument("pdf", type=Path, help="Path to PDF file")
    parser.add_argument("-o", "--output", type=Path, help="Output JSON path")
    args = parser.parse_args()

    output = args.output or Path("data/pdfs") / (args.pdf.stem + ".json")
    pages = extract_pdf_text(args.pdf)
    save_json(pages, output)


if __name__ == "__main__":
    main()
