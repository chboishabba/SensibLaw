from __future__ import annotations

from io import StringIO

from src.ontology.external_enrichment import ExternalLookupDemand
from src.ontology.wikimedia_providers import (
    MemoryLookupCache,
    WikidataProvider,
    WikimediaMicrobatchRunner,
    WiktionaryProvider,
)


class JsonResponse:
    status_code = 200

    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self.payload


class WikidataSession:
    def __init__(self) -> None:
        self.calls = []

    def get(self, _url, **kwargs):
        params = kwargs["params"]
        self.calls.append(dict(params))
        if params["action"] == "wbsearchentities":
            return JsonResponse(
                {
                    "search": [
                        {
                            "id": "Q30",
                            "label": "United States of America",
                            "description": "country in North America",
                            "score": 100,
                        }
                    ]
                }
            )
        return JsonResponse(
            {
                "entities": {
                    "Q30": {
                        "labels": {"en": {"value": "United States of America"}},
                        "aliases": {
                            "en": [
                                {"value": "United States"},
                                {"value": "the United States"},
                                {"value": "U.S."},
                                {"value": "America"},
                            ]
                        },
                        "descriptions": {
                            "en": {"value": "country in North America"}
                        },
                        "claims": {},
                    }
                }
            }
        )


class WiktionarySession:
    def __init__(self) -> None:
        self.calls = []

    def get(self, _url, **kwargs):
        params = kwargs["params"]
        self.calls.append(dict(params))
        return JsonResponse(
            {
                "query": {
                    "pages": {
                        "1": {"pageid": 1, "title": "bank", "extract": "A financial institution."},
                        "2": {"pageid": 2, "title": "trust", "extract": "Confidence or reliance."},
                    }
                }
            }
        )


def test_wikidata_runner_deduplicates_lookup_and_reuses_cache() -> None:
    session = WikidataSession()
    provider = WikidataProvider(session=session)
    runner = WikimediaMicrobatchRunner(
        [provider],
        cache=MemoryLookupCache(),
        microbatch_size=8,
        request_budget_per_provider=10,
    )
    demands = (
        ExternalLookupDemand("demand:a", "factor:a", "the United States"),
        ExternalLookupDemand("demand:b", "factor:b", " the united states "),
    )

    first = runner.run(demands, progress_stream=StringIO())
    call_count = len(session.calls)
    second = runner.run(demands, progress_stream=StringIO())

    assert call_count == 2  # one search plus one batched detail request
    assert len(session.calls) == call_count
    assert len(first) == 2
    assert len(second) == 2
    assert first[0].candidate_sets[0].candidates[0].external_id == "Q30"
    assert first[0].candidate_sets[0].to_dict()["identity_closed"] is False
    assert all(row.cache_state == "fresh_cache_hit" for row in second)


def test_wiktionary_batches_multiple_titles_in_one_request() -> None:
    session = WiktionarySession()
    runner = WikimediaMicrobatchRunner(
        [WiktionaryProvider(session=session)],
        microbatch_size=16,
        request_budget_per_provider=2,
    )
    demands = (
        ExternalLookupDemand(
            "demand:bank",
            "factor:bank",
            "bank",
            demand_kind="lexical_sense",
        ),
        ExternalLookupDemand(
            "demand:trust",
            "factor:trust",
            "trust",
            demand_kind="lexical_sense",
        ),
    )

    results = runner.run(demands, progress_stream=StringIO())

    assert len(session.calls) == 1
    assert session.calls[0]["titles"] in {"bank|trust", "trust|bank"}
    assert {row.candidate_sets[0].candidates[0].label for row in results} == {
        "bank",
        "trust",
    }
    assert all(
        "lexical_sense_unresolved" in row.candidate_sets[0].residuals
        for row in results
    )
