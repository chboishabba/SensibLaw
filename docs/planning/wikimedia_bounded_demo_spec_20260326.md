# Wikimedia Bounded Demo Spec for the Wikidata Lane

Last updated: 2026-03-26

## Purpose
Choose a concrete, repo-backed demo scope for the Wikimedia Rapid Fund draft so
the proposal stops speaking in generic "Wikipedia -> Wikidata" terms and starts
naming the exact bounded slice, baseline, and reviewer-facing pain points.

## Why this spec exists
The grant draft is already shaped correctly, but reviewers still need one
explicit answer to:
- what exact demo subset will be used
- what properties and artifacts are in scope
- what counts as contradiction, missing claim, and unsupported claim
- what baseline the evaluation uses

This note keeps the answer aligned with current repo reality rather than with a
broader aspirational extraction story.

## Attribution discipline
This proposal surface must distinguish:
- who surfaced or popularized a case or method
- what the repo itself implemented, pinned, or tested

Primary attribution matrix:
- `docs/planning/wikimedia_demo_attribution_matrix_20260326.md`
- `docs/planning/wikimedia_prior_work_and_originality_note_20260326.md`

Current attribution reading for this bounded demo:
- `GNU` / `GNU Project` should not be presented here as a repo-original
  discovery; the repo contribution is the bounded page-review/fixture/reporting
  integration around that case, not claiming first discovery
- broader classification-hierarchy / `P31`-`P279` inconsistency context should
  explicitly credit Shixiong Zhao and Hideaki Takeda where the proposal
  references recent hierarchy-diagnosis work adjacent to this slice
- bounded `P2738` disjointness framing should explicitly credit Ege Doğan and
  Peter Patel-Schneider where the proposal references the broader
  disjointness-violation method/problem space
- if a case is used only because it is legible and already fixture-backed, say
  that; do not imply original authorship by the repo

## Selected demo shape
Use a two-tier bounded demonstration:

1. a primary foreground demo built from the safest repo-owned structural packs
2. a secondary attributed appendix of article/page-review entity-kind examples

This is the safest submission choice because:
- the repo-owned structural packs are the clearest fixtures to foreground
- the attributed entity-kind examples remain useful, but do not need to carry
  the whole proposal story
- this reduces attribution risk without discarding the Wikipedia-facing angle

## Primary foreground demo: repo-owned structural packs

### Exact bounded inputs
Use these exact fixture-backed inputs as the lead submission/demo surface:

#### 1. Mixed-order pack
- pack:
  `mixed_order_live_pack_v1`
- source artifact:
  `SensibLaw/tests/fixtures/wikidata/live_p31_p279_slice_20260307.json`
- focus QIDs:
  - `Q9779`
  - `Q8192`
  - `Q21169592`
  - `Q7187`
- focus PIDs:
  - `P31`
  - `P279`

#### 2. `P279` SCC pack
- pack:
  `p279_scc_live_pack_v1`
- source artifact:
  `SensibLaw/tests/fixtures/wikidata/live_p31_p279_slice_20260307.json`
- focus QIDs:
  - `Q22652`
  - `Q22698`
  - `Q52040`
  - `Q188`
- focus PIDs:
  - `P279`

#### 3. Qualifier-drift packs
- primary pinned case:
  - `Q100104196|P166`
  - revisions `2277985537 -> 2277985693`
  - artifacts:
    - `SensibLaw/tests/fixtures/wikidata/q100104196_p166_2277985537_2277985693/slice.json`
    - `SensibLaw/tests/fixtures/wikidata/q100104196_p166_2277985537_2277985693/projection.json`
- secondary pinned case:
  - `Q100152461|P54`
  - revisions `2456615151 -> 2456615274`
  - artifacts:
    - `SensibLaw/tests/fixtures/wikidata/q100152461_p54_2456615151_2456615274/slice.json`
    - `SensibLaw/tests/fixtures/wikidata/q100152461_p54_2456615151_2456615274/projection.json`

#### 4. Bounded disjointness packs
- contradiction case:
  - `fixed_construction_contradiction`
  - artifact:
    `SensibLaw/tests/fixtures/wikidata/disjointness_p2738_fixed_construction_real_pack_v1/slice.json`
- contradiction case:
  - `working_fluid_contradiction`
  - artifact:
    `SensibLaw/tests/fixtures/wikidata/disjointness_p2738_working_fluid_real_pack_v1/slice.json`
- zero-violation baseline:
  - `nucleon_baseline`
  - artifact:
    `SensibLaw/tests/fixtures/wikidata/disjointness_p2738_nucleon_real_pack_v1/slice.json`

