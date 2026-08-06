# No-JSON Execution Authority

## Rule

PostgreSQL is the typed execution state machine. JSON and JSONB are forbidden as:

- semantic state;
- execution transport;
- identity substrate;
- checkpoint or resume authority;
- lease, attempt, cursor, receipt, lifecycle, outbox, or publication authority.

The compiler may use ordinary Python domain objects and mappings within one
process. Crossing a durable boundary requires either typed relational rows or a
content-addressed binary artifact registered by typed database columns.

## Canonical identity

Semantic identities use `itir.typed-canonical.v1`: a length-prefixed typed byte
language with explicit tags for null, booleans, integers, floats, text, bytes,
sequences, and mappings. Mutable execution context such as owner revision,
lease epoch, fence token, or retry ordinal is not part of stable job identity.

## PostgreSQL representation

Stable semantic job input is normalized across typed columns and child relations.
Mutable scheduling state remains narrow:

```text
job identity            immutable
expected owner revision mutable scheduling state
lease epoch             attempt state
fence token             attempt state
resulting revision      admission state
```

Reawakening a stale job updates only scheduling columns. It must not load,
rewrite, serialize, or re-hash stable semantic input.

## Binary artifacts

Large bounded local handoffs use content-addressed binary artifacts. Their raw
bytes are hashed before decode, and their semantic value is separately checked
against typed canonical identity. Binary artifacts do not replace PostgreSQL
authority: PostgreSQL records their digest, byte count, encoding contract,
producer work item, and completion state.

## Legacy columns

Historical JSON/JSONB columns remain nullable solely so already-migrated
databases can be upgraded. New execution writes must leave them `NULL`.
Database triggers reject attempts to restore blob authority.

## Sin bin

Run:

```bash
uv run python scripts/audit_json_sin_bin.py \
  --write docs/architecture/JSON_SIN_BIN.md \
  --check-authority
```

The generated report names every JSON touchpoint with file, line, category,
symbol, and evidence. Authority-critical findings fail CI. Boundary/import/export
and legacy definitions remain visible as quarantined debt until removed; they
are not an implicit allow-list.

## Acceptance

A strict-execution change is not accepted unless all of the following hold:

1. authority scan reports zero violations;
2. execution migrations apply to a fresh PostgreSQL database;
3. deprecated execution blob columns remain `NULL`;
4. typed v2 outbox events are emitted transactionally;
5. stable job input digest does not change with owner revision;
6. coordinator death resumes with zero recomputation of committed work;
7. no worker survives a dead local coordinator;
8. a frontier profile contains no JSON encoder/decoder or JSONB manifest path.
