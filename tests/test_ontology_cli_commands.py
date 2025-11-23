import json
import sqlite3
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from cli import __main__ as cli_main
from sensiblaw.db.dao import LegalSourceDAO, ensure_database


class _FakeResponse:
    def __init__(self, payload, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError()

    def json(self):
        return self._payload


def test_ontology_lookup_cli(monkeypatch, capsys):
    payload = [
        {"id": "a", "label": "Consent", "aliases": ["permission"]},
        {"id": "b", "label": "Consultation"},
    ]

    def fake_get(url, params=None):
        assert url == "https://ontology.test/lookup"
        assert params == {"q": "consent"}
        return _FakeResponse(payload)

    monkeypatch.setattr(cli_main.requests, "get", fake_get)

    cli_main.main(
        [
            "ontology",
            "lookup",
            "--term",
            "consent",
            "--url",
            "https://ontology.test/lookup",
            "--threshold",
            "0.5",
            "--limit",
            "1",
        ]
    )
    stdout = capsys.readouterr().out
    results = json.loads(stdout)
    assert results[0]["id"] == "a"
    assert results[0]["score"] >= 0.9


def test_ontology_upsert_cli(tmp_path, capsys):
    db_path = tmp_path / "ontology.db"
    cli_main.main(
        [
            "ontology",
            "upsert",
            "--db",
            str(db_path),
            "--legal-system",
            "AU.COMMON",
            "--category",
            "STATUTE",
            "--citation",
            "[2024] HCA 99",
            "--title",
            "Sample Title",
        ]
    )
    stdout = capsys.readouterr().out
    payload = json.loads(stdout)
    assert payload["citation"] == "[2024] HCA 99"

    connection = sqlite3.connect(db_path)
    try:
        dao = LegalSourceDAO(connection)
        record = dao.get_by_citation(
            legal_system_code="AU.COMMON", citation="[2024] HCA 99"
        )
        assert record
        assert record.title == "Sample Title"
    finally:
        connection.close()
