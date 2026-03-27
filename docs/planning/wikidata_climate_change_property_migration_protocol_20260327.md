# Wikidata Climate-Change Property Migration Protocol (2026-03-27)

## Purpose
Define how the repo's existing Wikidata review methods should be applied to a
real property-migration problem in the climate-change domain, using the current
discussion around migrating `carbon footprint (P5991)` statements to
`annual greenhouse gas emissions (P14143)` as the anchor case.

This note is intentionally about review and migration discipline, not about
claiming that all `P5991` statements should be rewritten.

## Inputs reviewed
- Local repo status/method docs:
  - `SensibLaw/docs/wikidata_working_group_status.md`
  - `SensibLaw/docs/planning/wikidata_transition_plan_20260306.md`
  - `SensibLaw/docs/wikidata_report_contract_v0_1.md`
  - `SensibLaw/docs/planning/wikidata_working_group_review_template_20260307.md`
  - `SensibLaw/docs/planning/wikidata_property_constraint_pressure_test_20260307.md`
- Local implementation/test surfaces:
  - `SensibLaw/src/ontology/wikidata.py`
  - `SensibLaw/scripts/run_wikidata_qualifier_drift_scan.py`
  - `SensibLaw/tests/test_wikidata_cli.py`
  - `SensibLaw/tests/test_wikidata_finder.py`
  - `SensibLaw/tests/test_wikidata_projection.py`
- External coordination context:
  - `Wikipedia:WikiProject Climate change`
    (`https://en.wikipedia.org/wiki/Wikipedia:WikiProject_Climate_change`,
    viewed 2026-03-27, source = web)
  - Current signals pulled from that page:
    - recommended-source discipline is explicit
    - controversial-topic editing discipline is explicit
    - community to-do/alerts/quality surfaces are explicit
    - article metrics and prioritization are explicit

## Problem framing
The repo already has a strong method for:
- bounded candidate discovery
- deterministic statement-bundle projection
- qualifier-drift detection across windows/revisions
- reviewer-facing checked/dense handoff surfaces

The climate-change migration case should therefore be treated as a
property-migration review lane, not as a direct bot-rewrite lane.

Concrete anchor case:
- source property: `P5991`
- proposed target property: `P14143`

Key risk:
- this is not obviously a property rename
- some source statements may be semantically compatible with the target
- some may require qualifier transfer/remapping
- some may remain legitimately modeled with the old property

## What the WikiProject page changes
The WikiProject page does not give a migration protocol, but it does sharpen
what a useful repo-facing protocol must respect:

- sourcing quality must stay first-class
- disagreement handling should be evidence-first rather than editor-first
- high-visibility/high-pageview topics need more conservative rollout
- community task queues and metrics matter, so outputs should be reviewable and
  legible to non-tool-builders

That matches the repo's existing non-goals:
- no auto-fix presumption
- no ontology-governance prescription
- no silent transformation of evidence

## ZKP framing of the WikiProject surface
The user's ZKP framing is consistent with existing repo doctrine about
Wikipedia/Wikidata ingest.

### `O` — organization
`Wikipedia:WikiProject Climate change` is best treated as a decentralized,
soft-consensus coordination layer:
- volunteers
- talk-page and task-list coordination
- policy-weighted social review

Repo interpretation:
- this is a high-noise proposal/review collective
- it is not a canonical semantic authority surface

### `R` — requirement
The WikiProject's visible requirement is editorial:
- improve article quality and coverage
- keep sourcing quality high
- preserve neutrality and manage disputes

Repo interpretation:
- optimize for reviewability, sourcing, and coordination legibility
- do not confuse those goals with MDL-optimal semantic compression or promoted
  truth

### `C` — code / mechanisms
The WikiProject's operative mechanisms are:
- edits
- reverts
- templates/tags
- citation changes
- talk-page proposals

Repo interpretation:
- this is a proposal-edit surface over article state
- it is not an invariant-enforcing semantic runtime

### `S` — state
The Wikipedia/WikiProject state is:
- article text
- revision history
- talk/dispute context
- maintenance metadata

Repo interpretation:
- this is a noisy upstream substrate and candidate surface
- it should not be collapsed directly into promoted semantic state

This matches existing repo context:
- revision-locked article -> canonical wiki state -> projections
- compare canonical wiki state first, then derived deltas

### `L` — lattice
The WikiProject has only a weak social ordering:
- newer revisions
- more stable consensus
- less active dispute

Repo interpretation:
- this is not the repo's admissibility lattice
- there is no MDL ordering, contraction rule, or semantic promotion rule
  inherent in the WikiProject itself

