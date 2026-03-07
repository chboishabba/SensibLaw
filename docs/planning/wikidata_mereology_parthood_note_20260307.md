# Bounded Wikidata Mereology/Parthood Note

Date: 2026-03-07
Status: reviewed design note for Niklas/Ege/Peter lane
Status Detail: parthood typing diagnostics now implemented in `src/ontology/wikidata.py` and exercised in `tests/test_wikidata_projection.py`.

## Scope
Define a bounded diagnostic lane for parthood typing without turning this into
generic ontology cleanup.

## Target property family
- `P361` (`part of`)
- `P527` (`has part(s)`)
- closely related parthood-like properties only when explicitly pinned in the
  slice configuration

## Typed parthood buckets
- class -> class parthood
- instance -> instance parthood
- instance -> class parthood

Each candidate edge is classified by endpoint type profile from the bounded
slice and reported with explicit uncertainty when typing evidence is mixed.

## Diagnostic questions
- Is the asserted direction plausible for the typed bucket?
- Is an inverse edge present and does it add information or only redundancy?
- Are we seeing type-mixing patterns that suggest modeling instability?

## Outputs (diagnostic only)
- per-edge typed bucket + confidence tier
- inverse-pair validity/redundancy flags
- mixed-typing counts per property
- reviewer summary with abstentions and uncertain cases

No output from this lane is allowed to mutate canonical internal ontology rows.

## Safe DASHI-style reuse (bounded)
Safe reuse:
- epistemic carrier representation for uncertain/contradictory evidence
- deterministic projection receipts and severity ranking surfaces
- report-level instability aggregation

Not safe in this lane:
- broad ontology repair proposals
- schema rewrites driven only by external graph patterns
- replacing bounded diagnostics with abstract formalism-first work

## Execution constraints
- deterministic and reproducible on pinned slice inputs
- explicit abstention when endpoint typing is insufficient
- no label-text heuristics as ontology truth
- data-version assumption: the active diagnostic lane operates against the latest
  pinned importer slice for practical throughput; historical rewrites are deferred
  until explicitly requested because they add useful context but materially raise
  context-switching cost.

## Next concrete step
DONE (2026-03-07): Added deterministic typed parthood diagnostics in projection output
(`windows[*].diagnostics.parthood_typing`) with classification counts plus inverse-pair
coverage, backed by an inline regression test in `tests/test_wikidata_projection.py`.

DONE (2026-03-08): Added a fixture-backed parthood pilot pack
(`tests/fixtures/wikidata/parthood_pilot_pack_20260308`) with pinned
`projection.json` and cross-property inverse-validity coverage (`P361` ↔ `P527`).
