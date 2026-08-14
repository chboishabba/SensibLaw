# Self-hosted PostgreSQL authority

Self-hosted PostgreSQL validation runs on the `cachy-lambo` runner and uses
the TrueNAS PostgreSQL application rather than a PostgreSQL server bound to
the runner's loopback interface.

The repository secret `SENSIBLAW_CI_ADMIN_DATABASE_URL` contains an admin
connection URL for the TrueNAS maintenance database. Workflows pass that URL
to `provision_local_postgres`, which creates a uniquely named database for the
run, applies the migration chain, and reports the disposable database URL to
later steps. The shared benchmark database is not used by CI.

The secret must not be committed to the repository. If the TrueNAS address,
port, or password changes, rotate the repository secret rather than editing
workflow files.

The exact-0008 reference workflow is intentionally separate: it consumes a
pre-seeded tranche database and is not a disposable migration smoke test. It
must be migrated independently before being pointed at a new host.
