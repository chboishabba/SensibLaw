BEGIN;

-- JSON/JSONB is forbidden as execution authority.  Existing blob columns are
-- retained only so previously migrated databases remain readable while their
-- historical rows are retired.  New strict execution writes only the typed
-- columns and relations introduced below.

ALTER TABLE execution.semantic_run
    ADD COLUMN IF NOT EXISTS fixed_point_state TEXT,
    ADD COLUMN IF NOT EXISTS fixed_point_round_count INTEGER,
    ADD COLUMN IF NOT EXISTS fixed_point_zero_change_round INTEGER,
    ADD COLUMN IF NOT EXISTS fixed_point_owner_revision BIGINT,
    ADD COLUMN IF NOT EXISTS fixed_point_sha256 BYTEA;

ALTER TABLE execution.semantic_closure_job
    ALTER COLUMN input_manifest DROP NOT NULL,
    ADD COLUMN IF NOT EXISTS declaration_ref TEXT,
    ADD COLUMN IF NOT EXISTS rule_set_revision TEXT,
    ADD COLUMN IF NOT EXISTS scope_ref TEXT,
    ADD COLUMN IF NOT EXISTS factor_family TEXT,
    ADD COLUMN IF NOT EXISTS stable_input_ref TEXT,
    ADD COLUMN IF NOT EXISTS priority INTEGER NOT NULL DEFAULT 100,
    ADD COLUMN IF NOT EXISTS operation_kind TEXT NOT NULL DEFAULT 'streaming_operator';

CREATE TABLE IF NOT EXISTS execution.semantic_job_input_ref (
    job_ref TEXT NOT NULL REFERENCES execution.semantic_closure_job(job_ref) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    input_ref TEXT NOT NULL,
    PRIMARY KEY (job_ref, ordinal),
    UNIQUE (job_ref, input_ref)
);

CREATE TABLE IF NOT EXISTS execution.semantic_job_coverage_requirement (
    job_ref TEXT NOT NULL REFERENCES execution.semantic_closure_job(job_ref) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    requirement_ref TEXT NOT NULL,
    PRIMARY KEY (job_ref, ordinal),
    UNIQUE (job_ref, requirement_ref)
);

CREATE TABLE IF NOT EXISTS execution.semantic_job_assumption (
    job_ref TEXT NOT NULL REFERENCES execution.semantic_closure_job(job_ref) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    assumption_ref TEXT NOT NULL,
    PRIMARY KEY (job_ref, ordinal),
    UNIQUE (job_ref, assumption_ref)
);

CREATE TABLE IF NOT EXISTS execution.semantic_streaming_operator_job_input (
    job_ref TEXT PRIMARY KEY REFERENCES execution.semantic_closure_job(job_ref) ON DELETE CASCADE,
    observation_delta_ref TEXT NOT NULL,
    batch_ref TEXT NOT NULL,
    scope_ref TEXT NOT NULL,
    sequence_no BIGINT NOT NULL CHECK (sequence_no >= 0),
    parser_contract TEXT NOT NULL,
    token_start BIGINT NOT NULL CHECK (token_start >= 0),
    token_end BIGINT NOT NULL CHECK (token_end >= token_start),
    char_start BIGINT NOT NULL CHECK (char_start >= 0),
    char_end BIGINT NOT NULL CHECK (char_end >= char_start),
    token_count BIGINT NOT NULL CHECK (token_count >= 0),
    coverage_barrier TEXT NOT NULL,
    coverage_complete BOOLEAN NOT NULL,
    structural_carrier_ref TEXT
);

CREATE TABLE IF NOT EXISTS execution.semantic_streaming_operator_token (
    job_ref TEXT NOT NULL REFERENCES execution.semantic_closure_job(job_ref) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    observation_ref TEXT NOT NULL,
    semantic_coordinate_ref TEXT,
    observation_type TEXT NOT NULL,
    fibre_kind TEXT NOT NULL,
    sentence_index BIGINT NOT NULL CHECK (sentence_index >= 0),
    authority_ref TEXT,
    token_index BIGINT NOT NULL,
    token_text TEXT NOT NULL,
    lemma TEXT,
    pos_ref TEXT,
    tag_ref TEXT,
    dependency_ref TEXT,
    head_index BIGINT,
    start_char BIGINT NOT NULL CHECK (start_char >= 0),
    end_char BIGINT NOT NULL CHECK (end_char >= start_char),
    entity_type_ref TEXT,
    whitespace_text TEXT,
    PRIMARY KEY (job_ref, ordinal),
    UNIQUE (job_ref, observation_ref)
);

