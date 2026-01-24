from src.models.provision import RuleReference
from src.pdf_ingest import _canonicalize_references, _extract_hyperlink_references


def test_link_precedence_over_token_reference():
    pages = [
        {
            "page": 1,
            "heading": "h",
            "text": "",
            "lines": [],
            "links": [
                {
                    "uri": "https://example.com/Western_Sydney_Parklands_Act_2006#sec4",
                    "rect": (0, 0, 1, 1),
                    "text": "Western Sydney Parklands Act 2006",
                    "page": 1,
                }
            ],
        }
    ]

    link_refs = _extract_hyperlink_references(pages, source_id="doc")
    token_refs = [
        RuleReference(
            work="Western Sydney Parklands Act 2006",
            section="section",
            pinpoint="4",
            source=None,
        )
    ]

    merged = _canonicalize_references(link_refs + token_refs, preferred_sources=("link", None))
    assert len(merged) == 1
    ref = merged[0]
    assert ref.source == "link"
    assert ref.work == "western sydney parklands act 2006"
    assert ref.pinpoint == "4"


def test_link_and_token_coexist_for_distinct_sections():
    pages = [
        {
            "page": 1,
            "heading": "h",
            "text": "",
            "lines": [],
            "links": [
                {
                    "uri": "https://example.com/Western_Sydney_Parklands_Act_2006#sec4",
                    "rect": (0, 0, 1, 1),
                    "text": "Western Sydney Parklands Act 2006",
                    "page": 1,
                }
            ],
        }
    ]

    link_refs = _extract_hyperlink_references(pages, source_id="doc")
    token_refs = [
        RuleReference(
            work="Western Sydney Parklands Act 2006",
            section="section",
            pinpoint="6",
        )
    ]

    merged = _canonicalize_references(link_refs + token_refs, preferred_sources=("link", None))
    keys = {(ref.section, ref.pinpoint) for ref in merged}
    assert keys == {("section", "4"), ("section", "6")}
    assert any(ref.source == "link" and ref.pinpoint == "4" for ref in merged)


def test_link_text_without_uri_still_emits_reference():
    pages = [
        {
            "page": 1,
            "heading": "",
            "text": "",
            "lines": [],
            "links": [
                {
                    "uri": None,
                    "rect": (0, 0, 1, 1),
                    "text": "section 7 of the Crimes Act 1914",
                    "page": 1,
                }
            ],
        }
    ]

    link_refs = _extract_hyperlink_references(pages, source_id="doc")
    assert len(link_refs) == 1
    ref = link_refs[0]
    assert ref.work == "crimes act 1914"
    assert ref.pinpoint == "7"
