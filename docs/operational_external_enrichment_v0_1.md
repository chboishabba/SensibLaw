# Operational external enrichment v0.2

Date: 2026-07-19

## Purpose

The local compiler produces stable PNF factors and resolution demands before
any registry request is made. External enrichment is a later, explicit phase:

```text
source bytes
  -> canonical text
  -> local parser / annotation graph
  -> local PNF factors and open demands
  -> persisted or artifact-derived external lookup plan
  -> bounded Wikimedia microbatches
  -> candidate sets and pressure receipts
  -> governed typed meet (not implemented by lookup)
```

Parsing and exact document-build reuse therefore do not depend on Wikidata,
Wiktionary, rate limits, network availability, or a provider cache.

## Candidate and authority boundary

A provider result is represented as `ExternalCandidate`, grouped in an
`ExternalCandidateSet` attached to one existing `resolution.demand`.

The runtime may transition:

```text
external_candidate_absent
  -> external_candidates_available
```

It may not transition:

```text
external_identity_unresolved -> closed
lexical_sense_unresolved     -> closed
```

A QID is a candidate identity reference, not an identity decision. In
particular, `the United States`, `U.S.`, and `America` may each receive `Q30` as
a candidate while retaining distinct mention refs, factor refs, demand refs,
candidate-set refs, and pressure receipts.

## Pressure surface

Each provider candidate set emits a before/after vector containing:

- lookup absence;
- candidate ambiguity;
- local-type mismatch;
- unresolved external identity;
- unresolved lexical sense.

Lookup can remove absence pressure while revealing ambiguity or type pressure.
`monotone` compares the complete vector totals, not only lookup absence. A
three-candidate result can therefore be correctly non-monotone even though a
provider returned useful candidates.

Wikidata P31/P279 QIDs are compared only with explicit QID-shaped local type
constraints. Linguistic types such as `named_entity_candidate` are retained as
incomplete cross-vocabulary evidence rather than falsely declared incompatible.
Candidate mutation and promotion remain downstream governance operations.

## Microbatch and cache policy

`WikimediaMicrobatchRunner`:

- deduplicates normalized semantic lookup keys across demands;
- applies a provider request budget;
- sends Wiktionary titles in bounded multi-title requests;
- batches Wikidata `wbgetentities` detail requests after bounded entity search;
- applies separate positive and negative cache TTLs;
- emits reusable progress events;
- returns transport receipts for completed, failed, empty, and budget-exhausted
  requests.

The default runner does not write to Wikidata or Wiktionary.

## PostgreSQL

Migration `014_external_pnf_enrichment.sql` adds normalized provider request,
snapshot, candidate, alias, type, candidate-set, assessment, residual, and
pressure tables. Database checks require:

```text
candidate authority = candidate_only
identity_closed = false
demand_closed = false
```

The original `resolution.demand` remains authoritative for whether work is
open. External rows are evidence and candidate projections linked to that
demand.

`enrichment_planner.py` reconstructs provider work directly from normalized
PostgreSQL rows:

```text
resolution.demand
  -> factor revision
  -> factor alternatives
  -> licensed mention annotation node
  -> parser POS / open residuals
  -> ExternalLookupDemand
```

It skips pronominal factors, prioritizes structurally entity-shaped mentions,
applies a hard plan limit, and performs no network work.

## Running over a persisted corpus

Plan directly from a compiled corpus without network access:

```bash
python scripts/run_wikimedia_enrichment.py \
  --corpus-ref "$CORPUS_REF" \
  --database-url "$DATABASE_URL" \
  --output test-results/wikimedia-plan.json \
  --plan-only
```

Run bounded providers and persist candidate sets against the existing demands:

```bash
python scripts/run_wikimedia_enrichment.py \
  --corpus-ref "$CORPUS_REF" \
  --database-url "$DATABASE_URL" \
  --output test-results/wikimedia-results.json \
  --plan-limit 1000 \
  --microbatch-size 16 \
  --request-budget-per-provider 64
```

## Running over compiler artifacts

The same phase can operate on explicit compiler artifact JSON:

```bash
python scripts/run_wikimedia_enrichment.py \
  --input path/to/compiler-output.json \
  --output test-results/wikimedia-plan.json \
  --plan-only
```

Add `--database-url` only when those artifact demands already exist in that
database and the candidate sets should be persisted.

## URL ingestion and source follow

`web_fetch.py` returns a success or failure receipt for every requested URL.
Failures are printed with the URL so an operator can inspect or manually acquire
the source. HTML is passed through `HtmlDocumentMediaAdapter`; raw bytes and
canonical text remain separate.

`link_follow.py` owns bounded breadth-first traversal, URL/content
deduplication, link labels, and explicit truncation. A lane supplies its own host
and link policy.

## Legal lanes

AU, GB, and US share one `LegalFollowProfile` contract and one bounded runtime.
Endpoints are tagged as official or supporting and by source role. The profiles
include official legislation and court surfaces plus selected research indexes.

The Brexit v2 lane uses real legislation.gov.uk and Find Case Law targets and
never silently substitutes a fixture after a failed live request. The legacy
National Archives module remains only for compatibility with existing fixtures.

Run a lane:

```bash
python scripts/run_legal_follow.py \
  --jurisdiction GB \
  --max-depth 1 \
  --max-documents 20 \
  --output-dir test-results/gb-follow
```

## CI

`.github/workflows/external-enrichment.yml` is offline by design. It applies all
immutable migrations and tests mocked Wikimedia transports, cache reuse, Q30
alias behavior, full-vector pressure semantics, direct PostgreSQL planning, URL
failure receipts, bounded traversal, and equal legal-follow capability. Live
provider smoke tests are intentionally not required for pull-request
correctness.
