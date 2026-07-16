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

When a policy model exists, the expected shape starts normatively and is refined
only by independently reviewed, revision-pinned conforming members. Runtime
must retain policy requirements, empirical regularities, conditional branches,
and legacy/noise separately. A candidate cannot join a trusted cohort merely
because it resembles that cohort; admission follows a separate governed review
decision and produces a contribution/revision receipt.

For sufficiently covered, context-compatible comparisons, the richer runtime
goal is a typed residual graph rather than a scalar missing-field score. It may
show structural clusters, cuts, bridges, outliers, nearby-class candidates,
class-split, merge, or disjointness candidates, and possible abstractions. Similarity is
admissible only where entity kind, relation domain/range, temporal/source/PNF
context, superclass neighbourhood, and disjointness constraints permit it.
Forbidden or weakly covered analogies remain masked or unknown, never ontology
assignments; all resulting repair/class proposals remain diagnostic-only.
The corresponding DASHI boundary also permits only reviewed conforming cases
to contribute to an empirical invariant; it does not formalize retrieval,
closure, cohort induction, or the runtime topology solve.

The first runtime implementation of this admission boundary is the generic
`src/policy/domain_invariants.py` carrier. It accepts only a named confirmed
review disposition, source revision, review-decision receipt, reviewer
authority, observed coverage, and explicit feature contributions. It emits a
`TrustedConformingMember`, `InvariantContributionReceipt`, deterministic
`DomainInvariantSnapshot`, and `InvariantRevisionReceipt`. The records keep
policy requirements, empirical feature counts, conditional branches,
exceptions/noise, and coverage requirements separate, with no promotion or
edit effect. A classifier family label or an unreviewed live row is not enough
to enter a trusted cohort.

`src/policy/review_confirmation.py` supplies the separate explicit decision
artifact required by that carrier. A confirmation references the reviewed
candidate/packet and source revision, names reviewer authority and a supported
confirmed disposition, and preserves the feature contributions. A confirmed
split additionally requires an approved split-plan reference. It is the only
implemented conversion path into `TrustedConformingMember`; a review packet or
Family A/B/C classification cannot be treated as a decision by itself.

### Residual-profile and review-packet convergence

The next runtime seam is deliberately shared: a coverage-qualified
`TypedResidualProfile` is projected both into a compact reviewer packet and
into the typed residual graph.  This avoids a packet-specific explanation
surface drifting away from the later topology/spectral surface.

```text
DomainPressureAssessment + context gates
-> TypedResidualProfile
   -> reviewer packet projection
   -> typed residual-graph projection
```

The packet is a review surface only.  It may show an observed statement,
proposed decomposition, qualifier/reference carry plan, residual evidence,
coverage limits, and confirmation choices.  It cannot confirm a split,
admit a trusted member, revise an invariant, promote a statement, or edit an
external graph.  Nat's Family-B page is the first bounded consumer; its
climate-profile selection remains a thin input wrapper over this generic
carrier.

The initial live three-row packet page at `Q101416961@2419927005` is retained
as a rejected classifier-error artifact, not a Family-B precedent. It exposed
that page selection omitted a fourth sibling source statement and the
classifier mistook sibling multiplicity for overload of each atomic GUID. The
corrected materializer now hydrates the complete pinned family and keeps the
three selected GUIDs atomic: the four-member family is
`already_partitioned`, its scoped components exactly reconcile with the total,
and all selected rows are Family-A `safe_with_reference_transfer`. It emits no
split packet or residual-graph node. Family-level context remains distinct from
statement-level residuals before a later genuine split packet is reviewable.

### Conservative ontology-class merge proposals

Merge is a first-class proposal family alongside split and disjointness; it is
not the positive-edge dual of a split.  A raw or even context-admissible
similarity signal may say only that the observed class boundary lacks support.
It cannot merge classes.  A generic `OntologyMergeCandidate` must separately
retain normative compatibility, residual-geometry evidence, negative edges,
context masks, conditional distinctions, relation substitutability, bounded
downstream impact, provenance transfer, counterevidence, and coverage.

A direct merge becomes `checked_merge_reviewable` only if all of these pass:
adequate coverage, compatible normative invariants, no typed incompatibility,
no meaningful conditional distinction, substitutable surrounding relations,
bounded impact, and complete provenance transfer.  Otherwise the review-only
outcome may prefer a shared superclass, bridge class, conditional distinction,
historical alias, hold, block, or abstention.  A merge impact report must name
affected members, subclass/property/disjointness edges, external identifiers,
query/projection changes, labels/aliases, reconstruction requirements, and
provenance preservation.  No result redirects classes or edits Wikidata.

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

The first runtime policy-DSP output now comes from Nat's climate migration
profile. Each generated `P5991 -> P14143` candidate carries a generic
`DomainPressureAssessment` with separately preserved target-model,
subject-type, qualifier, reference, temporal, split, and currently-unresolved
peer-cohort residuals. Its A--E migration family remains a review-disposition
projection; the assessment itself is `diagnostic_only` with
`promotion_effect = not_evaluated`.

The next implementation boundary is Nat's explicit policy-DSP residuals,
governed invariant admission/revision, the typed residual graph, and
review-only split/disjoint/bridge/abstraction proposals. The richer
residual-topology solve follows that graph. Generic external-context replay
through GWB, AU, Brexit, and Affidavit then proves that this mature surface is
shared rather than Nat-owned. Supplied-observation normalization,
coverage-explicit bounded closure, city/capital and Peter/Ege/Rosario proving
packs, multi-view projections, and routed Zelph transport follow. The full
staged programme is
`../../docs/planning/generic_world_model_compiler_convergence_20260716.md`.
Fine-grained QID execution, route indexes, smaller shards, and adaptive joins
remain transport follow-up; they do not change bridge semantics.
