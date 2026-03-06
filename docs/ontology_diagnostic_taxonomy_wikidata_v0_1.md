# Wikidata Ontology Diagnostic Taxonomy v0.1

## Purpose
Define the deterministic diagnostic categories used by the Wikidata control-plane
work in SensibLaw/ITIR. This taxonomy is for review, reporting, and stability
measurement only. It does not prescribe ontology governance decisions or
automated repairs.

This document is the missing taxonomy referenced by:
- `docs/wikidata_ontology_issue_review_20260306.md`
- `docs/wikidata_epistemic_projection_operator_spec_v0_1.md`
- `docs/planning/wikidata_transition_plan_20260306.md`

## Position in the stack
- Canonical text, token, and lexeme layers remain authoritative for document
  identity and span anchoring.
- Internal legal ontology layers remain authoritative for legal meaning.
- Wikidata remains advisory only.
- This taxonomy describes a read-only diagnostic lens over Wikidata statement
  bundles and graph structure.

## Scope (v0.1)
Primary bounded slice:
- `P31` (`instance of`)
- `P279` (`subclass of`)

Included in v0.1:
- class/instance boundary confusion
- subclass loops / SCCs
- metaclass misuse
- mixed-order neighborhood diagnostics

Documented but deferred from the first executable slice:
- qualifier drift / qualifier entropy
- negative constraint surfacing
- broader external-ref curation workflows

## Diagnostic classes

### D1. Class/Instance Boundary Confusion
Signal:
- the same QID participates in `P31` and `P279` neighborhoods in a way that
  collapses expected order boundaries within the bounded slice

Examples:
- an item behaves simultaneously like a first-order instance and a class node
  in the same review neighborhood

Deterministic checks:
- count same-QID mixed-order appearances within the inspected subgraph
- flag neighborhoods where `P31` and `P279` paths converge on the same node in
  incompatible roles

Outputs:
- `mixed_order_count`
- `mixed_order_nodes[]`
- audit trace identifying the contributing paths

### D2. Subclass Loops / Circular Modeling
Signal:
- strongly connected components in the `P279` graph with size greater than 1

Deterministic checks:
- run SCC detection over the bounded `P279` slice
- record SCC size and member QIDs

Outputs:
- `scc_count`
- `scc_size`
- `scc_members[]`
- optional neighborhood EII coupling when time windows are available

Current example hygiene:
- thread-derived examples of loops must be distinguished from currently live
  item-state examples
- use `alphabet` / `writing system` as the primary live mixed-order demo case
  unless a current live SCC case has been reconfirmed from a dump or item graph

### D3. Metaclass Misuse
Signal:
- repeated use of higher-order classes where first-order typing is expected in
  the operational slice

Deterministic checks:
- compute the ratio of `P31` targets that are themselves primarily functioning
  as meta-level class nodes in the inspected neighborhood
- flag repeated `P31` links from common first-order items into meta-heavy
  targets

Outputs:
- `metaclass_ratio`
- `candidate_metaclass_targets[]`
- audit trace showing the `P31` chain involved

### D4. Qualifier Drift
Status:
- taxonomy defined now; executable detection deferred from the first bounded
  slice unless explicitly enabled

Signal:
- multiple qualifier properties used to express the same semantic role across
  equivalent slots over time

Deterministic checks:
- canonicalize qualifier sets
- measure qualifier entropy per `(s, p)` slot

Outputs:
- `qualifier_entropy`
- `qualifier_property_set[]`
- trace showing the canonicalized qualifier signatures

### D5. Negative Constraint Surface
Status:
- taxonomy defined now; review-only in v0.1

Signal:
- property constraints imply deterministic type exclusions or incompatibilities

Deterministic checks:
- surface candidate incompatible-type relationships from explicit constraint
  metadata or curated rule tables

Outputs:
- `negative_constraint_candidates[]`
- provenance identifying the originating property/constraint

## Audit trace requirements
Every diagnostic emission must be explainable without free-text reasoning.
Minimum trace fields:
- `diagnostic_id`
- `subject_qid`
- `property_pid`
- `time_window` or dump identifiers when applicable
- `path_edges[]` for graph-derived findings
- `qualifier_signature` when qualifier analysis is enabled
- `rule_ids[]`

## Alignment with tokenizer / lexeme contracts
This taxonomy must not leak Wikidata semantics into canonical text handling.

Invariants:
- lexemes are pre-semantic and must not store Wikidata IDs
- tokenizer identity is not ontology identity
- canonical spans remain authoritative for text provenance
- diagnostic outputs operate on Wikidata statement bundles and graph paths, not
  on regex-derived semantic guesses

See:
- `docs/tokenizer_contract.md`
- `docs/lexeme_layer.md`
- `docs/lexeme_normalizer_character_class_layer.md`
- `docs/extractor_ontology_mapping_contract_20260213.md`

## Working-team packet (Niklas / Ege / Peter)
Initial review packet should answer:
- Which `P31` / `P279` neighborhoods are structurally unstable?
- Which SCCs are operationally important enough to review first?
- Which mixed-order nodes are most likely to break deterministic downstream
  classification?
- Which findings are diagnostic only, versus candidates for ontology working
  group discussion?

Expected first report sections:
- top SCC neighborhoods
- top mixed-order nodes
- metaclass-heavy regions
- bounded assumptions and non-goals

## Non-goals
- no auto-fix generation
- no ontology governance recommendations
- no authority transfer from Wikidata to internal legal ontology
- no semantic mutation of canonical text, token, or lexeme layers
