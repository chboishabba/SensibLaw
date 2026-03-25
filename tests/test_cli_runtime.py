from __future__ import annotations

import io
from contextlib import redirect_stderr

from scripts.cli_runtime import build_progress_callback


def test_build_progress_callback_disabled_returns_none() -> None:
    assert build_progress_callback(enabled=False) is None


def test_human_progress_writes_readable_stderr() -> None:
    callback = build_progress_callback(enabled=True, fmt="human")
    stream = io.StringIO()
    with redirect_stderr(stream):
        assert callback is not None
        callback(
            "persist_progress",
            {
                "section": "facts",
                "completed": 3,
                "total": 10,
                "elapsed_seconds": 1.5,
                "items_per_second": 2.0,
                "eta_seconds_remaining": 3.5,
                "message": "Persisting facts.",
            },
        )
    output = stream.getvalue()
    assert "[progress] persist_progress" in output
    assert "section=facts" in output
    assert "3/10" in output
    assert "eta=3.5s" in output


def test_bar_progress_falls_back_to_human_when_not_tty(monkeypatch) -> None:
    callback = build_progress_callback(enabled=True, fmt="bar")
    stream = io.StringIO()
    monkeypatch.setattr(stream, "isatty", lambda: False)
    with redirect_stderr(stream):
        assert callback is not None
        callback(
            "scan_progress",
            {
                "section": "wikidata_scan",
                "completed": 2,
                "total": 4,
                "message": "Scanning candidates.",
            },
        )
    output = stream.getvalue()
    assert "[progress] scan_progress" in output
    assert "2/4" in output


def test_json_progress_writes_json_line() -> None:
    callback = build_progress_callback(enabled=True, fmt="json")
    stream = io.StringIO()
    with redirect_stderr(stream):
        assert callback is not None
        callback("stage", {"section": "demo", "completed": 1, "total": 1})
    output = stream.getvalue().strip()
    assert '"stage": "stage"' in output
    assert '"section": "demo"' in output
