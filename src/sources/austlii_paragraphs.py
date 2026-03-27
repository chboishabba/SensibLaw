from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
import re

from .paragraphs import select_paragraphs


_WS_RE = re.compile(r"\s+")
_LEADING_NUMBER_RE = re.compile(r"^\[?(?P<number>\d+)\]?(?:[.)]|\s)+")


def _collapse_ws(text: str) -> str:
    return _WS_RE.sub(" ", (text or "")).strip()


@dataclass(frozen=True)
class AustLiiParagraph:
    number: int
    text: str


class _ParagraphHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.paragraphs: list[AustLiiParagraph] = []
        self._capture_tag: str | None = None
        self._capture_number: int | None = None
        self._capture_text: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        t = tag.lower()
        attr_map = dict(attrs)
        number: int | None = None

        if t == "li":
            value = attr_map.get("value")
            if value and str(value).isdigit():
                number = int(str(value))
        elif t in {"p", "div"}:
            css_class = str(attr_map.get("class") or "")
            if "quote" in css_class.lower():
                return

        if self._capture_tag is None and t in {"li", "p", "div"}:
            self._capture_tag = t
            self._capture_number = number
            self._capture_text = []

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if self._capture_tag != t:
            return

        text = _collapse_ws("".join(self._capture_text))
        number = self._capture_number
        if text:
            if number is None:
                match = _LEADING_NUMBER_RE.match(text)
                if match:
                    number = int(match.group("number"))
                    text = text[match.end() :].strip()
            elif text.startswith(f"[{number}]"):
                text = text[len(f"[{number}]") :].strip()
            elif text.startswith(f"{number} "):
                text = text[len(str(number)) :].strip()

        if number is not None and text:
            self.paragraphs.append(AustLiiParagraph(number=number, text=text))

        self._capture_tag = None
        self._capture_number = None
        self._capture_text = []

    def handle_data(self, data: str) -> None:
        if self._capture_tag is not None:
            self._capture_text.append(data)


def parse_austlii_paragraphs(html: str) -> list[AustLiiParagraph]:
    parser = _ParagraphHTMLParser()
    parser.feed(html)

    deduped: list[AustLiiParagraph] = []
    seen: set[int] = set()
    for paragraph in parser.paragraphs:
        if paragraph.number in seen:
            continue
        seen.add(paragraph.number)
        deduped.append(paragraph)
    return deduped
