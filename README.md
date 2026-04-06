# SensibLaw

SensibLaw is the suite's deterministic review and provenance layer.

In plain language, it takes difficult source material and turns it into
structured, inspectable outputs instead of opaque summaries. It is used for
legal/normative review, structured evidence handling, and bounded ontology
diagnostics such as the current Wikidata work.

## What SensibLaw Does

SensibLaw currently provides:

- ingestion of source material into structured, anchored artifacts
- deterministic review/report surfaces instead of free-form narrative output
- provenance-backed JSON artifacts and handoff bundles
- bounded Wikidata diagnostics over pinned slices
- export/handoff paths into downstream reasoning and review layers such as
  Zelph

## Observation Substrate Doctrine

OpenRecall and WorldMonitor should be treated as two observation sources in
the same ingestion substrate, not as separate semantic planes.

- WorldMonitor:
  external observation source
- OpenRecall:
  internal observation source
- SensibLaw:
  canonicalization, reconciliation, promotion, and abstention
- StatiBaker:
  governance and workflow state

The current bounded rule is:

- normalize WM and OpenRecall into the same observation-style substrate
- feed that substrate into the existing relation/equivalence path
- keep the result derived-only and operator-facing first

For WorldMonitor specifically, the supported bridge is:

- import WorldMonitor into ITIR through the observation lane
- export SB-safe `worldmonitor_capture` rows into `StatiBaker/runs/<date>/logs/worldmonitor/<date>.jsonl`
- run `StatiBaker/scripts/run_day.sh`
- read the imported lane back through `SensibLaw/scripts/query_observation_import.py --lane worldmonitor summary`
- build an SL chronology readout through `SensibLaw/scripts/query_worldmonitor_import.py chronology`

The one-command local path is:

```bash
../.venv/bin/python StatiBaker/scripts/run_worldmonitor_bridge.py \
  --date 2026-04-06 \
  --repo-path . \
  --worldmonitor-repo-path ../worldmonitor
```

By default this uses `../worldmonitor/data` as the source export path. Add:

- `--bootstrap-worldmonitor` to run `npm install` in the sibling WorldMonitor repo first
- `--smoke-worldmonitor-dev` to start the local WorldMonitor dev server, wait for it to answer, then stop it before ingest

If the data tree has not changed and WorldMonitor import de-duplicates to zero
new captures, the bridge reuses the latest populated import run for that same
resolved source path so the SL summary/chronology and SB export stay non-empty.

The bridge exports the whole effective import run into SB by default. Use
`--captured-date YYYY-MM-DD` only if you intentionally want to narrow the SB
observed export to one WorldMonitor source date.

The current explicit non-goals are also important:

- do not introduce a separate "perception layer" yet
- do not promote OpenRecall capture/OCR as truth by itself
- do not land cognitive-join or attention-invariant machinery yet
- do not let perception-vs-truth divergence or Delta-cone work outrun the
  shared observation-ingestion contract

The next honest seam on this front is substrate normalization, not a full
slice-state or epistemic-control regime.

The current architecture direction is no longer lane-by-lane growth. It is a
single normalized process that different source families and work lanes bind
onto over time.

## Canonical Ingestion Doctrine

The stronger parser doctrine is now:

- one upstream media-adapter layer
- one canonical text substrate for ordinary content
- one parser spine over canonical text
- extraction behavior sits above the parser as a profile, not a separate
  parser family
- first landed bounded profile:
  `normative_policy`
- source provenance is metadata, not parser identity
- mixed-content documents are first-class:
  prose with embedded code, quotes, tables, headings, citations, and lists
  should stay inside the same parser spine

## Normalized Ingestion Contract

- ordinary inputs are adapted into canonical text
- the parser spine discovers structure from canonical text; structure is not
  an input type
- extraction profiles consume parsed output and emit domain-specific artifacts
- code, quotes, tables, headings, citations, and lists may appear inline in
  ordinary documents and must remain inside the same parser spine
- PDF, HTML, JSON rows, transcript markup, and similar forms are adapter or
  segmentation details, not canonical parser categories
- provenance such as outlet, issuer, publisher, archive, genre, entity scope,
  or document numbering remains metadata unless it changes extraction behavior
  materially
- structuredness is a property of parsed segments and graphs, not a declared
  source ontology

