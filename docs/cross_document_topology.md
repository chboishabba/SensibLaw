# Cross-Document Norm Topology (Sprint 7B Planning)

Purpose: project explicit relationships across instruments without inference or precedence reasoning.

## Edge grammar (explicit-only)

Allowed edge types and required trigger phrases (examples):
- `supersedes` — “repeals”, “supersedes”, “replaces”
- `amends` — “amends”, “inserts”, “substitutes”
- `ceases_under` — “ceases under”, “expires under”, “ceases upon”
- `applies_instead_of` — “despite”, “subject to”, “applies instead of”

Rules:
- Edge exists only if trigger phrase is present in text and cites source/target clauses.
- Source/target must already exist as OBL-ID nodes.
- No synonym/ontology expansion; phrases must appear verbatim (case-insensitive match).
- Temporal qualifiers (“from 1 Jan 2020”, “until repeal”) attach only when explicitly present.

## Payload: `obligation.crossdoc.v1` (draft)

```jsonc
{
  "version": "obligation.crossdoc.v1",
  "nodes": ["<obligation_id>", "..."],
  "edges": [
    {
      "from": "<obligation_id>",
      "to": "<obligation_id>",
      "type": "supersedes|amends|ceases_under|applies_instead_of",
      "basis": {
        "document": "Act2020 s5",
        "text_span": [123, 140],
        "reference_id": "CR-ID-123"
      },
      "effective_from": "2020-01-01",
      "effective_to": null
    }
  ]
}
```

## Guardrails
- ❌ No inferred edges; text span + reference_id are mandatory.
- ❌ No conflict resolution / precedence ranking.
- ❌ No ontology/semantic normalization beyond lowercase phrase match.
- ✅ Deterministic ordering for nodes/edges for snapshotting.
- ✅ Cycles are allowed but must be flagged; never pruned automatically.
- ✅ Formatting/OCR/renumbering noise must not create or remove edges.

## Tests to add (red-flag style)
- Missing citation → no edge.
- Formatting/renumbering variants yield identical edge sets.
- Temporal overlays only when explicit dates exist.
- Cycles detected but not resolved.
- No “effective law”/“winner” field emitted.

## Implementation plan (minimal sequence)
1) Extract explicit edge candidates per document using phrase match + clause refs.
2) Lift edges into cross-doc graph; keep payload deterministic.
3) Snapshot graph outputs for a fixed corpus fixture.
4) Add red-flag tests for the above guardrails.
