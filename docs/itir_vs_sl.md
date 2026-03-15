# SL profile vs ITIR/TIRC pipelines

This note captures the cross-domain invariants that apply to generic documents, legal authorities, financial/regulatory texts, and academic papers. It positions SensibLaw (SL) as a policy-hardened profile over general ITIR/TIRC-style pipelines.

## Shared core problems (all domains)
- Lexical identity: authoritative tokens.
- Structural decomposition: sections/clauses/claims.
- Cross-reference topology: links/citations/references.
- Stable interpretation surface: summaries/arguments/compliance views.

Differences are policy and enforcement, not architecture.

## Invariant stack

### Level 0 — Canonical text (all agree)
- **Invariant:** words exist exactly once.
- SL: tokens are canonical; everything references spans.
- ITIR/TIRC: raw text + token index (not always enforced).

### Level 1 — Structural IR
- SL: logic tree; deterministic; spans-only storage; document-stable ordering.
- ITIR/TIRC: rhetorical/section units; often mixed storage; traversal may be heuristic.
- **SL invariant:** structure indexes text; never re-stores it.

### Level 2 — Constraint topology
- SL: explicit CONDITION/EXCEPTION/MODAL edges; directional; diffable.
- ITIR/TIRC: often implicit or heuristic.
- Cross-domain invariant: “X applies unless Y” must be representable without inference.

### Level 3 — Cross-document references
- SL: span-anchored; missing citations surfaced; edges require provenance.
- ITIR/TIRC: doc-anchored/ref-anchored; missing or inferred links often tolerated.
- **SL invariant:** no edge without provenance.

### Level 4 — Interpretation surface
- SL: UI is non-inventive; read-only projections; activation requires explicit facts.
- ITIR/TIRC: interpretation often baked into presentation.

## Bidirectional value
- What ITIR/TIRC gain from SL: enforced invariants (determinism, no duplication, provenance-complete edges, non-inventive UI) and a “no-reasoning zone” to anchor audits.
- What SL gains from ITIR/TIRC: multiple interpretive projections (argumentative/rhetorical/salience) layered as mentions over spans; hypotheses stay outside SL until reviewed.

## SB / TiRC boundary clarification
- SB is a personal state compiler, not a semantic or legal authority surface.
- TiRC is a capture/disagreement lane, not a canonical semantic owner.
- SB/TiRC may consume or extend SL-owned lexer/compression outputs where
  shared canonical text handling is needed.
- Supported import path for that reuse:
  `sensiblaw.interfaces.shared_reducer`.
- That reuse does not transfer SL semantic ownership into SB/TiRC.
- If SB/TiRC receive legal-looking canonical IDs or fixtures, those are opaque
  SL-origin payloads used for preservation, replay, or cross-product
  consistency only.

## Profile model
- Single canonical parser/tokeniser.
- SL is the “strict profile”: deterministic, auditable, no inference; legal-specific enrichers gated by mode.
- ITIR/TIRC are “interpretive profiles”: richer analyses, but outputs must reference SL spans and remain reversible.
- Multi-modal operation is allowed (assistive, intent-tracking, scheduling) so long
  as epistemic status is explicit and authority boundaries are enforced.

## Safe handshake object
- **Mention:** `(doc_id, span, role, confidence, source)`.
- Interpretive systems produce mentions; SL keeps spans authoritative; UI renders mentions over spans.

## Next actions (planned)
- Formal mapping table: ITIR/TIRC primitives → SL primitives (lossless vs lossy).
- Page-stability invariant test across paginated variants.
- Large-doc ingest path (chunking + repetition metadata) exposed in both general and legal modes.

## Boundary references
- `docs/planning/extraction_enrichment_boundary_20260307.md`
- `docs/tokenizer_contract.md`
- `docs/external_ontologies.md`