### What Counts As Input

- the adapter layer may branch on real media mechanics only, for example:
  - document-like binary input
  - document-like text input
  - non-text media that must be transcribed or transformed upstream
- ordinary document-like inputs should collapse to one canonical text
  substrate before parsing
- non-text media remain upstream adapter concerns; they do not create
  parser-family doctrine

### What Stays Metadata

- outlet, publisher, issuer, archive, entity scope, and document numbering
- source URLs, public-record IDs, retrieval details, and checksums
- genre-like hints such as affidavit, memoir, journalism, or standard
- any lane-local grouping label used for review orchestration rather than
  parsing

The important design choice is that SensibLaw is not trying to be "the model
that knows the answer." It is trying to preserve source traceability while
making reviewable structure.

One caution matters here: a lane-local facade is not the same thing as a
cross-lane canonical substrate. Files such as
`src/policy/affidavit_normalized_surface.py` are useful stabilization layers,
but they are still adapter-local. They should be treated as temporary
normalization shells until the underlying concepts are extracted into
lane-agnostic surfaces that AU, GWB, affidavit, Wikidata/Nat, and future lanes
can all share.

Another caution also matters: not every decision surface in the suite should
share one vocabulary.

- product gate:
  promotion posture over normalized products
- proposition resolution:
  resolution posture over proposition identity/relation work

Those are related but distinct ontologies. Today that means:

- product gate uses:
  `promote | audit | abstain`
- proposition resolution uses:
  `hold | abstain`

The important boundary is semantic, not cosmetic. Product-gate `abstain`
currently means the gate declines promotion, typically because there are no
promoted outcomes. Proposition-resolution `hold` is the neutral fail-closed
state for unresolved proposition work. Future normalization should keep those
layers distinct unless a full cross-consumer migration deliberately changes the
product-gate contract.

One more normalization boundary is now pinned too: cross-lane normalization
must follow semantic convergence, not structural similarity alone.

- current maximal shared review primitive:
  `review_candidate`
- current interpretation:
  a weak, descriptive candidate carrier with:
  - `candidate_id`
  - `candidate_kind`
  - `source_kind`
  - `selection_basis`
  - `anchor_refs`
  - optional `target_proposition_id`
- current non-goal:
  do not promote a shared `review_alignment` surface yet

Why that boundary exists:

- affidavit targeting currently means proposition -> best source row
- GWB targeting currently means source-review row -> review item / seed-linked
  target
- AU targeting currently means review-queue row -> event-target subset

Those can belong to one broader targeting family, but they are not yet one
shared emitted semantic object. The repo therefore treats:

- `review_text`
- `review_candidate`

as the current honest shared normalized outcome, while higher-order alignment
or targeting interpretation stays lane-local until at least two lanes converge
on the same source meaning, target meaning, basis vocabulary, and downstream
interpretation.

The practical doctrine is:

- normalize shared primitives now
- normalize the targeting kernel before emitted alignment semantics
- keep emitted structural targeting results weak and descriptive
- hold composite alignment surfaces until semantics converge
- do not let shared methods or structural similarity be mistaken for shared
  meaning

The renewed targeting/alignment formalism is:

- current canonical shared emitted primitives:
  - `review_text`
  - `review_candidate`
- current bounded carrier:
  - `selection_basis`
- next shared method layer:
  - `TargetingKernel`
- next shared structural layer:
  - `WeakTargetingResult`
- future experimental layer:
  - `AlignmentPrimitive`
- explicit hold:
  - shared emitted `review_alignment`
- deeper unifying read:
  - one shared `Targeting` primitive
  - many lane-local interpretations

Interpretation:

- `TargetingKernel` normalizes how targets are generated, filtered, and
  selected
- `WeakTargetingResult` normalizes the weak structural result of that process
- affidavit, GWB, and AU can all be treated as members of one targeting
  family under different boundary conditions and constraints
- `AlignmentPrimitive` is only a future experimental surface for lanes that
  really converge
- `review_alignment` remains held until semantic convergence is explicitly
  proven

The stronger reframing is:

- one targeting primitive:
  `Targeting := (Origin, CandidateSet, Constraints, SelectionOperator)`
- one lane-specific parameterization:
  `Targeting_L := Targeting | sigma_L`
