BEGIN;

-- 157: retire migration-045 mention/recurrence derivation from ordinary
-- numeric closure.
--
-- The 045 carrier predates proof-relevant demand occurrence provenance and the
-- parser-entity occurrence bridge. It compiles noun/PROPN/pronoun/entity
-- candidates procedurally on every sentence closure, and recursively derives
-- recurrence groups at every non-sentence closure. Current H9 authority no
-- longer consumes that carrier: migrations 130/133/135 route world-facing work
-- through exact parser entity spans plus producer-authored target occurrence
-- provenance. Recurrence groups have no production consumer outside 045.
--
-- Preserve all historical tables, functions and rows for audit/replay. What is
-- removed is only unconditional automatic execution on closure_state updates.
-- Trigger functions are intentionally retained as historical implementation
-- artefacts; PostgreSQL trigger functions are not ordinary callable repair APIs,
-- so this migration does not manufacture a fake compatibility entrypoint.

DROP TRIGGER IF EXISTS semantic_pnf_sentence_mention_derivation
    ON execution.semantic_pnf_region;
DROP TRIGGER IF EXISTS semantic_pnf_region_recurrence_derivation
    ON execution.semantic_pnf_region;

COMMENT ON FUNCTION execution.derive_numeric_sentence_mentions() IS
'Historical migration-045 trigger implementation retained for audit/schema compatibility. Automatic strict numeric execution retired by migration 157.';
COMMENT ON FUNCTION execution.derive_numeric_region_recurrence() IS
'Historical migration-045 recurrence trigger implementation retained for audit/schema compatibility. Automatic strict numeric execution retired by migration 157.';

COMMIT;
