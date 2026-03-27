from pathlib import Path

from src.sources.jade_search import (
    JadeSearchAdapter,
    build_jade_search_url,
    fallback_hit_for_query,
    parse_jade_search_html,
)


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "jade" / "search_results_sample.html"


def test_build_jade_search_url_uses_path_template():
    url = build_jade_search_url("https://jade.io/search", "[2021] FamCA 83")
    assert url == "https://jade.io/search/%5B2021%5D%20FamCA%2083"


def test_parse_jade_search_html_extracts_article_and_mnc_links():
    hits = parse_jade_search_html(FIXTURE.read_text(encoding="utf-8"))
    assert [hit.citation for hit in hits[:2]] == ["[2021] FamCA 83", "[2010] FamCAFC 13"]
    assert hits[0].url == "https://jade.io/article/791483"
    assert hits[1].url == "https://jade.io/mnc/2010/FamCAFC/13"


def test_fallback_hit_for_query_builds_mnc_url():
    hit = fallback_hit_for_query("[2021] FamCA 83")
    assert hit is not None
    assert hit.citation == "[2021] FamCA 83"
    assert hit.url == "https://jade.barnet.com.au/mnc/2021/FamCA/83"


def test_jade_search_adapter_builds_one_request():
    calls: list[str] = []

    class FakeSession:
        def get(self, url, headers, timeout):
            calls.append(url)

            class Response:
                text = "<html></html>"

                def raise_for_status(self):
                    return None

            return Response()

    adapter = JadeSearchAdapter(session=FakeSession())
    html = adapter.search("Marvel & Marvel")
    assert html == "<html></html>"
    assert calls == ["https://jade.io/search/Marvel%20%26%20Marvel"]
