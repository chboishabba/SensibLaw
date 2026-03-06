import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from cli import __main__ as cli_main
from src.ontology import wikidata as wikidata_mod
from src.ontology.wikidata import FINDER_SCHEMA_VERSION, find_qualifier_drift_candidates


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


def _statement(qid: str, value_qid: str, *, time: str | None = None, reason_qid: str | None = None):
    qualifiers = {}
    if time is not None:
        qualifiers["P585"] = [{"datavalue": {"value": {"time": time}}}]
    if reason_qid is not None:
        qualifiers["P7452"] = [{"datavalue": {"value": {"id": reason_qid}}}]
    return {
        "id": f"{qid}$statement",
        "rank": "preferred",
        "mainsnak": {"datavalue": {"value": {"id": value_qid}}},
        "qualifiers": qualifiers,
        "references": [],
    }


def _entity_export(qid: str, claims: dict) -> dict:
    return {
        "entities": {
            qid: {
                "id": qid,
                "claims": claims,
            }
        }
    }


def _fake_requests_get(url, *, params=None, headers=None, timeout=None):
    if url == wikidata_mod.SPARQL_ENDPOINT:
        return _FakeResponse(
            {
                "results": {
                    "bindings": [
                        {
                            "item": {"value": "http://www.wikidata.org/entity/Q1"},
                            "itemLabel": {"value": "Candidate drift"},
                            "property_pid": {"value": "P166"},
                            "statement": {"value": "http://www.wikidata.org/entity/statement/Q1-s1"},
                            "qualifier_pids": {"value": "P585"},
                        },
                        {
                            "item": {"value": "http://www.wikidata.org/entity/Q2"},
                            "itemLabel": {"value": "Stable baseline"},
                            "property_pid": {"value": "P39"},
                            "statement": {"value": "http://www.wikidata.org/entity/statement/Q2-s1"},
                            "qualifier_pids": {"value": "P580,P582"},
                        },
                    ]
                }
            }
        )
    if url == wikidata_mod.MEDIAWIKI_API_ENDPOINT:
        title = params["titles"]
        if title == "Q1":
            return _FakeResponse(
                {
                    "query": {
                        "pages": {
                            "1": {
                                "revisions": [
                                    {"revid": 200, "timestamp": "2026-03-07T00:00:00Z"},
                                    {"revid": 100, "timestamp": "2025-03-07T00:00:00Z"},
                                ]
                            }
                        }
                    }
                }
            )
        if title == "Q2":
            return _FakeResponse(
                {
                    "query": {
                        "pages": {
                            "2": {
                                "revisions": [
                                    {"revid": 210, "timestamp": "2026-03-07T00:00:00Z"},
                                    {"revid": 110, "timestamp": "2025-03-07T00:00:00Z"},
                                ]
                            }
                        }
                    }
                }
            )
    if url.endswith("Q1.json?revision=100"):
        return _FakeResponse(
            _entity_export(
                "Q1",
                {
                    "P166": [
                        _statement("Q1", "Qaward", time="+1950-01-01T00:00:00Z"),
                    ]
                },
            )
        )
    if url.endswith("Q1.json?revision=200"):
        return _FakeResponse(
            _entity_export(
                "Q1",
                {
                    "P166": [
                        _statement(
                            "Q1",
                            "Qaward",
                            time="+1950-01-01T00:00:00Z",
                            reason_qid="Qreason",
                        ),
                    ]
                },
            )
        )
    if url.endswith("Q2.json?revision=110"):
        return _FakeResponse(
            _entity_export(
                "Q2",
                {
                    "P39": [
                        {
                            "id": "Q2$statement",
                            "rank": "preferred",
                            "mainsnak": {"datavalue": {"value": {"id": "Qoffice"}}},
                            "qualifiers": {
                                "P580": [{"datavalue": {"value": {"time": "+2000-01-01T00:00:00Z"}}}],
                                "P582": [{"datavalue": {"value": {"time": "+2001-01-01T00:00:00Z"}}}],
                            },
                            "references": [],
                        }
                    ]
                },
            )
        )
    if url.endswith("Q2.json?revision=210"):
        return _FakeResponse(
            _entity_export(
                "Q2",
                {
                    "P39": [
                        {
                            "id": "Q2$statement",
                            "rank": "preferred",
                            "mainsnak": {"datavalue": {"value": {"id": "Qoffice"}}},
                            "qualifiers": {
                                "P580": [{"datavalue": {"value": {"time": "+2000-01-01T00:00:00Z"}}}],
                                "P582": [{"datavalue": {"value": {"time": "+2001-01-01T00:00:00Z"}}}],
                            },
                            "references": [],
                        }
                    ]
                },
            )
        )
    raise AssertionError(f"unexpected request: {url} params={params}")


def test_find_qualifier_drift_candidates_detects_real_change(monkeypatch) -> None:
    monkeypatch.setattr(wikidata_mod.requests, "get", _fake_requests_get)

    report = find_qualifier_drift_candidates(
        property_filter=("P166", "P39"),
        candidate_limit=5,
        revision_limit=2,
    )

    assert report["schema_version"] == FINDER_SCHEMA_VERSION
    assert report["candidate_count"] == 2
    assert report["confirmed_drift_cases"][0]["qid"] == "Q1"
    assert report["confirmed_drift_cases"][0]["qualifier_drift"][0]["severity"] == "high"
    assert report["stable_baselines"][0]["qid"] == "Q2"
    assert report["failures"] == []


def test_wikidata_find_qualifier_drift_cli_writes_report(tmp_path, capsys, monkeypatch) -> None:
    monkeypatch.setattr(wikidata_mod.requests, "get", _fake_requests_get)
    out_path = tmp_path / "qualifier_drift_finder.json"

    cli_main.main(
        [
            "wikidata",
            "find-qualifier-drift",
            "--property",
            "P166",
            "--property",
            "P39",
            "--candidate-limit",
            "5",
            "--revision-limit",
            "2",
            "--output",
            str(out_path),
        ]
    )

    stdout = json.loads(capsys.readouterr().out)
    file_payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert stdout["output"] == str(out_path)
    assert stdout["confirmed_drift_case_count"] == 1
    assert file_payload["confirmed_drift_cases"][0]["qid"] == "Q1"
    assert file_payload["stable_baselines"][0]["qid"] == "Q2"


def test_find_qualifier_drift_candidates_reports_candidate_query_failure(monkeypatch) -> None:
    def _raise_timeout(url, *, params=None, headers=None, timeout=None):
        raise requests.exceptions.ReadTimeout("timed out")

    monkeypatch.setattr(wikidata_mod.requests, "get", _raise_timeout)

    report = find_qualifier_drift_candidates(
        property_filter=("P166",),
        candidate_limit=2,
        revision_limit=2,
    )

    assert report["candidate_count"] == 0
    assert report["confirmed_drift_cases"] == []
    assert report["stable_baselines"] == []
    assert report["failures"][0]["stage"] == "candidate_query"
