# Deterministic Logic Tree IR (v1)

The logic tree is a deterministic, structural intermediate representation that sits between raw token streams and downstream reasoning. It is **structural-only**: no NLP inference or environment-dependent behaviour is required, and identical inputs always yield byte-identical outputs.

## Goals and invariants

- Purely structural overlay on a canonical token stream; no duplicated text.
- Deterministic: stable IDs, ordering, JSON, and DOT output for identical inputs.
- Single root per document, acyclic, preorder traversal in document order.
- Empty input is valid: a ROOT-only tree.

## Reference extraction invariants (logic-tree scoped)

- **LT-REF-1 Scope & provenance**: Every emitted `RuleReference` originates from a bounded span of the logic tree. Formally, let `T` be the token stream, `L = build_logic_tree(T)`, and `S` the spans attached to nodes in `L` of type `{REFERENCE, MODAL, CLAUSE}`. Then `∃ s ∈ S` such that `reference.tokens ⊆ tokens(s)`. No whole-document or global regex scanning is permitted.
- **LT-REF-2 No semantic invention**: `work`, `section`, `pinpoint` are normalisations of substrings of `T` (whitespace/punctuation/case folding/parenthesis tightening/deictic resolution only). Forbidden: inserting years, guessing jurisdiction, expanding abbreviations not present in tokens.
- **LT-REF-3 Monotone refinement**: Post-processing is many-to-one only. If `R₀…R₃` are reference sets after canonicalisation/deictic resolution/anchor merge, then `|R₀| ≥ |R₁| ≥ |R₂| ≥ |R₃|`, and every `r ∈ Rₖ` is a canonical form of some `r' ∈ Rₖ₋₁`. No splitting or new references are allowed.
- **LT-REF-4 Deictic binding**: Deictics (“the/that/this Act”, “nt act”, etc.) resolve only within the same clause span to the strongest anchored act there (preferring Act/Constitution + year + longest span). If no anchor exists, the deictic is dropped/unresolved.
- **LT-REF-5 Clause-local anchor dominance (anchor-core merge)**: Within a clause span, all act-like references rewrite to the strongest anchor core in that span (by Act/Constitution presence, year, length). No cross-clause merges; no override of hyperlink-derived anchors; no invention of new act names.
- **LT-REF-LINK Hyperlink precedence**: Within a clause span, hyperlink-derived references dominate token-derived references on overlapping spans. A link’s act/section/pinpoint replaces any compatible token-derived reference in the same span; links are ignored if they cannot be mapped to a clause span. Links never increase reference cardinality; they only collapse ambiguity.
- **LT-REF-6 Anchor-core dominance (fallback, token-only)**: If and only if a clause span has no hyperlink-derived anchors, rewrite all token-derived act names in that span to the single strongest anchor core (Act/Constitution present, year preferred, longest span, deterministic tie-break). Deictics resolve to this core; unresolved deictics are dropped. No cross-clause propagation; link-derived references are never rewritten.

## Reference identity, diffing, and provenance (above extraction)

- **CR-ID-1 Text-derived identity**: `identity_hash` is a pure function of extracted text (canonical work, family key, year, jurisdiction hint, section/pinpoint) and does not depend on external registries or network calls.
- **CR-ID-2 Non-invasive**: Adding identity must not create, remove, or rewrite references; it is metadata-only.
- **CR-ID-3 Deterministic**: Identical inputs yield identical `identity_hash` values; OCR variants that canonicalise to the same work collapse to the same identity.
- **CR-ID-4 Distinctness**: Different Acts within the same clause produce different identities (family key + year prevents over-collapse).
- **DIFF-1 Proof-safe diffs**: Reference diffs operate on `identity_hash` sets (`added/removed/unchanged`) so pagination/reordering/canonicalisation changes never surface as differences.
- **DIFF-2 Monotone**: Computing diffs cannot introduce new references; it only classifies the existing identity set relations.
- **PROV-1 Provenance is non-behavioural**: Clause span ID, page numbers, source, and anchor used are attached for audit/debug only and must not affect identity or reference cardinality.
- **PROV-2 Drop-safe**: Provenance may be omitted in downstream projections without changing semantics.

**Global safety theorem (soundness)**: For any document `D`, the pipeline yields a reference set `R` that is: (1) sound—every reference corresponds to text in `D`; (2) scope-safe—bounded to its logical clause; (3) non-inventive—no new instruments/sections appear; (4) deterministic—identical input ⇒ identical `R`; (5) monotonically refined—normalisation only reduces noise, never expands claims.

**Hyperlink soundness lemma**: Replacing token-derived references with hyperlink-derived references on overlapping spans preserves soundness and reduces ambiguity. Formally, let `R_token` and `R_link` be references from tokens and links respectively; for any hyperlink span `s`, if `r_token.span ⊆ s` and `r_link.span = s`, then `R_final = (R_token ∪ R_link) \ {r_token}` is still sound and satisfies LT-REF-1…5.

**Anchor-core lemma (token fallback)**: For a clause span `s` with no link anchors, let `A(s)` be the strongest token anchor. Rewriting all token-derived references in `s` to `A(s)` preserves LT-REF-1…5 and reduces surface variance without introducing new instruments. If `A(s)` is undefined, no rewrite occurs.

