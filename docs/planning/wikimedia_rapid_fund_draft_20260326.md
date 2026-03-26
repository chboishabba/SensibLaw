# Wikimedia Rapid Fund Draft for the Wikidata Lane

Last updated: 2026-03-26

## Status
This is a repo-local grant draft, not a submitted Wikimedia application.

It is intended as the first concrete proposal surface after
`wikimedia_grant_framing_20260326.md`, and it keeps the pitch legible to
Wikimedia programs by describing a bounded Wikidata tool rather than asking for
funding for the broader SL/ITIR stack.

The current concrete demo/evaluation collapse for this draft is documented in:
- `docs/planning/wikimedia_bounded_demo_spec_20260326.md`
- `docs/planning/wikimedia_demo_attribution_matrix_20260326.md`
- `docs/planning/wikimedia_prior_work_and_originality_note_20260326.md`

Attribution for demo cases and method lineage should follow that note rather
than being improvised in the final submission text.

Novelty and prior-work wording should also defer to that note before any final
submission text is pasted into Wikimedia systems.

## Draft title
`Provenance-Aware Wikidata Validation and Ingestion Tool`

## Wikimedia application form draft
This section is written in a Fluxx/Meta-style question-and-answer shape so it
can be translated with minimal rewriting into an actual Wikimedia Rapid Fund
application.

### Project title
`Provenance-Aware Wikidata Validation and Ingestion Tool`

### Project summary
This project will develop a prototype tool that extracts structured facts from
Wikipedia with exact provenance and compares them against Wikidata to identify
inconsistencies, missing claims, and unsupported statements, while also
surfacing fixture-backed structural contradictions and qualifier drift from
bounded reproducible Wikidata review packs.

The system emphasizes deterministic extraction, auditable transformations, and
abstention when uncertainty is present, improving Wikidata data quality and
supporting editors with traceable validation tools.

### What problem are you trying to solve?
Wikidata contributors currently face:
- inconsistent or conflicting claims
- limited fine-grained provenance tracking
- high manual effort for verification

Existing tools often rely on heuristic or probabilistic extraction methods
that:
- lose traceability
- introduce ambiguity
- still require substantial manual validation

There is not yet a widely used pipeline in this repo's target shape that:
- deterministically extracts facts from Wikipedia with exact provenance
- compares those facts against bounded Wikidata slices
- helps reviewers distinguish contradictions, missing claims, and unsupported
  statements

### What is your proposed solution?
Build a prototype validation and ingestion-support system that:
1. extracts candidate facts from Wikipedia using deterministic parsing
2. attaches span-level provenance through exact text anchors
3. compares extracted facts with Wikidata
4. flags contradictions, missing claims, and unsupported statements
5. also packages pinned structural findings such as mixed-order, SCC,
   qualifier-drift, and disjointness review into structured, traceable outputs
   for Wikidata editors

### How does this support Wikimedia projects?
This project supports Wikidata by:
- improving data consistency and reliability
- reducing editor verification workload
- enabling traceable, evidence-based review and edits

It supports the broader Wikimedia ecosystem by:
- increasing trust in structured knowledge
- enabling more reliable downstream reuse in search, AI, and research

### Who are the target users?
- Wikidata editors
- Wikimedia technical contributors
- researchers using Wikidata
- tool developers building on Wikimedia data

### What are the main activities?
- develop the deterministic extraction pipeline
- implement the validation and comparison layer
- integrate with Wikidata-aligned slice/import surfaces
- build a prototype CLI or minimal reviewer-facing UI/report surface
- test on the bounded Wikipedia/Wikidata subset defined in
  `docs/planning/wikimedia_bounded_demo_spec_20260326.md`
- document and publish results

### What are the expected outputs?
- open-source prototype tool
- demonstration dataset and results
- documentation and usage examples
- report on validation findings and tool limits

### Reviewer route
Preferred:
- 1-2 Wikidata/ontology-adjacent reviewers from the working-group/contact lane
  if available

Fallback:
- 1-2 technically adjacent reviewers focused on output legibility,
  provenance clarity, and usefulness of the bounded findings

### Timeline
Indicative 8-10 week shape:
- weeks 1-2:
  bounded ingestion/extraction wiring
- weeks 3-5:
  validation/comparison layer
- weeks 6-8:
  interface/reporting and demonstration slice
- weeks 9-10:
  documentation, evaluation, and community-facing write-up

