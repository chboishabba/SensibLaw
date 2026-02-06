# TiRCorder ↔ WhisperX WebUI Adapter (Execution Envelope Contract)

Purpose: emit WhisperX-WebUI outputs from TiRCorder as SB-ready execution
envelopes plus `audio_segment` events, without inference or semantic labels.

This adapter is **write-only**: TiRCorder emits JSON envelopes alongside
transcripts. SB/ITIR can ingest those envelopes later.

## Inputs
- WhisperX JSON transcript with fields:
  - `model`: model/checkpoint id
  - `language`: optional
  - `segments`: list with `start`, `end`, `text`, `confidence`, optional `speaker`
- Optional audio file path (hash only; audio not ingested)

## TiRCorder config (webui)
Set these under `transcription.webui` in `tircorder/config.json`:

- `emit_envelope` (bool, default `false`): write an execution envelope JSON.
- `envelope_dir` (string, optional): directory to write the envelope JSON.
  - If omitted, uses the audio file directory.
- `envelope_format` (string, optional): currently `sb_execution_envelope_v1`.

Envelope output path defaults to:
`<audio_stem>.execution_envelope.json`

## SB representation

**Envelope (node type: `execution_envelope`)**
- data:
  - `source`: "whisperx_webui"
  - `toolchain`: `{model, language}`
  - `audio_hash`: sha256 of audio file (if supplied)
  - `segment_count`
  - `provenance`: includes transcript hash and ingest adapter version

**Segment events (node type: `audio_segment`)**
- data per segment:
  - `text`
  - `start`, `end`
  - `speaker` (optional)
  - `confidence`
  - `audio_hash` (if available)
  - `provenance`: `{"source":"whisperx","envelope_id":<id>}`

## Invariants
- No intent/emotion/summary fields added.
- No alignment or diarisation beyond provided labels.
- Absences (missing audio, missing speaker) left as missing; no fill-in.
- Envelope/segment creation is append-only; no mutation of transcript content.

## Tests (must pass)
- Envelope stores provenance and audio/transcript hashes.
- Segment nodes retain `confidence` exactly as provided.
- Segment nodes contain no semantic keys beyond the allowed set.
