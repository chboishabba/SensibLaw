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

7) Mereology / parthood typing ambiguity
- Later discussion in the same archived thread extended the issue set toward
  mereology: the high-yield unresolved problem is not "parthood exists", but
  which kind of parthood is being asserted.
- Required distinctions:
  - class-class parthood
  - instance-instance parthood
  - instance-class parthood
  - inverse validity vs mere redundancy
- Risk: `has part` / `part of` becomes semantically overloaded and hard to
  diagnose deterministically, even when local graph structure looks coherent.

8) Property-definition / constraint interaction
- Later discussion in the same archived thread and Telegram follow-up made it
  explicit that properties are in scope for ontology review when their subject,
  value-type, and usage restrictions interact with class structure.
- Example pressures:
  - `total revenue` / `currency` subject constraints on `account`
  - subset-vs-total revenue modeling
  - point-in-time vs span semantics for financial flow reporting
- Risk: modeling disputes get treated as one-off property questions when they
  are actually structural ontology/constraint interactions.

9) Label harmonization as a modeling smell
- Examples:
  - `XXX subclass`
  - `type of XXX`
  - `XXX type`
- Risk: labels drift in ways that confuse non-expert users and may correlate
  with inconsistent class-order or property use, even if labels are not the
  ontology truth source.

10) Support / ontological dependence boundary
- Example: whether a property like `supports` should relate a continuant to an
  activity (`a path supports walking`, `paper supports writing`) or whether
  existing proxies like `P366` (`has use`) are the practical boundary.
- Risk: the group blurs central ontology work with adjacent dependence/use
  questions without an explicit scope line.

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

- Mereology / parthood typing ambiguity
  - Signal: parthood edges whose endpoint typing or inverse structure suggests
  more than one semantic reading.
  - Metric: counts of mixed parthood typing patterns plus inverse-pair
  redundancy vs contradiction candidates.

- Property-definition / constraint interaction
  - Signal: repeated modeling friction around subject/value constraints,
    quantity typing, or time-span representation that clusters around a small
    set of properties.
  - Metric: constraint-conflict families plus recurring workaround patterns.

- Label harmonization as a modeling smell
  - Signal: repeated naming variants for near-equivalent class/type items.
  - Metric: label-pattern families that correlate with mixed-order or
    inconsistent property usage.

- Support / ontological dependence boundary
  - Signal: repeated proposals for semantically loaded properties where the
    group itself treats scope as blurry.
  - Metric: count and clustering of "loaded property" discussions, with a note
    on whether practical proxies like `P366` are being used instead.

## Doc follow-ups (proposed)

1) Add a short "Ontology diagnostic taxonomy" doc mapping observed issues to
   deterministic checks, with explicit non-goals (no auto-fixes).

2) Extend the projection operator spec with a "diagnostic lens" appendix that
   defines how EII ties to class-order SCCs and qualifier entropy.

3) Add a note to external-ontology integration docs about avoiding metaclass
   escalation during external ID mapping.

4) Add a bounded mereology/parthood extension note linked from the working-group
   status doc so Niklas / Ege / Peter can review typed parthood as a diagnostic
   problem before any solution proposal.

5) Add a property/constraint pressure-test note covering:
   - financial-flow/timeseries modeling
   - graphing/report surfaces
   - practical loaded-property questions like `supports` / `has use`
   - label harmonization as a diagnostic clue rather than ontology truth

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
- The same archived thread now also includes a Mereology Task Force / parthood
  follow-up. That material should be treated as design-direction input for a
  later bounded extension, not as evidence that the current qualifier-drift
  pack is superseded.
