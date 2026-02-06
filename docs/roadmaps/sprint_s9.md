# Sprint S9 — Human Interfaces (Read-Only, Trust-First)

Thesis: make the system legible to humans without letting humans (or UI) mutate
meaning.

## Goals
- Make Layer 0–3 understandable to users.
- Reinforce trust and provenance visually.
- Keep all surfaces read-only.

## Non-goals
- No editing or persistent annotations.
- No user-defined concepts.
- No reasoning widgets.

## Deliverables

### S9.1 Text & span inspector
- Click to highlight TextSpan.
- Show revision, offsets, signal hypotheses, promotion receipts.

### S9.2 Obligation explorer
- Actor/Action/Object lenses.
- Timeline view (version diffs).
- Clause-local explanation only.

### S9.3 Graph & diff UI hardening
- Fixture-mode rendering.
- Playwright smoke tests.
- Forbidden-language assertions.

### S9.4 UI doctrine enforcement
- Read-only invariant tests.
- No mutation controls rendered.
- Labs tab clearly quarantined.

## Exit criteria
- A user can answer: "Where did this obligation come from, and what changed?"
- A user cannot answer: "What should I do?"

## Delivery rules
- UI remains a consumer of deterministic payloads.
- Any new semantics require a new sprint and schema version.
