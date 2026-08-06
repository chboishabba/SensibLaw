# JSON Sin Bin

> This is the visible bootstrap roster. `scripts/audit_json_sin_bin.py` is the
> authoritative line-level scanner and regenerates this report in CI with file,
> line, category, symbol, and evidence.

## Policy

JSON and JSONB are forbidden in semantic execution authority, identity, replay,
checkpointing, leases, attempts, receipts, cursors, outboxes, finalisation, and
publication. Boundary/import/export uses below are quarantined debt, not an
allow-list.

## Cleared execution authority in this tranche

The following paths have been migrated to typed relational state or binary
content-addressed artifacts and are guarded by CI:

- `src/policy/carriers/canonical.py`
- `src/policy/no_json_checkpoint_execution.py`
- `src/policy/reference_backed_finalization.py`
- `src/policy/stage_budget_execution.py`
- `src/policy/typed_execution_callback_views.py`
- `src/pnf/streaming_build_reader.py`
- `src/runtime/durable_stage_state.py`
- `src/runtime/durable_work_item_hardening.py`
- `src/runtime/durable_work_items.py`
- `src/runtime/reference_receipt.py`
- `src/runtime/strict_postgres_execution.py`
- `src/storage/postgres/distributed_semantic_execution.py`
- `src/storage/postgres/typed_value_store.py`
- `scripts/run_durable_coordinator_kill_probe.py`
- `scripts/run_post_closure_probe.py`
- migrations `032` through `036`

## Quarantined `import json` offenders

The following files were found by repository code search at the start of this
tranche. They remain named until the generated scanner confirms removal or an
explicit non-authoritative boundary replacement:

### Import, ingestion, and source adapters

- `scripts/import_wiki_timeline_aoo_json_to_db.py`
- `scripts/import_openrecall.py`
- `scripts/import_observation.py`
- `scripts/import_worldmonitor.py`
- `scripts/import_openrecall_raw_rows.py`
- `scripts/query_openrecall_import.py`
- `scripts/query_observation_import.py`
- `scripts/query_worldmonitor_import.py`
- `scripts/query_openrecall_raw_import.py`
- `scripts/build_personal_handoff_from_chat_json.py`
- `scripts/migrate_drop_document_json.py`
- `scripts/dbpedia_lookup.py`
- `scripts/dbpedia_lookup_api.py`
- `scripts/inspect_gwb_sqlite.py`
- `src/reporting/openrecall_raw_import.py`
- `src/reporting/worldmonitor_import.py`
- `src/fact_intake/personal_chat_import.py`
- `src/fact_intake/messenger_export_import.py`
- `src/sensiblaw/interfaces/story_importer.py`
- `src/sensiblaw/ingest/story_importer.py`
- `src/ingest/polis.py`
- `src/ingestion/cache.py`
- `src/ingestion/parser.py`
- `src/ingestion/dispatcher.py`
- `src/ingestion/citation_follow.py`
- `src/sources/courtlistener.py`
- `src/sources/uk_legislation.py`
- `src/sources/eur_lex_adapter.py`
- `src/austlii_client.py`

### Ontology, graph, language, and reasoning

- `src/ontology/wikimedia_providers.py`
- `src/ontology/nat.py`
- `src/ontology/tagger.py`
- `src/ontology/enrichment.py`
- `src/ontology/courtlistener.py`
- `src/graph/rgcn.py`
- `src/graph/query.py`
- `src/graph/inference.py`
- `src/language/graph.py`
- `src/reason/timeline.py`
- `src/concepts/loader.py`
- `src/concepts/matcher.py`
- `src/definitions/graph.py`
- `src/distinguish/loader.py`
- `src/distinguish/factor_packs.py`
- `src/reference_identity.py`
- `src/obligation_identity.py`
- `src/au_semantic/linkage.py`
- `src/gwb_us_law/linkage.py`

### Policy, storage, runtime, and models

- `src/policy/gwb_spot_audit.py`
- `src/policy/resolution_store.py`
- `src/policy/domain_invariants.py`
- `src/runtime/progress.py`
- `src/runtime/semantic_parity.py`
- `src/runtime/typing_hierarchy.py`
- `src/storage/core.py`
- `src/storage/manifest_runtime.py`
- `src/storage/postgres_compiler.py`
- `src/schema_utils.py`
- `src/rules/checker.py`
- `src/models/conflict.py`
- `src/models/document.py`
- `src/pipeline/__init__.py`
- `src/review_collection.py`
- `src/sensiblaw/db/dao.py`

### Reporting, publishing, health, and tools

- `src/harm/index.py`
- `src/tools/harm_index.py`
- `src/tools/counter_brief.py`
- `src/publish/mirror.py`
- `src/glossary/service.py`
- `src/reports/research_health.py`
- `ui/app.py`
- `sensiblaw_streamlit/shared.py`

### CLI and operational scripts

- `cli/brief.py`
- `cli/receipts.py`
- `cli/code_observer.py`
- `cli/grounding_depth.py`
- `cli/cohort_e_diagnostics.py`
- `cli/cohort_b_operator_index.py`
- `scripts/au_semantic.py`
- `scripts/gwb_semantic.py`
- `scripts/cli_runtime.py`
- `scripts/eval_goldset.py`
- `scripts/zelph_runner.py`
- `scripts/compile_corpus.py`
- `scripts/conversation_vm.py`
- `scripts/au_fact_review.py`
- `scripts/run_legal_follow.py`
- `scripts/narrative_compare.py`
- `scripts/gwb_us_law_linkage.py`
- `scripts/validate_integrity.py`
- `scripts/transcript_semantic.py`
- `scripts/run_legal_pnf_probe.py`
- `scripts/qg_unification_smoke.py`
- `scripts/wiki_revision_runset.py`
- `scripts/wiki_revision_harness.py`
- `examples/distinguish_glj/demo.py`
- `sl_zelph_demo/sl_extract.py`
- `sl_zelph_demo/lex_to_zelph.py`

## Active legacy definitions overridden at installation

These modules still contain historical JSON helper definitions and therefore
remain explicitly shamed even though the installed execution policy replaces
their physical sinks before document work begins:

- `src/policy/parallel_semantic_execution.py`
- `src/policy/parallel_typing_tail.py`
- `src/policy/progress_observability_execution.py`

They are scheduled for source-level removal after the typed execution tranche is
validated. Runtime override is not permission to add further JSON use.

## Scanner coverage beyond imports

The generated report additionally catches:

- `json.dump`, `json.dumps`, `json.load`, and `json.loads`;
- alternative JSON libraries and adapters;
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

Any authority-critical finding fails CI. Quarantined findings stay visible until
removed; silence is not an accepted state.
