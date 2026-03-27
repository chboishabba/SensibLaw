import json
from datetime import date
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src import cli
from src.fact_intake import build_authority_ingest_summary, list_authority_ingest_runs
from src.sources.austlii_fetch import AustLiiFetchAdapter
from src.sources.austlii_sino import AustLiiSearchAdapter
from src.sources.base import FetchResult
from src.sources.jade import JadeAdapter
from src.sources.jade_search import JadeSearchAdapter


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "austlii"
JADE_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "jade"


def run_cli(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", argv)
    cli.main()


def test_austlii_search_can_emit_local_paragraphs(monkeypatch, capsys, tmp_path):
    html = (FIXTURES / "sino_results_realistic.html").read_text(encoding="utf-8")
    fetched_html = (FIXTURES / "judgment_paragraphs_sample.html").read_text(encoding="utf-8")
    db_path = tmp_path / "itir.sqlite"

    monkeypatch.setattr(AustLiiSearchAdapter, "search", lambda self, q: html)
    monkeypatch.setattr(
        AustLiiFetchAdapter,
        "fetch",
        lambda self, url: FetchResult(
            content=fetched_html.encode("utf-8"),
            content_type="text/html",
            url=url,
            metadata={"source": "austlii", "status_code": 200},
        ),
    )

    run_cli(
        monkeypatch,
        [
            "sensiblaw",
            "austlii-search",
            "--query",
            "mabo",
            "--pick",
            "by_mnc",
            "--mnc",
            "[1992] HCA 23",
            "--paragraph",
            "120",
            "--paragraph-window",
            "1",
            "--db-path",
            str(db_path),
        ],
    )
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["selection_reason"] == "by_mnc:[1992] HCA 23"
    assert data["paragraph_count"] == 3
    assert [row["number"] for row in data["paragraphs"]] == [119, 120, 121]
    assert data["persistence"]["segment_count"] == 3

    import sqlite3

    with sqlite3.connect(str(db_path)) as conn:
        runs = list_authority_ingest_runs(conn, authority_kind="austlii")
        assert runs[0]["segment_count"] == 3
        summary = build_authority_ingest_summary(conn, ingest_run_id=runs[0]["ingest_run_id"])
        assert summary["run"]["selection_reason"] == "by_mnc:[1992] HCA 23"
        assert [row["paragraph_number"] for row in summary["segments"]] == [119, 120, 121]


def test_austlii_case_fetch_can_resolve_citation_and_emit_local_paragraphs(monkeypatch, capsys, tmp_path):
    fetched_html = (FIXTURES / "judgment_paragraphs_sample.html").read_text(encoding="utf-8")
    db_path = tmp_path / "itir.sqlite"

    monkeypatch.setattr(
        AustLiiFetchAdapter,
        "fetch",
        lambda self, url: FetchResult(
            content=fetched_html.encode("utf-8"),
            content_type="text/html",
            url=url,
            metadata={"source": "austlii", "status_code": 200, "path": "/au/cases/cth/HCA/1992/23.html"},
        ),
    )

    run_cli(
        monkeypatch,
        [
            "sensiblaw",
            "austlii-case-fetch",
            "--citation",
            "[1992] HCA 23",
            "--paragraph",
            "120",
            "--paragraph-window",
            "1",
            "--db-path",
            str(db_path),
        ],
    )
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["selection_reason"] == "by_citation:[1992] HCA 23"
    assert data["url"].endswith("/au/cases/cth/HCA/1992/23.html")
    assert [row["number"] for row in data["paragraphs"]] == [119, 120, 121]

    import sqlite3

    with sqlite3.connect(str(db_path)) as conn:
        runs = list_authority_ingest_runs(conn, authority_kind="austlii")
        summary = build_authority_ingest_summary(conn, ingest_run_id=runs[0]["ingest_run_id"])
        assert summary["run"]["selection_reason"] == "by_citation:[1992] HCA 23"
        assert [row["paragraph_number"] for row in summary["segments"]] == [119, 120, 121]


def test_jade_fetch_can_emit_local_paragraphs(monkeypatch, capsys, tmp_path):
    fetched_text = (JADE_FIXTURES / "judgment_paragraphs_sample.txt").read_text(encoding="utf-8")
    db_path = tmp_path / "itir.sqlite"

    monkeypatch.setattr(
        JadeAdapter,
        "fetch",
        lambda self, citation: FetchResult(
            content=fetched_text.encode("utf-8"),
            content_type="text/plain",
            url="https://jade.barnet.com.au/content/ext/mnc/2021/famca/83",
            metadata={"source": "jade.io", "status_code": 200, "citation": citation},
        ),
    )

    run_cli(
        monkeypatch,
        [
            "sensiblaw",
            "jade-fetch",
            "--citation",
            "[2021] FamCA 83",
            "--paragraph",
            "120",
            "--paragraph-window",
            "1",
            "--db-path",
            str(db_path),
        ],
    )
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["citation"] == "[2021] FamCA 83"
    assert data["paragraph_count"] == 3
    assert [row["number"] for row in data["paragraphs"]] == [119, 120, 121]
    assert data["persistence"]["segment_count"] == 3

    import sqlite3

    with sqlite3.connect(str(db_path)) as conn:
        runs = list_authority_ingest_runs(conn, authority_kind="jade")
        assert runs[0]["citation"] == "[2021] FamCA 83"
        summary = build_authority_ingest_summary(conn, ingest_run_id=runs[0]["ingest_run_id"])
        assert summary["run"]["ingest_mode"] == "fetch"
        assert [row["paragraph_number"] for row in summary["segments"]] == [119, 120, 121]


def test_jade_search_can_emit_local_paragraphs(monkeypatch, capsys, tmp_path):
    html = (JADE_FIXTURES / "search_results_sample.html").read_text(encoding="utf-8")
    fetched_text = (JADE_FIXTURES / "judgment_paragraphs_sample.txt").read_text(encoding="utf-8")
    db_path = tmp_path / "itir.sqlite"

    monkeypatch.setattr(JadeSearchAdapter, "search", lambda self, query: html)
    monkeypatch.setattr(
        JadeAdapter,
        "fetch",
        lambda self, citation: FetchResult(
            content=fetched_text.encode("utf-8"),
            content_type="text/plain",
            url="https://jade.io/article/791483",
            metadata={"source": "jade.io", "status_code": 200, "citation": citation},
        ),
    )

    run_cli(
        monkeypatch,
        [
            "sensiblaw",
            "jade-search",
            "--query",
            "Marvel & Marvel",
            "--pick",
            "by_mnc",
            "--mnc",
            "[2021] FamCA 83",
            "--paragraph",
            "120",
            "--paragraph-window",
            "1",
            "--db-path",
            str(db_path),
        ],
    )
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["selection_reason"] == "by_mnc:[2021] FamCA 83"
    assert data["fallback_hit_used"] is False
    assert data["paragraph_count"] == 3
    assert [row["number"] for row in data["paragraphs"]] == [119, 120, 121]
    assert data["persistence"]["segment_count"] == 3

    import sqlite3

    with sqlite3.connect(str(db_path)) as conn:
        runs = list_authority_ingest_runs(conn, authority_kind="jade")
        assert runs[0]["ingest_mode"] == "search"
        summary = build_authority_ingest_summary(conn, ingest_run_id=runs[0]["ingest_run_id"])
        assert summary["run"]["selection_reason"] == "by_mnc:[2021] FamCA 83"
        assert [row["paragraph_number"] for row in summary["segments"]] == [119, 120, 121]
