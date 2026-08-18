BEGIN;

-- The work-conserving staging carrier is addressed by deterministic stage_ref.
-- Live replay instrumentation observed zero scans of the historical
-- (document_ref, build_key_sha256) index while the stage/kind index served the
-- authority publication path. Maintaining this secondary B-tree therefore adds
-- one index insertion/update for every provisional row without serving the hot
-- execution contract.
--
-- This table is UNLOGGED execution state and never semantic authority. Retry and
-- cleanup continue to address deterministic stage_ref values and the run ledger.
DROP INDEX IF EXISTS execution.document_persistence_stage_document_idx;

COMMIT;
