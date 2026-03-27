from __future__ import annotations

from dataclasses import dataclass
import re

from .austlii_paragraphs import parse_austlii_paragraphs


_BRACKETED_START_RE = re.compile(r"^\[(?P<number>\d+)\]\s*(?P<rest>.*)$")
_PLAIN_START_RE = re.compile(r"^(?P<number>\d+)\s+(?P<rest>.+)$")


@dataclass(frozen=True)
class JadeParagraph:
    number: int
    text: str


def _collapse_ws(text: str) -> str:
    return " ".join((text or "").split()).strip()


def parse_jade_paragraphs(content: bytes | str, *, content_type: str | None = None) -> list[JadeParagraph]:
    text = content.decode("utf-8", errors="replace") if isinstance(content, bytes) else content
    ct = (content_type or "").lower()

    if "html" in ct or "<html" in text.lower():
        parsed = parse_austlii_paragraphs(text)
        if parsed:
            return [JadeParagraph(number=row.number, text=row.text) for row in parsed]

    paragraphs: list[JadeParagraph] = []
    current_number: int | None = None
    current_lines: list[str] = []

    def _flush() -> None:
        nonlocal current_number, current_lines
        if current_number is None:
            current_lines = []
            return
        body = _collapse_ws(" ".join(current_lines))
        if body:
            paragraphs.append(JadeParagraph(number=current_number, text=body))
        current_number = None
        current_lines = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            _flush()
            continue

        match = _BRACKETED_START_RE.match(line) or _PLAIN_START_RE.match(line)
        if match:
            _flush()
            current_number = int(match.group("number"))
            rest = _collapse_ws(match.group("rest"))
            current_lines = [rest] if rest else []
            continue

        if current_number is not None:
            current_lines.append(line)

    _flush()
    return paragraphs
