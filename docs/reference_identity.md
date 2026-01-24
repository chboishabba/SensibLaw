# Reference Identity & Diff Layer (S3)

Status: additive-only; LT-REF-1..6 remain frozen.

## Canonical Reference Identity (CR-ID)
- CR-ID-1: identity is a pure function of extracted text.
- CR-ID-2: identity never alters extraction, merge, or dedup behaviour.
- CR-ID-3: identical inputs yield identical `identity_hash`.
- CR-ID-4: different act families must not collide.

## Proof-Safe Reference Diff
- DIFF-1: operate on identity, not surface text.
- DIFF-2: canonicalisation alone never introduces a diff.
- DIFF-3: reordering/pagination does not introduce a diff.
- DIFF-4: only genuine statute changes appear.

## Reference Provenance (diagnostic)
- PROV-1: provenance never affects identity.
- PROV-2: provenance is droppable.
- PROV-3: provenance traces to spans (clause/page/source/anchor).