### `P` — proposal
Editors propose edits and migration ideas.

Repo interpretation:
- the WikiProject is a proposal generator and candidate-review surface
- it is not the truth layer

### `G` — governance
The WikiProject governs through:
- consensus
- policy
- dispute resolution

Repo interpretation:
- useful upstream governance for public edits
- insufficient as the repo's semantic promotion rule by itself

### `F` — gap
The key gap is the distance between:
- social/editorial acceptability
- and a provenance-preserving, semantically classified migration state

Repo interpretation:
- the repo can help measure this gap by turning free-form migration ideas into
  bounded candidate packs, explicit buckets, and auditable statement-bundle
  comparisons

## Consequence of the ZKP framing
The WikiProject should be integrated into the repo as:
- upstream coordination surface
- candidate/proposal generator
- public-facing review and acceptance context

It should not be treated as:
- the semantic truth layer
- the promotion lattice
- the migration engine

Practical consequence for the `P5991 -> P14143` case:
- community consensus can authorize and prioritize the work
- but the repo still needs a separate bounded review surface that preserves
  qualifiers, references, and semantic mismatch buckets before any migration
  action is treated as safe

## Proposed ITIR method stack

### 1. Freeze the migration claim before touching statements
Define the candidate migration claim explicitly:

- which `P5991` statements are believed to mean annual emissions
- which `P5991` statements are broader than annual emissions
- which qualifiers/references are expected to survive transfer unchanged
- which qualifiers imply that the old and new statements are not equivalent

This should be recorded as a bounded migration note before any batch output is
generated.

### 2. Build a bounded candidate slice first
Use the repo's existing "bounded slice first" doctrine.

Required slice contents:
- a small candidate set of current `P5991` statements
- a mix of apparently safe and apparently ambiguous cases
- full statement bundles:
  - subject
  - value
  - rank
  - qualifiers
  - references

Initial bounded slice size:
- target: 20-50 representative items, not whole-Wikidata scale

Selection strategy:
- include easy-looking annual-emissions cases
- include likely edge cases
- include at least some heavily-qualified/reference-rich cases

### 3. Treat migration as statement-bundle comparison
The unit of review should be the full statement bundle, not just `(subject,
property, value)`.

For this lane, the repo should preserve and compare:
- qualifier property sets
- qualifier signatures
- reference block structure
- rank changes
- temporal qualifiers
- review qualifiers / reason qualifiers

The existing statement-bundle projection already preserves most of this shape.
The migration lane should extend that discipline to reference-transfer review,
not collapse down to raw QS rows too early.

### 4. Add explicit migration buckets
Do not treat output as binary "migrate / do not migrate".

Minimum review buckets:
- `safe_rewrite`
  - source and target semantics align
  - qualifiers/references transfer cleanly
- `safe_rewrite_with_qualifier_remap`
  - core meaning aligns, but qualifier/property adjustments are needed
- `safe_add_target_keep_source_temporarily`
  - useful when community wants staged validation before deletion
- `semantic_mismatch_keep_source`
  - source statement is not equivalent to annual emissions
- `reference_or_qualifier_conflict_manual_review`
  - evidence structure is too ambiguous for automated action
- `split_required`
  - one source statement would need more than one target statement or a target
    plus retained source statement

### 5. Reuse revision-window methods before claiming stability
The current qualifier-drift finder already compares revisions and materializes a
confirmed case into:
- `from_entity.json`
- `to_entity.json`
- `slice.json`
- `projection.json`

The same pattern should be reused here:
- sample candidate statements across revisions
- detect whether qualifier/reference structures are stable enough to migrate
- separate stable baselines from true drift/problem cases

This is especially important if `P5991` usage has already been changing in
response to `P14143`.

### 6. Generate review surfaces before bot/export surfaces
The first outputs should be review artifacts, not edit commands.

Recommended artifact families:
- checked migration review
- dense migration review
- candidate scorecard
- explicit unresolved bucket list

Minimum reviewer-facing questions:
1. Which candidate statements are safe to rewrite now?
2. Which cases need qualifier/reference review first?
3. Which cases should remain on `P5991` because the semantics are broader?

### 7. Only generate edit payloads from the checked-safe subset
QuickStatements or bot-ready payloads should be generated only from the
reviewed `safe_rewrite` subset.

Guardrails:
- no whole-property rewrite
- no edits from unreviewed candidates
- no destructive deletion path in the first batch
- preserve a reviewable mapping from source statement to proposed target action

