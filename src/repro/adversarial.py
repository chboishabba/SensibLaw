from __future__ import annotations

from pathlib import Path
from typing import Iterable, List


def _parse_yaml(text: str) -> List[dict]:
    """Parse a very small subset of YAML used for adversarial files."""
    items: List[dict] = []
    current: dict | None = None
    current_list: List[str] | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("- "):
            if current:
                items.append(current)
            current = {}
            current_list = None
            line = line[2:]
            if line:
                key, value = line.split(":", 1)
                current[key.strip()] = value.strip().strip('"')
        elif line.startswith("    - ") and current_list is not None:
            current_list.append(line[6:].strip().strip('"'))
        elif line.startswith("  ") and current is not None:
            line = line.strip()
            if line.endswith(":"):
                key = line[:-1]
                current[key] = []
                current_list = current[key]
            else:
                key, value = line.split(":", 1)
                current[key] = value.strip().strip('"')
                current_list = None
    if current:
        items.append(current)
    return items


def load_adversarial(topic: str) -> List[dict]:
    """Load adversarial arguments for a topic."""
    path = Path("data/adversarial") / f"{topic}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"No adversarial file for topic '{topic}'")
    data = _parse_yaml(path.read_text(encoding="utf-8"))
    for item in data:
        if not all(k in item for k in ("claim", "reply", "receipts")):
            raise ValueError("Each item must have claim, reply and receipts fields")
    return data


def render_html(items: Iterable[dict]) -> str:
    """Render adversarial arguments to a simple HTML string."""
    parts = ["<html><body>"]
    for idx, item in enumerate(items, 1):
        parts.append(f"<h2>Argument {idx}</h2>")
        parts.append(f"<p><strong>Claim:</strong> {item['claim']}</p>")
        parts.append(f"<p><strong>Reply:</strong> {item['reply']}</p>")
        receipts = item.get("receipts") or []
        if receipts:
            parts.append("<ul>")
            for r in receipts:
                parts.append(f"<li>{r}</li>")
            parts.append("</ul>")
    parts.append("</body></html>")
    return "\n".join(parts)


def render_pdf(items: Iterable[dict], path: Path) -> None:
    """Render adversarial arguments to a minimal PDF file without dependencies."""
    lines: List[str] = []
    for idx, item in enumerate(items, 1):
        lines.append(f"Claim {idx}: {item['claim']}")
        lines.append(f"Reply: {item['reply']}")
        receipts = item.get("receipts") or []
        if receipts:
            lines.append("Receipts:")
            for r in receipts:
                lines.append(f"- {r}")
        lines.append("")
    text = "\n".join(lines)

    # Build a very small PDF with one page of text
    def escape(t: str) -> str:
        return t.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    content_lines = []
    y = 720
    for line in text.split("\n"):
        content_lines.append(f"BT /F1 12 Tf 72 {y} Td ({escape(line)}) Tj ET")
        y -= 14
    content_stream = "\n".join(content_lines)
    content_bytes = content_stream.encode("latin-1")
    offsets: List[int] = []
    pdf = "%PDF-1.1\n"

    def add_obj(obj: str) -> None:
        nonlocal pdf
        offsets.append(len(pdf))
        pdf += obj + "\n"

    add_obj("1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj")
    add_obj("2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj")
    add_obj(
        "3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        "/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj"
    )
    add_obj(
        f"4 0 obj << /Length {len(content_bytes)} >> stream\n{content_stream}\nendstream endobj"
    )
    add_obj("5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj")

    xref_offset = len(pdf)
    pdf += "xref\n0 6\n0000000000 65535 f \n"
    for off in offsets:
        pdf += f"{off:010d} 00000 n \n"
    pdf += (
        "trailer << /Size 6 /Root 1 0 R >>\nstartxref\n"
        f"{xref_offset}\n%%EOF"
    )

    path.write_bytes(pdf.encode("latin-1"))


def build_bundle(topic: str, output_dir: Path) -> dict:
    """Create HTML and PDF bundle for a topic."""
    items = load_adversarial(topic)
    output_dir.mkdir(parents=True, exist_ok=True)
    html_content = render_html(items)
    html_path = output_dir / f"{topic}.html"
    html_path.write_text(html_content, encoding="utf-8")
    pdf_path = output_dir / f"{topic}.pdf"
    render_pdf(items, pdf_path)
    return {"html": html_path, "pdf": pdf_path}