## Data model

### Node

```
Node {
  id: str                 # deterministic, monotonic (n0, n1, ...)
  node_type: NodeType     # ROOT | CLAUSE | CONDITION | ACTION | MODAL | EXCEPTION | REFERENCE | TOKEN
  span: (int, int) | None # half-open token offsets into the source token stream
  text: str | None        # debug-only view reconstructed from tokens
  source_id: str          # document/provision identifier
}
```

### Edge

```
Edge {
  parent_id: str
  child_id: str
  edge_type: EdgeType     # SEQUENCE | DEPENDS_ON | QUALIFIES | EXCEPTS
}
```

### LogicTree envelope

```
{
  "version": "logic-tree-v1",
  "root_id": "n0",
  "nodes": [...],
  "edges": [...]
}
```

## Deterministic ID and ordering rules

- IDs are assigned incrementally in creation order with the prefix `n` (root is always `n0`).
- Clauses are created before their tokens; tokens follow document order.
- Node emission (DOT) places ROOT first, then other nodes sorted by span start, then numeric ID.
- Child ordering is span-driven: increasing child span start, then edge-type priority (SEQUENCE, DEPENDS_ON, QUALIFIES, EXCEPTS), then ID. Parent spans do not affect ordering (ROOT uses a high sentinel to stay out of child ordering).
- Traversal order follows the child ordering; node list order is an implementation detail.
- SQLite projections must persist `ord` per parent exactly as produced by the in-memory edge ordering. SQLite is a projection/index only; JSON remains canonical.
- FTS indexing stores document text once (e.g., `docs_fts(doc_id, raw_text)`), and search results resolve to nodes via span overlap; no `node_text` columns are added.

## Builder contract: `build(tokens, *, source_id="unknown") -> LogicTree`

Inputs are sequences of token-like objects exposing `.text`, `.lemma` (optional), `.pos` (optional), `.dep` (optional), and `.ent_type` (optional). No global state or randomness is used.

### Clause segmentation

- Start a new clause at the beginning of the token stream.
- Terminate a clause when encountering a token whose `text` ends with `.` or `;` or is exactly `"."`/`";"`.
- If no boundary is found, all tokens belong to a single clause.

### Node classification (priority order)

1. **EXCEPTION**: `lemma/text` in {`"unless"`, `"except"`, `"excluding"`, `"save"`}.
2. **CONDITION**: `lemma/text` in {`"if"`, `"when"`, `"where"`, `"provided"`, `"subject"`, `"until"`, `"upon"`}.
3. **MODAL**: modal verbs (`lemma/text` in {`"must"`, `"shall"`, `"may"`, `"should"`, `"will"`, `"would"`, `"can"`, `"cannot"`}) or tokens with `pos == "AUX"`.
4. **ACTION**: tokens with `pos == "VERB"` or `dep == "ROOT"`.
5. **REFERENCE**: tokens with a non-empty `ent_type`.
6. **TOKEN**: fallback.

### Spans and text

- Clause span covers all tokens inside the clause: `[first_index, last_index + 1)`.
- Token span is `[index, index + 1)`.
- `text` on nodes is optional and only used for debugging/visualisation.

### Edges

- Root → Clause: `SEQUENCE` in clause order.
- Clause → Token: edge type determined by the child node type:
  - `EXCEPTION` → `EXCEPTS`
  - `CONDITION` → `DEPENDS_ON`
  - `MODAL` → `QUALIFIES`
  - otherwise → `SEQUENCE`

## Traversal helpers (read-only)

- `walk_preorder(tree)`: root, then children in stable order.
- `walk_postorder(tree)`: children first, then parent.
- `walk_root_to_leaves(tree)`: sequences of node IDs for every leaf path.

Traversal order is stable by sorting children with the edge-type priority and child ID tie-breaker.

## Persistence and round-tripping

- JSON is emitted as a plain dict with stable key order: `version`, `root_id`, `nodes`, `edges`.
- `from_dict` reconstructs the tree; `to_dict` + `from_dict` is round-trip safe.
- No database required; no optional dependencies.

## DOT / Graphviz export

`to_dot(tree) -> str` produces deterministic DOT with:

- Node labels as `"{node_type}: {text}"` when text exists, else `node_type`.
- Optional colours keyed by node type (root, clauses, modals, conditions, exceptions, references, actions, tokens).
- Nodes emitted with ROOT first, then span/id sort; edges sorted by the child ordering rules for stable output.

### Ordering invariants (clarification)

- ROOT is emitted first for readability but excluded from span-based ordering of its children.
- Child order is document-aligned (by child span start); edge type priority is only a tie-breaker.
- Traversal order is defined by edge ordering; do not rely on raw node list order for traversal semantics.

## Acceptance checklist

- Empty input yields a ROOT-only tree.
- Identical input produces byte-identical JSON and DOT.
- Traversal order is documented and stable.
- Tree persists and reloads without loss.
- Tests cover: empty input, single clause, multi-clause sequence, qualifier/exception tokens, DOT snapshot, determinism.
