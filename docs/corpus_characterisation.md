Corpus Characterisation: Structural vs Interpretive Load
=========================================================

Purpose
-------
Characterise the PDF corpus to decide where the span-based SL profile is sufficient and where ITIR/TIRC overlays add value. All metrics are lexical/structural; none depend on semantics.

Metrics (non-semantic)
----------------------
- `tokens` – document scale.
- `unique` – lexical diversity.
- `mvd = new_vocab_added / new_tokens` – marginal vocabulary density; concept expansion pressure.
- `repeat_ratio_5gram` – verbatim structural reuse.
- `entropy_rate_bits` – estimated Shannon entropy rate (bits/byte) via small n-gram block entropies.
- `token_entropy_proxy` – local distributional entropy proxy (entropy_rate_bits / 8); heuristic only.
- `empirical_compression_ratio` – zlib-compressed byte size / raw byte size; primary empirical signal.
- `lz_entropy_floor` – Lempel–Ziv-style entropy proxy over tokens (estimated bits/token, normalized to bits/byte using token byte length).
- `document_presence` – token appears in how many documents (reasoning glue).

Metric semantics
----------------
- `empirical_compression_ratio` measures observed redundancy using a real-world compressor over canonicalized token streams and is the primary empirical signal.
- `lz_entropy_floor` estimates the Lempel–Ziv-style floor SL is aiming to approximate via canonicalized tokens.
- `token_entropy_proxy` reports a local distributional entropy estimate over tokens and is provided only as a heuristic descriptor; it is not treated as a theoretical lower bound.

SL as LZ target (design framing)
--------------------------------
SL is not "compression plus zlib". The target behavior is LZ-style factorisation made explicit via deterministic canonicalization of token streams. In this framing:
- LZ is the north-star behavior (discover repeated phrases); SL is a conservative, auditable approximation.
- The gap between `empirical_compression_ratio` and `lz_entropy_floor` is the amount of phrase structure that has not been promoted to stable composite atoms yet.
- `token_entropy_proxy` remains a descriptive proxy only; it is not a bound or invariant.

Lexeme layer (redundancy substrate)
-----------------------------------
Lexeme normalization collapses casing/format noise before phrase promotion. This improves
repeat statistics without changing canonical spans:
- `rr5` and `mvd` are computed on lexeme-normalized tokens when available.
- Lexeme occurrences remain span-anchored; no semantic labels are introduced.
- Phrase atoms are built over lexeme sequences, preserving reversibility.

Deterministic span promotion (minimal design)
---------------------------------------------
Goal: expose an LZ-like factorisation over canonical tokens without compromising SL determinism or auditability.

Inputs (frozen):
- Canonical token stream per document.
- Deterministic document ordering (e.g., stable doc_id sort).
- Parameters: `Nmax`, `min_df`, `min_cf`, `min_gain_units`, optional `max_atoms`.

Candidate generation:
- Enumerate n-grams for n=2..Nmax across the corpus.
- Keep spans with `df >= min_df` and `cf >= min_cf`.

Value function (cheap MDL proxy):
- `gain(s) = cf(s) * (len(s) - 1) - dict_cost(s)`
- Use deterministic `dict_cost(s)` (e.g., `alpha * len(s)`).
- Keep spans with `gain >= min_gain_units`.

Deterministic selection:
- Sort candidates by `gain desc`, `len desc`, `df desc`, `payload_hash asc`.
- Accept spans in order, rejecting strict subspans of any accepted longer span.

Deterministic rewrite:
- Leftmost-longest matching against promoted phrases.
- Tie-break by `payload_hash` when equal length.
- One pass only (no phrase-of-phrases) in v1.

Phrase atom contract (SL layer only)
------------------------------------
Identity:
- `atom_id = "p:" + hash(expansion || schema_version)`
Definition:
- `expansion`: exact canonical token tuple.
- `len`: base token length.
Provenance:
- `promoted_by`, `params_hash`, optional `corpus_fingerprint`.
Statistics (non-normative):
- `df`, `cf`, `gain_estimate`, optional examples (doc_id + offsets).

Invariants:
- Deterministic identity for identical expansions.
- Lossless expansion (rewrite is invertible).
- No interpretive labels in SL (meaning belongs to ITIR).
- Stable emission order when exporting phrase atoms.

ITIR composition boundary
-------------------------
SL outputs immutable structural artifacts: canonical tokens, phrase atoms, rewritten streams, and occurrence indices.
ITIR consumes these artifacts via overlays that attach interpretations without mutating SL:
- `target`: (`doc_id`, `offset_range`) or `atom_id`
- `layer`, `label`, `score`, `evidence`, `model_id`
ITIR must not alter canonicalisation, promotion thresholds, or SL dictionaries.

Observed Patterns
-----------------
- Vocabulary growth is sublinear across the corpus; later documents add fewer new terms per token.
- Two dominant regimes emerge:
  - Exploratory: high MVD, low 5-gram (e.g., DASHI vs LES).
  - Iterative/consolidating: low–mid MVD, higher 5-gram (e.g., JavaCrust, Filament Fining).
  - Formal specification: low MVD, mid 5-gram (e.g., V5 Operator Definition).
- High 5-gram repetition signals recombination of existing concepts, not novelty.

Implications for SL vs ITIR
---------------------------
- SL remains stable where MVD is low–moderate and repetition collapses into shared spans.
- ITIR adds value where MVD spikes or argumentative/explanatory structure dominates.
- No document shows uncontrolled lexical drift that would force semantics into SL.

Takeaway
--------
5-gram repetition tells us how often we say the same thing again; marginal vocabulary density tells us whether we’re saying new things at all. Separation of concerns stands: deterministic spans for SL, interpretive layering via ITIR.

Latest corpus_stats run (2026-02-03)
------------------------------------
Per-PDF snapshot (repo root PDFs):

| PDF | tokens | unique | rr5 | token_entropy_proxy | empirical_compression_ratio | lz_entropy_floor |
| --- | --- | --- | --- | --- | --- | --- |
| SensibLaw_ Open Legal Knowledge Graph & Reasoning Platform.pdf | 6,618 | 1,835 | 0.005 | 0.324 | 0.399 | 0.126 |
| act-2005-004.pdf | 15,654 | 1,617 | 0.295 | 0.278 | 0.257 | 0.108 |
| 1936 HCA House v. The King.pdf | 4,302 | 1,019 | 0.109 | 0.285 | 0.360 | 0.129 |
| Native Title (New South Wales) Act 1994 (NSW).pdf | 33,048 | 1,782 | 0.596 | 0.276 | 0.202 | 0.105 |
| Plaintiff S157_2002 v Commonwealth - [2003] HCA 2.pdf | 56,907 | 4,192 | 0.337 | 0.311 | 0.293 | 0.122 |
| Mabo [No 2] - [1992] HCA 23.pdf | 144,878 | 7,246 | 0.342 | 0.326 | 0.290 | 0.124 |

Corpus-level compression:
- empirical_compression_ratio = 0.2823
- token_entropy_proxy = 0.3130
- lz_entropy_floor = 0.1203

Note: the corpus aggregate compression ratio is below the current Shannon estimate. This suggests the entropy-rate estimator (or aggregation method) may be overstating the lower bound and should be reviewed.
