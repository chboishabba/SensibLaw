# JSON Sin Bin

> This is the visible bootstrap roster. `scripts/audit_json_sin_bin.py` is the
> authoritative line-level scanner and regenerates the complete report in CI
> with file, line, category, symbol, and evidence.

## Policy

JSON and JSONB are forbidden in semantic execution authority, identity, replay,
checkpointing, leases, attempts, receipts, cursors, outboxes, parser
observations, finalisation, and publication. Boundary/import/export uses are
quarantined debt, not an allow-list.

The target architecture is:

```text
native subsystem workspace
→ one typed/binary boundary crossing
→ typed PostgreSQL authority or content-addressed binary cache
```

Never:

```text
object → dict → JSON → JSONB → dict → object
```

## Cleared execution authority

These paths are guarded by both the generated scanner and source-level tests:

- `src/nlp/spacy_adapter.py`
- `src/policy/binary_family_integrity_execution.py`
- `src/policy/carriers/canonical.py`
- `src/policy/no_json_checkpoint_execution.py`
- `src/policy/reference_backed_finalization.py`
- `src/policy/stage_budget_execution.py`
- `src/policy/streaming_spacy_parser_execution.py`
- `src/policy/typed_execution_callback_views.py`
- `src/pnf/streaming_build_reader.py`
- `src/runtime/durable_stage_state.py`
- `src/runtime/durable_work_item_hardening.py`
- `src/runtime/durable_work_items.py`
- `src/runtime/reference_receipt.py`
- `src/runtime/strict_postgres_execution.py`
- `src/storage/postgres/deterministic_admission_execution.py`
- `src/storage/postgres/distributed_semantic_execution.py`
- `src/storage/postgres/spacy_parser_carrier.py`
- `src/storage/postgres/spacy_parser_model.py`
- `src/storage/postgres/spacy_parser_store.py`
- `src/storage/postgres/streaming_spacy_execution.py`
- `src/storage/postgres/typed_execution_pool.py`
- `src/storage/postgres/typed_value_store.py`
- `scripts/run_durable_coordinator_kill_probe.py`
- `scripts/run_post_closure_probe.py`
- migrations `032` through `039`

## Parser-specific name and shame

### Strict authority: cleared

Strict spaCy execution now uses:

```text
immutable UTF-8 source
→ typed structural partition rows
→ ephemeral spaCy Doc
→ typed sentence/token/dependency/morphology/entity rows
→ typed sentence-local graph work
```

No strict parser source, partition, attempt, observation, receipt, coverage row,
outbox event, or cache descriptor is JSON/JSONB. Optional spaCy `DocBin` files
are content-addressed binary caches and are never authority.

### Compatibility materialisation debt

The following source-level surfaces remain explicitly shamed:

- `src/nlp/spacy_adapter.py::parse`
  - constructs the historical nested sentence/token mapping;
  - retained only for non-strict callers;
  - strict execution uses `get_streaming_nlp()` and `Language.pipe` instead.
- `src/pnf/document_fibres.py`
  - retains historical JSON parser checkpoints and summary sidecars;
  - reloads parsed mappings and performs document-wide token renumbering;
  - bypassed entirely by strict typed parser execution.
- `src/policy/entity_resolution.py`
  - contains legacy JSON canonicalisation for mention/carrier identities;
  - remains migration debt for sentence-native typed graph consumers.
- `src/policy/indexed_projection_execution.py`
  - still exposes compatibility projections that may collect parser token rows;
  - sentence-local PostgreSQL work is now ready immediately, but source-level
    removal of the compatibility population build remains a separate cleanup.

Runtime bypass is not permission to add more use. These names stay visible until
the old definitions themselves are deleted or moved to an explicit boundary
package.

## Repository JSON offenders

The generated scanner enumerates every occurrence rather than relying on this
hand-maintained summary. Major quarantined groups include:

### Import, ingestion, and external source adapters

- `scripts/import_*json*`
- `src/fact_intake/*`
- `src/ingestion/*`
- `src/sources/*`
- external API adapters such as Wikimedia, CourtListener, DBpedia, and EUR-Lex

### Legacy graph, ontology, policy, runtime, and reporting surfaces

- graph/ontology loaders and exports;
- old receipt, progress, parity, and manifest paths;
- UI, CLI, reports, demos, and test fixtures;
- historical SQLite/document compatibility models.

These are not silently accepted. Every concrete file and line appears in the
generated table.

## Active legacy definitions overridden at installation

These modules still contain historical JSON helper definitions and remain
explicitly shamed even where installed execution policy replaces their sinks:

- `src/policy/parallel_semantic_execution.py`
- `src/policy/parallel_typing_tail.py`
- `src/policy/progress_observability_execution.py`
- `src/pnf/document_fibres.py`

They are scheduled for source-level removal after typed execution acceptance.

## Scanner coverage

The scanner catches:

- `json`, `orjson`, `ujson`, and `simplejson` imports;
- `dump`, `dumps`, `load`, `loads`, encoder, and decoder calls;
- JSON adapters;
- JSON/JSONB SQL columns, casts, and builders;
- `.json` and `.jsonl` paths;
- JSON media types and encoding contracts;
- `jq` and `json_pp` in scripts and workflows.

Regenerate and enforce with:

```bash
uv run python scripts/audit_json_sin_bin.py \
  --write docs/architecture/JSON_SIN_BIN.md \
  --check-authority
```

Any authority-critical finding fails CI. Quarantined findings remain visible
until removed; silence is not an accepted state.
