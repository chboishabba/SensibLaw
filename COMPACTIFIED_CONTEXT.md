# COMPACTIFIED_CONTEXT

## 2026-07-15 — WD bridge architecture context refresh

- Resolved archived thread:
  - title: `WD Bridge Architecture`
  - online UUID: `6a54b21f-ba30-83ec-b08e-0e62cb9d0933`
  - canonical thread ID: `71e63a13e10f7370ace24a676750577ca63e3317`
  - source: `db`, snapshot `pull_20260714T035959Z` (141 archived rows; the
    resolver's latest six-row snapshot was incomplete)
  - live refresh attempted on 2026-07-15 but ingested zero messages; do not
    describe the archive as freshly web-verified
- Main decisions retained:
  - every mature lane needs the shared external-authority bridge *capability*,
    but external traversal remains conditional on the candidate and never
    substitutes for local evidence, role, authority, or promotion;
  - external identity attachment and structural pressure are separate,
    revision-bound products;
  - pressure is multi-view and domain-bounded: WD class/property structure is
    the first substrate, with Wikipedia/Simple/Abstract Wiki, translation, and
    domain cohorts later contributing reviewable expected-shape pressure;
  - a checked external graph slice is one input to a forkable basis revision;
    public channels project basis revisions and attestations but do not turn
    subscriber counts into truth.
- Archive hygiene:
  - the first pages contain hidden Project/NotebookLM source dumps, including
    the unexpected Agda text. These are tool/file-context records, not
    user-visible thread authorship and not architecture evidence.

## Purpose
Compact snapshot of the current architecture and next seam.

## Current state
- one media-adapter layer canonicalizes ordinary inputs into `CanonicalText`
- one parser spine operates over `CanonicalText`
- extraction profiles sit above the parser spine; parser logic is structural,
  not semantic
- mixed-content ordinary documents are first-class:
  - prose, inline code, quotes, tables, lists, headings, citations all survive one parser
- code is not a source class or parser family
- provenance is metadata, not parser identity
- structure is discovered from parsed output and graph relations, not declared
  as an input type

## Parser doctrine
- parser input: `CanonicalText`
- parser output: one parsed observation stream with stable segments, units, and anchors
- block `segment_kind`:
  - `heading`
  - `paragraph`
  - `list`
  - `quote`
  - `table`
  - `code_block`
  - `divider`
- inline `unit_kind`:
  - `text_run`
  - `code_span`
  - `citation`
  - `link`
  - `emphasis`
- separate parsers are justified only for truly different primary mechanics,
  not prose-with-code
- adapter distinctions such as PDF, HTML, rows, or transcripts are not
  top-level parser doctrine

## Active lanes
- affidavit/Wikidata typed reconciliation:
  - current contract:
    `docs/planning/affidavit_wikidata_typed_reconciliation_contract_20260606.md`
  - current helper:
    `src/fact_intake/typed_claim_reconciliation.py`
  - purpose: operational Python carrier layer for proposition/response rows,
    object-type assertions, and Wikidata statement rows that stays aligned with
    the DASHI formal object grammar
  - relation labels are the canonical affidavit finite vocabulary:
    `exact_support`, `equivalent_support`, `explicit_dispute`,
    `implicit_dispute`, `partial_overlap`, `adjacent_event`, `substitution`,
    `procedural_nonanswer`, `unrelated`
  - dog fixture boundary: `walked the dog` versus `did not walk the dog`
    reduces to `explicit_dispute` / `invalidates` / `disputed`; it does not
    decide truth
  - object-type boundary: `6 is a 1-morphism` is a typed-object assertion, not
    a proof. It remains witness/context pending unless a category or
    bicategory context and typing rule are supplied
  - Wikidata boundary: QID/PID/value rows are provenance/evidence carriers with
    qualifier/reference metadata; rank and deprecation do not become truth,
    contradiction, proof, edit authority, or promotion
  - current formalism review result against DASHI:
    - relation algebra alignment: passed
    - dog dispute fixture: aligned
    - object-type witness/review/promotion fields: now materialized
    - Wikidata `truth_claimed = false` and `live_edit_authority = false`: now
      materialized
    - caller hints: now marked with `relation_derivation = caller_hint`
  - remaining honest seams:
    - add first-class statement IDs and revision windows when importers supply
      them
    - thread envelopes into persisted affidavit read-model tables only after a
      storage contract is explicit
    - add direct Python-vs-DASHI field grammar fixture coverage
- bounded Wikidata ontology-repair candidate comparison:
  - `wikidata compare-candidates` now evaluates a review-only
    `ChangeReviewPacket` against a bounded slice
  - current fixture is synthetic `Q27968055`
  - candidate mutations are in-memory only and reports carry
    `edit_authority: false`
  - this is Level 0 of the broader global structural-coherence roadmap, not a
    QID-only repair bot or Wikidata edit authority
  - bounded `mereology` / `temporal_exclusivity` coverage is now wired for
    `P361`/`P527`-style review packets, using curated policy only inside the
    supplied slice
  - reports can now carry pressure attribution buckets and candidate
    `held_*`/review reasons, so Q27968055-style local fixes can still surface
    upstream ontology pressure without turning that caveat into edit authority
- semantic-memory bridge:
  - future lane is pinned at
    `docs/planning/semantic_memory_bridge_future_lane_20260506.md`
  - first helper builds `sl.semantic_memory_index.v0_1` from supplied atoms,
    grounding candidates, and ontology closure paths
  - retrieval returns source snippets plus explanation paths, e.g.
    "great dane" matching a "dogs" query through `Great Dane -> dog breed -> dog`
  - boundary remains private memory retrieval only: no live entity linking, no
    fabricated QIDs/PIDs, no public Wikidata truth, and no belief inference
- operator-only relation-equivalence work on one ambiguous seed
- additive relation graph and structure metrics over the shared spine
- bounded extraction-profile layer above the parser spine
  - `normative_policy` now landed for `policy_statements` and `ir_queries`
  - `legal_review` now landed for `review_text`-first projection
- bounded ISO lane:
  - real ISO 42001 excerpt-pack fixtures are already landed on the same
    `normative_policy` projector
  - external ISO catalogue / PAS pages are reconnaissance only
  - ISO stays a bounded normative adopter/reuse lane, not a separate parser
    family or standards-catalog ingestion program
- verification gate
- docs/governance thresholding

## Holds
- OCR
- emitted `review_alignment`
- gate/resolution churn
- reporting/UI widening
- provenance-specific parser branches
- code-specific top-level source families
- structuredness as an input taxonomy

## Next implementation seam
- run one-seed operator-only relation equivalence on
  `gwb_us_law:nsa_surveillance_review`
- add the smallest clustering/invariant readout helper above relation
  similarity
- keep the ISO lane bounded to normative reuse/recon and fixture-quality
  review
- widen downstream consumers only where canonical refs materially reduce
  duplicate parsing
# 2026-07-17 climate-GHG orthogonal assessment V2 decision

- The immutable 232-family / 3,562-statement company-direct replay remains the
  source substrate; V2 is installed only below `derived/orthogonal_v2/`.
- Generic shared policy code owns orthogonal carrier validation, deterministic
  ordering/hashes, authority checks, and aggregation. Climate profile code owns
  GHG QIDs, semantic derivation, predicates, and A1-A5/H4 projections.
- Eligibility is candidate-review-only and cannot create promotion, execution,
  edit, or source-quality authority. Reference adequacy is structural only.
- Canonical contract:
  `docs/planning/climate_ghg_orthogonal_assessment_v2_20260717.md`.
