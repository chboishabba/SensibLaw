# Sprint 8 Review Model (Planning)

Objects (non-semantic):

- `ReviewerNote`
  - `target`: obligation|edge
  - `identity_hash`: string
  - `note`: string
  - `author`: string
  - `timestamp`: datetime (ISO 8601)
- `DisagreementMarker`
  - `target`: obligation|edge
  - `identity_hash`: string
  - `reason`: string
  - `author`: string
  - `timestamp`: datetime
- `ReviewBundle`
  - `obligations`: existing payloads (no mutation)
  - `activation`: existing payloads (no mutation)
  - `topology`: existing payloads (no mutation)
  - `notes`: list[ReviewerNote]
  - `disagreements`: list[DisagreementMarker]

Rules:
- Notes and disagreements are **metadata only**; removing them restores identical hashes.
- No approvals, scoring, or compliance labels.
- Export is deterministic: same inputs → same bundle bytes.
- UI must not synthesize or modify obligations, activation, or topology.
