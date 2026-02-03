# Logic parsers: generic vs legal profile

## Shared core
- Same normalisation/tokenisation pipeline (pipeline.normalise + pipeline.tokenise).
- Same deterministic logic-tree builder (`src.logic_tree`) with span-anchored nodes/edges:
  - Node types: ROOT, CLAUSE, CONDITION, ACTION, MODAL, EXCEPTION, REFERENCE, TOKEN.
  - Edge ordering/determinism preserved; DOT/SQLite exports identical for the same text.
- No text duplication: spans reference the canonical token stream.

## Generic logic parser (what we used for `test_generic_docs`)
- Entry: `python -m cli pdf-fetch <pdf> ...` with no legal metadata.
- Treats the PDF as a general document:
  - Builds logic tree only; no citation normalisation, no authority assumptions.
  - Provenance set to the PDF path; jurisdiction/citation empty unless supplied.
- Suitable for briefs, technical docs, notes, chat dumps, academic PDFs.

## Legal logic parser (profile for authorities)
- Same logic-tree construction, plus:
  - Citation extraction/normalisation where legal signals exist.
  - Jurisdiction/citation metadata expected; provenance recorded.
  - Optional obligation extraction/alignment when flags are set (`--emit-obligations`, `--diff-obligations-against`).
- Surfaces missing/ambiguous citations instead of silently ignoring them.

## How to choose
- **general mode**: ingest evidence/non-authority material; skip legal enrichers; still deterministic and span-anchored.
- **legal mode** (current default when legal metadata present): run citation/provenance checks; gate enrichment on legal signals.

## Outputs
- Logic tree JSON: `{artifacts_dir}/{source_id}.logic_tree.json`
- Logic tree SQLite: `logic_tree.sqlite` (optionally with FTS)
- Graphviz DOT/SVG/PDF can be generated from the JSON (e.g., `dot -Tsvg ...`).
  - `LogicTree.to_dot(include_tokens=False)` (default) renders structural hierarchy; SEQUENCE edges are dotted, non-constraining.
  - Pass `include_tokens=True` if you need token-level edges; expect very wide graphs.

## Future alignment
- Expose explicit `--mode {general,legal}` switch (default legal when metadata provided).
- Add page_map capture and stability test across paginated variants.
- Record chunking/repetition metadata for large docs (even in general mode) while keeping tokens authoritative.
