BEGIN;

ALTER TABLE execution.semantic_stage_manifest
    ADD COLUMN IF NOT EXISTS logical_output_ref TEXT,
    ADD COLUMN IF NOT EXISTS descendant_payload_bytes_reconstructed BIGINT
        NOT NULL DEFAULT 0;

ALTER TABLE execution.semantic_stage_instance
    ADD COLUMN IF NOT EXISTS last_error_reason TEXT,
    ADD COLUMN IF NOT EXISTS completed_work_count BIGINT,
    ADD COLUMN IF NOT EXISTS incomplete_work_count BIGINT;

COMMIT;
