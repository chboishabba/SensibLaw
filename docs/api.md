# API Endpoints (Sprint 7 surfaces)

Read-only, deterministic endpoints that expose existing obligation data. No reasoning, no inference, no identity changes.

## `POST /obligations/query`
- **Purpose:** Filter extracted obligations.
- **Request:**
  ```json
  {
    "text": "The operator must keep records…",
    "source_id": "doc-1",
    "enable_actor_binding": true,
    "enable_action_binding": true,
    "filters": {
      "actor": "the operator",
      "action": "keep",
      "scope_category": "time",
      "lifecycle_kind": "activation",
      "clause_id": "doc-1-clause-0",
      "modality": "must",
      "reference_id": null
    }
  }
  ```
- **Response:** `{"version": "obligation.query.v1", "results": [<obligation dicts>]}` (deterministic ordering).

## `POST /obligations/explain`
- **Purpose:** Return clause-local trace for each obligation.
- **Request:** same as `query` but without filters.
- **Response:** `{"version": "obligation.explanation.v1", "explanations": [ … ]}`.

## `POST /obligations/alignment`
- **Purpose:** Compare two texts and report added/removed/modified obligations (metadata only).
- **Request:**
  ```json
  {
    "old_text": "…",
    "new_text": "…",
    "source_id": "doc",
    "enable_actor_binding": true,
    "enable_action_binding": true
  }
  ```
- **Response:** `{"version": "obligation.alignment.v1", "added": [], "removed": [], "unchanged": [], "modified": []}`.

## `POST /obligations/projections/{view}`
- **Purpose:** Deterministic read-only projections.
- **Path param:** `view` ∈ `actor|action|clause|timeline`.
- **Request:** same shape as `query` without filters.
- **Response:** `{"version": "obligation.projection.v1", "view": "<view>", "results": [...]}`.

## `POST /obligations/activate`
- **Purpose:** Describe activation/termination state using declared facts (no compliance judgement).
- **Request:**
  ```json
  {
    "text": "...",
    "source_id": "doc-1",
    "facts": {
      "version": "fact.envelope.v1",
      "facts": [
        {"key": "upon commencement", "value": true}
      ]
    }
  }
  ```
- **Response:**
  ```json
  {
    "version": "obligation.activation.v1",
    "obligations": [...],
    "activation": {
      "version": "obligation.activation.v1",
      "active": ["<hash>"],
      "inactive": ["<hash>"],
      "terminated": [],
      "reasons": {
        "<hash>": [
          {"trigger": "activation", "text": "upon commencement", "fact_key": "upon commencement", "fact_value": true}
        ]
      }
    }
  }
  ```
- **Guardrails:** No inferred facts, no compliance labels, identity hashes unchanged, deterministic ordering.

## Legacy demo endpoints (unchanged)
- `POST /import_stories` — import stories into memory.
- `POST /check_event` — membership check for story events.
- `POST /rules` — regex-based rule extraction demo.
