from __future__ import annotations

import json
from pathlib import Path

from sensiblaw.ingest.asr_adapter import import_asr_transcript
from storage.core import Storage


def test_generic_asr_importer(tmp_path):
    transcript = {
        "model": "example-asr",
        "language": "en",
        "segments": [
            {"start": 0.0, "end": 0.5, "text": "hi", "confidence": 0.8},
            {"start": 0.5, "end": 1.0, "text": "there", "confidence": 0.9},
        ],
    }
    store = Storage(tmp_path / "test.db")
    try:
        env_id = import_asr_transcript(store, transcript, source="asr_test")
        env = store.get_node(env_id)
        assert env is not None
        assert env.type == "execution_envelope"
        assert env.data["toolchain"]["model"] == "example-asr"
        rows = store.conn.execute("SELECT data FROM nodes WHERE type='audio_segment'").fetchall()
        assert len(rows) == 2
        for row in rows:
            data = json.loads(row["data"])
            assert "confidence" in data
            assert data["provenance"]["envelope_id"] == env_id
            assert {"intent", "emotion", "action_item"}.isdisjoint(data.keys())
    finally:
        store.close()
