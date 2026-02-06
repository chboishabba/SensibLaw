# Cross-Document Norm Topology (Sprint S8)

Purpose: project **explicit** relationships across instruments **without inference, precedence, or ontology expansion**.

## Edge set (closed)

Only these edge kinds exist in `obligation.crossdoc.v2`:

- `repeals` — explicit repeal/revocation
- `modifies` — explicit amendment/modification
- `references` — explicit reference pointer
- `cites` — explicit citation pointer

❌ No other edge kinds are permitted.

## Preconditions (all must hold)

1) Explicit textual marker present (grammar below).
2) Resolvable reference to another instrument **and clause/section**.
3) Reference resolves to a known obligation identity (OBL-ID) in the target doc.
4) Marker + reference are clause-local (no cross-paragraph synthesis).
5) Provenance recorded verbatim.

If any precondition fails → **no edge**.

## Grammar (regex, case-insensitive)

### Repeals
```
\brepeals?\b
\brevokes?\b
\bceases to have effect\b
```

### Modifies
```
\bamends?\b
\bmodif(?:y|ies)\b
\bvaries\b
\bupdates\b
```

### References
```
\bsee\b
\brefer to\b
\bas provided in\b
\bas set out in\b
```

### Cites
```
\bcites?\b
\bcited in\b
\bas cited in\b
```

### Forbidden (must never emit edges)

```
\bconflict\b
\bconflicts?\b
\boverride\b
\boverrides?\b
\bprevails?\b
\bcontrols?\b
```

## Payload (frozen)

```jsonc
{
  "version": "obligation.crossdoc.v2",
  "nodes": [
    {"obl_id": "<obligation_hash>", "source_id": "Act2024", "clause_id": "Act2024-clause-0"}
  ],
  "edges": [
    {
      "kind": "repeals",
      "from": "<obl_id>",
      "to": "<obl_id>",
      "text": "repeals",
      "provenance": {"source_id": "Act2024", "clause_id": "Act2024-clause-3", "span": [12, 45]}
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