-- Typed relational value trees are used only for genuinely open semantic
-- mappings such as qualifier state and candidate payload.  They are rows, not
-- serialized blobs, and each scalar is represented by a typed column.
CREATE TABLE IF NOT EXISTS execution.semantic_typed_value_root (
    root_ref TEXT PRIMARY KEY,
    contract_ref TEXT NOT NULL,
    root_kind TEXT NOT NULL CHECK (root_kind IN ('mapping', 'sequence', 'scalar', 'null')),
    root_sha256 BYTEA NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS execution.semantic_typed_value_node (
    root_ref TEXT NOT NULL REFERENCES execution.semantic_typed_value_root(root_ref) ON DELETE CASCADE,
    path_ref TEXT NOT NULL,
    parent_path_ref TEXT,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    key_ref TEXT,
    value_kind TEXT NOT NULL CHECK (
        value_kind IN ('mapping', 'sequence', 'text', 'integer', 'float', 'boolean', 'bytes', 'null')
    ),
    text_value TEXT,
    integer_value NUMERIC,
    float_value DOUBLE PRECISION,
    boolean_value BOOLEAN,
    bytes_value BYTEA,
    PRIMARY KEY (root_ref, path_ref),
    CHECK (
        (value_kind IN ('mapping', 'sequence', 'null')
         AND text_value IS NULL AND integer_value IS NULL
         AND float_value IS NULL AND boolean_value IS NULL AND bytes_value IS NULL)
        OR (value_kind = 'text' AND text_value IS NOT NULL
            AND integer_value IS NULL AND float_value IS NULL
            AND boolean_value IS NULL AND bytes_value IS NULL)
        OR (value_kind = 'integer' AND integer_value IS NOT NULL
            AND text_value IS NULL AND float_value IS NULL
            AND boolean_value IS NULL AND bytes_value IS NULL)
        OR (value_kind = 'float' AND float_value IS NOT NULL
            AND text_value IS NULL AND integer_value IS NULL
            AND boolean_value IS NULL AND bytes_value IS NULL)
        OR (value_kind = 'boolean' AND boolean_value IS NOT NULL
            AND text_value IS NULL AND integer_value IS NULL
            AND float_value IS NULL AND bytes_value IS NULL)
        OR (value_kind = 'bytes' AND bytes_value IS NOT NULL
            AND text_value IS NULL AND integer_value IS NULL
            AND float_value IS NULL AND boolean_value IS NULL)
    )
);

CREATE INDEX IF NOT EXISTS semantic_typed_value_node_parent_idx
    ON execution.semantic_typed_value_node (root_ref, parent_path_ref, ordinal);

ALTER TABLE execution.semantic_immutable_delta
    ALTER COLUMN payload DROP NOT NULL,
    ADD COLUMN IF NOT EXISTS receipt_ref TEXT,
    ADD COLUMN IF NOT EXISTS receipt_sha256 BYTEA;

CREATE TABLE IF NOT EXISTS execution.semantic_solver_receipt (
    receipt_ref TEXT PRIMARY KEY,
    delta_ref TEXT NOT NULL UNIQUE REFERENCES execution.semantic_immutable_delta(delta_ref) ON DELETE CASCADE,
    job_ref TEXT NOT NULL REFERENCES execution.semantic_closure_job(job_ref) ON DELETE RESTRICT,
    run_ref TEXT NOT NULL REFERENCES execution.semantic_run(run_ref) ON DELETE CASCADE,
    document_ref TEXT NOT NULL,
    owner_ref TEXT NOT NULL,
    owner_scope_ref TEXT NOT NULL,
    owner_factor_family TEXT NOT NULL,
    input_revision BIGINT NOT NULL CHECK (input_revision >= 0),
    rule_set_revision TEXT NOT NULL,
    backend_ref TEXT NOT NULL,
    metrics_root_ref TEXT REFERENCES execution.semantic_typed_value_root(root_ref) ON DELETE RESTRICT,
    receipt_sha256 BYTEA NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS execution.semantic_solver_receipt_ref (
    receipt_ref TEXT NOT NULL REFERENCES execution.semantic_solver_receipt(receipt_ref) ON DELETE CASCADE,
    ref_kind TEXT NOT NULL CHECK (ref_kind IN ('input', 'residual', 'assumption', 'coverage')),
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    value_ref TEXT NOT NULL,
    PRIMARY KEY (receipt_ref, ref_kind, ordinal),
    UNIQUE (receipt_ref, ref_kind, value_ref)
);

CREATE TABLE IF NOT EXISTS execution.semantic_factor_proposal (
    proposal_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL,
    source_revision_ref TEXT NOT NULL,
    semantic_coordinate_ref TEXT NOT NULL,
    scope_ref TEXT NOT NULL,
    statement_role TEXT NOT NULL,
    coordinate_kind TEXT NOT NULL,
    fibre_kind TEXT NOT NULL,
    derivation_role TEXT NOT NULL,
    factor_type_ref TEXT NOT NULL,
    structural_signature TEXT NOT NULL,
    producer_contract TEXT NOT NULL,
    producer_scope TEXT NOT NULL,
    operation_contract TEXT NOT NULL,
    declaration_revision TEXT NOT NULL,
    support_state TEXT NOT NULL,
    confidence DOUBLE PRECISION,
    qualifier_root_ref TEXT REFERENCES execution.semantic_typed_value_root(root_ref) ON DELETE RESTRICT,
    candidate_root_ref TEXT REFERENCES execution.semantic_typed_value_root(root_ref) ON DELETE RESTRICT,
    execution_root_ref TEXT REFERENCES execution.semantic_typed_value_root(root_ref) ON DELETE RESTRICT,
    proposal_sha256 BYTEA NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS execution.semantic_factor_proposal_ref (
    proposal_ref TEXT NOT NULL REFERENCES execution.semantic_factor_proposal(proposal_ref) ON DELETE CASCADE,
    ref_kind TEXT NOT NULL CHECK (
        ref_kind IN ('source_span', 'input_observation', 'dependency_factor',
                     'residual', 'ontology_axis', 'transport', 'assumption', 'coverage')
    ),
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    value_ref TEXT NOT NULL,
    PRIMARY KEY (proposal_ref, ref_kind, ordinal),
    UNIQUE (proposal_ref, ref_kind, value_ref)
);

CREATE TABLE IF NOT EXISTS execution.semantic_factor_proposal_role (
    proposal_ref TEXT NOT NULL REFERENCES execution.semantic_factor_proposal(proposal_ref) ON DELETE CASCADE,
    role_ref TEXT NOT NULL,
    value_ref TEXT NOT NULL,
    PRIMARY KEY (proposal_ref, role_ref)
);

CREATE TABLE IF NOT EXISTS execution.semantic_solver_receipt_proposal (
    receipt_ref TEXT NOT NULL REFERENCES execution.semantic_solver_receipt(receipt_ref) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    proposal_ref TEXT NOT NULL REFERENCES execution.semantic_factor_proposal(proposal_ref) ON DELETE RESTRICT,
    PRIMARY KEY (receipt_ref, ordinal),
    UNIQUE (receipt_ref, proposal_ref)
);

ALTER TABLE execution.semantic_round_manifest
    ALTER COLUMN manifest DROP NOT NULL;

ALTER TABLE execution.semantic_finalization_cursor
    ALTER COLUMN manifest DROP NOT NULL,
    ADD COLUMN IF NOT EXISTS graph_ref TEXT,
    ADD COLUMN IF NOT EXISTS ledger_ref TEXT,
    ADD COLUMN IF NOT EXISTS certificate_ref TEXT,
    ADD COLUMN IF NOT EXISTS owner_fingerprint_ref TEXT,
    ADD COLUMN IF NOT EXISTS factor_count BIGINT,
    ADD COLUMN IF NOT EXISTS residual_count BIGINT,
    ADD COLUMN IF NOT EXISTS byte_count BIGINT;

ALTER TABLE execution.semantic_publication
    ALTER COLUMN manifest DROP NOT NULL,
    ADD COLUMN IF NOT EXISTS graph_ref TEXT,
    ADD COLUMN IF NOT EXISTS certificate_ref TEXT,
    ADD COLUMN IF NOT EXISTS build_ref TEXT,
    ADD COLUMN IF NOT EXISTS factor_count BIGINT,
    ADD COLUMN IF NOT EXISTS residual_count BIGINT,
    ADD COLUMN IF NOT EXISTS publication_sha256 BYTEA;

ALTER TABLE execution.semantic_execution_receipt
    ALTER COLUMN payload DROP NOT NULL,
    ADD COLUMN IF NOT EXISTS graph_ref TEXT,
    ADD COLUMN IF NOT EXISTS certificate_ref TEXT,
    ADD COLUMN IF NOT EXISTS owner_revision BIGINT,
    ADD COLUMN IF NOT EXISTS factor_count BIGINT,
    ADD COLUMN IF NOT EXISTS residual_count BIGINT;

ALTER TABLE execution.semantic_lifecycle_event
    ADD COLUMN IF NOT EXISTS prior_lifecycle TEXT,
    ADD COLUMN IF NOT EXISTS resulting_lifecycle TEXT,
    ADD COLUMN IF NOT EXISTS owner_ref TEXT,
    ADD COLUMN IF NOT EXISTS owner_revision BIGINT,
    ADD COLUMN IF NOT EXISTS round_ordinal INTEGER;

ALTER TABLE execution.semantic_work_item
    ALTER COLUMN input_manifest DROP NOT NULL;

ALTER TABLE execution.semantic_work_receipt
    ALTER COLUMN payload DROP NOT NULL,
    ADD COLUMN IF NOT EXISTS attempt_ref TEXT,
    ADD COLUMN IF NOT EXISTS input_sha256 BYTEA,
    ADD COLUMN IF NOT EXISTS output_sha256 BYTEA,
    ADD COLUMN IF NOT EXISTS artifact_ref TEXT,
    ADD COLUMN IF NOT EXISTS byte_count BIGINT,
    ADD COLUMN IF NOT EXISTS lease_epoch BIGINT,
    ADD COLUMN IF NOT EXISTS worker_pid BIGINT,
    ADD COLUMN IF NOT EXISTS backend_pid INTEGER,
    ADD COLUMN IF NOT EXISTS admission_state TEXT;

ALTER TABLE execution.semantic_stage_cursor
    ALTER COLUMN cursor_manifest DROP NOT NULL,
    ADD COLUMN IF NOT EXISTS total_work_count BIGINT,
    ADD COLUMN IF NOT EXISTS last_completed_work_ref TEXT,
    ADD COLUMN IF NOT EXISTS cursor_revision BIGINT NOT NULL DEFAULT 0;

ALTER TABLE execution.semantic_stage_manifest
    ALTER COLUMN child_work_refs DROP NOT NULL,
    ADD COLUMN IF NOT EXISTS child_count BIGINT NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS execution.semantic_stage_manifest_child (
    manifest_ref TEXT NOT NULL REFERENCES execution.semantic_stage_manifest(manifest_ref) ON DELETE CASCADE,
    ordinal BIGINT NOT NULL CHECK (ordinal >= 0),
    work_ref TEXT NOT NULL REFERENCES execution.semantic_work_item(work_ref) ON DELETE RESTRICT,
    output_sha256 BYTEA NOT NULL,
    PRIMARY KEY (manifest_ref, ordinal),
    UNIQUE (manifest_ref, work_ref)
);

ALTER TABLE execution.semantic_outbox
    ALTER COLUMN payload DROP NOT NULL,
    ADD COLUMN IF NOT EXISTS run_ref TEXT,
    ADD COLUMN IF NOT EXISTS document_ref TEXT,
    ADD COLUMN IF NOT EXISTS work_ref TEXT,
    ADD COLUMN IF NOT EXISTS job_ref TEXT,
    ADD COLUMN IF NOT EXISTS delta_ref TEXT,
    ADD COLUMN IF NOT EXISTS owner_ref TEXT,
    ADD COLUMN IF NOT EXISTS prior_revision BIGINT,
    ADD COLUMN IF NOT EXISTS resulting_revision BIGINT,
    ADD COLUMN IF NOT EXISTS lease_epoch BIGINT,
    ADD COLUMN IF NOT EXISTS artifact_ref TEXT,
    ADD COLUMN IF NOT EXISTS ordinal BIGINT,
    ADD COLUMN IF NOT EXISTS publication_ref TEXT;

-- Replace JSON-producing outbox triggers with typed-column triggers.
DROP TRIGGER IF EXISTS semantic_strict_delta_admission_outbox
    ON execution.semantic_strict_delta_admission;
DROP FUNCTION IF EXISTS execution.emit_strict_semantic_delta_admitted();

CREATE FUNCTION execution.emit_typed_strict_delta_admitted()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO execution.semantic_outbox
        (event_ref, aggregate_ref, event_type_ref, run_ref, job_ref,
         delta_ref, owner_ref, prior_revision, resulting_revision, lease_epoch)
    SELECT
        'semantic-outbox:delta-admitted:' || NEW.delta_ref,
        NEW.owner_ref,
        'semantic.delta.admitted.v2',
        NEW.run_ref,
        d.job_ref,
        NEW.delta_ref,
        NEW.owner_ref,
        NEW.prior_revision,
        NEW.resulting_revision,
        NEW.lease_epoch
    FROM execution.semantic_immutable_delta d
    WHERE d.delta_ref = NEW.delta_ref
    ON CONFLICT (event_ref) DO NOTHING;
    RETURN NEW;
END;
$$;

CREATE TRIGGER semantic_typed_strict_delta_admission_outbox
AFTER INSERT ON execution.semantic_strict_delta_admission
FOR EACH ROW
EXECUTE FUNCTION execution.emit_typed_strict_delta_admitted();

DROP TRIGGER IF EXISTS semantic_work_item_completed_outbox
    ON execution.semantic_work_item;
DROP FUNCTION IF EXISTS execution.emit_work_item_completed();

CREATE FUNCTION execution.emit_typed_work_item_completed()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.state <> 'completed' OR OLD.state = 'completed' THEN
        RETURN NEW;
    END IF;
    INSERT INTO execution.semantic_outbox
        (event_ref, aggregate_ref, event_type_ref, run_ref, document_ref,
         work_ref, artifact_ref, ordinal, lease_epoch)
    VALUES (
        'semantic-outbox:work-completed:' || NEW.work_ref,
        NEW.stage_instance_ref,
        'semantic.work-item.completed.v2',
        NEW.run_ref,
        NEW.document_ref,
        NEW.work_ref,
        NEW.output_artifact_ref,
        NEW.ordinal,
        NEW.lease_epoch
    )
    ON CONFLICT (event_ref) DO NOTHING;
    RETURN NEW;
END;
$$;

CREATE TRIGGER semantic_typed_work_item_completed_outbox
AFTER UPDATE OF state ON execution.semantic_work_item
FOR EACH ROW
EXECUTE FUNCTION execution.emit_typed_work_item_completed();

DROP TRIGGER IF EXISTS semantic_publication_outbox
    ON execution.semantic_publication;
DROP FUNCTION IF EXISTS execution.emit_publication_committed();

CREATE FUNCTION execution.emit_typed_publication_committed()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.state <> 'committed' OR OLD.state = 'committed' THEN
        RETURN NEW;
    END IF;
    INSERT INTO execution.semantic_outbox
        (event_ref, aggregate_ref, event_type_ref, run_ref, document_ref,
         publication_ref)
    VALUES (
        'semantic-outbox:publication-committed:' || NEW.publication_ref,
        NEW.document_ref,
        'semantic.publication.committed.v2',
        NEW.run_ref,
        NEW.document_ref,
        NEW.publication_ref
    )
    ON CONFLICT (event_ref) DO NOTHING;
    RETURN NEW;
END;
$$;

CREATE TRIGGER semantic_typed_publication_outbox
AFTER UPDATE OF state ON execution.semantic_publication
FOR EACH ROW
EXECUTE FUNCTION execution.emit_typed_publication_committed();

COMMIT;
