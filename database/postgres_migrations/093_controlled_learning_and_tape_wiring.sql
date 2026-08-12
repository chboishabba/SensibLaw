BEGIN;

-- Controlled learning receipt.  The pre-092 recorder remains available for raw
-- observatory samples; theorem-level comparisons use this function so workload,
-- consumer and compiler configuration are all explicit and immutable inputs.
CREATE OR REPLACE FUNCTION execution.record_numeric_pnf_controlled_reuse_measurement(
    selected_run_id BIGINT,
    selected_document_id BIGINT,
    selected_workload_ref TEXT,
    selected_workload_digest BYTEA,
    selected_consumer_ref TEXT,
    selected_compiler_config_digest BYTEA
) RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE new_id BIGINT;
BEGIN
    IF octet_length(selected_workload_digest)<>32 THEN
        RAISE EXCEPTION 'workload digest must be SHA-256 width';
    END IF;
    IF octet_length(selected_compiler_config_digest)<>32 THEN
        RAISE EXCEPTION 'compiler config digest must be SHA-256 width';
    END IF;
    IF selected_consumer_ref='' THEN
        RAISE EXCEPTION 'consumer_ref must be non-empty';
    END IF;

    new_id := execution.record_numeric_pnf_corpus_reuse_measurement(
        selected_run_id,selected_document_id,selected_workload_ref
    );
    UPDATE execution.semantic_pnf_corpus_reuse_measurement
       SET workload_digest=selected_workload_digest,
           consumer_ref=selected_consumer_ref,
           compiler_config_digest=selected_compiler_config_digest
     WHERE measurement_id=new_id;
    RETURN new_id;
END;
$$;

-- Latest controlled samples are compared only within the complete workload key.
CREATE OR REPLACE VIEW execution.semantic_pnf_controlled_learning_curve_v1 AS
SELECT measurement.*,
       (measurement.fixed_numeric_work+measurement.unresolved_resolution_work)::NUMERIC
           / measurement.token_count::NUMERIC AS total_work_per_token,
       lag(measurement.unresolved_resolution_work)
           OVER (
             PARTITION BY measurement.workload_ref,measurement.workload_digest,
                          measurement.consumer_ref,measurement.compiler_config_digest
             ORDER BY measurement.measurement_id
           ) AS previous_unresolved_resolution_work
  FROM execution.semantic_pnf_corpus_reuse_measurement AS measurement
 WHERE measurement.workload_digest IS NOT NULL
   AND measurement.consumer_ref IS NOT NULL
   AND measurement.compiler_config_digest IS NOT NULL;

-- Exact tape registration is intentionally two-phase: Python first inserts an
-- unverified physical projection, independently decodes it, checks equality with
-- canonical parser rows/digest, then marks that exact row verified.  SQL never
-- infers exactness merely because bytes were supplied.
CREATE OR REPLACE FUNCTION execution.register_numeric_parser_tape(
    selected_run_ref TEXT,
    selected_document_ref TEXT,
    selected_codebook_revision BIGINT,
    selected_token_count BIGINT,
    selected_authority_digest BYTEA,
    selected_packed_digest BYTEA,
    selected_packed_payload BYTEA,
    selected_codec_version SMALLINT
) RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE new_id BIGINT;
BEGIN
    IF octet_length(selected_authority_digest)<>32
       OR octet_length(selected_packed_digest)<>32 THEN
        RAISE EXCEPTION 'tape digests must be SHA-256 width';
    END IF;
    INSERT INTO execution.semantic_parser_numeric_tape
        (run_ref,document_ref,representation_version,codebook_revision,token_count,
         authority_digest,packed_digest,packed_payload,codec_version,
         exact_roundtrip_verified)
    VALUES (selected_run_ref,selected_document_ref,2,selected_codebook_revision,
            selected_token_count,selected_authority_digest,selected_packed_digest,
            selected_packed_payload,selected_codec_version,FALSE)
    ON CONFLICT(run_ref,document_ref,representation_version,codebook_revision,codec_version)
    DO UPDATE SET
        token_count=EXCLUDED.token_count,
        authority_digest=EXCLUDED.authority_digest,
        packed_digest=EXCLUDED.packed_digest,
        packed_payload=EXCLUDED.packed_payload,
        exact_roundtrip_verified=FALSE,
        created_at=CURRENT_TIMESTAMP
    RETURNING tape_id INTO new_id;
    RETURN new_id;
END;
$$;

CREATE OR REPLACE FUNCTION execution.verify_registered_numeric_parser_tape(
    selected_tape_id BIGINT,
    selected_authority_digest BYTEA,
    selected_packed_digest BYTEA
) RETURNS BOOLEAN LANGUAGE plpgsql AS $$
DECLARE matched BOOLEAN;
BEGIN
    UPDATE execution.semantic_parser_numeric_tape
       SET exact_roundtrip_verified=TRUE
     WHERE tape_id=selected_tape_id
       AND authority_digest=selected_authority_digest
       AND packed_digest=selected_packed_digest
    RETURNING TRUE INTO matched;
    RETURN COALESCE(matched,FALSE);
END;
$$;

COMMIT;