#### 5. Checked review/report surfaces
- `SensibLaw/tests/fixtures/zelph/wikidata_structural_handoff_v1/`
- `SensibLaw/tests/fixtures/zelph/wikidata_structural_review_v1/`
- `SensibLaw/tests/fixtures/zelph/wikidata_dense_structural_review_v1/`

### Why this is foregrounded
- These are the safest repo-owned surfaces in the attribution matrix.
- They already have deterministic fixture/report backing.
- They cover multiple reviewer-legible problem classes:
  - mixed class/instance use
  - subclass loops
  - qualifier drift
  - disjointness contradiction

### Primary target properties
- `P31`
- `P279`
- `P166`
- `P54`
- `P2738`
- `P11260`

## Secondary attributed appendix: article-backed entity-kind review

### Scope
- Wikipedia/article-facing focus:
  - `GNU`
  - `GNU Project`
- Wikidata item focus:
  - `Q44571` (`GNU`)
  - `Q7598` (`GNU Project`)

### Target properties
- `P31`
- `P279`
- `P527`

### Why this slice
- It already appears in the repo's page-review candidate index:
  `docs/planning/wikidata_page_review_candidate_index_v1.json`
- It is legible to reviewers without domain-specific setup.
- It expresses a real Wikimedia pain point:
  artifact/project/community/entity-kind collapse.
- It supports the grant story that article-backed extraction plus exact
  provenance can help surface reviewable Wikidata structure problems.
- Attribution note:
  - treat `GNU` / `GNU Project` as an attributed, reviewed case rather than as
    a repo-original discovery
  - where this slice is contextualized as part of broader classification-
    hierarchy inconsistency work, credit Shixiong Zhao and Hideaki Takeda
  - the repo contribution in the grant story is the bounded deterministic
    review-pack/reporting surface built around the case

### Revision-lock status
For submission safety, this slice should remain secondary until exact
revision-locked article snapshots are named in a final submission pack.

Current safe wording:
- use this as an attributed appendix/example, not as the lead evidentiary demo
- do not claim the proposal depends on proving broad article-extraction
  coverage through this slice alone

### What counts as a missing claim in this slice
A deterministic candidate fact extracted from the selected revision-locked
article text counts as `missing_claim` when:
- it is in the bounded target predicate set above
- it carries exact span-level provenance
- it survives the repo's bounded extraction/review gating
- there is no corresponding bounded Wikidata statement in the target item after
  the selected normalization rules for this demo

### What counts as an unsupported claim in this slice
A current Wikidata statement in the bounded target predicate set counts as
`unsupported_claim_in_slice` when:
- it falls inside the selected demo subset
- the selected revision-locked article text does not yield matching bounded
  support under the demo extraction rules

Important:
- this means unsupported in the bounded article slice, not globally false
- the flag is a review prompt, not an automatic correction

### What counts as a contradiction in this slice
For the article-backed entity-kind slice, contradiction is secondary rather
than primary. The main outputs are:
- `missing_claim`
- `unsupported_claim_in_slice`
- entity-kind review pressure

If a bounded extracted candidate and the current Wikidata statement conflict in
predicate/object class within the chosen normalization rules, it may be
reported as `article_vs_item_conflict`, but this is not the primary evaluation
target for Slice A.

## Primary review-class definitions
These definitions govern the foreground repo-owned demo.

### Scope
Use the compact checked-review focus set:
- qualifier drift cases:
  - `Q100104196|P166`
  - `Q100152461|P54`
- disjointness contradiction cases:
  - `fixed_construction_contradiction`
  - `working_fluid_contradiction`

Primary artifacts:
- `SensibLaw/tests/fixtures/wikidata/q100104196_p166_2277985537_2277985693/`
- `SensibLaw/tests/fixtures/wikidata/q100152461_p54_2456615151_2456615274/`
- `SensibLaw/tests/fixtures/wikidata/disjointness_p2738_fixed_construction_real_pack_v1/`
- `SensibLaw/tests/fixtures/wikidata/disjointness_p2738_working_fluid_real_pack_v1/`
- `SensibLaw/tests/fixtures/zelph/wikidata_structural_review_v1/`
- `SensibLaw/tests/fixtures/zelph/wikidata_dense_structural_review_v1/`

### Target properties
- qualifier drift:
  - `P166`
  - `P54`
- disjointness/contradiction:
  - `P2738`
  - `P11260`

### Why this scope
- It is already the most compact and legible checked-review set named in
  `SensibLaw/docs/wikidata_working_group_status.md`.
- It covers two reviewer-legible Wikimedia pain points:
  - qualifier signature drift across revision windows
  - structurally contradictory class/item configurations