### 8. Verify after migration using the same control plane
Post-batch verification should report:
- migrated statement count
- retained/manual-review count
- qualifier-remap count
- unresolved semantic-mismatch count
- spot-check results on references

This keeps the migration legible to the WikiProject's task/quality culture
rather than turning it into an opaque one-shot bot run.

## How broader ITIR methods map to WikiProject Climate change needs

### Recommended sources
The WikiProject's source discipline aligns with the repo's provenance-first
approach:
- preserve reference blocks
- classify reference-transfer confidence
- do not let migration erase evidence shape

### Controversial-topic handling
The WikiProject explicitly warns that the topic can be contentious. The repo's
matching posture should be:
- review-first
- explainable buckets
- no "the tool decided" framing
- easy manual inspection of the exact evidence bundle

### To-do / article-alert workflow
The WikiProject already uses visible task queues. Repo outputs should therefore
be easy to turn into:
- candidate worklists
- spot-check queues
- "done / needs review / not equivalent" trackers

### Metrics and prioritization
The WikiProject page exposes quality/importance/pageview signals. A later,
broader climate-change lane could combine:
- article/page importance
- property-migration pressure
- reference instability
- qualifier drift

That would let the repo prioritize high-impact review packs first instead of
attempting a flat global migration.

### Canonical-state split
The repo should keep the same canonical-state split already used in the broader
Wikipedia ingest lane:
- Wikipedia / WikiProject surface = upstream noisy substrate and proposal layer
- canonical wiki state / statement bundle = normalized evidence surface
- promoted semantic state = separate downstream decision

This avoids conflating:
- article consensus
- statement presence
- semantic equivalence
- migration safety

## Formal cross-system mapping `Φ`
The climate-change migration lane now has a sharper cross-system mapping:

```text
Φ : W × Π × Κ → L(P)
```

Where:
- `W` = source corpus slice
  - Wikipedia article text
  - talk-page discussions
  - WikiProject task pages
  - revision metadata
- `Π` = promotion policy
  - sourcing thresholds
  - controversial-topic restrictions
  - abstention rules
  - bounded-review protocol
- `Κ` = canonicalization regime
  - entity normalization
  - property normalization
  - citation/provenance normalization
  - uncertainty/conflict handling
- `L(P)` = typed promoted-fact graph

Interpretation:
- the WikiProject/Wikipedia surface is not promoted directly
- it is passed through a policy-aware and provenance-preserving transformation
  before anything enters promoted graph state

### Factorization of `Φ`

```text
Φ = φ7 ∘ φ6 ∘ φ5 ∘ φ4 ∘ φ3 ∘ φ2 ∘ φ1
```

#### `φ1` — ingest

```text
φ1 : W → A
```

`A` = anchored source atoms:

```text
a = (doc_id, span_start, span_end, text, source_type, rev_id, timestamp, author?)
```

Role:
- preserve reversible, provenance-bearing source substrate

#### `φ2` — candidate extraction

```text
φ2 : A → C
```

`C` = candidate claims:

```text
c = (subject?, predicate?, object?, qualifiers?, refs?, polarity?, confidence, anchors)
```

Role:
- produce candidate-bearing rows without prematurely collapsing ambiguity

#### `φ3` — canonical normalization

```text
φ3 : C → Ĉ
```

Normalize:
- entity identity
- property identity
- units/dates/places
- citation structures
- alias forms
- claim-bundle structure

Role:
- convert string-level variation into typed semantic comparison
- this is where `P5991` vs `P14143` must be treated as a semantic/bundle
  question rather than a label-substitution question

#### `φ4` — bundle comparison

```text
φ4 : Ĉ → B
```

`B` = statement bundles:

```text
b = (main_snak, qualifiers, references, rank, provenance_set)
```

Role:
- make the bundle, not the naked triple, the review unit

#### `φ5` — migration/review classification

```text
φ5 : B → M
```

`M` = migration bucket:

```text
M ∈ {
  safe_equivalent,
  safe_with_reference_transfer,
  qualifier_drift,
  reference_drift,
  ambiguous_semantics,
  non_equivalent,
  needs_human_review,
  abstain
}
```

Role:
- formalize review outcomes before promotion
- make abstention first-class rather than implicit failure

#### `φ6` — promotion

```text
φ6 : M × Π → P
```

Promote only when policy permits:

```text
p = promote(b) iff
    semantic_equivalence_ok(b)
 ∧  provenance_ok(b)
 ∧  controversial_topic_guard_ok(b)
 ∧  bounded_review_ok(b)
 ∧  no_unresolved_drift(b)
```

