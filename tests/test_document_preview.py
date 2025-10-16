"""Tests covering the document preview HTML helpers."""

from __future__ import annotations

import json
import re
import sys
import types
from dataclasses import dataclass
from datetime import date
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Tuple

import pytest

# Ensure the repository root is importable when tests execute from subdirectories.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# Provide a lightweight ``streamlit`` stub so the preview helpers can be imported without
# pulling in the optional dependency during test collection.
def _no_op(*args, **kwargs):  # type: ignore[unused-argument]
    return None


streamlit_stub = types.ModuleType("streamlit")
streamlit_stub.set_page_config = _no_op
streamlit_stub.title = _no_op
streamlit_stub.caption = _no_op
streamlit_stub.session_state = {}
streamlit_stub.__getattr__ = lambda _name: _no_op  # type: ignore[assignment]

components_stub = types.ModuleType("streamlit.components")
components_v1_stub = types.ModuleType("streamlit.components.v1")
components_v1_stub.html = _no_op
components_v1_stub.__getattr__ = lambda _name: _no_op  # type: ignore[assignment]
components_stub.v1 = components_v1_stub  # type: ignore[attr-defined]
streamlit_stub.components = components_stub  # type: ignore[attr-defined]

sys.modules.setdefault("streamlit", streamlit_stub)
sys.modules.setdefault("streamlit.components", components_stub)
sys.modules.setdefault("streamlit.components.v1", components_v1_stub)

from sensiblaw_streamlit.document_preview import (  # noqa: E402
    _collect_provisions,
    _normalise_anchor_key,
    _normalise_provision_line,
    _render_toc,
    build_document_preview_html,
)
from src.models.document import Document, DocumentMetadata, DocumentTOCEntry  # noqa: E402
from src.models.document import (  # noqa: E402
    Document,
    DocumentMetadata,
    DocumentTOCEntry,
)
from src.models.provision import (  # noqa: E402
    Provision,
    RuleAtom,
    RuleElement,
    RuleReference,
)


class _DocumentPreviewParser(HTMLParser):
    """Small helper to inspect the generated preview markup."""

    def __init__(self) -> None:
        super().__init__()
        self.sections: Dict[str, Dict[str, str]] = {}
        self.links: List[Dict[str, str]] = []
        self.atom_badges: List[Dict[str, str]] = []
        self._current_link: int | None = None
        self._current_badge: int | None = None

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, str]]) -> None:
        attributes = dict(attrs)
        if tag == "section" and attributes.get("class") == "provision-section":
            anchor = attributes.get("id")
            if anchor:
                self.sections[anchor] = attributes
        if tag == "a":
            self.links.append({"href": attributes.get("href", ""), "text": ""})
            self._current_link = len(self.links) - 1
        if tag == "span" and attributes.get("class") == "atom-badge":
            badge = dict(attributes)
            badge["text"] = ""
            self.atom_badges.append(badge)
            self._current_badge = len(self.atom_badges) - 1

    def handle_data(self, data: str) -> None:
        if self._current_link is not None:
            self.links[self._current_link]["text"] += data
        if self._current_badge is not None:
            self.atom_badges[self._current_badge]["text"] += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._current_link is not None:
            self.links[self._current_link]["text"] = self.links[self._current_link][
                "text"
            ].strip()
            self._current_link = None
        if tag == "span" and self._current_badge is not None:
            self.atom_badges[self._current_badge]["text"] = self.atom_badges[
                self._current_badge
            ]["text"].strip()
            self._current_badge = None


@dataclass
class _PreviewFixture:
    document: Document
    parent_provision: Provision
    child_provision: Provision


def _build_preview_fixture() -> _PreviewFixture:
    metadata = DocumentMetadata(
        jurisdiction="AU",
        citation="Sample Act 2024",
        date=date(2024, 1, 1),
    )

    duty_atom = RuleAtom(
        stable_id="atom-duty",
        atom_type="duty",
        role="obligation",
        text="A person must comply with the duty.",
        references=[
            RuleReference(
                work="Sample Act", section="1", citation_text="Sample Act s 1"
            ),
        ],
        elements=[
            RuleElement(role="subject", text="A person", atom_type="subject"),
            RuleElement(role="action", text="must comply", atom_type="predicate"),
        ],
    )

    definition_atom = RuleAtom(
        stable_id="atom-definition",
        atom_type="definition",
        role="definition",
        text="Defines the scope of the duty.",
    )

    child_atom = RuleAtom(
        stable_id="atom-child",
        atom_type="exception",
        role="exception",
        text="An exception applies in limited cases.",
    )

    child_provision = Provision(
        text="Subsection text clarifying the obligation.",
        identifier="s 1(1)",
        heading="Subsection 1",
        toc_id=6,
        stable_id="stable-subsection",
        rule_atoms=[child_atom],
    )

    parent_provision = Provision(
        text="The primary duty provision.\nIt establishes the baseline.",
        identifier="s 1",
        heading="Section 1 – Duty",
        toc_id=5,
        stable_id="stable-section",
        cultural_flags=["sacred_information"],
        rule_atoms=[duty_atom, definition_atom],
        children=[child_provision],
    )

    document = Document(
        metadata=metadata,
        body="The body of the act is not rendered directly.",
        provisions=[parent_provision],
        toc_entries=[
            DocumentTOCEntry(
                identifier="s 1",
                title="Duty obligations",
                children=[
                    DocumentTOCEntry(identifier="s 1(1)", title="Subsection 1"),
                ],
            )
        ],
    )

    return _PreviewFixture(document, parent_provision, child_provision)


