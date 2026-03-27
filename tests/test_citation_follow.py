from pathlib import Path
import json

from src.citations.normalize import CitationKey
from src.ingestion.citation_follow import (
    CitationRef,
    extract_citations,
    follow_citations_bounded,
    resolve_austlii_search_plan,
    resolve_citation,
    resolve_citation_candidates,
)


def test_extract_citations_simple():
    text = "See [1992] HCA 23 and also [2003] HCA 2."
    refs = extract_citations(text)
    assert len(refs) == 2
    assert refs[0].key == CitationKey(1992, "HCA", 23)


def test_resolve_prefers_jade_and_skips_existing():
    ref = CitationRef(raw_text="[1992] HCA 23", offset=0, key=CitationKey(1992, "HCA", 23))
    plan = resolve_citation(ref, store_has=lambda k: False)
    assert plan and plan.source == "jade" and "content/ext/mnc" in (plan.url or "")

    plan2 = resolve_citation(ref, store_has=lambda k: True)
    assert plan2 is None


def test_resolve_candidates_include_austlii_fallback():
    ref = CitationRef(raw_text="[1992] HCA 23", offset=0, key=CitationKey(1992, "HCA", 23))
    plans = resolve_citation_candidates(ref, store_has=lambda k: False)
    assert [plan.source for plan in plans] == ["jade", "austlii"]
    assert plans[1].url and plans[1].url.endswith("/au/cases/cth/HCA/1992/23.html")


def test_follow_citations_bounded_respects_limits():
    seed_text = "See [1992] HCA 23 and [2003] HCA 2."

    fetch_calls = []

    def fetch(plan):
        fetch_calls.append(plan.citation)
        # return bytes that contain no further citations
        return b"%PDF-1.4 fake"

    def ingest(bytes_data, citation_key, parent_id):
        # doc_id increments with length of fetch_calls
        doc_id = len(fetch_calls)
        return doc_id, ""  # no further citations

    ingested = follow_citations_bounded(
        seed_text=seed_text,
        fetch=fetch,
        ingest=ingest,
        store_has=lambda k: False,
        max_depth=1,
        max_new_docs=1,  # volume bound
    )

    assert len(ingested) == 1
    assert len(fetch_calls) == 1  # volume bound enforced


def test_follow_citations_bounded_falls_back_to_austlii_after_jade_failure():
    seed_text = "See [1992] HCA 23."
    sources = []

    def fetch(plan):
        sources.append(plan.source)
        if plan.source == "jade":
            raise RuntimeError("jade unavailable")
        return b"<html>ok</html>"

    def ingest(bytes_data, citation_key, parent_id):
        return 1, ""

    ingested = follow_citations_bounded(
        seed_text=seed_text,
        fetch=fetch,
        ingest=ingest,
        store_has=lambda k: False,
        max_depth=1,
        max_new_docs=1,
    )

    assert ingested == {1}
    assert sources == ["jade", "austlii"]


def test_resolve_austlii_search_plan_requires_exact_citation_match():
    ref = CitationRef(raw_text="[1992] HCA 23", offset=0, key=CitationKey(1992, "HCA", 23))

    class FakeSearchAdapter:
        def search(self, query):
            return (
                '<html><body>'
                '<a href="/au/cases/cth/HCA/1992/23.html">Mabo v Queensland (No 2) [1992] HCA 23</a>'
                '<a href="/au/cases/cth/HCA/1992/24.html">Other Case [1992] HCA 24</a>'
                '</body></html>'
            )

    plan = resolve_austlii_search_plan(ref, search_adapter=FakeSearchAdapter())
    assert plan is not None
    assert plan.source == "austlii_search"
    assert plan.url and plan.url.endswith("/au/cases/cth/HCA/1992/23.html")


def test_follow_citations_bounded_uses_sino_after_direct_fetch_failures():
    seed_text = "See [1992] HCA 23."
    sources = []

    def fetch(plan):
        sources.append(plan.source)
        if plan.source in {"jade", "austlii"}:
            raise RuntimeError(f"{plan.source} unavailable")
        return b"<html>ok</html>"

    def ingest(bytes_data, citation_key, parent_id):
        return 1, ""

    def resolve_search(ref):
        return type("Plan", (), {
            "source": "austlii_search",
            "url": "https://www.austlii.edu.au/au/cases/cth/HCA/1992/23.html",
            "query": ref.raw_text,
            "vc": "/au",
            "citation": ref.key,
        })()

    ingested = follow_citations_bounded(
        seed_text=seed_text,
        fetch=fetch,
        ingest=ingest,
        store_has=lambda k: False,
        max_depth=1,
        max_new_docs=1,
        resolve_search=resolve_search,
    )

    assert ingested == {1}
    assert sources == ["jade", "austlii", "austlii_search"]


def test_unresolved_written_to_path(tmp_path):
    seed_text = "See [bad citation]."  # does not match neutral pattern
    unresolved = []

    ingested = follow_citations_bounded(
        seed_text=seed_text,
        fetch=lambda p: b"",
        ingest=lambda b, c, p: (0, ""),
        store_has=lambda k: False,
        max_depth=0,
        max_new_docs=1,
        unresolved=unresolved,
        unresolved_path=tmp_path / "unresolved.json",
    )

    assert ingested == set()
    data = json.loads((tmp_path / "unresolved.json").read_text(encoding="utf-8"))
    assert data == []  # no neutral citations extracted, but file written