Else:

```text
p = abstain
```

Role:
- keep public consensus and repo promotion distinct
- require checked-safe status before any migration action is treated as
  promotable

#### `φ7` — graph construction

```text
φ7 : P → L(P)
```

Role:
- embed promoted facts into the canonical graph instead of leaving them as
  one-off case outputs

## Exact graph schema for climate articles: `L(P)`

```text
L(P) = (V, E, τV, τE, Σ, Ι)
```

Where:
- `V` = nodes
- `E` = edges
- `τV` = node typing
- `τE` = edge typing
- `Σ` = constraints
- `Ι` = invariants

### Node types

#### Entity nodes

```text
Article(id, title, wiki_project?, page_type)
Topic(id, label, canonical_qid?)
Person(id, name, role?)
Organization(id, name)
Place(id, name, geo?)
Event(id, label, date_range?)
Policy(id, label, jurisdiction?)
Source(id, url_or_citation, source_class)
Revision(id, rev_id, timestamp, editor)
Task(id, label, queue_type)
Property(id, pid, label)
ClaimBundle(id)
ReferenceBundle(id)
QualifierBundle(id)
ReviewCase(id, bucket, status)
```

#### Semantic control nodes

```text
Motif(id, class)
Conflict(id, conflict_type)
Uncertainty(id, kind, score?)
ConsensusState(id, level)
MigrationCase(id, from_property, to_property)
```

### Edge types

#### Structural edges

```text
has_revision(Article → Revision)
belongs_to_project(Article → Topic|Organization)
has_task(Article|Topic → Task)
mentions(Article|Revision|TalkSection → Topic|Person|Organization|Event|Policy)
```

#### Claim edges

```text
claims(Article|Revision|TalkSection → ClaimBundle)
about(ClaimBundle → Topic|Person|Organization|Event|Policy|Place)
uses_property(ClaimBundle → Property)
has_value(ClaimBundle → Entity|Literal)
has_qualifiers(ClaimBundle → QualifierBundle)
has_references(ClaimBundle → ReferenceBundle)
```

#### Provenance edges

```text
anchored_in(ClaimBundle → Revision|Article|TalkSection)
derived_from(ClaimBundle → Source)
supported_by(ClaimBundle → Source)
contested_by(ClaimBundle → Source|Revision|TalkSection)
```

#### Review / migration edges

```text
migration_of(MigrationCase → ClaimBundle)
maps_from(MigrationCase → Property)
maps_to(MigrationCase → Property)
classified_as(MigrationCase → ReviewCase)
requires_review(MigrationCase → ReviewCase)
resolved_by(ReviewCase → Person|Process)
```

#### Semantic / reasoning edges

```text
equivalent_to(ClaimBundle ↔ ClaimBundle)
conflicts_with(ClaimBundle ↔ ClaimBundle)
refines(ClaimBundle → ClaimBundle)
subsumes(ClaimBundle → ClaimBundle)
instantiates_motif(ClaimBundle → Motif)
has_uncertainty(ClaimBundle → Uncertainty)
```

### Literal types

```text
String
NormalizedString
Boolean
Date
DateRange
Quantity(unit)
GeoPoint
URL
CitationString
RevisionID
ConfidenceScore
BucketLabel
```

## Climate-specific constraints `Σ`

### `Σ1` — provenance constraint
Every promoted claim must have at least one anchored provenance path.

```text
∀ p ∈ P :
  promoted(p) ⇒ ∃ a,s .
    anchored_in(p,a) ∧ supported_by(p,s)
```

### `Σ2` — controversial-topic guard
For climate-topic claims marked contested, policy-sensitive, or
causal-attribution-sensitive:

```text
controversial(p) ⇒
  high_quality_sources(p)
  ∧ no_single_source_promotion(p)
  ∧ review_status(p) ∈ {checked_safe, human_reviewed}
```

### `Σ3` — bundle integrity
No migration decision may compare main snaks only.

```text
equivalence(b1,b2) valid only if
  main_snak_eq(b1,b2)
  ∧ qualifier_policy_ok(b1,b2)
  ∧ reference_policy_ok(b1,b2)
  ∧ rank_policy_ok(b1,b2)
```

### `Σ4` — abstention admissibility
If semantic equivalence cannot be established, abstention is valid.

```text
underdetermined(b) ⇒ class(b) = abstain ∨ needs_human_review
```

### `Σ5` — bounded-slice review
No large migration is promotable without a pinned bounded slice.

```text
bulk_migration(M) ⇒ ∃ Sbounded .
  reviewed(Sbounded) ∧ checked_safe_subset(Sbounded)
```

