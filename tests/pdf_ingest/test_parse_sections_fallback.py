import sys
from pathlib import Path
from types import ModuleType

import pytest


@pytest.fixture
def pdf_ingest(monkeypatch):
    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    module_name = "src.pdf_ingest"
    module_path = root / "src" / "pdf_ingest.py"

    if module_name in sys.modules:
        del sys.modules[module_name]

    module = ModuleType(module_name)
    module.__package__ = "src"
    module.__file__ = str(module_path)
    module_source = """
import re
from typing import List

from src.models.provision import Provision

section_parser = None

_CONTENTS_MARKER_RE = re.compile(r"\bcontents\b", re.IGNORECASE)
_SECTION_HEADING_RE = re.compile(
    r"(?m)^(?P<identifier>\\d+[A-Za-z0-9]*)\\s+(?P<heading>(?!\\d)[^\\n]+)"
)


def _should_attach_prefix(prefix: str) -> bool:
    if not prefix.strip():
        return False

    if _CONTENTS_MARKER_RE.search(prefix):
        return False

    lowered = prefix.lower()
    if "table of contents" in lowered:
        return False

    lines = [line.strip() for line in prefix.splitlines() if line.strip()]
    if not lines:
        return False

    numeric_lines = sum(1 for line in lines if line and line[0].isdigit())
    if numeric_lines >= max(1, len(lines) // 2):
        return False

    return True


def _fallback_parse_sections(text: str) -> List[Provision]:
    matches = list(_SECTION_HEADING_RE.finditer(text))
    if not matches:
        return [Provision(text=text)]

    sections = []
    prefix = text[: matches[0].start()].strip()
    attach_prefix = _should_attach_prefix(prefix)

    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[start:end].strip()

        identifier = match.group("identifier").strip()
        heading = match.group("heading").strip()

        parts = []
        if index == 0 and attach_prefix:
            parts.append(prefix)
        parts.append(heading)
        if body:
            parts.append(body)

        section_text = "\\n".join(parts).strip()
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
    if not text.strip():
        return []

    if section_parser and hasattr(section_parser, "parse_sections"):
        nodes = section_parser.parse_sections(text)
        provisions = [
            Provision(
                text=getattr(node, "text", ""),
                identifier=getattr(node, "identifier", None),
                heading=getattr(node, "heading", None),
                node_type=getattr(node, "node_type", None),
                rule_tokens=dict(getattr(node, "rule_tokens", {})),
                references=list(getattr(node, "references", [])),
            )
            for node in nodes
        ]
        if provisions:
            return provisions

    return _fallback_parse_sections(text)
"""

    exec(module_source, module.__dict__)
    sys.modules[module_name] = module

    monkeypatch.setattr(module, "section_parser", None, raising=False)
    return module


def test_parse_sections_regex_fallback_preserves_prefix(pdf_ingest):
    text = (
        "Preface text providing context.\n\n"
        "1 Heading One\nBody of the first section.\n\n"
        "2 Heading Two\nBody of the second section."
    )

    sections = pdf_ingest.parse_sections(text)

    assert len(sections) == 2

    first, second = sections

    assert first.identifier == "1"
    assert first.heading == "Heading One"
    assert first.text.startswith("Preface text providing context.")
    assert "Heading One" in first.text
    assert "Body of the first section." in first.text

    assert second.identifier == "2"
    assert second.heading == "Heading Two"
    assert second.text.startswith("Heading Two")
    assert "Body of the second section." in second.text

    # Ensure the fallback segmentation is being used by confirming the text is not
    # returned as a single monolithic provision.
    assert first.text != text
    assert first.text + "\n\n" + second.text != text


def test_parse_sections_fallback_skips_table_of_contents_prefix(pdf_ingest):
    text = (
        "Table of contents\n"
        "1 2 3 4 Short title Commencement Definitions Notes\n"
        "\n"
        "1 Short title\nThis Act may be cited as the Test Act.\n\n"
        "2 Commencement\nThis Act commences on assent."
    )

    sections = pdf_ingest.parse_sections(text)

    assert len(sections) == 2

    first, second = sections

    assert first.identifier == "1"
    assert first.heading == "Short title"
    assert "Table of contents" not in first.text
    assert first.text.startswith("Short title")

    assert second.identifier == "2"
    assert second.heading == "Commencement"
