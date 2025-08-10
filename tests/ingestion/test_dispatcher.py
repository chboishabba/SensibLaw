import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.ingestion.dispatcher import SourceDispatcher


def test_dispatcher_triggers_fetchers(monkeypatch):
    sleeps = []

    def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr("src.ingestion.dispatcher.time.sleep", fake_sleep)

    dispatcher = SourceDispatcher(ROOT / "data" / "foundation_sources.json")
    results = dispatcher.dispatch(
        names=["Federal Register of Legislation", "AustLII (reference only)"]
    )

    assert 1 in sleeps

    fed = next(r for r in results if r["name"] == "Federal Register of Legislation")
    assert set(fed["fetchers"]) == {"official", "pdf"}

    austlii = next(r for r in results if r["name"] == "AustLII (reference only)")
    assert austlii["fetchers"] == ["austlii"]
