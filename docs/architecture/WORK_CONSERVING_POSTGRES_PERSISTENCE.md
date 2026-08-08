# Work-Conserving PostgreSQL Persistence

## Problem confirmed by the GWB run

The ordered parser-lookahead run established that document 0007 could be parsed
in roughly tens of seconds while the legacy `postgres_persistence` stage could
remain active for hours. The critical path was therefore not spaCy or semantic
closure; it was Python-driven relational amplification:

```text
semantic row
→ Python loop
→ cursor.execute
→ PostgreSQL round trip
→ repeat tens of thousands of times
```

The execution target is now:

```text
whichever kernel owns the critical path receives the full worker budget
```

while preserving one ordered semantic publication frontier.

## Authority boundary

Document compilation remains an ordered world fold:

```text
W0 --D1--> W1 --D2--> W2 ... --Dn--> Wn
```

Only one document may publish at a time. Work-conserving persistence does not
weaken that rule. It separates physical preparation from semantic authority:

```text
closed document artifacts
        │
        ▼
parallel typed provisional COPY lanes       no publication authority
        │
        ▼
fixed set-based INSERT ... SELECT merges     existing document savepoint
        │
        ▼
parent/closure validation
        │
        ▼
completed build + corpus occurrence          one ordered publication
```

A staged row cannot extend the world. Only the existing completed-build and
occurrence publication at the end of the canonical document savepoint can do
so.

## Dynamic worker ownership

The ordered runner initially divides the global application budget between the
foreground semantic lane and one parser-only lookahead process. With a four
worker budget and two parser workers:

```text
semantic/closure foreground: 2
parser lookahead:             2
```

At the exact document persistence savepoint, the foreground quiesces the active
lookahead. A completed speculative parse remains parser evidence only; failure
falls back to the ordinary foreground parser. The complete budget is then
transferred to persistence:

```text
PostgreSQL persistence lanes: 4
parser lookahead:              0
```

After the document transaction finishes or fails, the budget is returned and
the next heavy parser candidate may start. The scheduler is therefore
work-conserving without permitting concurrent semantic publication.

## Typed provisional carrier

Migration 061 introduces three execution relations:

- `execution.document_persistence_stage`: an unlogged, typed, generic carrier;
- `execution.document_persistence_run`: one scalar receipt per family/call;
- `execution.document_persistence_lane`: per-backend COPY telemetry.

Rows are keyed by deterministic stage, document, build, family, partition and
ordinal coordinates. The carrier contains scalar text, integer and bytea
fields only. It contains no JSON or JSONB and is not semantic authority.

A failed authority merge rolls back normalized writes while leaving provisional
rows and scalar receipts available for diagnosis. The next deterministic retry
clears and replaces that stage before copying it again.

## Parallel lanes

Each high-volume family is encoded into typed rows and partitioned modulo the
available worker budget. Separate PostgreSQL connections use `COPY` concurrently
into disjoint stage partitions. Current lanes cover:

- licensed spans;
- token lexemes, codec symbols and token-stream chunks;
- annotation nodes and relations;
- factors, immutable revisions, alternatives and residuals;
- evidence, demands, facets, typed meets and refinements;
- factor anchors, morphology, candidate sets, assessments, members and links.

The staged rows are then merged with a fixed number of set operations per
family. The intended round-trip relationship is:

```text
Q_SQL = O(F)
```

for a small number of relational families, rather than:

```text
Q_SQL = O(R_semantic_rows)
```

The existing per-refinement `persist_factor_revision` call is rebound to an
identity-only operation. Full resulting-factor rows, including alternatives and
residuals, are persisted in the resolution family set merge.

## Transaction and visibility requirements

Parallel stage backends commit provisional rows before the authority connection
reads them. The authority savepoint therefore requires PostgreSQL
`READ COMMITTED` isolation. The runtime fails closed under a different
isolation level rather than silently missing freshly staged rows.

The authority connection sets `max_parallel_workers_per_gather` to the global
worker budget for eligible PostgreSQL plans. Multiple COPY backends provide
reliable physical concurrency even when an individual `INSERT ... SELECT` plan
cannot use every PostgreSQL parallel worker.

## Receipts and observability

`execution.document_persistence_run` records:

- stage/document/build/family identity;
- configured worker budget and actual lane count;
- staged row count;
- fixed authority statement count;
- staging and publication timestamps;
- failure type/message.

`execution.document_persistence_lane` records:

- PostgreSQL backend PID and client worker PID;
- partition, row and byte counts;
- wall time and client user/system CPU time;
- sampled backend wait-event type and event.

Each lane publishes its backend PID with state `staging` before `COPY` begins,
then transitions to `staged` or `failed`. This makes live CPU and wait-state
inspection possible while the expensive operation is still running rather than
only after it finishes.

These rows make it possible to distinguish CPU work from client, lock, WAL or
storage waits without turning an execution receipt into semantic authority.

## Entry point

Migration 061 must be applied before the new ordered runner starts. The command
is unchanged:

```bash
uv run python scripts/run_complete_tranche_ordered.py \
  --tranche GWB \
  --database-url "$DATABASE_URL" \
  --output-root .tmp/gwb-ordered \
  --document-workers 1 \
  --parser-workers 2 \
  --closure-workers 4 \
  --worker-budget 4 \
  --strict-exact
```

`--document-workers 1` remains mandatory. Increase `--worker-budget` to the
number of application workers the machine should make available to the active
critical kernel. PostgreSQL server-side parallel-worker, memory and WAL settings
remain independent resource limits and should be measured rather than assumed.

In another terminal, the live watcher shows every active PostgreSQL lane,
backend PID, local backend CPU percentage, row/byte target, and PostgreSQL wait
state:

```bash
uv run python scripts/watch_work_conserving_persistence.py \
  --database-url "$DATABASE_URL" \
  --interval 1
```

On Linux with PostgreSQL running on the same host, aggregate backend CPU is read
from `/proc/<backend-pid>/stat`. For remote PostgreSQL servers the PID and wait
state remain available, while local CPU is reported as unavailable.

## Acceptance

The first controlled acceptance document is 0007. Compare the same immutable
source/build under the legacy and work-conserving paths.

Required invariants:

- identical operational build key, graph identity and sorted demand refs;
- one completed build and one corpus occurrence;
- no staged row is visible as a completed semantic document;
- parser lookahead never publishes;
- failed staging or merge cannot leave partial authority rows committed;
- migration and active authority surfaces contain no JSON/JSONB.

Required measurements:

```text
T_parse
T_postparse
T_persist
T_total
rows staged per family
COPY rows/bytes/second per lane
fixed SQL statement count per family
backend PIDs and wait events
CPU utilisation over the persistence interval
```

Initial performance gate:

```text
legacy 0007 postgres_persistence: > 2.5 hours observed
first work-conserving target:       < 10 minutes
strong target:                     < 2–5 minutes
```

No speedup or CPU-saturation claim is valid until the same 0007 build has been
run and its receipts inspected.