- one key boundary:
  normalize the primitive and weak structural result, not the emitted
  interpretation
- one falsification result:
  cross-applying lane interpretations shows shared process but non-identical
  interpretation

That means:

- all alignment is targeting
- not all targeting is alignment
- AU is clearly a targeting adopter even where alignment semantics remain too
  strong
- affidavit and GWB remain the first plausible future pair for a true
  alignment primitive

Cross-lane interpretation testing currently shows:

- affidavit interpretation is too strong to generalize cleanly
- GWB interpretation is still too seed-structured to generalize cleanly
- AU interpretation is the weakest and most general, but too lossy as a
  universal semantic reading

What survives that test is:

- shared process:
  origin -> constrained selection over a candidate set
- non-shared interpretation:
  alignment, linkage, and routing are still lane-local views over that
  process

So the next stronger normalization target is capability-based:

- normalize to the richest justified targeting structure
- let simpler lanes be degenerate cases of that structure
- do not freeze the shared contract at the weakest current adopter

In practice this points toward a set-based targeting result:

- the shared kernel should support selected-set targeting
- affidavit can remain a singleton case
- GWB can widen only when real multi-candidate linkage exists
- AU already fits the richer target-set form

The current likely convergence path is:

- affidavit + GWB:
  possible future `AlignmentPrimitive` pair
- AU:
  targeting-kernel adopter first, alignment adopter later if ever justified

One bounded vocabulary can still be normalized now without overclaiming shared
alignment semantics:

- `selection_basis` may reduce toward:
  - `source_row_match`
  - `seed_linkage`
  - `bounded_exact_ref`
  - `anchor_overlap`
  - `event_subset_targeting`
  - `lane_local_other`

That is basis normalization, not full emitted semantic-object normalization.

One governance rule is now pinned in code and tests too:

- `review_candidate` remains the canonical shared emitted primitive
- `alignment_readiness_assessment` is the promotion oracle
- internal set-based targeting may widen before any shared emitted alignment
  surface exists
- `multi_candidate_unresolved` is a valid fail-closed outcome, not a bug to
  smooth over
- no shared emitted `review_alignment` surface may appear unless the
  equivalence assessment verdict is `promote`

The first empirical GWB ambiguity audit forced one more implementation step:

- the earlier checked pipeline expressed singleton targeting only because
  `review_item_rows` collapsed to one row per `seed_id`
- that collapse point has now been widened upstream:
  - public review splits multi-match seeds by matched event
  - broader review splits multi-match seeds by matched source family

That widening exposed a stronger governance result too:

- real multiplicity is now representable in GWB
- but multiplicity alone still does not justify shared emitted alignment
- a forced synthetic multiplicity slice currently drops the affidavit↔GWB
  readiness read from `prototype_only` to `hold`
- reason:
  once GWB is genuinely multi-candidate and unresolved, stable target
  semantics are not yet instantiated on the emitted claim records

So the current doctrine is:

- representation fidelity comes before higher-order alignment semantics
- capability may exceed current data, but promotion follows represented data
- multiplicity alone is insufficient; emitted target semantics must still be
  stable enough for equivalence to read honestly

Post-widening evidence is now real:

- public GWB:
  - `28` `singleton_seed_linkage`
  - `42` `multi_candidate_unresolved`
- broader GWB:
  - `14` `singleton_seed_linkage`
  - `13` `multi_candidate_unresolved`

So candidate-set fidelity is no longer blocked by the old one-review-item-per-
seed construction. The system can now express multiplicity honestly and still
fail closed when multiplicity appears.

That does not change the emitted shared boundary:

- `review_candidate` remains canonical
- shared emitted `review_alignment` remains held
- `multi_candidate_unresolved` remains the correct fail-closed outward state
- promotion still depends on `alignment_readiness_assessment`

The refreshed archive thread also tightens the normalization doctrine itself. In
this repo, proper normalization now means all three of these hold:

- representation fidelity
- semantic separability
- safe promotion boundaries

Current read:

- representation fidelity:
  materially improved and now good enough for honest GWB multiplicity
- semantic separability:
  partially implemented through helper/oracle work, but not yet canonicalized as
  first-class shared interpretation entities
- safe promotion boundaries:
  working correctly; emitted shared alignment is still blocked

