import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import List

import src.ingest.polis as polis
from src.cli import main


class FakeResponse:
    def __init__(self, data, *, status_code: int = 200):
        self._data = data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code and self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")
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


def test_fetch_conversation_uses_cache(monkeypatch, tmp_path):
    polis._REQUEST_CACHE.clear()
    fixture = json.loads(
        (Path(__file__).resolve().parent.parent / "fixtures" / "polis_conversation.json").read_text()
    )

    calls: List[str] = []

    def fake_get(url, timeout=30):
        calls.append(url)
        return FakeResponse(fixture)

    monkeypatch.setattr(polis, "DATA_DIR", tmp_path / "concepts")
    monkeypatch.setattr(polis, "requests", SimpleNamespace(get=fake_get))

    first = polis.fetch_conversation("test", limit=1)
    second = polis.fetch_conversation("test", limit=1)

    assert calls == [f"{polis.POLIS_API}/test"]
    assert first == second


def test_fetch_conversation_retries(monkeypatch, tmp_path):
    polis._REQUEST_CACHE.clear()
    fixture = json.loads(
        (Path(__file__).resolve().parent.parent / "fixtures" / "polis_conversation.json").read_text()
    )

    attempts = 0
    sleeps: List[float] = []

    def fake_sleep(amount: float) -> None:
        sleeps.append(amount)

    def fake_get(url, timeout=30):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            return FakeResponse({}, status_code=500)
        return FakeResponse(fixture)

    monkeypatch.setattr(polis, "DATA_DIR", tmp_path / "concepts")
    monkeypatch.setattr(polis, "time", SimpleNamespace(sleep=fake_sleep))
    monkeypatch.setattr(polis, "requests", SimpleNamespace(get=fake_get))

    seeds = polis.fetch_conversation(
        "retry",
        max_retries=3,
        sleep_between_retries=0.25,
    )

    assert attempts == 3
    assert sleeps == [0.25, 0.5]
    assert len(seeds) == 2
