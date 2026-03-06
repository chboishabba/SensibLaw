# Wikidata Ontology Issue Review (2026-03-06)

## Purpose
Summarize a live Wikidata ontology discussion thread and translate it into
explicit diagnostic categories and doc-able requirements for deterministic
projection + stability tooling (EII) and class-order review.

Source thread: ChatGPT archive, title "Wikidata Ontology Issues"
(canonical_thread_id: 3f8bd79285b5125dcc96d5b47f2728596f91c5e2).

## Observed issue clusters

1) Class/instance boundary confusion
- Example: items like "alphabet" being both instance and subclass of
  "writing system".
- Risk: silently violating disjointness assumptions; produces brittle
  class-order behavior and inconsistent reasoning paths.

2) Subclass loops and circular modeling
- Example used in the discussion thread: referendum vs plebiscite (reported
  mutual `P279` loop).
- Risk: destroys partial order assumptions; breaks transitive reasoning and
  undermines export validations.

3) Qualifier semantics and standardization drift
- Example: "posthumous" expressed via many incompatible qualifiers and
  sometimes misused as a reference field.
- Risk: equivalence and aggregation become unstable across dumps; evidence
  signals are diluted across unrelated properties.

4) Metaclass misuse (higher-order class confusion)
- Example: third-order/second-order class usage in administrative geography
  where first-order classes suffice.
- Risk: accidental model-theoretic escalation; ontology becomes unusable
  for normal instance/subclass traversals.

5) Property constraint proposals (incompatible type / instances must not have)
- Signal: constraints belong in domain modeling, not only in constraint
  metadata.
- Opportunity: add a formal contract for "negative constraints" as
  deterministic, auditable rules.

6) Domain-specific taxonomic disputes
- Example: weapons classified by function vs generic type.
- Risk: scope drift and inconsistent conceptual criteria.

## Diagnostics mapping (for EII + structural checks)

- Class/instance boundary confusion
  - Signal: same QID appears in both P31 and P279 chains in the same slice.
  - Metric: count of mixed-order edges per class neighborhood.

- Subclass loops
  - Signal: SCCs in P279 graph with size > 1.
  - Metric: EII spikes in SCC neighborhoods across consecutive dumps.

- Qualifier drift
  - Signal: multiple qualifier properties used to encode the same semantic
    concept over time.
  - Metric: qualifier entropy per property slot (s, p).

- Metaclass misuse
  - Signal: repeated P31 links to meta-classes for common first-order items.
  - Metric: ratio of P31 targets that are themselves P31-classed.

- Negative constraints
  - Signal: property constraint usage that implies type exclusions.
  - Metric: candidate "incompatible type" edges surfaced for review.

## Doc follow-ups (proposed)

1) Add a short "Ontology diagnostic taxonomy" doc mapping observed issues to
   deterministic checks, with explicit non-goals (no auto-fixes).

2) Extend the projection operator spec with a "diagnostic lens" appendix that
   defines how EII ties to class-order SCCs and qualifier entropy.

3) Add a note to external-ontology integration docs about avoiding metaclass
   escalation during external ID mapping.

## Notes
This review is intended to feed deterministic diagnostics and reporting only.
It does not prescribe normative fixes or ontology governance decisions.

Live-check note (2026-03-07):
- `alphabet` / `writing system` remains a current live class/instance boundary
  example on Wikidata and is suitable as the primary bounded-slice demo case.
- `referendum` / `plebiscite` should be treated as a historical
  discussion-thread example unless reconfirmed from a current dump or item
  graph; on 2026-03-07 the live `referendum` item exposed `plebiscite` as an
  alias/synonym surface, not as a confirmed current `P279` loop.
