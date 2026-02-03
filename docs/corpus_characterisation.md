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
- `document_presence` – token appears in how many documents (reasoning glue).

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
