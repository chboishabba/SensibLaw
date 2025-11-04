import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.ingestion.section_parser import (
    LogicTokenClass,
    annotate_logic_tokens,
    fetch_section,
)


def test_extract_modality_conditions_and_refs():
    html = "<p>1 A person must not drive if intoxicated under s 5B.</p>"
    data = fetch_section(html)
    assert data["number"] == "1"
    assert data["rules"]["modality"] == "must not"
    assert data["rules"]["conditions"] == ["if"]
    assert data["rules"]["references"] == [
        {
            "work": "this_act",
            "section": "section",
            "pinpoint": "5B",
            "citation_text": "s 5B",
            "glossary_id": None,
        }
    ]


def test_subject_to_and_this_part():
    html = "<div>2 The authority may issue permits subject to this Part.</div>"
    data = fetch_section(html)
    assert data["number"] == "2"
    assert data["rules"]["modality"] == "may"
    assert data["rules"]["conditions"] == ["subject to"]
    assert data["rules"]["references"] == [
        {
            "work": "this_act",
            "section": "part",
            "pinpoint": None,
            "citation_text": "this Part",
            "glossary_id": None,
        }
    ]


def test_multiple_conditions_and_references():
    html = "<div>3 A body must comply unless exempt despite s 10.</div>"
    data = fetch_section(html)
    assert data["number"] == "3"
    assert data["rules"]["modality"] == "must"
    assert data["rules"]["conditions"] == ["unless", "despite"]
    assert data["rules"]["references"] == [
        {
            "work": "this_act",
            "section": "section",
            "pinpoint": "10",
            "citation_text": "s 10",
            "glossary_id": None,
        }
    ]


def test_structure_markers_are_detected():
    html = "<p>Part III — Indigenous land use agreements</p>"
    data = fetch_section(html)
    assert data["rules"]["references"] == [
        {
            "work": "this_act",
            "section": "part",
            "pinpoint": "III",
            "citation_text": "Part III",
            "glossary_id": None,
        }
    ]


def test_cross_act_reference_with_section():
    html = (
        "<p>4 The tribunal must consider Native Title Act 1993 (Cth) s 223 when deciding.</p>"
    )
    data = fetch_section(html)
    assert data["rules"]["modality"] == "must"
    assert {
        "work": "Native Title Act 1993 (Cth)",
        "section": "section",
        "pinpoint": "223",
        "citation_text": "Native Title Act 1993 (Cth) s 223",
        "glossary_id": None,
    } in data["rules"]["references"]


def test_section_15_reference_normalization():
    html = "<p>4 The board must consider section 15 before acting.</p>"
    data = fetch_section(html)
    assert data["number"] == "4"
    assert data["rules"]["modality"] == "must"
    assert data["rules"]["references"] == [
        {
            "work": "this_act",
            "section": "section",
            "pinpoint": "15",
            "citation_text": "section 15",
            "glossary_id": None,
        }
    ]


def test_logic_token_annotation_assigns_classes():
    text = "A person must not drive if intoxicated under s 5B."
    doc = annotate_logic_tokens(text)
    tokens = [(token.text, token._.class_) for token in doc if not token.is_space]
    assert tokens == [
        ("A", LogicTokenClass.ACTOR),
        ("person", LogicTokenClass.ACTOR),
        ("must", LogicTokenClass.MODALITY),
        ("not", LogicTokenClass.MODALITY),
        ("drive", LogicTokenClass.ACTION),
        ("if", LogicTokenClass.CONDITION),
        ("intoxicated", LogicTokenClass.CONDITION),
        ("under", LogicTokenClass.CONDITION),
        ("s", LogicTokenClass.REFERENCE),
        ("5B.", LogicTokenClass.REFERENCE),
    ]
    assert all(token._.class_ is not None for token in doc)


def test_logic_token_annotation_handles_subject_to_reference():
    text = "The authority may issue permits subject to this Part."
    doc = annotate_logic_tokens(text)
    mapping = {token.text: token._.class_ for token in doc if token.text in {"subject", "to", "this", "Part"}}
    assert mapping["subject"] == LogicTokenClass.CONDITION
    assert mapping["to"] == LogicTokenClass.CONDITION
    assert mapping["this"] == LogicTokenClass.REFERENCE
    assert mapping["Part"] == LogicTokenClass.REFERENCE


def test_fetch_section_includes_token_classes():
    html = "<p>1 A person must not drive if intoxicated under s 5B.</p>"
    data = fetch_section(html)
    token_classes = data["rules"].get("token_classes", [])
    assert token_classes
    labels = {entry["text"]: entry["class"] for entry in token_classes}
    assert labels["person"] == "ACTOR"
    assert labels["must"] == "MODALITY"
    assert labels["if"] == "CONDITION"
    assert labels["s"] == "REFERENCE"
    assert all({"text", "start", "end", "class"} <= set(entry) for entry in token_classes)
