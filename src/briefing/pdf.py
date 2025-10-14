"""PDF rendering helpers for the brief pack."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .models import BriefPack


def _format_pack(pack: BriefPack) -> Iterable[str]:
    yield "Brief Prep & Critique Pack"
    yield ""
    for issue, skeleton in sorted(pack.submission_skeletons.items()):
        yield f"Issue: {issue.title()}"
        for section in skeleton.sections:
            yield f"- {section.heading}"
            for slot in section.authorities:
                pin = f" at {slot.pin_cite}" if slot.pin_cite else ""
                yield f"    Authority: {slot.name} ({slot.citation}){pin}"
            if section.anchors:
                yield f"    Anchors: {', '.join(section.anchors)}"
            yield ""
    yield "Factor Coverage"
    for row in pack.coverage_grid.rows:
        missing = f" missing: {', '.join(row.missing)}" if row.missing else ""
        exhibits = f" exhibits: {', '.join(row.exhibits)}" if row.exhibits else ""
        yield f"- {row.factor_id} [{row.issue}] {row.section} -> {row.status}{exhibits}{missing}"
    yield ""
    yield "Counter-Arguments"
    for factor_id, arguments in pack.counter_arguments.items():
        yield f"Factor {factor_id}"
        for argument in arguments:
            yield f"  {argument.title}: {argument.pushback}"
            yield f"    Response: {argument.response}"
            if argument.evidence:
                joined = ", ".join(
                    f"{item.exhibit_id}: {item.description}"
                    for item in argument.evidence
                )
                yield f"    Receipts: {joined}"
        yield ""
    yield "Bundle Check"
    if pack.bundle_report.missing_annexures:
        for issue in pack.bundle_report.missing_annexures:
            yield f"- {issue.exhibit_id}: {issue.reason} ({issue.details})"
    else:
        yield "- No missing annexures"
    if pack.bundle_report.unreferenced_exhibits:
        yield "- Unreferenced exhibits: " + ", ".join(
            pack.bundle_report.unreferenced_exhibits
        )
    else:
        yield "- All exhibits referenced"


def render_brief_pack_pdf(pack: BriefPack, path: Path) -> None:
    """Render *pack* to a minimal PDF stored at *path*."""

    lines = list(_format_pack(pack))
    text = "\n".join(lines)

    def escape(content: str) -> str:
        return content.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    content_lines = []
    y = 780
    for line in text.split("\n"):
        content_lines.append(f"BT /F1 10 Tf 36 {y} Td ({escape(line)}) Tj ET")
        y -= 12
        if y < 36:
            # rudimentary line wrapping to avoid negative coordinates
            content_lines.append("BT /F1 10 Tf 36 780 Td () Tj ET")
            y = 768
    content_stream = "\n".join(content_lines)
    content_bytes = content_stream.encode("latin-1", errors="ignore")
    offsets: list[int] = []
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
    for offset in offsets:
        pdf += f"{offset:010d} 00000 n \n"
    pdf += f"trailer << /Size 6 /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF"
    path.write_bytes(pdf.encode("latin-1", errors="ignore"))


__all__ = ["render_brief_pack_pdf"]
