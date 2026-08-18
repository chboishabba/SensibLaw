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
-- Preserve all historical tables, functions and rows for audit/replay. Also
-- preserve explicit callable repair functions. What is removed is only the
-- unconditional automatic execution on closure_state updates. A compatibility
-- or migration tool that deliberately needs the historical projection can call
-- derive_numeric_sentence_mentions_compat / derive_numeric_region_recurrence_compat
-- below for selected already-closed regions.

DROP TRIGGER IF EXISTS semantic_pnf_sentence_mention_derivation
    ON execution.semantic_pnf_region;
DROP TRIGGER IF EXISTS semantic_pnf_region_recurrence_derivation
    ON execution.semantic_pnf_region;

-- Explicit compatibility adapters. They re-use the old trigger functions rather
-- than inventing a second implementation. The synthetic OLD row keeps the old
-- closure-transition guard meaningful while making the caller's intent explicit.
CREATE OR REPLACE FUNCTION execution.derive_numeric_sentence_mentions_compat(
    selected_region_id BIGINT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    selected_region execution.semantic_pnf_region%ROWTYPE;
    prior_region execution.semantic_pnf_region%ROWTYPE;
BEGIN
    SELECT * INTO selected_region
      FROM execution.semantic_pnf_region
     WHERE region_id = selected_region_id;
    IF selected_region.region_id IS NULL
       OR selected_region.region_kind <> 1
       OR selected_region.closure_state NOT IN (2, 3) THEN
        RETURN 0;
    END IF;

    prior_region := selected_region;
    prior_region.closure_state := 1;
    PERFORM execution.derive_numeric_sentence_mentions(
        ROW(prior_region.*), ROW(selected_region.*)
    );
    RETURN 1;
END;
$$;

CREATE OR REPLACE FUNCTION execution.derive_numeric_region_recurrence_compat(
    selected_region_id BIGINT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    selected_region execution.semantic_pnf_region%ROWTYPE;
    prior_region execution.semantic_pnf_region%ROWTYPE;
BEGIN
    SELECT * INTO selected_region
      FROM execution.semantic_pnf_region
     WHERE region_id = selected_region_id;
    IF selected_region.region_id IS NULL
       OR selected_region.region_kind = 1
       OR selected_region.closure_state NOT IN (2, 3) THEN
        RETURN 0;
    END IF;

    prior_region := selected_region;
    prior_region.closure_state := 1;
    PERFORM execution.derive_numeric_region_recurrence(
        ROW(prior_region.*), ROW(selected_region.*)
    );
    RETURN 1;
END;
$$;

COMMENT ON FUNCTION execution.derive_numeric_sentence_mentions_compat(BIGINT) IS
'Explicit historical migration-045 projection. Not part of strict numeric production authority.';
COMMENT ON FUNCTION execution.derive_numeric_region_recurrence_compat(BIGINT) IS
'Explicit historical migration-045 recurrence projection. Not part of strict numeric production authority.';

COMMIT;
