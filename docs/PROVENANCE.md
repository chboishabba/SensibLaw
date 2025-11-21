# Provenance Model

Provenance links every visual element back to its evidentiary source so that timelines remain explainable and auditable.

- **Source capture**: retain document/utterance IDs, timestamps, and actor identifiers for each observation or feature.
- **Transformation trace**: record derived metrics (e.g., rolling sentiment, dependency ratios) with the windowing and formulas applied.
- **Cross-layer joins**: connect finance events, harms, wrong types, and value frames through explicit link tables rather than implicit inference.
- **Display hooks**: expose the sentence/transaction/order snippets underlying any ribbon point in Streamline, along with perspective metadata.
- **Integrity**: ensure updates are versioned so analysts can trace when and how a data point entered the system.

Use this as the reference for provenance requirements in `TIMELINE_STREAM_VIZ_ROADMAP.md` and related specs.