That means the next higher-order normalization work is no longer more emitted
alignment pressure. It is the bounded helper/design program around:

- semantic fingerprint schema aligned to the SL layers
- cross-system alignment schema and mapping rules
- explicit source/target semantics relation maps for asymmetric lanes
- stronger but still helper-only existential/path-intersection matching for
  affidavit ↔ GWB style comparisons

One source-classification correction is now pinned too:

- the repo now has real Bush-family affidavit/public-record PDFs, but they do
  not all belong to the same entity lane
- `Affidavit_of_George_William_Bush_880921.pdf` is affidavit-shaped and useful,
  but it is for George William Bush, i.e. George H. W. Bush, not George W.
  Bush
- `CIA-RDP99-01448R000401570001-1.pdf` is a declassified documentary/public-
  record source about the older Bush/CIA question, not an affidavit and not a
  George W. Bush memoir/public-review analogue
- `21-3071-2022-10-24.pdf` is an unrelated criminal appeal for another
  `George Bush, Jr.` and should stay out of Bush normalization work
- image-only PDFs such as `Jordan Paust Affidavit.pdf`,
  `104-10336-10008.pdf`, and `t081-059e-725789-1-59639.pdf` remain pending OCR
  before they can be classified honestly

The current source-normalization read is therefore:

- primary normalized axes:
  - `entity_scope`
  - `source_class`
  - `source_subtype`
  - `artifact_kind`
  - `unit_kind`
- normalization rule:
  do not make medium labels such as `book` or lane-local names such as
  `gwb_books_memoir_corpus` into primary canonical families unless they drive
  materially different provenance handling or extraction behavior
- current working class split:
  - `text_source`
- normalization consequence:
  `normative` stays a provenance/extraction subtype under `text_source`, not a
  separate top-level class
- derived outputs must stay out of source typing:
  - `artifact_kind` examples:
    - `extractability_checkpoint`
    - `claim_sheet`
    - `policy_extract`
    - `ir_extract`
    - `graph_extract`
  - `unit_kind` examples:
    - `text_unit`
    - `timeline_event`
    - `aoo_event`
    - `policy_statement`
    - `ir_query`

Applied to the current Bush-family material, that means:

- GHWB affidavit/public-record material:
  - `entity_scope`: `ghwb`
  - current default `source_class`: `text_source`
  - current `source_subtype` values:
    - `affidavit`
    - `declassified_public_record`
- GWB official-public-record material:
  - `entity_scope`: `gwb`
  - `source_class`: `text_source`
  - current `source_subtype` values:
    - `dod_foia`
    - `federal_register_document`
    - `federal_register_notice`
    - `official_record_index`
    - `official_record_attachment`
- GWB underused book/memoir/public-writing material:
  - `entity_scope`: `gwb`
  - current default `source_class`: `text_source`
  - current `source_subtype` values are intentionally restrained:
    - `memoir`
    - `biography`
    - `investigative_nonfiction`
- GWB journalistic/public-reporting material:
  - `entity_scope`: `gwb`
  - current default `source_class`: `text_source`
  - current `source_subtype`:
    - `journalistic_reporting`
- bounded normative-docset pilot material:
  - example `entity_scope`: `iso_42001`
  - current default `source_class`: `text_source`
  - current `source_subtype`:
    - `normative_standard`
    - `excerpt_pack`
  - current lane doctrine:
    - ISO material stays on the same shared parser spine and bounded
      `normative_policy` projection as other text sources
    - external ISO catalogues, PAS indexes, and similar discovery pages are
      reconnaissance aids only, not canonical runtime semantic sources
    - the allowed ISO lane is bounded reuse, excerpt-pack quality, and
      profile proof, not a separate parser family or broad standards-catalog
      ingestion program
- GWB affidavit-style material:
  still not present as a normalized runtime artifact

This also sharpens one priority call:

- the underused GWB book/memoir material should be normalized as
  `textual_source`, not elevated into a top-level book family by name alone
- the broader corpus already includes `corpus_book_timeline` and local book
  files under `demo/ingest/gwb/`, including memoir/public-book material such
  as `Decision Points`
- the next honest move above that textual source class is extractability proof
  first
- only after that does a bounded memoir/public-record claim sheet become
  honest
- a fake affidavit surface remains out of scope

