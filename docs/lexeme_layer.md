Lexeme Layer (Redundancy-First, Span-Anchored)
==============================================

Purpose
-------
Introduce a redundancy-collapsing lexeme layer that is anchored to canonical
character spans and does not alter or reinterpret source text. This is a
compression substrate, not a semantic layer.

Scope
-----
- **In scope**: lexeme dictionary, lexeme occurrences, phrase atoms built from
  lexeme sequences, deterministic promotion rules.
- **Out of scope**: semantic concepts, reasoning, compliance judgments, or
  any cross-document meaning.

Canonical invariants
--------------------
- Canonical text is immutable and authoritative.
- All lexeme occurrences point to canonical `TextSpan` offsets.
- Lexemes are **pre-semantic**; they are not concepts.
- Lexeme and phrase promotion are deterministic and reproducible.

Lexeme dictionary
-----------------
A lexeme is a normalized token form used to collapse case and trivial
surface variance while preserving provenance through span anchoring.

- **Normalization**: Unicode NFKC + casefold.
- **Classification**: `word`, `number`, `punct`, `symbol`, `other`.
- **Identity**: `(norm_text, norm_kind)`.
- **No semantic metadata**: lexemes are not meanings.

Lexeme occurrence
-----------------
Each occurrence is a span-anchored record linking a lexeme to a position in the
canonical body.

Required fields:
- `doc_id`, `rev_id`
- `occ_id` (stable sequence per revision)
- `lexeme_id`
- `start_char`, `end_char`
- `flags` (format/anomaly bits; e.g., ALL_CAPS, TITLE_CASE, NON_ASCII)

Optional fields:
- `token_index` (cache only; never authoritative)
- `surface_hash` (diagnostic only)

Phrase atoms (lexeme sequences)
-------------------------------
Phrase atoms are stable, reversible sequences of lexemes that reduce
redundancy without semantic interpretation.

Identity:
- `lexeme_seq_hash` = hash of ordered lexeme IDs.
- `lexeme_ids_json` stores the exact sequence.

Occurrences:
- Each phrase occurrence records `start_char/end_char` and optional
  `start_occ_id/end_occ_id` for fast expansion.

Deterministic promotion (v1)
----------------------------
Promotion is deterministic and reversible. A phrase is promoted if it
meets repeat/coverage thresholds and improves description length.

Minimal criterion:
- `f(s) * (len(s) - 1) > dict_cost`

Selection:
- Leftmost-longest rewrite.
- Tie-breakers: higher count, longer length, stable hash order.

Audit and safety
----------------
- Promotions emit receipts with parameters and corpus fingerprints.
- Phrase atoms are **non-authoritative**; no semantic labels are allowed.
- ITIR overlays may annotate phrases but must not mutate lexeme or phrase
  dictionaries.

Relationship to tokenizer contract
----------------------------------
Tokenizers produce ordered spans. Lexeme occurrences are derived from those
spans and are anchored to canonical text, not to any tokenizer identity.
Lexeme and phrase layers **do not** replace canonical spans.

See also
--------
- `docs/tokenizer_contract.md`
- `docs/corpus_characterisation.md`
- `docs/ir_invariants.md`
