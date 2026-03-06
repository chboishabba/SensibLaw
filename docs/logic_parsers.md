# Logic parsers: generic vs legal profile

## Shared core
- Same normalisation/tokenisation pipeline (pipeline.normalise + pipeline.tokenise).
- Same deterministic logic-tree builder (`src.logic_tree`) with span-anchored nodes/edges:
  - Node types: ROOT, CLAUSE, CONDITION, ACTION, MODAL, EXCEPTION, REFERENCE, TOKEN.
  - Edge ordering/determinism preserved; DOT/SQLite exports identical for the same text.
- No text duplication: spans reference the canonical document text; token text is derived, never stored.
- Logic tree is domain-agnostic: structure precedes interpretation; legal enrichers are overlays.

## Structural guarantees (as evidenced by `logic_tree.sqlite`)
- Graph-first: nodes carry `(node_type, span_start, span_end)`; edges encode hierarchy/order.
- Span-authoritative: all offsets resolve into the canonical text; tokens/sentences are optional views.
- TOKEN nodes are structural leaves, **not** a canonical tokenizer output; they mark the smallest structural anchor.
- No sentence table: sentencehood is a presentation/view concern, not structural.
- Deterministic exports: repeated ingests with the same inputs produce byte-identical JSON/DOT/SQLite.

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

## Non-goals / guardrails
- Do not treat TOKEN nodes as spaCy/regex tokens; they are structure-only.
- Sentence boundaries must not drive identity, counts, or logic edges.
- Legal enrichers must not mutate spans or structural ordering; they attach metadata only.

## Future alignment
- Expose explicit `--mode {general,legal}` switch (default legal when metadata provided).
- Add page_map capture and stability test across paginated variants.
- Record chunking/repetition metadata for large docs (even in general mode) while keeping tokens authoritative.
- Add optional tokenizer_id tag for TOKEN nodes or decouple lexical tokens into a separate view without changing structure.
- Provide a one-page “What the DB guarantees” checklist mirroring this doc and `docs/tokenizer_contract.md`.