- It is fully fixture-backed and reproducible.
- Attribution note:
  - the broader `P2738` disjointness problem/method context should explicitly
    credit Ege Doğan and Peter Patel-Schneider
  - the repo claim is narrower: bounded deterministic reporting, pinned cases,
    culprit-oriented review output, and live-first candidate discovery

### What counts as a contradiction in the foreground demo
A case counts as `contradiction` when the pinned structural review artifacts
show an explicit disjointness violation or equivalent structural conflict in
the selected real pack.

For this bounded demo, the canonical contradiction cases are:
- `fixed_construction_contradiction`
- `working_fluid_contradiction`

Mixed-order and SCC packs are diagnostic structure surfaces, not
missing-claim surfaces. Missing-claim accounting is therefore not primary in
the foreground demo and should only be reported where the checked review
surface already exposes a review gap in a predicate/window explicitly covered
by the selected artifacts.

### What counts as an unsupported claim in the foreground demo
For the qualifier-drift cases, the relevant bounded signal is not "unsupported"
in the article-text sense but:
- signature drift across revision windows
- changed qualifier structure requiring reviewer inspection

Do not relabel qualifier-drift findings as article unsupported-claim findings.

## Reviewer-facing pain points to name explicitly
Use these in the submission draft and any reviewer conversations:
- mixed-order class/instance confusion on pinned `P31` / `P279` slices
- reciprocal/circular subclass pressure on pinned `P279` SCC slices
- `Q100104196|P166` and `Q100152461|P54`:
  qualifier drift across pinned revision windows
- `fixed_construction_contradiction`:
  real contradiction around immaterial vs material entity treatment
- `working_fluid_contradiction`:
  real contradiction around gas vs liquid disjointness
- secondary appendix only:
- `GNU` / `GNU Project`:
  entity-kind collapse across artifact/project/community boundaries

When naming these pain points:
- credit the broader hierarchy/classification-inconsistency context to
  Shixiong Zhao and Hideaki Takeda where relevant
- credit the disjointness-method context to Ege/Peter where relevant
- avoid implying that the `GNU` / `GNU Project` case was first discovered by
  this repo

## Chosen evaluation baseline
Use a two-part baseline:

### Primary adjudication baseline
Manual bounded review over the selected subset.

Why:
- the demo is intentionally small
- reviewer trust matters more than high-volume automated scoring
- the repo doctrine requires visible absences and no silent promotion

### Secondary comparison process
Use the current repo checked-review process as the operational comparison
surface:
- `SensibLaw/tests/fixtures/zelph/wikidata_structural_review_v1/`
- `SensibLaw/tests/fixtures/zelph/wikidata_structural_handoff_v1/`

Why:
- this keeps the proposal grounded in already reproducible repo behavior
- it avoids pretending there is a stable external heuristic comparator already
  adopted by the repo
- it still gives the grant draft a concrete "current process vs improved tool"
  story

Do not claim a broad external NLP baseline unless one is actually chosen and
checked later.

## Reviewer route
Use a two-tier reviewer route:

### Preferred route
- 1-2 Wikidata/ontology-adjacent reviewers from the working-group/contact lane
  if available

### Fallback route
- 1-2 technically adjacent reviewers who can assess:
  - legibility of the review outputs
  - clarity of provenance
  - usefulness of the bounded contradictions/drift findings

This keeps the submission honest:
- Wikimedia-native review is preferred
- the proposal does not depend on promising named external reviewers before
  they are actually confirmed

## Demo acceptance reading
The demo is good enough for the submission story if:
- the foreground repo-owned packs reproduce the named mixed-order, SCC,
  qualifier-drift, and disjointness findings
- the pinned structural slice reproduces the named qualifier-drift and
  contradiction findings
- the outputs stay inspectable and bounded
- the preferred/fallback reviewer route is made explicit in the submission pack
- unsupported-in-slice is kept clearly distinct from globally false
- no part of the story implies autonomous bot-style Wikidata repair

## What this demo is not
- not a claim of broad open-domain Wikipedia extraction coverage
- not a claim of general-purpose Wikidata ontology repair
- not a claim that every review class is article-backed today
- not a replacement for human editor judgment
- not a claim of first discovery for every demo case in the submission pack

## Promotion decision
For the current proposal, promote this as the bounded demo scope.

That means:
- submission wording should foreground the repo-owned structural packs and keep
  the entity-kind cases as attributed secondary examples
- evaluation wording should use the baseline defined here
- reviewer-story hardening should name the pain points listed here
- final submission text should preserve the preferred/fallback reviewer route