### Budget
Rapid Fund-scale categories only:
- development time
- minimal compute resources
- documentation and dissemination/community feedback time

Keep this repo note budget-shaped rather than amount-specific until a real
application is being entered into Wikimedia systems.

### Community engagement
- publish tool outputs and documentation openly
- share bounded results on Wikimedia Meta or other appropriate Wikimedia
  channels
- invite feedback from Wikidata contributors on usefulness and limitations

## Core pipeline
1. Input:
   bounded Wikipedia articles
2. Extraction:
   deterministic fact extraction plus exact text anchors
3. Validation:
   constraint/review reasoning over Wikidata-aligned structures
4. Output:
   flagged inconsistencies, suggested additions, and provenance-linked review
   material

## Key innovation
Compared with more heuristic pipelines, this proposal centers:
- deterministic extraction
- reversible or auditable transformation steps
- explicit provenance
- abstention when support is weak

The proposal should not overclaim general ontology repair. Its value is
review-support, traceability, and bounded quality improvement.

## Deliverables
- working open-source prototype
- CLI plus a small reviewer-facing interface or report surface
- bounded Wikipedia -> Wikidata demonstration pack
- documentation and usage examples

## Bounded demo scope
The proposal now uses one explicit bounded demo surface rather than a generic
"Wikipedia -> Wikidata" claim.

Selected demo spec:
- `docs/planning/wikimedia_bounded_demo_spec_20260326.md`

In short, the foreground demo is built from repo-owned structural packs:
- mixed-order `P31` / `P279` review on pinned slice artifacts
- `P279` SCC review on pinned slice artifacts
- qualifier-drift review on:
  - `Q100104196|P166`
  - `Q100152461|P54`
- bounded disjointness review on:
  - `fixed_construction_contradiction`
  - `working_fluid_contradiction`
  - `nucleon_baseline`

Secondary attributed appendix examples:
- `GNU` / `GNU Project`
- finance entity-kind-collapse pack

This choice keeps the proposal honest:
- the foreground story is carried by the safest repo-owned artifacts
- the attributed appendix examples remain useful without carrying ownership
  claims the repo should not make

## Reviewer-facing pain points
The current reviewer story should name concrete Wikimedia problems already
visible in repo artifacts:
- mixed-order class/instance confusion on pinned `P31` / `P279` slices
- reciprocal/circular subclass pressure on pinned `P279` SCC slices
- qualifier drift across pinned revision windows for `Q100104196|P166` and
  `Q100152461|P54`
- explicit structural contradiction review on
  `fixed_construction_contradiction`
- explicit structural contradiction review on
  `working_fluid_contradiction`
- secondary appendix only:
  entity-kind collapse around `GNU` / `GNU Project`

When this section is translated into submission text:
- credit Shixiong Zhao and Hideaki Takeda where the broader
  classification-hierarchy inconsistency context is referenced
- credit Ege Doğan and Peter Patel-Schneider where the broader `P2738`
  disjointness method/problem context is referenced
- treat the `GNU` / `GNU Project` case as an attributed reviewed example, not
  as a repo-original discovery

## ZKP formalization
This section keeps the proposal internally disciplined and extensible.

### O — Organization
- Wikimedia ecosystem
- Wikidata editors/reviewers
- SL/ITIR deterministic extraction substrate
- Zelph-style review/constraint reasoning layer
- downstream users of structured, provenance-aware knowledge

### R — Requirements
- deterministic fact extraction
- span-level provenance preservation
- abstention support
- Wikidata-compatible comparison surfaces
- auditable promotion/review transformations

### C — Code / mechanisms
- deterministic extraction pipeline
- candidate-to-review boundary
- constraint/review comparison logic
- Wikidata slice import/integration surfaces
- diff and validation reporting

### S — State
Three-layer state:
1. source substrate:
   raw or revision-bounded Wikipedia text with anchors
2. candidate state:
   extracted, non-canonical fact candidates plus provenance
3. promoted/review state:
   Wikidata-aligned validation outputs and suggested review actions

### L — Lattice
- candidate facts form a partial order by support, consistency, and review
  readiness
- promotion/review should be monotonic and non-destructive
- abstention preserves integrity by preventing unsupported collapse into false
  certainty

### P — Proposals
The system emits typed proposals such as:
- candidate facts
- contradiction findings
- unsupported-claim findings
- suggested additions or review actions