@pytest.fixture
def preview_fixture() -> _PreviewFixture:
    return _build_preview_fixture()


def test_normalise_provision_line_collapses_leader_dots() -> None:
    noisy = "Heading title .............. 42"
    cleaned = _normalise_provision_line(noisy)
    assert cleaned == "Heading title 42"

    dotted = "Clause title · · · · · · 99"
    cleaned_dotted = _normalise_provision_line(dotted)
    assert cleaned_dotted == "Clause title 99"

    genuine = "An actual ... ellipsis remains."
    assert _normalise_provision_line(genuine) == genuine
def _extract_toc_labels(html: str) -> List[str]:
    pattern = re.compile(r"<a[^>]*>(.*?)</a>", re.DOTALL)
    labels = []
    for match in pattern.findall(html):
        text = re.sub(r"\s+", " ", match).strip()
        if text:
            labels.append(unescape(text))
    return labels


def test_collect_provisions_registers_all_link_targets(
    preview_fixture: _PreviewFixture,
) -> None:
    parent = preview_fixture.parent_provision
    child = preview_fixture.child_provision

    anchors, lookup = _collect_provisions(preview_fixture.document.provisions)

    assert [anchor for _, anchor in anchors] == ["segment-1", "segment-2"]

    parent_anchor = anchors[0][1]
    for key in (
        parent.identifier,
        parent.heading,
        parent.stable_id,
        str(parent.toc_id),
        f"toc-{parent.toc_id}",
    ):
        normalised = _normalise_anchor_key(key)
        assert normalised is not None
        assert lookup[normalised] == parent_anchor

    child_anchor = anchors[1][1]
    for key in (
        child.identifier,
        child.heading,
        child.stable_id,
        str(child.toc_id),
        f"toc-{child.toc_id}",
    ):
        normalised = _normalise_anchor_key(key)
        assert normalised is not None
        assert lookup[normalised] == child_anchor


def test_render_toc_links_to_registered_segments(
    preview_fixture: _PreviewFixture,
) -> None:
    anchors, lookup = _collect_provisions(preview_fixture.document.provisions)

    toc_html = _render_toc(preview_fixture.document.toc_entries, lookup)

    hrefs = re.findall(r"href='#([^']+)'", toc_html)
    assert set(hrefs) == {anchor for _, anchor in anchors}

    # Labels combine identifier and title, ensuring the reader sees familiar headings.
    assert "s 1 Duty obligations" in toc_html
    assert "s 1(1) Subsection 1" in toc_html


@pytest.mark.parametrize(
    "identifier,title,expected_label,allow_terminal_digits",
    [
        (
            "s 1",
            "General provisions .............. Page 3",
            "s 1 General provisions",
            False,
        ),
        (
            "s 2",
            "Interpretation ··········· 12",
            "s 2 Interpretation",
            False,
        ),
        (
            "Part 3",
            "Savings provisions ..... page 14",
            "Part 3 Savings provisions",
            False,
        ),
        ("Part 4", "............. Page 20", "Part 4", True),
    ],
)
def test_render_toc_strips_leaders_and_page_tokens(
    identifier: str, title: str, expected_label: str, allow_terminal_digits: bool
) -> None:
    entry = DocumentTOCEntry(identifier=identifier, title=title)
    normalised_identifier = _normalise_anchor_key(identifier)
    assert normalised_identifier is not None
    toc_html = _render_toc([entry], {normalised_identifier: "segment-1"})
    labels = _extract_toc_labels(toc_html)
    assert labels == [expected_label]
    for label in labels:
        assert "Page" not in label
        assert not re.search(r"[.·⋅•●∙]{2,}", label)
        if not allow_terminal_digits:
            assert not re.search(r"\b\d+\s*$", label)


def test_document_preview_html_contains_links_badges_and_details(
    preview_fixture: _PreviewFixture,
) -> None:
    html = build_document_preview_html(preview_fixture.document)

    parser = _DocumentPreviewParser()
    parser.feed(html)

    # Ensure that every section rendered has a matching link target in the table of contents.
    section_ids = set(parser.sections.keys())
    link_targets = {link["href"].lstrip("#") for link in parser.links if link["href"]}
    assert section_ids == {"segment-1", "segment-2"} == link_targets

    # Highlight counts: each provision with rule atoms should render an "Atoms" badge row.
    expected_badges = sum(
        len(provision.rule_atoms)
        for provision in [
            preview_fixture.parent_provision,
            preview_fixture.child_provision,
        ]
    )
    assert len(parser.atom_badges) == expected_badges
    assert html.count("<div class='atom-badges'><strong>Atoms:</strong>") == 2

    # Linearizer outputs: the badge payload should expose the structured atom data.
    expected_atoms = (
        preview_fixture.parent_provision.rule_atoms
        + preview_fixture.child_provision.rule_atoms
    )
    for badge, atom in zip(parser.atom_badges, expected_atoms):
        assert badge["data-label"] == atom.atom_type
        detail_payload = json.loads(unescape(badge["data-detail"]))
        assert detail_payload["atom_type"] == atom.atom_type
        assert detail_payload["stable_id"] == atom.stable_id
        if atom.references:
            assert (
                detail_payload["references"][0]["citation_text"]
                == atom.references[0].citation_text
            )
        if atom.elements:
            assert detail_payload["elements"][0]["role"] == atom.elements[0].role
