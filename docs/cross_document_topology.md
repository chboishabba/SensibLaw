# Cross-Document Norm Topology (Sprint 7B)

Purpose: project **explicit** relationships across instruments **without inference, precedence, or ontology expansion**.

## Edge set (closed)

Only these edge kinds exist in `obligation.crossdoc.v1`:

- `supersedes` — explicit replacement/repeal
- `conflicts_with` — explicit inconsistency statement
- `exception_to` — explicit exception carved out
- `applies_despite` — applies despite another provision
- `applies_subject_to` — applies only if another provision holds

❌ No other edge kinds are permitted.

## Preconditions (all must hold)

1) Explicit textual marker present (grammar below).
2) Resolvable reference to another instrument **and clause/section**.
3) Reference resolves to a known obligation identity (OBL-ID) in the target doc.
4) Marker + reference are clause-local (no cross-paragraph synthesis).
5) Provenance recorded verbatim.

If any precondition fails → **no edge**.

## Grammar (regex, case-insensitive)

### Supersession
```
\brepeals?\b
\brevokes?\b
\bsupersedes?\b
\bhas effect instead of\b
\bceases to have effect\b
```

### Conflict
```
\binconsistent with\b
\bdespite any other provision\b
\bto the extent of any inconsistency\b
```

### Exception
```
\bexcept as provided in\b
\bdoes not apply to\b
\bthis (section|regulation) does not apply\b
```

### Applies Despite
```
\bdespite (section|regulation)\b
\bdespite anything in\b
```

### Applies Subject To
```
\bsubject to (section|regulation)\b
\bsubject to this act\b
```

### Forbidden (must never emit edges)

```
\bhaving regard to\b
\bconsistent with\b
\bguided by\b
\bfor the purposes of\b
\bas if\b
\btaken to\b
```

## Payload (frozen)

```jsonc
{
  "version": "obligation.crossdoc.v1",
  "nodes": [
    {"obl_id": "<obligation_hash>", "source_id": "Act2024", "clause_id": "Act2024-clause-0"}
  ],
  "edges": [
    {
      "kind": "supersedes",
      "from": "<obl_id>",
      "to": "<obl_id>",
      "text": "supersedes",
      "provenance": {"source_id": "Act2024", "clause_id": "Act2024-clause-3"}
    }
  ]
}
```

Ordering: nodes sorted by `obl_id`; edges sorted lexicographically by `(kind, from, to)`.

## Guardrails

- ❌ No inferred edges; missing reference → no edge.
- ❌ No compliance/precedence reasoning.
- ❌ No ontology/synonym expansion beyond regex above.
- ✅ Deterministic ordering for snapshotting.
- ✅ Removing topology must not alter obligations.

## Temporal overlays (Phase 2 — design only)

Overlays annotate edges; they **never** change topology or activation.

Allowed phrases: `on commencement`, `from the commencement of`, `until repeal`, `until expiry`.

Disallowed: `currently`, `at present`, `as amended`, `from time to time` (would imply inference).

Payload sketch (non-binding until Phase 2):

```jsonc
{
  "edge_id": "<hash>",
  "temporal": {
    "effective_from": "2024-07-01",
    "effective_until": null,
    "text": "applies from 1 July 2024"
  }
}
```