The refreshed thread also restores the full active lane map for this area. The
current live lanes are:

- GHWB text-source normalization over affidavit/declassified-public-record
  material
- GWB text-source normalization over official-record material
- GWB text-source tightening over the underused books/memoir material and
  later claim-sheet readiness
- GWB text-source journalistic/public-reporting normalization
- affidavit ↔ GWB convergence/oracle work
- basis/source-semantics normalization for the oracle and claim surfaces
- operator/dev ambiguity and source inspection helpers
- semantic fingerprint schema design
- cross-system alignment schema design
- bounded text-source ingestion and extraction pilot work for normative
  material, including:
  - Qur'an -> Sharia subset
  - ISO docsets -> policy / graph extraction
- explicit verification planning after each helper/builder round

The OCR lane is now explicitly held rather than active:

- image-only PDFs such as `Jordan Paust Affidavit.pdf`,
  `104-10336-10008.pdf`, and `t081-059e-725789-1-59639.pdf` stay behind OCR
  until OCR is proven to be the real blocker for a promoted source-family move

The standards/governance overlays for those lanes are now explicit too. They are
not separate runtime products, but they are mandatory governance lenses over the
work:

- ITIL: change control, rollback clarity, and service continuity
- ISO 9000: traceable requirements, acceptance criteria, nonconformance
  handling
- ISO 42001: intended AI use, oversight, lifecycle controls
- ISO 27001: least privilege and security-sensitive handling
- ISO 27701: privacy minimization if personal data appears
- ISO 23894: AI risk identification, treatment, and residual-risk clarity
- NIST AI RMF: govern, map, measure, manage
- Six Sigma: defect framing, root-cause discipline, and control after fix
- C4/PlantUML: only if architecture/topology changes enough to justify diagrams

Current promotion rule remains strict:

- no shared emitted `review_alignment`
- no source-family promotion without entity clarity
- no OCR-first widening unless OCR is the real blocker
- no normative-docset pilot promoted into canonical runtime surfaces until the
  ingestion and extraction layer proves it can emit bounded policy / graph / IR
  surfaces honestly
- no cross-system pilot promoted into canonical runtime surfaces until the
  helper/design layers prove semantic fit honestly

## What You Can Do With It Today

### 1. Build structured review artifacts from messy source material

SensibLaw can turn source material into:

- structured slices
- projections
- review queues
- handoff bundles
- provenance-aware JSON outputs

Why that matters:

- a later reviewer can inspect what was extracted
- uncertainty and disagreement can stay visible
- downstream systems do not need to depend on ad hoc notes

### 2. Run bounded Wikidata review/diagnostic workflows

This is one of the clearest current external examples of SensibLaw doing
something real.

Current repo-backed examples include:

- a clean baseline around `nucleon` / `proton` / `neutron`, where the
  disjointness relation is present but there are no violations
- a real contradiction around `working fluid`, where `working fluid` is typed
  as both `gas` and `liquid`
- a real contradiction in the `fixed construction` / `geographic entity` area,
  where the current pinned slice shows several subclass violations
- a synthetic transport example used to keep the reporting deterministic, with
  amphibious/land/water subclass and instance violations

What those examples imply:

- the lane can preserve a genuine zero-violation baseline
- it can catch direct instance-level contradictions
- it can also catch longer structural subclass problems
- it can present those findings in reviewer-facing summaries rather than only
  raw graph output

### 3. Produce checked handoff artifacts

SensibLaw already has bounded, checked handoff outputs for multiple lanes.

That matters because the outputs are:

- stable enough to discuss with collaborators
- backed by repo artifacts and tests
- explicit about what is demonstrated and what is not yet being claimed

## Proven Abilities

These are the strongest current categories to point at.

### Bounded Wikidata structural review

SensibLaw can already:

- turn live or imported Wikidata slices into deterministic reports
- preserve zero-violation baselines
- surface direct contradictions
- surface subclass contradiction chains
- package those outputs into checked summaries and fixture-backed artifacts

### Bounded Nat automation proof

SensibLaw now also has one bounded measured-automation success in the Nat
`P5991 -> P14143` lane:

- exact promoted subset:
  `Q1068745|P5991|1` and `Q1489170|P5991|1`
- scope:
  pilot-ready only for that exact family subset
