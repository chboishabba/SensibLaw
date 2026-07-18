# Generic semantic algebra refactor

This tranche establishes the reusable centre beneath entity resolution, PNF,
language reduction, evidence reconciliation, and proof fixtures.

## Architectural rule

No domain or corpus may introduce a separate semantic pipeline where the result
can be represented as a grammar-generated typed alternative, factor constraint,
typed meet, residual, pressure assessment, or factor refinement.

Domain and registry adapters may contribute observations, type declarations,
grammar declarations, capabilities, evidence, closure policy, and authority
policy. They may not silently select interpretations.

GWB and AU are proof corpora. They are not annotation profiles, parser modes, or
media adapters. Media adapters are selected by generic capability such as PDF,
plain text, HTML, or structured records.

## Added reusable layers

- `src/policy/carriers`: canonical JSON, hashing, reference normalization,
  schema validation, and authority validation.
- `src/policy/algebra`: typed alternatives, factors, constraints, typed meets,
  pressure envelopes, residual transitions, and factor refinements.
- `src/language`: immutable annotation layers, one annotation graph, and
  declarative branch-preserving reduction grammars.
- `src/pnf`: factorized PNF graph, closure contracts, and backend-free demand
  projection.
- `src/resolution`: generic external snapshot envelope, meet-product
  reconciliation, and shared proof-report generation.
- `src/ingestion/media_refs.py`: immutable text-span and segment references.
- `src/ingestion/media_adapter_contract.py`: capability-oriented media adapter
  protocol with no corpus-specific adapters.
- `tests/factories`: minimal valid semantic carrier factories.

## Compatibility and migration boundary

This tranche deliberately does not delete or rename the existing
`src/policy/entity_resolution.py`, `src/ingestion/section_parser.py`, or
`src/pdf_ingest.py`. They remain compatibility implementations while callers are
migrated to the reusable modules under parity tests.

The safe migration sequence is:

1. replace local `_text`, `_refs`, JSON, and digest helpers with
   `src.policy.carriers` imports;
2. project existing PartialPNF slots into `Factor` values and preserve the
   current public serialized form through an adapter;
3. make existing entity/event reconciliation emit `TypedMeet` coordinates;
4. make refinement consume and return `Factor`/`FactorRefinement` while
   preserving old entry points;
5. project spaCy-derived facts into immutable `AnnotationLayer` values before
   removing mutable token-extension writes;
6. move page normalization behind a dedicated generic PDF stage and prove the
   omitted-lines fixture behaviour;
7. migrate canonical units to `TextSpanRef` and `SegmentRef` after artifact
   parity is demonstrated;
8. split the legacy entity-resolution and PDF modules only after import and
   serialization parity tests pass.

This avoids a flag-day package conversion and prevents the new algebra from
becoming another monolith.

## Non-authority guarantees

- deterministic ordering is serialization-only;
- grammars expand alternatives and never rank them;
- annotation layers do not resolve entities or mutate PNF;
- typed meets assess compatibility and do not establish claim truth;
- snapshot envelopes carry evidence only;
- PNF demand projection is backend-free;
- proof reports carry no editing authority.
