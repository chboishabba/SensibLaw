import os
import pytest

from src.sources.austlii_fetch import AustLiiFetchAdapter
from src.sources.austlii_paragraphs import parse_austlii_paragraphs
from src.sources.austlii_sino import AustLiiSearchAdapter, SinoQuery
from src.sources.austlii_sino_parse import parse_sino_search_html


pytestmark = [pytest.mark.live]


def test_live_sino_opt_in():
    if os.environ.get("RUN_LIVE_AUSTLII") != "1":
        pytest.skip("Set RUN_LIVE_AUSTLII=1 to run live AustLII SINO sanity check.")

    adapter = AustLiiSearchAdapter()
    html = adapter.search(SinoQuery(meta="/au", query="mabo", results=5, offset=0))
    hits = parse_sino_search_html(html)
    assert len(hits) > 0
    # Ensure at least one case-like link exists
    assert any("/cases/" in h.url for h in hits)


def test_live_fetch_and_local_paragraph_parse_opt_in():
    if os.environ.get("RUN_LIVE_AUSTLII") != "1":
        pytest.skip("Set RUN_LIVE_AUSTLII=1 to run live AustLII fetch sanity check.")

    adapter = AustLiiFetchAdapter()
    fetched = adapter.fetch("https://www.austlii.edu.au/cgi-bin/viewdoc/au/cases/cth/HCA/2010/1.html")
    paragraphs = parse_austlii_paragraphs(fetched.content.decode("utf-8", errors="replace"))
    assert fetched.metadata["source"] == "austlii"
    assert len(paragraphs) > 0
