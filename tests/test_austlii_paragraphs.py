from pathlib import Path

from src.sources.austlii_paragraphs import parse_austlii_paragraphs
from src.sources.paragraphs import select_paragraphs

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "austlii" / "judgment_paragraphs_sample.html"


def test_parse_austlii_paragraphs_from_list_items():
    html = FIXTURE.read_text(encoding="utf-8")
    paragraphs = parse_austlii_paragraphs(html)
    assert [paragraph.number for paragraph in paragraphs] == [119, 120, 121]
    assert paragraphs[1].text == "Paragraph 120 text with markup."


def test_select_paragraphs_with_window():
    html = FIXTURE.read_text(encoding="utf-8")
    paragraphs = parse_austlii_paragraphs(html)
    selected = select_paragraphs(paragraphs, requested=[120], window=1)
    assert [paragraph.number for paragraph in selected] == [119, 120, 121]
