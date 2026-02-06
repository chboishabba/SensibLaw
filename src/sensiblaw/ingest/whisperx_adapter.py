from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from storage.core import Storage


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def import_whisperx_transcript(
    storage: Storage,
    transcript: Mapping[str, Any],
    *,
    audio_path: str | Path | None = None,
    source: str = "whisperx_webui",
) -> int:
    """Ingest a WhisperX transcript as an execution envelope + audio_segment nodes.

    No inference, emotion, or intent is added. Provenance and confidence are
    preserved as provided.
    """

    audio_hash = None
    if audio_path:
        audio_hash = _sha256_file(Path(audio_path))

    model = transcript.get("model")
    language = transcript.get("language")
    segments = transcript.get("segments", [])

    envelope_id = storage.insert_node(
        "execution_envelope",
        {
            "source": source,
            "toolchain": {"model": model, "language": language},
            "audio_hash": audio_hash,
            "segment_count": len(segments),
            "provenance": {
                "transcript_hash": hashlib.sha256(
                    json.dumps(transcript, sort_keys=True).encode("utf-8")
                ).hexdigest(),
                "adapter": "whisperx_importer_v1",
            },
        },
    )

    allowed_keys = {"text", "start", "end", "speaker", "confidence"}
    for seg in segments:
        data = {k: seg.get(k) for k in allowed_keys if k in seg}
        data["provenance"] = {"source": "whisperx", "envelope_id": envelope_id}
        if audio_hash:
            data["audio_hash"] = audio_hash
        storage.insert_node("audio_segment", data)

    return envelope_id


__all__ = ["import_whisperx_transcript"]