- non-claim:
  this does not establish broader Cohort A or backlog-wide automation

The next Nat bottleneck is not more proof for those two rows. It is
independent evidence for a second structural family.

The Nat lane now also has the bounded evidence lifecycle around that blocker:

- `AWAITING_EVIDENCE` families emit machine-readable intake contracts
- intake contracts can be aggregated into an acquisition backlog
- routed acquisition tasks can accept supplied evidence bundles
- same-family acquisition can be built directly from a revision-locked entity
  export and must still survive the existing verification step
- successful acquisition can move a family to `READY_TO_RERUN`
- reruns still have to pass the same convergence and governance path before
  any promotion claim is allowed
- some held families also now need a migration-aware read:
  `MIGRATION_PENDING` explains that the upstream migration protocol is active
  but the required after-state is not yet observed; it is explanatory state,
  not a promotion shortcut

Current held second-family seeds are:

- `climate_family_safe_reference_transfer_subset`
- `parthood_family_safe_reference_transfer_subset`

`parthood_family_safe_reference_transfer_subset` is now the primary second-family
proving target. As of April 4, 2026 its bounded live candidate set is:
`Q16572|P361|1`, `Q3700011|P361|1`, and `Q980357|P361|1`.
Its current same-family live acquisition route is still blocked, because the
bounded family migrates toward synthetic `P99999` and current live exports only
carry `P361`.
A bounded manual/acquired artifact path is now proven for `Q16572|P361|1`,
which is enough to move the family to `READY_TO_RERUN` through the existing
state machine even though the live same-family route still fails.
With acquired artifacts for the remaining two rows, the full parthood family is
also now proven to reach `PROMOTED` through the same generic acquisition and
convergence loop.
The same acquisition plan can now also drive a bounded live revision sweep over
recent Wikidata revisions and mark the family `PROMOTED` with
`state_basis = live_same_family_acquisition` when a later revision-locked
entity export actually verifies. The currently pinned live exports are still
blocked, so that proves live-path capability rather than a current live-data
success for parthood.
The Nat state machine now records a separate `state_basis`, so this result is
explicitly queryable as `supplied_acquired_artifact` rather than being
conflated with baseline runtime promotion or live same-family acquisition.

`climate_family_safe_reference_transfer_subset` now has a different read. It is
not just a thin held family. It is also a controlled migration lane:

- before-state is known: `P5991`
- desired after-state is known: `P14143`
- but the verifier still only counts real observed after-states

That means climate can be truthfully described as `MIGRATION_PENDING` where the
upstream migration protocol is active but the required `P14143` state is not
yet present in live source reality. This does not count as a second witness
and does not relax promotion.

That migration-aware read is now reflected in the runtime too:

- the Nat state machine can emit `MIGRATION_PENDING`
- climate intake routes now include:
  - `same_family_after_state`
  - `cross_row_migrated_p14143`
  - `text_bridge_promoted_observation`
- the repo carries a bounded `climate_family_v2_live_p14143_subset` seed for
  migrated-row confirmation against live `P14143` enterprise statements

The current highest-yield next move is therefore not more pressure on the same
thin climate row. It is:

- use a higher-churn live-backed family for the first observed
  `live_same_family_acquisition` promotion
- keep climate on a migration-aware recovery path through:
  - already-migrated row discovery
  - bounded cross-source confirmation
  - or legitimate family expansion if new safe climate rows become real

The broader `P5991` population is also now treated as semantically
heterogeneous rather than implicitly uniform. Nat can triage rows into:

- `direct_migrate`
- `split_required`
- `migration_pending`
- `out_of_scope`
- `needs_review`

That means the next scale lever is tighter segmentation and stronger abstention,
not more aggressive blanket automation across the whole property.

Nat now also has a bounded execution-side overlay:

- batch finder:
  selects promoted, live-target-capable families for migration work
- execution payload:
  shapes review-first OpenRefine / QuickStatements-compatible rows from
  checked-safe promoted candidates
- pre-execution contract layer:
  the repo now also owns explicit candidate contracts, backend routing plans,
  receipt contracts, and post-write verification contracts for operator handoff
- lifecycle overlay:
  `NOT_STARTED -> READY -> EXECUTED -> VERIFIED`

Current read:

