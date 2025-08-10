import json
from datetime import date
from pathlib import Path
import sys

import pytest

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src import cli
from src.austlii_client import AustLIIClient
from src.models.document import Document, DocumentMetadata


def run_cli(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", argv)
    cli.main()


def test_austlii_fetch_and_view(tmp_path, monkeypatch, capsys):
    db = tmp_path / "store.db"
    urls: list[str] = []

    def fake_fetch(self, url: str) -> Document:
        urls.append(url)
        name = url.split("/")[-1].replace(".html", "")
        meta = DocumentMetadata(
            jurisdiction="AU",
            citation=name,
            date=date(2020, 1, 1),
            canonical_id=name,
            provenance=url,
            ontology_tags={"test": ["tag"]},
        )
        text = f"{name} body must act"
        return Document(meta, text)

    monkeypatch.setattr(AustLIIClient, "fetch_legislation", fake_fetch)

    run_cli(
        monkeypatch,
        [
            "sensiblaw",
            "austlii-fetch",
            "--db",
            str(db),
            "--act",
            "http://example.com/act",
            "--sections",
            "s1,s2",
        ],
    )
    capsys.readouterr()

    assert any(u.endswith("table.html") for u in urls)
    assert any(u.endswith("notes.html") for u in urls)
    assert any(u.endswith("s1.html") for u in urls)
    assert any(u.endswith("s2.html") for u in urls)

    run_cli(
        monkeypatch,
        ["sensiblaw", "view", "--db", str(db), "--id", "s1"],
    )
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["text"].startswith("s1 body")
    assert data["provenance"].endswith("s1.html")
    assert data["ontology_tags"]["test"] == ["tag"]
    assert data["rules"]  # rule extracted from "must"

