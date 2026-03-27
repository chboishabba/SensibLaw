import os

import pytest

from src.sources.jade import JadeAdapter
from src.sources.jade_paragraphs import parse_jade_paragraphs


pytestmark = [pytest.mark.live]


def test_live_jade_fetch_and_local_paragraph_parse_opt_in():
    if os.environ.get("RUN_LIVE_JADE") != "1":
        pytest.skip("Set RUN_LIVE_JADE=1 to run live JADE fetch sanity check.")

    adapter = JadeAdapter()
    fetched = adapter.fetch("[2011] HCA 1")
    paragraphs = parse_jade_paragraphs(fetched.content, content_type=fetched.content_type)
    assert fetched.metadata["source"] == "jade.io"
    assert len(paragraphs) > 0
