PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

ALTER TABLE concept_external_refs ADD COLUMN confidence REAL;
ALTER TABLE actor_external_refs ADD COLUMN confidence REAL;

COMMIT;
