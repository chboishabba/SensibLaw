from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from storage.core import Storage


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def import_asr_transcript(
    storage: Storage,
    transcript: Mapping[str, Any],
    *,
    source: str,
    model: str | None = None,
    language: str | None = None,
    audio_path: str | Path | None = None,
    segment_keys: Sequence[str] = ("text", "start", "end", "speaker", "confidence"),
    adapter_label: str = "asr_importer_v1",
) -> int:
    """Generic ASR ingest: envelope + audio_segment nodes, no inference."""

    audio_hash = _sha256_file(Path(audio_path)) if audio_path else None
    segments = transcript.get("segments", [])

    envelope_id = storage.insert_node(
        "execution_envelope",
        {
            "source": source,
            "toolchain": {"model": model or transcript.get("model"), "language": language or transcript.get("language")},
            "audio_hash": audio_hash,
            "segment_count": len(segments),
            "provenance": {
                "transcript_hash": hashlib.sha256(
                    json.dumps(transcript, sort_keys=True).encode("utf-8")
                ).hexdigest(),
                "adapter": adapter_label,
            },
        },
    )

    allowed = set(segment_keys)
    for seg in segments:
        data = {k: seg.get(k) for k in allowed if k in seg}
        data["provenance"] = {"source": source, "envelope_id": envelope_id}
        if audio_hash:
            data["audio_hash"] = audio_hash
        storage.insert_node("audio_segment", data)

    return envelope_id


__all__ = ["import_asr_transcript"]