Each proposal remains provenance-linked and reviewable.

### G — Governance
- promotion/review criteria should require consistency checks and sufficient
  provenance
- editors remain the final authority for accepted Wikidata changes
- the tool is reviewer support, not autonomous truth authority

### F — Gap function
The operational gap is the mismatch between:
- Wikipedia-supported bounded candidate facts
- current Wikidata state

This includes:
- contradictions
- missing facts
- unsupported claims

Optimization goal:
- reduce inconsistency and reviewer burden while preserving provenance
  integrity and abstention discipline

## Evaluation metrics and acceptance criteria
These metrics are intended to make the draft reviewer-facing rather than merely
descriptive.

### Core evaluation question
Does the system measurably improve bounded Wikidata data-quality review while
preserving exact provenance and deterministic reproducibility?

The selected bounded evaluation subset and baseline are defined in:
- `docs/planning/wikimedia_bounded_demo_spec_20260326.md`

### Metrics
#### 1. Consistency detection rate
- measure:
  contradiction or inconsistency findings on the bounded test subset compared
  with baseline/manual review
- target:
  identify at least `20%` additional inconsistencies on the bounded evaluation
  subset relative to the selected baseline process

#### 2. Provenance coverage
- measure:
  percentage of extracted facts carrying exact text-span provenance
- target:
  at least `95%` provenance completeness on emitted candidate facts

#### 3. Abstention accuracy
- measure:
  rate at which weak-support cases are correctly abstained rather than emitted
  as misleading fact candidates
- target:
  lower false-positive rate than the selected baseline heuristic/NLP comparison
  process on weak-support cases

#### 4. Editor utility
- measure:
  bounded qualitative review from a small group of Wikidata contributors or
  technically adjacent reviewers on:
  - usefulness of flagged issues
  - clarity of provenance
  - actionability of the outputs
- target:
  majority-positive usefulness assessment on the bounded review set

#### 5. Reproducibility
- measure:
  ability to reproduce the same outputs from the same inputs
- target:
  `100%` deterministic reproducibility on the bounded demonstration pack

### Acceptance criteria
- the prototype can run end-to-end on the bounded foreground fixture/revision
  set named in `docs/planning/wikimedia_bounded_demo_spec_20260326.md`
- emitted candidate facts are predominantly provenance-complete
- the system surfaces bounded contradictions, missing claims, or unsupported
  claims in a way that reviewers can inspect directly
- repeated runs over the same bounded inputs reproduce the same outputs
- the public documentation clearly states scope, limits, and abstention
  behavior
- the preferred/fallback reviewer route is explicit in the submission pack

## Evaluation plan
- use the exact bounded fixture/revision set named in
  `docs/planning/wikimedia_bounded_demo_spec_20260326.md`
- run the prototype pipeline over that subset
- compare extracted facts and flagged issues against:
  - current Wikidata state
  - manual bounded review
  - the current repo checked-review process where applicable
- review the outputs for contradiction yield, provenance completeness,
  abstention behavior, and reviewer utility

For the current draft, the chosen baseline is:
- primary:
  manual bounded review
- secondary:
  the existing repo checked-review process documented in
  `docs/planning/wikimedia_bounded_demo_spec_20260326.md`

## Constraints and cautions
- Do not describe this as a general-purpose autonomous Wikidata fixer.
- Do not collapse the proposal into abstract system language.
- Keep the public story focused on bounded validation, provenance, and review
  support.
- Keep internal stack names secondary to the Wikimedia-facing tool description.
- Do not imply first discovery or method parity where the repo docs only
  support attributed use, method adjacency, or narrower fixture-backed
  implementation.

## Risks and mitigations
### Risk 1: extraction complexity
- mitigation:
  start with limited article families or structured sections rather than
  claiming broad open-domain coverage

### Risk 2: Wikidata schema variability
- mitigation:
  focus first on common properties and a bounded review subset

### Risk 3: editor adoption
- mitigation:
  keep outputs evidence-linked, inspectable, and clearly documented rather than
  opaque or over-automated

## Immediate next step
If the repo moves from draft to active submission work:
1. translate this draft into the exact Wikimedia submission form fields
2. preserve the bounded demo scope and baseline already chosen in
   `docs/planning/wikimedia_bounded_demo_spec_20260326.md`
3. preserve the preferred/fallback reviewer route already documented here
4. compare wording against a small set of funded and rejected Wikimedia
   proposals
