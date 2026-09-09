# OALC / LegalFollow PostgreSQL source persistence

Migration `181_oalc_external_source_revision_persistence.sql` makes the existing
SensibLaw PostgreSQL substrate the durable persistence owner for governed OALC
source resolution.

The operational chain is:

```text
LegalFollow demand
  -> governed OALC resolver
  -> corpus.document / corpus.canonical_content
  -> corpus.external_source_revision
  -> evidence.external_source_resolution
  -> corpus.span / corpus.external_source_slice
  -> spaCy annotation
  -> Rust PNF
```

No OALC-specific table duplicates canonical text, parser annotations, or PNF
state.  `corpus.external_source_revision` is an identity/provenance attachment
to `corpus.document`.

## Database configuration

Normal runtime configuration uses `DATABASE_URL`, consistent with the existing
PostgreSQL runtime.  Runtime adapters may load it from a local `.env` file for
operator convenience, with this precedence:

1. an already-set process `DATABASE_URL`;
2. an explicitly selected env file (for example `--env-file /path/to/.env`);
3. repository/local working-directory `.env`;
4. otherwise fail with a configuration residual.

Env-file loading must **not overwrite** an already-set process variable.  Tests
and CI should normally provide `DATABASE_URL` explicitly.

`.env` files are operator-local configuration and must not be treated as source,
legal evidence, semantic state, or provenance.  Secrets must never be committed.
Only non-secret examples belong in `.env.example`.

Recommended local entry:

```dotenv
# Example only; adapt host, port, database and authentication locally.
DATABASE_URL=postgresql://postgres@localhost:5433/sensiblaw_tranche
```

The SLR runtime leaf should expose both default `.env` discovery and an explicit
env-file override while preserving the precedence above.

## Temporal boundary

An OALC document persisted with `temporal_coverage_ref = 'latest_known_only'` is
parser-admissible but does not establish that its text was in force on a prior
requested date. PostgreSQL retention cannot promote that status.

## Failure boundary

Provider, network, shard, PostgreSQL, migration, or configuration failure is an
operational/source residual. It is never negative legal evidence and must not
close the LegalFollow frontier by itself.
