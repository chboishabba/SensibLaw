# Ordered World Parser Lookahead

## Contract

Document compilation is an ordered world fold:

```text
W0 --compile D1--> W1 --compile D2--> W2 ... --compile Dn--> Wn
```

Exactly one document may cross the semantic publication frontier at a time. A later document is compiled against the world produced by all earlier committed documents.

The physical parser lane may run ahead because parser observations are immutable, document-local evidence. Parser lookahead never performs:

- mention licensing;
- semantic promotion;
- world-relative entity resolution;
- PNF closure;
- demand discharge;
- canonical factor/object publication;
- document occurrence publication; or
- world extension.

## Execution shape

```text
ordered semantic lane:
    compile D1 against W0 -> commit W1
    compile D2 against W1 -> commit W2
    compile D3 against W2 -> commit W3

bounded parser lane:
    pre-parse one partition-worthy future document
    persist document-scoped parser-fibre checkpoints
    wait until the semantic frontier consumes that document
    then pre-parse the next heavy document
```

The scheduler is deliberately size-skew aware. It selects documents that cross the adaptive parser-fibre threshold rather than assigning equal document counts to workers. A 2 MB document can therefore begin parsing while preceding 50 KB documents complete semantic closure and publication.

## Global worker budget

The parser lane and foreground lane share one hard budget:

```text
foreground_worker_budget + parser_lookahead_workers <= worker_budget
```

Parser checkpoint identity currently includes the parser-fibre worker count. Lookahead is enabled only when the budget can reserve the requested `parser_workers` for both lanes without changing that identity:

```text
worker_budget >= 2 * parser_workers
```

Otherwise execution remains semantically ordered and parsing occurs inline.

Examples:

```text
worker_budget=4, parser_workers=2
    parser lookahead: 2 workers
    foreground:       2 workers

worker_budget=4, parser_workers=1
    parser lookahead: 1 worker
    foreground:       3 workers

worker_budget=3, parser_workers=2
    lookahead disabled; foreground retains all 3 workers
```

## Duplicate-work fence

The foreground parser binding is temporarily wrapped during ordered compilation. If the semantic frontier reaches a document whose prefetch is still active, foreground execution waits for that prefetch. It then invokes the normal parser-fibre path, which validates and reuses the completed checkpoints.

This prevents two spaCy executions from racing over the same future document while keeping `compile_document_operational` as the sole semantic compiler.

## Durability

Parser lookahead writes only the existing document-scoped parser-fibre checkpoints:

```text
<compilation-state-stem>_chunks/<document-id>/
```

It also writes an execution receipt beside the compilation state:

```text
<compilation-state-stem>_parser_lookahead.json
```

That receipt is execution metadata, not semantic authority. It records:

- the ordered-world contract;
- worker-budget allocation;
- selected heavy documents;
- active and completed prefetches;
- parser elapsed time; and
- checkpoint directories.

## Entry point

Use the ordered runner with the existing complete-tranche arguments:

```bash
uv run python scripts/run_complete_tranche_ordered.py \
  --tranche GWB \
  --database-url "$DATABASE_URL" \
  --output-root .tmp/gwb-ordered \
  --document-workers 1 \
  --parser-workers 2 \
  --closure-workers 4 \
  --worker-budget 4
```

`document_workers > 1` is rejected by this entry point. Parallelism remains available inside parser fibres and document-local closure, while semantic publication remains ordered.

Set `SENSIBLAW_ORDERED_WORLD_LOOKAHEAD=0` to disable parser lookahead while retaining the same ordered foreground compiler.

## Performance target

The intended performance relation is:

```text
post-spaCy document work <= spaCy parsing work
```

With overlap, tranche wall time should approach:

```text
sum(ordered semantic closure and publication)
+ parser time not hidden behind earlier documents
```

The lookahead receipt and existing stage timing ledger provide the measurements needed to test that target without weakening the semantic order of the world fold.
