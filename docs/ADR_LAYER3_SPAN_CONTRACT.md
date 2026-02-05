# ADR: Layer 3 Span-Only Role Hypotheses

Date: 2026-02-05
Status: Proposed

## Context

Layer 3 is where interpretive artifacts begin to appear (e.g., role-like noun candidates, subject/object hints, or procedural actors). These artifacts are useful, but they must not contaminate Layer 0/1/2 truth or imply ontology membership. Past drafts used entity-like names (e.g., "candidate legal entity"), which risked smuggling in legal commitments.

## Decision

Layer 3 will store **span-only role hypotheses** and nothing stronger. The preferred term is **SpanRoleHypothesis** (formerly "CandidateRoleSpan") to emphasize uncertainty.

A Layer 3 record:

- MUST reference a stable text span: `(doc_id, rev_id, span_start, span_end, span_source)` where `span_source` declares whether offsets are token- or char-based.
- MAY include `role_hypothesis`, `extractor`, `evidence`, and `confidence` metadata.
- MUST NOT assert cross-document identity or merge spans into a single global entity.
- MUST be regenerable from Layer 0/2 outputs without reading or rewriting canonical text.

Promotion into ontology tables is a separate, explicit step governed by auditable rules (e.g., defined-term detection, repeated independent spans, or modal-verb participation). Promotion never mutates Layer 3 artifacts; it references them.

## Consequences

- Layer 3 artifacts are **pre-ontological** and **local to a span**.
- Determinism is preserved: deleting Layer 3 tables and rebuilding must yield identical outputs given the same Layer 0/2 inputs.
- Schema or storage for Layer 3 must remain isolated from ontology tables until promotion criteria are satisfied.

## Non-goals

- Defining the promotion rule set (documented separately).
- Building extraction pipelines or heuristics in this ADR.
- Changing Layer 0/1/2 storage semantics.

## Follow-ups

- Define a SpanRoleHypothesis schema and storage location.
- Specify promotion gates and tests for determinism/regeneration.
