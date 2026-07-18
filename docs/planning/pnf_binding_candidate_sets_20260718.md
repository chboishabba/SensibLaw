# Set-valued PNF binding candidates

Date: 2026-07-18
Status: implemented PostgreSQL compaction tranche

## Purpose

The v0.6 local compiler correctly preserved document-local antecedent ambiguity,
but its compatibility carrier expanded every reference × referential type ×
candidate pair into a complete evidence payload and often a complete factor
alternative. This was semantically branch-preserving but unsuitable as the
operational representation.

The PostgreSQL path now uses a first-class set-valued PNF object:

```text
ArgumentReferenceFactor
× accessibility declaration
× referential type
→ BindingCandidateSet
× normalized members
× compact exclusion summaries
→ immutable factor revision delta
```

Candidate membership is not identity closure. An empty set is not evidence that
a grammatical argument is expletive.

## Operational representation

Migration `008_binding_candidate_sets.sql` adds:

- `pnf.factor_anchor` and document/position/kind/morphology indexes;
- `resolution.binding_candidate_set`;
- `resolution.binding_compatibility_assessment`;
- `resolution.binding_candidate_member`;
- `resolution.binding_exclusion_summary`;
- `resolution.refinement_candidate_set`;
- `resolution.v_binding_candidate_set_summary`.

One reference-factor revision and referential type produce one candidate set.
Compatible candidates are member rows. Predictable inaccessible/incompatible
negative cases are retained as deterministic reason counts instead of duplicate
evidence payloads.

## Compatibility boundary

The existing local compiler remains the source of parser-derived candidates for
this tranche. `compact_binding_artifacts(...)` transforms its expanded carrier
before PostgreSQL persistence. The explicit `--emit-legacy-json` path remains an
expanded compatibility/review export and is not the operational authority.

Typed meets keep actual evidence references separate from candidate-set
references. Factor refinements retain candidate-set references and a delta
surface rather than requiring PostgreSQL to store expanded prior/result JSON as
the binding representation.

## Build identity

A candidate set is keyed by:

```text
reference factor revision
+ document PNF graph/index revision
+ accessibility declaration revision
+ compatibility declaration revision
+ referential type
```

External snapshots are not inputs and cannot invalidate local candidate-set
builds.

## Authority boundary

This tranche performs no:

- antecedent selection;
- coreference or identity closure;
- proposition-truth decision;
- event-occurrence decision;
- expletive inference from an empty candidate search;
- external registry request;
- readiness or promotion action.

## Validation and measurement

Focused tests cover deterministic grouping, member/exclusion separation,
set-referenced refinement alternatives, idempotence, expletive independence,
and normalized/indexed PostgreSQL structure.

`scripts/benchmark_binding_candidate_sets.py` compares an explicit expanded
legacy compilation with the set-valued projection. PostgreSQL relation, TOAST,
and index sizes remain a live-database measurement rather than being inferred
from the former 174 MB JSON artifact.
