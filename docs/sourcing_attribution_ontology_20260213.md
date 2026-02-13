# Sourcing and Attribution Ontology (v0.1)

## Purpose
Define deterministic source/attribution structures for AAO events so numeric and temporal reasoning can distinguish:
- content actor,
- reporting actor,
- document source,
- extraction provenance.

This specification is schema-first and intentionally minimal for current AAO integration.

## Core Principle
Separate these lanes explicitly:
1. `attributed_actor` (who is responsible for the claim content),
2. `reporting_actor` (who reports/relays the claim),
3. `source_entity` (which artifact carries the statement),
4. `extraction_record` (which pipeline run produced the structured row).

## Entity Schemas

### SourceEntity
Represents the source artifact that contains the statement text.

```yaml
SourceEntity:
  id: string
  type: enum
    - wikipedia_article
    - news_article
    - government_report
    - speech
    - transcript
    - court_opinion
    - dataset
  title: string
  publication_date: string?   # TimePoint id or iso-like value
  publisher: string?
  url: string?
  version_hash: string?
```

Identity:
- prefer stable external id/hash when available;
- otherwise deterministic fallback key from (`type`, normalized `title`, normalized `url`).

### Attribution
Claim-level provenance attachment.

```yaml
Attribution:
  id: string
  claim_id: string
  attributed_actor_id: string
  attribution_type: enum
    - direct_statement
    - reported_statement
    - inferred_statement
    - anonymous_source
    - editorial_summary
  reporting_actor_id: string?
  source_entity_id: string
  certainty_level: enum
    - explicit
    - implicit
    - inferred
  extraction_method: enum
    - direct_quote
    - paraphrase
    - summary
    - structured_table
  parent_attribution_id: string?
```

Constraints:
- `attributed_actor_id` and `source_entity_id` are required.
- `parent_attribution_id` must not introduce cycles.

### ExtractionRecord
Machine-level reproducibility record.

```yaml
ExtractionRecord:
  id: string
  source_entity_id: string
  parser_version: string
  extraction_timestamp: string
  confidence_score: float?
```

## AAO Integration (Current Direction)
Current system keeps implicit claim structure in AAO action rows.
For v0.1, attach attribution directly to event/step payloads:

```yaml
AAOEvent:
  event_id: string
  ...
  attributions: Attribution[]
  source_entities: SourceEntity[]
  extraction_record: ExtractionRecord?
```

No explicit top-level `Claim` entity is required in this slice.

## Conflict Logic Hooks (Attribution-Aware)
Quantified conflict checks should include attribution context:
- run conflict checks on claim-bearing lanes only;
- require temporal overlap + numeric non-overlap;
- keep attribution metadata in result payload so consumers can distinguish:
  - same attributed actor conflicts,
  - cross-actor disagreements.

Authority weighting is out of scope for v0.1.

## Determinism Rules
1. No heuristic actor injection without provenance marker.
2. No circular attribution chains.
3. Stable ids for source/attribution records from deterministic key functions.
4. Attribution layer must not mutate AAO role lanes.

## Minimal MVP Implementation Scope
1. Add model classes for:
   - `SourceEntity`,
   - `Attribution`,
   - `ExtractionRecord`.
2. Provide deterministic key helpers.
3. Provide lightweight edge projection helpers for graph integration.
4. Add unit tests for:
   - id stability,
   - attribution chain cycle detection,
   - attachment shape invariants.

## Non-goals (v0.1)
- No authority scoring/ranking.
- No probabilistic source credibility updates.
- No automatic cross-document claim truth adjudication.
