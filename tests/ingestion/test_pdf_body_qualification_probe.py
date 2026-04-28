from __future__ import annotations

from pathlib import Path

from scripts.probe_demo_pdf_page_quality import build_page_quality_probe
from src.pdf_ingest import build_document


def test_build_document_preserves_cross_page_continuation_order() -> None:
    pages = [
        {
            "page": 1,
            "heading": "Facts",
            "text": "The Court held that",
            "lines": ["Facts", "The Court held that"],
        },
        {
            "page": 2,
            "heading": "Facts",
            "text": "the appellant succeeded on the first ground.",
            "lines": ["Facts", "the appellant succeeded on the first ground."],
        },
    ]

    document = build_document(pages, Path("2025 HCA Cross Page Demo.pdf"))
    body = document.body

    assert "The Court held that" in body
    assert "the appellant succeeded on the first ground." in body
    assert body.index("The Court held that") < body.index(
        "the appellant succeeded on the first ground."
    )

    probe = build_page_quality_probe(pages)
    assert probe["continuation_candidate_count"] == 1
    assert probe["boundary_reports"][0]["same_heading"] is True
    assert probe["boundary_reports"][0]["continuation_candidate"] is True


def test_build_document_rejects_wrapper_title_and_falls_back_to_filename() -> None:
    pages = [
        {
            "page": 1,
            "heading": "Case Name",
            "text": "The Court allowed the appeal.",
            "lines": ["Case Name", "The Court allowed the appeal."],
        }
    ]

    document = build_document(pages, Path("2025 HCA Demo Body Qualification.pdf"))

    assert document.metadata.title == "2025 HCA Demo Body Qualification"
    assert document.metadata.title != "Case Name"


def test_page_quality_probe_surfaces_polluted_wrapper_pages_structurally() -> None:
    pages = [
        {
            "page": 1,
            "heading": "Case Name",
            "text": "Case Name",
            "lines": ["Case Name", "Case Name"],
        },
        {
            "page": 2,
            "heading": "Case Name",
            "text": "Appendix A",
            "lines": ["Case Name", "Appendix A"],
        },
        {
            "page": 3,
            "heading": "Findings",
            "text": "The respondent admitted the loss.",
            "lines": ["Findings", "The respondent admitted the loss."],
        },
    ]

    probe = build_page_quality_probe(pages)

    assert probe["page_count"] == 3
    assert probe["repeated_heading_pages"] == 2
    assert probe["pages_with_body"] == 3

    first = probe["page_reports"][0]
    second = probe["page_reports"][1]
    third = probe["page_reports"][2]

    assert first["heading_repeated"] is True
    assert second["heading_repeated"] is True
    assert first["body_word_count"] <= 2
    assert second["body_word_count"] <= 2
    assert third["body_word_count"] > second["body_word_count"]


def test_build_document_strips_front_page_wrapper_lines() -> None:
    pages = [
        {
            "page": 1,
            "heading": "jade.io",
            "text": "BarNet Jade View this document in a browser Attribution HIGH COURT OF AUSTRALIA Mabo v Queensland",
            "lines": [
                "jade.io",
                "BarNet Jade",
                "View this document in a browser",
                "Attribution",
                "HIGH COURT OF AUSTRALIA",
                "Mabo v Queensland",
            ],
        }
    ]

    document = build_document(pages, Path("Mabo Wrapper Demo.pdf"))

    assert document.metadata.title == "Mabo Wrapper Demo"
    assert "jade.io" not in document.body
    assert "BarNet Jade" not in document.body
    assert "View this document in a browser" not in document.body
    assert "HIGH COURT OF AUSTRALIA" in document.body


def test_build_document_suppresses_citation_panel_lines_but_keeps_prose() -> None:
    pages = [
        {
            "page": 1,
            "heading": "MASON C.J.",
            "text": "",
            "lines": [
                "MASON C.J.",
                "Following paragraph cited by:",
                "Commonwealth v Yarmirr (11 October 2001) Wik Peoples v Queensland (23 December 1996)",
                "Decisions Commonwealth of Australia v Yunupingu (12 March 2025)",
                "The common law of this country recognizes a form of native title.",
            ],
        }
    ]

    document = build_document(pages, Path("Mabo Citation Panel Demo.pdf"))

    assert "Following paragraph cited by:" not in document.body
    assert "Commonwealth v Yarmirr" not in document.body
    assert "Commonwealth of Australia v Yunupingu" not in document.body
    assert "recognizes a form of native title" in document.body


def test_build_document_suppresses_citation_digest_continuation_lines() -> None:
    pages = [
        {
            "page": 3,
            "heading": "Reasons",
            "text": "",
            "lines": [
                "Reasons",
                "The common law recognizes a form of native title. Commonwealth of Australia v Yunupingu",
                "(12 March 2025) (Gageler CJ; Gordon, Edelman,",
                "Steward, Gleeson, Jagot and Beech-Jones JJ)",
                "The radical title survived annexation.",
            ],
        }
    ]

    document = build_document(pages, Path("Mabo Citation Digest Continuation Demo.pdf"))

    assert "The common law recognizes a form of native title." in document.body
    assert "The radical title survived annexation." in document.body
    assert "Commonwealth of Australia v Yunupingu" not in document.body
    assert "(12 March 2025)" not in document.body
    assert "Beech-Jones JJ" not in document.body
