from pathlib import Path

from src.sources.austlii_sino_parse import parse_sino_search_html


FIXTURE = Path("tests/fixtures/austlii/sino_results_sample.html")
FIXTURE_REAL = Path("tests/fixtures/austlii/sino_results_realistic.html")
FIXTURE_LIVE = Path("tests/fixtures/austlii/sino_results_live_mabo.html")


def test_parse_sino_hits_extracts_links():
    html = FIXTURE.read_text(encoding="utf-8")
    hits = parse_sino_search_html(html)
    assert len(hits) >= 2
    assert hits[0].title
    assert hits[0].url.startswith("http")


def test_parse_sino_hits_citation_detection():
    html = FIXTURE.read_text(encoding="utf-8")
    hits = parse_sino_search_html(html)
    citations = [h.citation for h in hits if h.citation]
    assert "[1992] HCA 23" in citations


def test_parse_sino_hits_heading_and_external_url():
    html = FIXTURE_REAL.read_text(encoding="utf-8")
    hits = parse_sino_search_html(html)
    assert any(h.database_heading for h in hits)
    assert any(h.url.startswith("https://") for h in hits)


def test_parse_live_fixture_has_case_hits():
    html = FIXTURE_LIVE.read_text(encoding="utf-8")
    hits = parse_sino_search_html(html)
    assert len(hits) > 0
    assert any("/cases/cth" in h.url for h in hits)
