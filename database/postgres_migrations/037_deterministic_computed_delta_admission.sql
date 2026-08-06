BEGIN;

-- Workers may complete semantic computation concurrently.  They persist a
-- typed immutable delta before acknowledgement, but owner revisions are
-- allocated later by the coordinator in canonical (priority, job_ref) order.
-- This separates computation completion from deterministic admission without
-- serializing the result or recomputing it after an owner revision advances.

ALTER TABLE execution.semantic_closure_job
    DROP CONSTRAINT IF EXISTS semantic_closure_job_state_check;
ALTER TABLE execution.semantic_closure_job
    ADD CONSTRAINT semantic_closure_job_state_check
    CHECK (state IN ('open', 'leased', 'computed', 'completed', 'failed'));

ALTER TABLE execution.semantic_strict_job_attempt
    DROP CONSTRAINT IF EXISTS semantic_strict_job_attempt_state_check;
ALTER TABLE execution.semantic_strict_job_attempt
    ADD CONSTRAINT semantic_strict_job_attempt_state_check
    CHECK (state IN ('leased', 'computed', 'completed', 'stale', 'failed'));

ALTER TABLE execution.semantic_immutable_delta
    ALTER COLUMN resulting_revision DROP NOT NULL,
    ALTER COLUMN prior_revision DROP NOT NULL,
    ADD COLUMN IF NOT EXISTS computed_at TIMESTAMPTZ
        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ADD COLUMN IF NOT EXISTS admitted_at TIMESTAMPTZ;

ALTER TABLE execution.semantic_immutable_delta
    DROP CONSTRAINT IF EXISTS semantic_immutable_delta_resulting_revision_check;
ALTER TABLE execution.semantic_immutable_delta
    ADD CONSTRAINT semantic_immutable_delta_resulting_revision_check
    CHECK (resulting_revision IS NULL OR resulting_revision > 0);

ALTER TABLE execution.semantic_immutable_delta
    DROP CONSTRAINT IF EXISTS semantic_immutable_delta_prior_revision_check;
ALTER TABLE execution.semantic_immutable_delta
    ADD CONSTRAINT semantic_immutable_delta_prior_revision_check
    CHECK (prior_revision IS NULL OR prior_revision >= 0);

CREATE UNIQUE INDEX IF NOT EXISTS semantic_immutable_delta_one_per_job_idx
    ON execution.semantic_immutable_delta (run_ref, job_ref);

CREATE INDEX IF NOT EXISTS semantic_computed_delta_admission_idx
    ON execution.semantic_closure_job (run_ref, state, priority, job_ref)
    WHERE state = 'computed';

COMMIT;
