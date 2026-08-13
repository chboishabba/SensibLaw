BEGIN;

-- Durable nested execution authority shared by parser, typing, closure and
-- finalisation. A worker result is not complete until its immutable artifact,
-- receipt, cursor and outbox event commit in the same transaction.
CREATE TABLE IF NOT EXISTS execution.semantic_stage_instance (
    stage_instance_ref TEXT PRIMARY KEY,
    run_ref TEXT NOT NULL REFERENCES execution.semantic_run(run_ref) ON DELETE CASCADE,
    document_ref TEXT NOT NULL,
    stage_contract_ref TEXT NOT NULL,
    operation_ref TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'running'
        CHECK (state IN ('running', 'completed', 'completed_with_failures', 'failed')),
    input_manifest_sha256 BYTEA NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (run_ref, document_ref, stage_contract_ref, operation_ref, input_manifest_sha256)
);

CREATE TABLE IF NOT EXISTS execution.semantic_work_item (
    work_ref TEXT PRIMARY KEY,
    stage_instance_ref TEXT NOT NULL
        REFERENCES execution.semantic_stage_instance(stage_instance_ref) ON DELETE CASCADE,
    run_ref TEXT NOT NULL REFERENCES execution.semantic_run(run_ref) ON DELETE CASCADE,
    document_ref TEXT NOT NULL,
    stage_contract_ref TEXT NOT NULL,
    operation_ref TEXT NOT NULL,
    partition_ref TEXT NOT NULL,
    ordinal BIGINT NOT NULL CHECK (ordinal >= 0),
    input_manifest JSONB NOT NULL,
    input_sha256 BYTEA NOT NULL,
    state TEXT NOT NULL DEFAULT 'ready'
        CHECK (state IN ('blocked', 'ready', 'leased', 'completed', 'retryable', 'failed')),
    lease_owner TEXT,
    lease_token TEXT,
    lease_epoch BIGINT NOT NULL DEFAULT 0 CHECK (lease_epoch >= 0),
    lease_expires_at TIMESTAMPTZ,
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    output_artifact_ref TEXT,
    output_sha256 BYTEA,
    completed_at TIMESTAMPTZ,
    last_error JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (run_ref, document_ref, stage_contract_ref, operation_ref, partition_ref, input_sha256)
);

CREATE INDEX IF NOT EXISTS semantic_work_item_ready_idx
    ON execution.semantic_work_item
       (run_ref, state, lease_expires_at, stage_contract_ref, operation_ref, ordinal);

CREATE TABLE IF NOT EXISTS execution.semantic_work_dependency (
    work_ref TEXT NOT NULL REFERENCES execution.semantic_work_item(work_ref) ON DELETE CASCADE,
    dependency_work_ref TEXT NOT NULL REFERENCES execution.semantic_work_item(work_ref) ON DELETE RESTRICT,
    PRIMARY KEY (work_ref, dependency_work_ref),
    CHECK (work_ref <> dependency_work_ref)
);

