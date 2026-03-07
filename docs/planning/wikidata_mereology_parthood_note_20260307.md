# Bounded Wikidata Mereology/Parthood Note

Date: 2026-03-07
Status: reviewed design note for Niklas/Ege/Peter lane

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

## Next concrete step
Add a small pinned fixture pack with representative edges for each typed bucket
and at least one inverse-pair ambiguity case, then run through the existing
review report surface.
