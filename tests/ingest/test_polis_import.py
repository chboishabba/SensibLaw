import json
import sys
from pathlib import Path

import src.ingest.polis as polis
from src.cli import main


class FakeResponse:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        return None

    def json(self):
        return self._data


def test_polis_import(monkeypatch, tmp_path):
    fixture = json.loads(
        (Path(__file__).resolve().parent.parent / "fixtures" / "polis_conversation.json").read_text()
    )

    def fake_get(url, timeout=30):
        return FakeResponse(fixture)

    # Redirect output locations to the temporary directory
    monkeypatch.setattr(polis, "DATA_DIR", tmp_path / "concepts")
    monkeypatch.setattr(
        polis, "requests", __import__("types").SimpleNamespace(get=fake_get)
    )

    out_dir = tmp_path / "packs"
    argv = [
        "sensiblaw",
        "polis",
        "import",
        "--conversation",
        "test",
        "--out",
        str(out_dir),
    ]
    monkeypatch.setattr(sys, "argv", argv)

    main()

    seeds_path = tmp_path / "concepts" / "polis_test.json"
    data = json.loads(seeds_path.read_text())
    assert data == {
        "concepts": [
            {
                "id": "polis_test_1",
                "label": "Cats are better than dogs",
                "cluster": "Feline Fans",
            },
            {
                "id": "polis_test_2",
                "label": "Dogs are the best pets",
                "cluster": "Canine Crew",
            },
        ],
        "relations": [],
    }
    assert (out_dir / "polis_test_1" / "verify.sh").exists()