- `business_family_reconciled_low_qualifier_checked_safe_subset` is the first
  execution-ready batch
- climate is still held and migration-aware, not execution-ready
- parthood can be promoted for convergence purposes, but its current synthetic
  target keeps it out of live execution batches
- operator-facing export, receipt ingestion, post-write verification, and proof
  CLI surfaces are now real locally
- but genuine external operator receipts still require an actual external
  action:
  a real review/export handoff, a real execution against Wikidata or an
  equivalent tool, and a real returned record of what was applied
- the repo can generate receipt schema, receipt examples, derived receipts from
  pinned exports, and proof bundles that consume receipts
- the repo cannot honestly generate evidence that an external write happened
  when it did not
- so the remaining blocker for operator-real status is provenance, not format
- the closure paths are:
  a real Nat handoff that writes back a receipt file, a QS/OpenRefine wrapper
  that emits receipts, or a manual signed receipt surface with applied rows and
  timestamps

Start here:

- [docs/wikidata_working_group_status.md](docs/wikidata_working_group_status.md)
- [../docs/planning/wikidata_disjointness_report_contract_v1_20260325.md](../docs/planning/wikidata_disjointness_report_contract_v1_20260325.md)
- [../docs/planning/wikidata_disjointness_case_index_v1.json](../docs/planning/wikidata_disjointness_case_index_v1.json)
- [tests/fixtures/zelph/wikidata_structural_handoff_v1/wikidata_structural_handoff_v1.summary.md](tests/fixtures/zelph/wikidata_structural_handoff_v1/wikidata_structural_handoff_v1.summary.md)

### Checked Zelph handoff paths

SensibLaw can already export small checked bundles for downstream reasoning
without pretending the entire corpus is complete.

Start here:

- [../docs/planning/gwb_zelph_handoff_v1_20260324.md](../docs/planning/gwb_zelph_handoff_v1_20260324.md)
- [../docs/planning/au_zelph_handoff_v1_20260324.md](../docs/planning/au_zelph_handoff_v1_20260324.md)
- [../docs/planning/zelph_real_world_pack_v1_6_20260325.md](../docs/planning/zelph_real_world_pack_v1_6_20260325.md)

### Deterministic review over provenance-backed artifacts

The broader point of SensibLaw is not just that it stores data. It provides a
bounded route from messy input to reviewed structure while keeping the source
trail visible.

## Quick Start

SensibLaw is usually worked on inside the top-level `ITIR-suite` workspace.

From the repo root:

```bash
./env_init.sh
cd SensibLaw
../.venv/bin/pip install -e .[dev,test]
```

Useful first commands:

```bash
../.venv/bin/python -m sensiblaw.cli --help
../.venv/bin/python -m pytest -q tests/test_wikidata_disjointness.py
../.venv/bin/python -m pytest -q tests/test_wikidata_structural_handoff.py
```

If you want the Streamlit surface:

```bash
../.venv/bin/streamlit run streamlit_app.py
```

Note:

- the test suite expects the superproject venv (`../.venv`)
- many docs and fixtures assume the full `ITIR-suite` workspace is present

## Common Workflows

### Wikidata diagnostics

Current operational entry points include:

```bash
../.venv/bin/python -m cli.__main__ wikidata build-slice
../.venv/bin/python -m cli.__main__ wikidata project
../.venv/bin/python -m cli.__main__ wikidata find-qualifier-drift
../.venv/bin/python scripts/run_wikidata_qualifier_drift_scan.py
```

Use this lane when you want bounded, pinned review artifacts rather than
generic ontology cleanup claims.

### CLI-first exploration

If you want to see what the current CLI exposes:

```bash
../.venv/bin/python -m sensiblaw.cli --help
../.venv/bin/python -m cli.__main__ --help
```

### Checked artifact review

If you want the fastest route to current examples, read the checked summaries
and fixture artifacts first, then drill down into the raw JSON/tests only if
needed.

## Where To Find Things

### Start here

- system/role overview:
  [docs/ITIR.md](docs/ITIR.md)
- architecture layers:
  [docs/ARCHITECTURE_LAYERS.md](docs/ARCHITECTURE_LAYERS.md)
