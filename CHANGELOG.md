# Changelog

## Unreleased
- Docs: define Layer 3 SpanRoleHypothesis contract (ADR + IR invariants).
- Docs: add TODOs for Layer 3 span storage, promotion gates, regeneration tests.
- Storage: add `span_role_hypotheses` table and helpers in `VersionedStore`.
- Ingestion: add deterministic defined-term span extraction for SpanRoleHypothesis.
- Tests: add regeneration test for span role hypotheses.
- Docs: add promotion rules and gates for Layer 3 span hypotheses.
- Docs: add SpanSignalHypothesis spec for textual signal spans.
- Promotion: add gate evaluator and receipt schema helpers.
- Storage: add `span_signal_hypotheses` and `promotion_receipts` tables.
- Docs: document Layer 3 hypothesis families (role, structure, alignment, signal).
- Ingestion: add SpanSignalHypothesis extractor utilities for text signals.
