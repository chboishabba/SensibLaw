# COMPACTIFIED_CONTEXT

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
