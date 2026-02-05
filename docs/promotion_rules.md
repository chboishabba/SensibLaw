# Layer 3 Promotion Rules (Span Hypotheses → Ontology)

This document defines the **promotion boundary** between Layer 3 span-only hypotheses
and ontology tables. Promotion converts local, pre-ontological spans into durable
ontology rows and links, without mutating canonical text or Layer 3 records.

## Scope

Applies to **SpanRoleHypothesis** records and **SpanSignalHypothesis** records that
are derived deterministically from canonical text spans.

## Core principles

1. **Span-only inputs**: promotions use span hypotheses that carry
   `(doc_id, rev_id, span_start, span_end, span_source)` and metadata.
2. **No in-place mutation**: Layer 3 records are immutable after creation.
3. **Auditable rules**: every promotion is traceable to a rule ID and evidence spans.
4. **Deterministic outputs**: given identical inputs, promotion yields identical
   ontology rows and linkage tables.
5. **Local to global only by rule**: cross-document identity is created only by
   explicit rules that are documented here.

## Layer 3 hypothesis families (minimal set)

- **SpanRoleHypothesis**: role-like spans (actor, object, construct, procedural).
- **SpanStructureHypothesis**: list markers, headings, scope cues, structural hints; never asserts meaning.
- **SpanAlignmentHypothesis**: cross-version correspondence only; never asserts identity or legal continuity.
- **SpanSignalHypothesis**: glyph/OCR/layout anomalies and integrity signals.

## Promotion staging

Promotion is a staged pipeline. Each stage may emit **candidates**, but only
finalized promotions reach ontology tables.

1. **Span collection** → gather hypotheses within a doc revision.
2. **Span normalization** → normalize labels for matching (lowercase, trim, collapse
   whitespace). Do not rewrite canonical text.
3. **Promotion gates** → evaluate rules; either approve or reject with reason.
4. **Ontology upsert** → create/update ontology rows; attach provenance.
5. **Receipt** → store promotion receipt with rule ID, spans, and timestamps.

## Promotion gates (initial set)

A hypothesis may be promoted **only** if at least one gate succeeds.

### Gate A: Defined-term rule

- **Input**: SpanRoleHypothesis with `role_hypothesis = defined_term`.
- **Rule**: Promote if the defined-term span appears in a valid definition pattern
  within the same document revision.
- **Output**: create or update a concept row keyed by normalized term text.
- **Provenance**: link to the defining span and the definition span.

### Gate B: Repeated independent spans

- **Input**: SpanRoleHypothesis with the same normalized label appearing in ≥ N
  distinct spans within a document revision.
- **Rule**: Promote only if spans are separated by at least M tokens or different
  sections (to avoid list artifacts).
- **Default**: N=3, M=50 tokens (tunable constants). When only char spans are
  available, use a deterministic char-distance fallback.
- **Output**: create or update a concept row; attach all contributing spans.

### Gate C: Modal participation

- **Input**: SpanRoleHypothesis with `role_hypothesis` in {actor, object, construct}
  that occurs in the same clause as a **modality marker** (e.g., must, may, must not).
- **Rule**: promote only when a modal marker span is present and within K tokens.
- **Default**: K=40 tokens. When only char spans are available, use a deterministic
  char-distance fallback.
- **Output**: create or update a concept row with role-specific provenance.

### Gate D: Signal escalation (optional)

- **Input**: SpanSignalHypothesis with `signal_type` in {encoding_loss, ocr_uncertain}.
- **Rule**: do **not** promote to ontology; instead, emit a warning receipt and
  mark affected spans as **promotion-blocking** for Gates A–C.
- **Output**: a promotion receipt with `blocked_by_signal = true`.

## Rejection handling

Each rejected hypothesis must yield a receipt containing:

- `hypothesis_id` or span reference
- `gate_id` evaluated
- `reason` (structured code, not free text)
- `evidence` (span references)

## Receipt schema (minimum fields)

- `doc_id`, `rev_id`
- `gate_id`
- `status` (`promoted`, `rejected`, `blocked`)
- `reason` (machine code)
- `hypothesis` (span + metadata snapshot)
- `evidence` (span references, rule notes)

## Determinism requirements

- Sort inputs by `(doc_id, rev_id, span_start, span_end, role_hypothesis)`.
- Use stable hashing for any derived IDs.
- Avoid wall-clock timestamps inside identity or matching logic.

## Non-goals

- No ML-based promotion.
- No cross-document merging outside explicit gates.
- No mutation of Layer 0/1/2 canonical data.
