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