CREATE TABLE IF NOT EXISTS execution.semantic_work_attempt_v2 (
    attempt_ref TEXT PRIMARY KEY,
    work_ref TEXT NOT NULL REFERENCES execution.semantic_work_item(work_ref) ON DELETE RESTRICT,
    worker_ref TEXT NOT NULL,
    worker_pid BIGINT,
    backend_pid INTEGER,
    lease_token TEXT NOT NULL,
    lease_epoch BIGINT NOT NULL CHECK (lease_epoch > 0),
    state TEXT NOT NULL CHECK (state IN ('leased', 'completed', 'stale', 'failed')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,
    error JSONB
);

CREATE TABLE IF NOT EXISTS execution.semantic_artifact_segment (
    artifact_ref TEXT PRIMARY KEY,
    run_ref TEXT NOT NULL REFERENCES execution.semantic_run(run_ref) ON DELETE CASCADE,
    document_ref TEXT NOT NULL,
    stage_contract_ref TEXT NOT NULL,
    operation_ref TEXT NOT NULL,
    work_ref TEXT NOT NULL REFERENCES execution.semantic_work_item(work_ref) ON DELETE RESTRICT,
    content_sha256 BYTEA NOT NULL,
    byte_count BIGINT NOT NULL CHECK (byte_count >= 0),
    media_type TEXT NOT NULL,
    encoding_ref TEXT NOT NULL,
    locator TEXT NOT NULL,
    sealed BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (work_ref, content_sha256)
);

CREATE TABLE IF NOT EXISTS execution.semantic_stage_cursor (
    stage_instance_ref TEXT PRIMARY KEY
        REFERENCES execution.semantic_stage_instance(stage_instance_ref) ON DELETE CASCADE,
    run_ref TEXT NOT NULL REFERENCES execution.semantic_run(run_ref) ON DELETE CASCADE,
    document_ref TEXT NOT NULL,
    stage_contract_ref TEXT NOT NULL,
    operation_ref TEXT NOT NULL,
    committed_ordinal BIGINT NOT NULL DEFAULT -1 CHECK (committed_ordinal >= -1),
    completed_work_count BIGINT NOT NULL DEFAULT 0 CHECK (completed_work_count >= 0),
    cursor_manifest JSONB NOT NULL DEFAULT '{}'::jsonb,
    cursor_sha256 BYTEA NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS execution.semantic_stage_manifest (
    manifest_ref TEXT PRIMARY KEY,
    stage_instance_ref TEXT NOT NULL
        REFERENCES execution.semantic_stage_instance(stage_instance_ref) ON DELETE CASCADE,
    run_ref TEXT NOT NULL REFERENCES execution.semantic_run(run_ref) ON DELETE CASCADE,
    document_ref TEXT NOT NULL,
    child_work_refs JSONB NOT NULL,
    manifest_sha256 BYTEA NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('staged', 'committed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    committed_at TIMESTAMPTZ,
    UNIQUE (stage_instance_ref, manifest_sha256)
);

CREATE TABLE IF NOT EXISTS execution.semantic_work_receipt (
    receipt_ref TEXT PRIMARY KEY,
    work_ref TEXT NOT NULL REFERENCES execution.semantic_work_item(work_ref) ON DELETE RESTRICT,
    run_ref TEXT NOT NULL REFERENCES execution.semantic_run(run_ref) ON DELETE CASCADE,
    payload JSONB NOT NULL,
    payload_sha256 BYTEA NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (work_ref)
);

CREATE TABLE IF NOT EXISTS execution.semantic_coordinator_lease (
    run_ref TEXT PRIMARY KEY REFERENCES execution.semantic_run(run_ref) ON DELETE CASCADE,
    coordinator_ref TEXT NOT NULL,
    lease_token TEXT NOT NULL,
    lease_epoch BIGINT NOT NULL DEFAULT 1 CHECK (lease_epoch > 0),
    lease_expires_at TIMESTAMPTZ NOT NULL,
    heartbeat_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    backend_pid INTEGER,
    acquired_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE OR REPLACE FUNCTION execution.emit_strict_delta_admitted()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    event_ref_value text;
    job_ref_value text;
BEGIN
    SELECT delta.job_ref
      INTO job_ref_value
      FROM execution.semantic_immutable_delta delta
     WHERE delta.delta_ref = NEW.delta_ref;
    event_ref_value := 'semantic-outbox:delta-admitted:' || NEW.delta_ref;
    INSERT INTO execution.semantic_outbox
        (event_ref, aggregate_ref, event_type_ref, payload)
    VALUES (
        event_ref_value,
        NEW.owner_ref,
        'semantic.delta.admitted.v1',
        jsonb_build_object(
            'delta_ref', NEW.delta_ref,
            'run_ref', NEW.run_ref,
            'job_ref', job_ref_value,
            'owner_ref', NEW.owner_ref,
            'lease_epoch', NEW.lease_epoch,
            'prior_owner_revision', NEW.prior_revision,
            'resulting_owner_revision', NEW.resulting_revision
        )
    )
    ON CONFLICT (event_ref) DO NOTHING;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS semantic_strict_delta_admission_outbox
ON execution.semantic_strict_delta_admission;
CREATE TRIGGER semantic_strict_delta_admission_outbox
AFTER INSERT ON execution.semantic_strict_delta_admission
FOR EACH ROW
EXECUTE FUNCTION execution.emit_strict_delta_admitted();

CREATE OR REPLACE FUNCTION execution.emit_work_item_completed()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    event_ref_value text;
BEGIN
    IF NEW.state <> 'completed' OR OLD.state = 'completed' THEN
        RETURN NEW;
    END IF;
    event_ref_value := 'semantic-outbox:work-completed:' || NEW.work_ref;
    INSERT INTO execution.semantic_outbox
        (event_ref, aggregate_ref, event_type_ref, payload)
    VALUES (
        event_ref_value,
        NEW.stage_instance_ref,
        'semantic.work-item.completed.v1',
        jsonb_build_object(
            'work_ref', NEW.work_ref,
            'run_ref', NEW.run_ref,
            'document_ref', NEW.document_ref,
            'stage_contract_ref', NEW.stage_contract_ref,
            'operation_ref', NEW.operation_ref,
            'partition_ref', NEW.partition_ref,
            'ordinal', NEW.ordinal,
            'output_artifact_ref', NEW.output_artifact_ref,
            'lease_epoch', NEW.lease_epoch
        )
    )
    ON CONFLICT (event_ref) DO NOTHING;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS semantic_work_item_completed_outbox
ON execution.semantic_work_item;
CREATE TRIGGER semantic_work_item_completed_outbox
AFTER UPDATE OF state ON execution.semantic_work_item
FOR EACH ROW
EXECUTE FUNCTION execution.emit_work_item_completed();

COMMIT;
