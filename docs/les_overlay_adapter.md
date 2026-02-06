# LES → SB Overlay Adapter (environment snapshots)

Purpose: ingest Living Environment System (LES) snapshots as read-only context
overlays in SB, aligning events with external environment state without
introducing inference or causality.

## Inputs
- LES snapshot JSON (or dict) with fields:
  - `snapshot_id` (str, stable)
  - `captured_at` (ISO datetime)
  - `environment_state`: arbitrary mapping of external signals
    (e.g., season labels, soil moisture trend, volatility regime)
  - `models`: provenance describing model versions/sources
  - Optional: `location`

## SB representation (context_fields)
- `context_type`: `les_environment`
- `context_id`: `les:<snapshot_id>`
- `payload`: `environment_state`
- `provenance`: includes `models`, `captured_at`
- `symbolic`: `0`

## Invariants
- Snapshot is non-authoritative; no advice, alerts, or behavioural claims.
- No merging with user events; SB events may reference the snapshot id.
- Absence/uncertainty in the snapshot is preserved; no fill-in.

## Tests that must hold
- Upsert stores payload/provenance and sets `symbolic = 0`.
- Retrieval echoes `environment_state` exactly; no extra keys.
- No semantic or causal fields are injected by the adapter.
