# Actor Coalescing Contract (Wiki Timeline / AAO)

## Purpose
Consolidate actor and subject coalescing rules into one deterministic contract for
wiki timeline AAO extraction and projections.

This document is actor-focused only. Numeric, temporal, and fact-row contracts
remain in their dedicated specs.

## Scope
- Actor/subject identity normalization in extraction output.
- Requester-lane actor normalization and coverage.
- Actor coalescing boundaries across steps/frames/events.
- Attribution-role separation for actor identities.

## Canonical Actor Identity Rules
1. Prefer resolved identity keys when available (stable resolver/external ID).
2. If no resolved ID exists, use deterministic canonical surface normalization.
3. Strip leading definite article in actor/subject labels (`the X` -> `X`) to
   prevent identity fragmentation.
4. Canonicalize requester surfaces by removing possessive/title noise before
   alias resolution (for example, `President Obama's` -> `Barack Obama`).
5. Alias-only coalescing is allowed only when alias maps are explicit profile
   input and provenance-preserved.
6. Actor-type conflicts must not silently merge (for example, `PERSON` vs `ORG`).

## Requester-Lane Rules
1. Detect requester actors from dependency/step structure first.
2. Canonicalize requester labels before lane projection.
3. Do not collapse request-bearing rows into `req:none` when request evidence exists.
4. Emit requester coverage diagnostics:
   - `request_signal_events`
   - `requester_events`
   - `missing_requester_event_ids`
5. `req:none` projections must expose missing-requester diagnostics rather than
   silently returning empty results when request signals are present.

## Attribution Role Separation
1. Keep actor roles distinct:
   - `attributed_actor`
   - `reporting_actor`
   - `source_entity`
2. Coalescing must not collapse these roles into one actor lane key.
3. Evidence/source lanes are context lanes, not role lanes.

## Step/Frame/Event Coalescing Boundaries (Actor-Relevant)
1. Step coalescing requires equality on normalized subject set plus canonical
   action/object fields and frame-local context.
2. No silent cross-frame actor coalescing in frame-scoped views.
3. Fact rows must be event-local and anchor-aware; never coalesce across
   different `event_id` values based on text similarity alone.
4. Chain-linked governing/complement facts remain distinct when actions differ,
   even if sentence text is identical.

## Forbidden Actor Coalescing Inputs
- Embedding similarity.
- Levenshtein/fuzzy distance.
- Regex-only subject inference in authoritative paths.
- Global document union when projecting frame-scoped actor rows.

## Provenance Requirements
Each coalesced actor artifact must preserve:
1. Source `event_id` / frame reference.
2. Canonicalization fields used for merge (surface normalization + alias source).
3. Profile identity/version/hash when profile-driven rules apply.
4. Any fallback markers used during extraction.

## Validation Invariants
1. Actor coalescing is deterministic and idempotent across repeated runs.
2. No cross-frame actor leakage in frame-scoped projections.
3. Requester diagnostics remain consistent with extraction outputs.
4. Attribution-role separation remains intact after coalescing.

## Source Trace
- `SensibLaw/docs/wiki_timeline_requirements_v2_20260213.md` (`R17`, `R25`)
- `docs/planning/wiki_timeline_coalescing_contract_20260212.md`
- `SensibLaw/docs/sourcing_attribution_ontology_20260213.md`
- `SensibLaw/docs/wiki_timeline_requirements_698e95ec_20260213.md`
