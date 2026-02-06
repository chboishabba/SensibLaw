from __future__ import annotations

import json
import wave
from pathlib import Path

import pytest

from sensiblaw.ingest.whisperx_adapter import import_whisperx_transcript
from storage.core import Storage


def _make_silent_wav(path: Path, seconds: float = 1.0, rate: int = 16000) -> None:
    nframes = int(seconds * rate)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(rate)
        wf.writeframes(b"\x00\x00" * nframes)


@pytest.fixture()
def sample_transcript() -> dict:
    here = Path(__file__).parent
    return json.loads((here / "fixtures" / "whisperx" / "sample.json").read_text())


def test_whisperx_importer_creates_envelope_and_segments(tmp_path, sample_transcript):
    audio_path = tmp_path / "sample.wav"
    _make_silent_wav(audio_path, seconds=1.0)
    store = Storage(tmp_path / "test.db")
    try:
        env_id = import_whisperx_transcript(store, sample_transcript, audio_path=audio_path)
        # Envelope exists
        env = store.get_node(env_id)
        assert env is not None
        assert env.type == "execution_envelope"
        assert env.data["source"] == "whisperx_webui"
        assert env.data["segment_count"] == 2
        assert "provenance" in env.data
        assert "audio_hash" in env.data

        # Segments recorded
        rows = store.conn.execute("SELECT id, data FROM nodes WHERE type = 'audio_segment'").fetchall()
        assert len(rows) == 2
        for row in rows:
            data = json.loads(row["data"])
            # confidence retained
            assert "confidence" in data
            # provenance present
            assert data["provenance"]["envelope_id"] == env_id
            # no semantic labels beyond allowed keys
            forbidden_keys = {"intent", "emotion", "action_item"}
            assert forbidden_keys.isdisjoint(data.keys())
    finally:
        store.close()
