# Retired local PostgreSQL failure record — 2026-08-18

This records the terminal diagnostic evidence from the retired disposable
cluster at `/tmp/sensiblaw-pr485-pg.wB1DN7`. The source log was retained long
enough to extract this record before that failed, quota-bound data directory was
removed.

The failure was storage capacity, not a semantic compiler receipt:

1. PostgreSQL could not extend a relation while inserting into
   `execution.semantic_parser_token`: `Disk quota exceeded`.
2. Autovacuum then panicked because it could not write
   `pg_wal/xlogtemp.3367`, also due to quota exhaustion.
3. PostgreSQL terminated active processes; recovery then failed when it could
   not extend a relation during WAL redo, and the server shut down.

The local cluster must not be restarted or used for comparison runs. The
replacement runtime is the migration-145 TrueNAS target defined in
[`../postgres_runtime.md`](../postgres_runtime.md). The raw exact-0008 EPUB
under the repository remains read-only; this note is the useful retained crash
evidence rather than a copy of a failed database data directory.
