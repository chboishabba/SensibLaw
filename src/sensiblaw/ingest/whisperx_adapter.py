from __future__ import annotations

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from sensiblaw.ingest.asr_adapter import import_asr_transcript
from storage.core import Storage


def import_whisperx_transcript(
    storage: Storage,
    transcript: Mapping[str, Any],
    *,
    audio_path: str | Path | None = None,
    source: str = "whisperx_webui",
) -> int:
    """Ingest WhisperX transcript via the generic ASR adapter."""

    return import_asr_transcript(
        storage,
        transcript,
        source=source,
        audio_path=audio_path,
        adapter_label="whisperx_importer_v1",
        segment_keys=("text", "start", "end", "speaker", "confidence"),
    )


__all__ = ["import_whisperx_transcript"]
