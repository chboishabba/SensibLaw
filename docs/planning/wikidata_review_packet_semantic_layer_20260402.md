# Wikidata Review Packet Semantic Layer Seam

Date: 2026-04-02

## Purpose

Introduce the smallest explicit seam for deeper semantic decomposition beside
`parsed_page` without changing the default review-packet contract behavior.

## Runtime shape

`build_wikidata_review_packet(..., include_semantic_decomposition=True)` now
attaches:

- `semantic_decomposition.layer_schema_version`
- `semantic_decomposition.decomposition_state`
- `semantic_decomposition.separate_from_parsed_page`
- `semantic_decomposition.candidate_units`
- `semantic_decomposition.missing_evidence`

The new layer is explicitly a sidecar derived from existing bounded packet
signals (`parsed_page`, `page_signals`, `follow_receipts`).

## Non-claims

- It does not replace or mutate `parsed_page`.
- It does not claim clause-level decomposition.
- It does not claim grounded semantic-unit extraction.
- It does not claim execution-grade migration semantics.

## Boundary

`missing_evidence` is the minimal API for the next layer. It records exactly
why candidate surface units cannot yet be treated as deeper semantic units.
