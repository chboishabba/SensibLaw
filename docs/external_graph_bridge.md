# External Graph Bridge Contract

This contract defines the generic bridge from a locally source-grounded
candidate world model to a bounded external graph view. Zelph/Wikidata is the
first implementation, but its transport paths, QIDs, and graph semantics are
adapter data rather than the core contract.

## Carrier

`CandidateWorldModel` may carry:

- `external_graph_views`: revision-bound selected graph coverage;
- `external_bridge_candidates`: proposed local-to-external attachments;
- `external_bridge_decisions`: reviewable acceptance/rejection/conflict
  decisions;
- `external_pressure_results`: revision-bound diagnostic results.

All four collections are receipt-free candidate state. Source/manifest and
completeness evidence belong in `provenance_graph` or are attached at the
projection boundary.

## Graph-view coverage

Two states are intentionally distinct:

```text
incomplete
  selected coverage only
  unresolved coverage remains
  candidate-only / non-exhaustive

complete
  coverage policy declared
  required coverage examined
  no unresolved coverage
  completeness receipt reference present
```

Completeness applies to a declared query or coverage policy at a named graph
revision. It does not mean that a graph process happened to load successfully.
An external graph adapter must fail closed if a caller labels a view `complete`
without all of those fields.

## Bridge semantics

Each bridge candidate names its exact local `subject_ref`, subject kind,
external namespace/reference, proposed attachment relation, evidence basis,
and graph-view reference. Attachments are candidates by default. Decisions are
separate records so rejection, conflict, stale external revisions, and several
possible external matches remain reconstructable.

The invariants are:

```text
attach(local, external) != replace(local, external)
external identity != local role
external identity != legal/evidentiary authority
pressure diagnostic != mutation or promotion
```

## Pressure diagnostics

External pressure results compare an observed candidate shape against a
bounded profile and graph view. They can record superclass, disjointness,
qualifier, cohort, expected-shape, or translation pressure. They remain
diagnostics/review candidates and must record the graph revision and profile
that produced them.

The intended pressure model is multi-view, but it is deliberately staged:

```text
local PNF / source evidence
  + bounded WD class/property view
  + optional article, simplification, translation, or domain-cohort view
  -> expected structural signature
  -> residual / pressure diagnostic
  -> review
```

The first implementation carries the resulting diagnostic generically. It does
not yet infer a global expected shape, copy peer values, or make an external
view a truth oracle. A city/capital profile may predict that certain fields are
common, conditional, absent, or structurally suspicious; it must still preserve
jurisdiction, time, split-versus-combined entity modelling, and legitimate
exceptions.

## Basis and federation compatibility

The bridge records are inputs to a versioned local basis, not a globally
sovereign world model. A publishable basis revision should retain its world
model root, source/graph revisions, profile and algorithm references, receipt
root, fork lineage, unresolved conflicts, and attestations. Human-facing
channels may project one or more bases under local trust/governance policy.

```text
external graph view + local evidence -> local basis revision
local basis revisions + selected attestations -> channel projection
```

Hosting, reproducing, reviewing, challenging, or following a basis are distinct
support signals. None is a universal truth score or a substitute for local
acceptance policy.

## Transport boundary

ITIR-MCP owns remote manifest/object transport and emits a normalized bounded
slice view. SensibLaw consumes that view as external graph provenance; it does
not expose raw `hf://` paths as its public product API and does not download
unbounded graph payloads itself.

For the current pruned Wikidata artifact, metadata-only consumption fetches
the manifest/header only. Before a consumer fetches payload bytes,
`itir.shard.bounded_graph_slice_plan` exposes its logical selectors, selected
sections/chunks, and declared payload cost. An earlier four-section chunk-0
example was about 778 MB; it is a coarse smoke-test example, not the current
acceptance selection or a required shape for every query. The current remote
acceptance selection (`left=74`, `right=74`, `nameOfNode=13`,
`nodeOfName=13`) cost 60,731,574 bytes (about 57.9 MiB). Both examples are
bounded payload costs, not full-graph downloads.

## Current implementation status

Remote manifest consumption, bounded-slice planning, graph-view coverage
validation, generic world-model/review/linkage/receipt projection, and the
revision-pinned supplied Wikibase entity-export adapter are implemented. The
adapter validates the requested QID/revision and emits bounded labels, aliases,
property observations, entity-valued references, and statement references. It
does not resolve the local candidate or decide identity.

The first real observation is `Q1785637@2443793937`: it attaches to generic
local entity and event candidates, retains explicit review decisions, and
observes direct `P31`; supplied revision-pinned `P279` evidence supports the
bounded `Q4830453 -> Q43229` organisation-compatible result. This is a real
vertical slice, not a pharmacy-chain structural signature, global closure, or
general WD type checker.

The historical synthetic/incomplete Q1785637 missing-`P31` fixture remains an
abstention regression: it proves an incomplete observation cannot turn an
observed absence into a global missing-type claim. It must not be confused with
the current live pinned observation, which positively observes `P31`.

The next implementation boundary is generic external-context replay through
GWB, AU, Brexit, and Affidavit wrappers, followed by supplied-observation
normalization, coverage-explicit bounded closure, cohort-derived structural
pressure, and multi-view projections. The full staged programme is
`../../docs/planning/generic_world_model_compiler_convergence_20260716.md`.
Fine-grained QID execution, route indexes, smaller shards, and adaptive joins
remain transport follow-up; they do not change bridge semantics.