### `Σ6` — no bot-before-safe-subset

```text
bot_export_allowed(M) only if
  checked_safe_subset_exists(M)
```

### `Σ7` — revision-window consistency
A migration case should be scored against revision-window drift, not a single
snapshot only.

```text
classify(b) depends_on compare_window(b, Δt)
```

## Invariants `Ι`

### `Ι1` — canonical/truth separation
Raw wiki text is never itself promoted truth.

```text
ArticleText ∉ P
```

### `Ι2` — provenance monotonicity
Adding a supporting source cannot reduce provenance completeness.

### `Ι3` — abstention safety
Abstention is not an error state. It is a valid terminal review state.

### `Ι4` — bundle over token priority
All semantic decisions are made over normalized bundles, not over label
similarity.

### `Ι5` — policy-aware promotion
Promotion for climate-topic content is gated by sourcing and controversy
constraints, not just syntactic equivalence.

### `Ι6` — migration honesty
A property migration may produce:
- promote
- review
- abstain
- non-equivalent

It is not required to produce a replacement claim in every case.

## Exact climate-article subgraph pattern

```text
Article
 ├── has_revision → Revision*
 ├── belongs_to_project → WikiProjectClimateChange
 ├── mentions → Topic*
 ├── claims → ClaimBundle*
 │      ├── about → Topic|Event|Policy|Place|Organization
 │      ├── uses_property → Property
 │      ├── has_value → Entity|Literal
 │      ├── has_qualifiers → QualifierBundle?
 │      ├── has_references → ReferenceBundle+
 │      ├── anchored_in → Revision|Article
 │      ├── equivalent_to / conflicts_with → ClaimBundle*
 │      ├── has_uncertainty → Uncertainty?
 │      └── instantiates_motif → Motif?
 └── has_task → Task*
```

For migration review:

```text
MigrationCase
 ├── migration_of → ClaimBundle
 ├── maps_from → Property(P5991)
 ├── maps_to → Property(P14143)
 ├── classified_as → ReviewCase(bucket)
 ├── supported_by → Source*
 ├── contested_by → Source|Revision|TalkSection*
 └── resolved_by → Person|Process?
```

## Minimal formal prototype contract

```text
Input:
  climate article slice W
Output:
  graph L(P)

Pipeline:
  W
  → anchored atoms A
  → candidate claims C
  → normalized bundles B
  → migration buckets M
  → promoted facts P
  → graph L(P)
```

Required review outputs:

```text
review_pack = {
  bounded_slice,
  statement_bundle_diffs,
  qualifier_drift_report,
  reference_drift_report,
  migration_bucket_counts,
  checked_safe_subset,
  abstentions,
  ambiguous_cases
}
```

## Recommended next repo steps
1. Keep this as a planning/review lane first; do not add a bot runner yet.
2. Use the new bounded migration-pack contract for property-to-property review:
   - `docs/planning/wikidata_migration_pack_contract_20260328.md`
   - `schemas/sl.wikidata_migration_pack.v1.schema.yaml`
3. Use `sensiblaw wikidata build-migration-pack` as the first executable
   surface for checked-safe subset construction.
4. Materialize one pinned climate-change migration pack before discussing any
   wider batch.
   - DONE in:
     `SensibLaw/data/ontology/wikidata_migration_packs/p5991_p14143_climate_pilot_20260328/`
   - built from revision-locked live exports via:
     `SensibLaw/scripts/materialize_wikidata_migration_pack.py`
   - first observed bucket distribution:
     - `safe_with_reference_transfer`: 2
     - `ambiguous_semantics`: 55
   - immediate lesson: the first live pressure is temporal/multi-value
     ambiguity, not qualifier/reference drift
5. Add richer policy-driven buckets such as `non_equivalent`,
   `needs_human_review`, and `split_required` only after a real pinned pack
   shows what the missing evidence actually is.

## Non-goals
- no claim that the repo should decide Wikidata ontology governance
- no claim that all `P5991` statements should move
- no automatic mass-edit generation from raw WDQS rows
- no loss of qualifiers/references in the name of cleanup speed

## Current recommendation
If answering the live discussion, the strongest repo-backed position is:

- frame the work as a bounded, review-first migration
- insist on statement-bundle comparison rather than property-name replacement
- propose a small checked sample before any batch action
- explicitly separate safe rewrites from semantic mismatches and manual-review
  cases

That answer is materially stronger than generic caution because it matches
methods already implemented in the repo's Wikidata lane.
