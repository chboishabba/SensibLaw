import os
import pytest

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
