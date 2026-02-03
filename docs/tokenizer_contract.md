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
