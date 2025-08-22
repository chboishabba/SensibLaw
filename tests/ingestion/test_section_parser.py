import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.ingestion.section_parser import fetch_section


def test_extract_modality_conditions_and_refs():
    html = "<p>1 A person must not drive if intoxicated under s 5B.</p>"
    data = fetch_section(html)
    assert data["number"] == "1"
    assert data["rules"]["modality"] == "must not"
    assert data["rules"]["conditions"] == ["if"]
    assert data["rules"]["references"] == ["s 5B"]


def test_subject_to_and_this_part():
    html = "<div>2 The authority may issue permits subject to this Part.</div>"
    data = fetch_section(html)
    assert data["number"] == "2"
    assert data["rules"]["modality"] == "may"
    assert data["rules"]["conditions"] == ["subject to"]
    assert data["rules"]["references"] == ["this Part"]


def test_multiple_conditions_and_references():
    html = "<div>3 A body must comply unless exempt despite s 10.</div>"
    data = fetch_section(html)
    assert data["number"] == "3"
    assert data["rules"]["modality"] == "must"
    assert data["rules"]["conditions"] == ["unless", "despite"]
    assert data["rules"]["references"] == ["s 10"]
