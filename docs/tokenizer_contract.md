Tokenizer & Structure Contract (SL-Compatible)
==============================================

Purpose
-------
Freeze the rules for tokenization, sentence segmentation, and structural IR so multiple parsers can coexist without semantic creep. This document is authoritative for SL; ITIR overlays must respect it.

Canonical text axiom
--------------------
- One canonical body string per document; immutable after ingest.
- All spans refer to this string; no other text copies are authoritative.

Tokenizers
----------
- A tokenizer is a pure function: text → ordered spans `(start, end, token_type)`.
- Token identity = `(doc_id, tokenizer_id, start, end)`. Text is derived, never stored.
- Multiple tokenizers may coexist; none is globally authoritative.
- Tokenizers declare scope and stability:
  - Example: `regex_simple_v1` (scope=metrics, stable=true)
  - Example: `spacy_word_v3` (scope=semantics, stable=false)
- Stable tokenizers may appear in invariants/tests; unstable ones may not.
- Canonical lexeme occurrences derive from a deterministic no-regex tokenizer in
  `SensibLaw/src/text/lexeme_index.py` (Layer‑1 only).
  Candidate stream: `deterministic_legal_v1` (`itir_legal_lexer_v1`).
- Legacy regex tokenization remains available for explicit parity and rollback
  runs via `ITIR_LEXEME_TOKENIZER_MODE=legacy_regex`.
- spaCy is used for semantic extraction, not canonical token streams.

## Transition Goal (Regex → Deterministic Multilingual Tokenizer)
Current lexeme occurrences are derived from the deterministic canonical stream.
Regression parity remains mandatory before any non-noise canonical configuration
changes.

End goal:
- Replace regex tokenization with a deterministic multilingual tokenizer
  (spaCy or other deterministic engine), preserving stable offsets.
- Maintain byte‑identical canonical spans for existing sources until parity is
  verified against checkpoint snapshots.

Success criterion:
- New token stream produces identical graph hydration payloads for
  `/graphs/wiki-timeline`, `/graphs/wiki-timeline-aoo`, and
  `/graphs/wiki-timeline-aoo-all` when compared against stored checkpoints.

Canonical token stream decision
-------------------------------
We must explicitly choose and version one of:
- lexeme-derived canonical tokens, or
- a dedicated tokenizer stream used as the canonical basis.
This decision must be documented before switching away from regex.

Lexeme layer (redundancy substrate)
----------------------------------
- Lexemes collapse surface variance (case/formatting) while preserving spans.
- Lexeme occurrences are anchored to canonical character offsets, not token IDs.
- Lexemes are **pre-semantic**; they must not carry meaning or concepts.
- Phrase atoms built from lexemes are deterministic and reversible.
- See `docs/lexeme_layer.md` for the authoritative contract.

Sentences
---------
- A sentence is an ordered sequence of token IDs for a single tokenizer.
- Sentences are views, not structural truth; they do not carry semantics.
- Boundaries must not be used for identity, logic, or counting guarantees.

Logic tree (structural IR)
--------------------------
- Logic nodes are typed spans over the canonical text: `ROOT`, `CLAUSE`, `CONDITION`, `EXCEPTION`, etc.
- Edges encode structure; nodes do not depend on tokenizers or sentences.
- Overlap between logic spans and token/sentence spans is allowed and non-binding.

Annotations (citations, mentions, ITIR)
---------------------------------------
- All annotations are spans over canonical text with provenance.
- ITIR/semantic layers must not mutate or reinterpret structural spans.

Provenance & determinism
------------------------
- Given `(doc, tokenizer_id, model/config version)`, outputs must be byte-identical.
- Every derived artifact records the versions that produced it.

Forbidden coupling
------------------
- No module may assume a “global tokenizer”.
- Logic tree construction must not import or depend on `tokenize_simple` (metrics-only).
- Sentence boundaries must not drive token counts or logic node identities.
- Regex is not permitted in semantic extraction layers; see
  `SensibLaw/docs/regex_semantic_policy.md`.

Enforcement hints (tests)
-------------------------
- Tokens resolve: `body[start:end]` is non-empty.
- Stable tokenizer determinism: `tokenize_v1(text)` is idempotent.
- Isolation: no imports of `tokenize_simple` outside metrics/report modules.
- Sentence text is reconstructed from tokens; never stored.

Argument graph note (AIF-core)
------------------------------
- Use AIF-style nodes for interchange: I-nodes (propositions/spans), S-nodes (scheme applications RA/CA/PA) with provenance (`method`, `evidence_span`, `score`).
- Relationships between propositions are mediated by scheme nodes; edges alone are insufficient.
