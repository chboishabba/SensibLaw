from pathlib import Path

from src.sources.jade_paragraphs import parse_jade_paragraphs
from src.sources.paragraphs import select_paragraphs


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "jade" / "judgment_paragraphs_sample.txt"


def test_parse_jade_paragraphs_from_plain_text():
    paragraphs = parse_jade_paragraphs(FIXTURE.read_text(encoding="utf-8"), content_type="text/plain")
    assert [paragraph.number for paragraph in paragraphs] == [119, 120, 121]
    assert paragraphs[1].text == "Paragraph 120 text continues on the next line."


def test_select_jade_paragraphs_with_window():
    paragraphs = parse_jade_paragraphs(FIXTURE.read_text(encoding="utf-8"), content_type="text/plain")
    selected = select_paragraphs(paragraphs, requested=[120], window=1)
    assert [paragraph.number for paragraph in selected] == [119, 120, 121]
