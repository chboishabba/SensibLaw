# Span Signal Hypotheses (Layer 3)

SpanSignalHypothesis records capture **textual signal spans** that indicate
encoding anomalies, layout artefacts, or OCR uncertainty. They are **span-only**
and pre-ontological, and they never modify canonical text.

## Core fields

- `span_start`, `span_end`, `span_source`
- `signal_type`
- `extractor`
- `evidence`
- `confidence`
- `metadata`

## Signal types (initial set)

- `non_ascii_glyph` — smart quotes, non-breaking spaces, ligatures, bullet glyphs.
- `ocr_uncertain` — ambiguous OCR reads (l/1/I, 0/O, rn/m).
- `encoding_loss` — replacement characters (�), missing glyphs, broken diacritics.
- `layout_artifact` — page headers/footers, footnote markers, marginalia.
- `list_marker` — bullets, (a), (i), hyphen bullets used as structure.
- `punctuation_damage` — collapsed or duplicated punctuation, broken brackets.
- `visual_emphasis` — ALL CAPS, italics/underline artefacts, heading emphasis.

## Rules

1. **Span-only**: must reference `(doc_id, rev_id, span_start, span_end, span_source)`.
2. **No cleanup**: signals do not rewrite or normalize text.
3. **Deterministic**: extractors must be repeatable and order-stable.
4. **Promotion blocking**: signal spans may block promotion gates when they
   overlap the candidate span (see `docs/promotion_rules.md`).

## Layer 3 families (context)

SpanSignalHypothesis is one of the four minimal Layer 3 hypothesis families:
SpanRoleHypothesis, SpanStructureHypothesis, SpanAlignmentHypothesis, and
SpanSignalHypothesis. It is the **textual signal** axis only.

## Non-goals

- No ML-driven correction.
- No automatic promotion to ontology.
- No mutation of Layer 0/1/2 text.