- whole-system world-model view:
  [docs/roadmaps/world_model_metasystem_20260404.puml](docs/roadmaps/world_model_metasystem_20260404.puml)
  [docs/roadmaps/world_model_metasystem_20260404.svg](docs/roadmaps/world_model_metasystem_20260404.svg)
- Dad/Johl affidavit lane child view:
  [docs/roadmaps/affidavit_dad_johl_lane_20260404.puml](docs/roadmaps/affidavit_dad_johl_lane_20260404.puml)
  [docs/roadmaps/affidavit_dad_johl_lane_20260404.svg](docs/roadmaps/affidavit_dad_johl_lane_20260404.svg)
- Dad/Johl claim-root arbitration child view:
  [docs/roadmaps/affidavit_dad_johl_claim_root_arbitration_20260405.puml](docs/roadmaps/affidavit_dad_johl_claim_root_arbitration_20260405.puml)
  [docs/roadmaps/affidavit_dad_johl_claim_root_arbitration_20260405.svg](docs/roadmaps/affidavit_dad_johl_claim_root_arbitration_20260405.svg)
- interfaces:
  [docs/interfaces.md](docs/interfaces.md)
- CLI examples:
  [docs/cli_examples.md](docs/cli_examples.md)

## Shared World-Model Process

SensibLaw is now converging toward one normalized process for all source
families rather than separate local truth models for Wikidata, AU, GWB,
Brexit, and future lanes.

That shared substrate currently exists in code as five ordered primitives:

1. cross-domain claim model
2. multi-source convergence
3. temporal update discipline
4. contradiction management
5. unified action policy

What this means in practice:

- source families should normalize into the same claim unit
- evidence should converge through the same governed merge surface
- later observations should relate to earlier ones through explicit temporal
  fields instead of silent overwrite
- contradictions should be represented explicitly rather than hidden in
  rejection
- action permissions should be downstream of evidence, convergence, temporal,
  and conflict state

Current status:

- the shared substrate exists in code
- Nat already emits the shared primitives additively in its convergence
  reports
- some lanes still expose lane-local grouped facades as an intermediate step;
  that is better than raw helper sprawl, but it is not the end-state
- the current canonical operator entrypoint for cross-lane reporting is:
  `../.venv/bin/python -m cli.__main__ wikidata world-model-lane-summary --input ...`
- broader lane rebinding and shared-surface extraction are still the next
  phase

This is the important distinction:

- `Nat` proves one source-adapter path into the substrate
- the world-model moonshot is the broader goal of rebinding all major lanes
  onto that same substrate
- lane-local facades such as the affidavit grouped surface are transitional;
  they should converge toward shared `text`, `candidate`, `claim`, `hint`,
  and `decision` surfaces instead of becoming a permanent second layer of
  bespoke APIs

### Wikidata lane

- current status:
  [docs/wikidata_working_group_status.md](docs/wikidata_working_group_status.md)
- current review pass:
  [docs/planning/wikidata_working_group_review_pass_20260307.md](docs/planning/wikidata_working_group_review_pass_20260307.md)
- current report contract:
  [docs/wikidata_report_contract_v0_1.md](docs/wikidata_report_contract_v0_1.md)
- external-facing bounded handoff:
  [../docs/planning/wikidata_zelph_single_handoff_20260325.md](../docs/planning/wikidata_zelph_single_handoff_20260325.md)

### Ingestion and review docs

- ingestion:
  [docs/ingestion.md](docs/ingestion.md)
- end-to-end view:
  [docs/end_to_end.md](docs/end_to_end.md)
- how to review:
  [docs/how_to_review.md](docs/how_to_review.md)
- provenance:
  [docs/PROVENANCE.md](docs/PROVENANCE.md)

### Onboarding and ontology docs

- onboarding playbooks:
  [docs/onboarding_playbooks.md](docs/onboarding_playbooks.md)
- ontology overview:
  [docs/ontology.md](docs/ontology.md)
- ontology ER:
  [docs/ontology_er.md](docs/ontology_er.md)
- ontology/versioning:
  [docs/ontology_versioning.md](docs/ontology_versioning.md)

## What SensibLaw Is Not

SensibLaw is not:

- a generic chatbot
- a free-form legal-answer engine
- a silent auto-correction bot for Wikidata
- a substitute for human review

Its job is to make bounded structure and provenance easier to inspect, test,
and hand off.
