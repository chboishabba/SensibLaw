import json
import subprocess
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


def test_bridge_batch_emitter_roundtrips_into_external_refs_cli(tmp_path, capsys):
    db_path = tmp_path / "ontology.db"
    connection = sqlite3.connect(db_path)
    try:
        ensure_database(connection)
        cur = connection.cursor()
        actor_ids = {}
        for label in [
            "United Nations",
            "United Nations Security Council",
            "International Criminal Court",
            "International Court of Justice",
        ]:
            cur.execute("INSERT INTO actors(kind, label) VALUES (?, ?)", ("ORG", label))
            actor_ids[label] = int(cur.lastrowid)
        connection.commit()
    finally:
        connection.close()

    anchor_map_path = tmp_path / "anchors.json"
    anchor_map_path.write_text(
        json.dumps(
            {
                "institution:united_nations": {"actor_id": actor_ids["United Nations"]},
                "institution:united_nations_security_council": {
                    "actor_id": actor_ids["United Nations Security Council"]
                },
                "court:international_criminal_court": {
                    "actor_id": actor_ids["International Criminal Court"]
                },
                "court:international_court_of_justice": {
                    "actor_id": actor_ids["International Court of Justice"]
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    batch_path = tmp_path / "bridge_batch.json"
    script_path = ROOT / "scripts" / "emit_bridge_external_refs_batch.py"
    subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--text",
            "UN inspectors briefed the United Nations Security Council while the ICC and ICJ were discussed.",
            "--anchor-map",
            str(anchor_map_path),
            "--output",
            str(batch_path),
        ],
        check=True,
        cwd=str(ROOT),
    )

    cli_main.main(
        [
            "ontology",
            "external-refs-upsert",
            "--db",
            str(db_path),
            "--file",
            str(batch_path),
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["actor_external_refs"] == 4
    assert payload["concept_external_refs"] == 0

    connection = sqlite3.connect(db_path)
    try:
        rows = connection.execute(
            "SELECT actor_id, provider, external_id FROM actor_external_refs ORDER BY actor_id, external_id"
        ).fetchall()
        assert {(row[0], row[1], row[2]) for row in rows} == {
            (actor_ids["United Nations"], "wikidata", "Q1065"),
            (actor_ids["United Nations Security Council"], "wikidata", "Q37470"),
            (actor_ids["International Criminal Court"], "wikidata", "Q47488"),
            (actor_ids["International Court of Justice"], "wikidata", "Q7801"),
        }
    finally:
        connection.close()
