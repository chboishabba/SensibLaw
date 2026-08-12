BEGIN;

-- 092: consumer/query-aware stopping, contextual world evidence, exact hot-state
-- verification, and a rebuildable packed observation-tape projection.
--
-- Formal reference: dashi_agda #521/#530/#531/#533.  In particular:
--   contextual preference != identity proof;
--   missing context != negative evidence;
--   query/policy sufficiency may stop execution without closing semantics;
--   hot projections must equal a rebuild from append-only authority;
--   physical compression must decode exactly to the canonical numeric tape.

-- ---------------------------------------------------------------------------
-- Exact hot/cold extensional verification.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION execution.verify_numeric_pnf_candidate_current_state()
RETURNS BOOLEAN LANGUAGE sql STABLE AS $$
SELECT NOT EXISTS (
    (SELECT demand_id,target_kind,target_id,event_id,event_kind,active_budget,reason_ref,created_at
       FROM execution.semantic_pnf_candidate_latest_execution
     EXCEPT
     SELECT demand_id,target_kind,target_id,event_id,event_kind,active_budget,reason_ref,created_at
       FROM execution.semantic_pnf_candidate_current_execution)
    UNION ALL
    (SELECT demand_id,target_kind,target_id,event_id,event_kind,active_budget,reason_ref,created_at
       FROM execution.semantic_pnf_candidate_current_execution
     EXCEPT
     SELECT demand_id,target_kind,target_id,event_id,event_kind,active_budget,reason_ref,created_at
       FROM execution.semantic_pnf_candidate_latest_execution)
    UNION ALL
    (SELECT demand_id,target_kind,target_id,event_id,event_kind,evidence_id,created_at
       FROM execution.semantic_pnf_candidate_latest_admissibility
     EXCEPT
     SELECT demand_id,target_kind,target_id,event_id,event_kind,evidence_id,created_at
       FROM execution.semantic_pnf_candidate_current_admissibility)
    UNION ALL
    (SELECT demand_id,target_kind,target_id,event_id,event_kind,evidence_id,created_at
       FROM execution.semantic_pnf_candidate_current_admissibility
     EXCEPT
     SELECT demand_id,target_kind,target_id,event_id,event_kind,evidence_id,created_at
       FROM execution.semantic_pnf_candidate_latest_admissibility)
    UNION ALL
    (SELECT demand_id,target_kind,target_id,horizon,revision,preferred,margin,evidence_count,preference_id
       FROM execution.semantic_pnf_candidate_latest_preference
     EXCEPT
     SELECT demand_id,target_kind,target_id,horizon,revision,preferred,margin,evidence_count,preference_id
       FROM execution.semantic_pnf_candidate_current_preference)
    UNION ALL
    (SELECT demand_id,target_kind,target_id,horizon,revision,preferred,margin,evidence_count,preference_id
       FROM execution.semantic_pnf_candidate_current_preference
     EXCEPT
     SELECT demand_id,target_kind,target_id,horizon,revision,preferred,margin,evidence_count,preference_id
       FROM execution.semantic_pnf_candidate_latest_preference)
);
$$;

-- ---------------------------------------------------------------------------
-- Contextual world-candidate requirements and signed fit.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS execution.semantic_pnf_world_candidate_requirement (
    world_entity_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_world_entity_numeric(world_entity_id)
        ON DELETE CASCADE,
    axis_kind SMALLINT NOT NULL CHECK (axis_kind BETWEEN 1 AND 32),
    required_symbol_id BIGINT NOT NULL
        REFERENCES execution.semantic_symbol(symbol_id) ON DELETE RESTRICT,
    required_polarity SMALLINT NOT NULL DEFAULT 1
        CHECK (required_polarity IN (-1,1)),
    requirement_revision BIGINT NOT NULL DEFAULT 1,
    evidence_ref TEXT NOT NULL,
    PRIMARY KEY(world_entity_id,axis_kind,required_symbol_id,required_polarity),
    UNIQUE(world_entity_id,evidence_ref)
);
CREATE INDEX IF NOT EXISTS semantic_pnf_world_requirement_symbol_idx
    ON execution.semantic_pnf_world_candidate_requirement
       (required_symbol_id,axis_kind,world_entity_id);

-- Context observations are axis-typed.  The pre-092 context-symbol table is
-- retained as authority-compatible input; this table provides the compiled
-- consumer-facing projection needed to distinguish e.g. country from state.
CREATE TABLE IF NOT EXISTS execution.semantic_pnf_world_context_axis_symbol (
    context_witness_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_world_context_witness(context_witness_id)
        ON DELETE CASCADE,
    axis_kind SMALLINT NOT NULL CHECK (axis_kind BETWEEN 1 AND 32),
    symbol_id BIGINT NOT NULL
        REFERENCES execution.semantic_symbol(symbol_id) ON DELETE RESTRICT,
    polarity SMALLINT NOT NULL DEFAULT 1 CHECK (polarity IN (-1,0,1)),
    PRIMARY KEY(context_witness_id,axis_kind,symbol_id,polarity)
);
CREATE INDEX IF NOT EXISTS semantic_pnf_world_context_axis_lookup_idx
    ON execution.semantic_pnf_world_context_axis_symbol
       (context_witness_id,axis_kind,symbol_id,polarity);

CREATE OR REPLACE VIEW execution.semantic_pnf_world_context_fit_v1 AS
WITH requirement AS (
    SELECT candidate.label_symbol_id,
           candidate.world_entity_id,
           requirement.axis_kind,
           requirement.required_symbol_id,
           requirement.required_polarity
      FROM execution.semantic_pnf_label_world_candidate AS candidate
      JOIN execution.semantic_pnf_world_candidate_requirement AS requirement
        ON requirement.world_entity_id=candidate.world_entity_id
), fit AS (
    SELECT witness.context_witness_id,
           witness.token_id,
           requirement.label_symbol_id,
           requirement.world_entity_id,
           count(*)::BIGINT AS requirement_count,
           count(*) FILTER (WHERE observed.symbol_id IS NOT NULL
                              AND observed.polarity=requirement.required_polarity)::BIGINT
               AS supporting_count,
           count(*) FILTER (WHERE observed.symbol_id IS NOT NULL
                              AND observed.polarity=-requirement.required_polarity)::BIGINT
               AS contradicting_count,
           count(*) FILTER (WHERE observed.symbol_id IS NULL)::BIGINT AS unknown_count
      FROM execution.semantic_pnf_world_context_witness AS witness
      JOIN requirement ON TRUE
      LEFT JOIN execution.semantic_pnf_world_context_axis_symbol AS observed
        ON observed.context_witness_id=witness.context_witness_id
       AND observed.axis_kind=requirement.axis_kind
       AND observed.symbol_id=requirement.required_symbol_id
       AND observed.polarity<>0
     GROUP BY witness.context_witness_id,witness.token_id,
              requirement.label_symbol_id,requirement.world_entity_id
)
SELECT fit.*,
       (fit.supporting_count-fit.contradicting_count) AS signed_margin,
       (fit.requirement_count>0
        AND fit.supporting_count=fit.requirement_count
        AND fit.contradicting_count=0
        AND fit.unknown_count=0) AS requirements_satisfied
  FROM fit;

CREATE TABLE IF NOT EXISTS execution.semantic_pnf_world_context_preference (
    preference_id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    token_id BIGINT NOT NULL
        REFERENCES execution.semantic_parser_token(token_id) ON DELETE CASCADE,
    label_symbol_id BIGINT NOT NULL
        REFERENCES execution.semantic_symbol(symbol_id) ON DELETE RESTRICT,
    world_entity_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_world_entity_numeric(world_entity_id) ON DELETE CASCADE,
    context_witness_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_world_context_witness(context_witness_id) ON DELETE CASCADE,
    signed_margin BIGINT NOT NULL,
    supporting_count BIGINT NOT NULL CHECK (supporting_count>=0),
    contradicting_count BIGINT NOT NULL CHECK (contradicting_count>=0),
    unknown_count BIGINT NOT NULL CHECK (unknown_count>=0),
    preferred BOOLEAN NOT NULL,
    revision BIGINT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(token_id,label_symbol_id,world_entity_id,context_witness_id,revision)
);
CREATE INDEX IF NOT EXISTS semantic_pnf_world_context_preference_lookup_idx
    ON execution.semantic_pnf_world_context_preference
       (token_id,label_symbol_id,revision,preferred,signed_margin DESC,world_entity_id);

CREATE OR REPLACE FUNCTION execution.refresh_numeric_pnf_world_context_preferences(
    selected_context_witness_id BIGINT,
    selected_revision BIGINT DEFAULT 1
) RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE affected BIGINT := 0;
BEGIN
    INSERT INTO execution.semantic_pnf_world_context_preference
        (token_id,label_symbol_id,world_entity_id,context_witness_id,signed_margin,
         supporting_count,contradicting_count,unknown_count,preferred,revision)
    SELECT fit.token_id,fit.label_symbol_id,fit.world_entity_id,fit.context_witness_id,
           fit.signed_margin,fit.supporting_count,fit.contradicting_count,fit.unknown_count,
           fit.requirements_satisfied,selected_revision
      FROM execution.semantic_pnf_world_context_fit_v1 AS fit
     WHERE fit.context_witness_id=selected_context_witness_id
    ON CONFLICT(token_id,label_symbol_id,world_entity_id,context_witness_id,revision)
    DO UPDATE SET
        signed_margin=EXCLUDED.signed_margin,
        supporting_count=EXCLUDED.supporting_count,
        contradicting_count=EXCLUDED.contradicting_count,
        unknown_count=EXCLUDED.unknown_count,
        preferred=EXCLUDED.preferred;
    GET DIAGNOSTICS affected=ROW_COUNT;
    RETURN affected;
END;
$$;

-- Strengthen attachment integrity.  A contextual attachment is still only a
-- mention-local preference/attachment.  It does not call the external identity
-- admission function and therefore cannot promote world identity.
CREATE OR REPLACE FUNCTION execution.attach_numeric_pnf_world_candidate(
    selected_token_id BIGINT,
    selected_label_symbol_id BIGINT,
    selected_world_entity_id BIGINT,
    selected_context_witness_id BIGINT
) RETURNS BOOLEAN LANGUAGE plpgsql AS $$
DECLARE witness_region BIGINT;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM execution.semantic_pnf_label_world_candidate AS candidate
         WHERE candidate.label_symbol_id=selected_label_symbol_id
           AND candidate.world_entity_id=selected_world_entity_id
    ) THEN
        RAISE EXCEPTION 'world candidate is not cached for this label';
    END IF;

    SELECT witness.region_id INTO witness_region
      FROM execution.semantic_pnf_world_context_witness AS witness
     WHERE witness.context_witness_id=selected_context_witness_id
       AND witness.token_id=selected_token_id;
    IF witness_region IS NULL THEN
        RAISE EXCEPTION 'context witness does not belong to mention token';
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM execution.semantic_parser_token AS token
          JOIN execution.semantic_pnf_region AS region ON region.region_id=witness_region
          JOIN execution.semantic_pnf_run_identity AS run_identity
            ON run_identity.run_id=region.run_id AND run_identity.run_ref=token.run_ref
          JOIN execution.semantic_pnf_document_identity AS document_identity
            ON document_identity.document_id=region.document_id
           AND document_identity.document_ref=token.document_ref
         WHERE token.token_id=selected_token_id
           AND token.representation_version=2
           AND selected_label_symbol_id IN (token.orth_symbol_id,token.lemma_symbol_id)
           AND token.start_char>=region.start_char
           AND token.end_char<=region.end_char
    ) THEN
        RAISE EXCEPTION 'mention label/region is not justified by the numeric parser observation';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM execution.semantic_pnf_world_context_fit_v1 AS fit
         WHERE fit.context_witness_id=selected_context_witness_id
           AND fit.token_id=selected_token_id
           AND fit.label_symbol_id=selected_label_symbol_id
           AND fit.world_entity_id=selected_world_entity_id
           AND fit.requirements_satisfied
    ) THEN
        RAISE EXCEPTION 'candidate context requirements are not positively witnessed';
    END IF;

    INSERT INTO execution.semantic_pnf_mention_world_attachment
        (token_id,label_symbol_id,world_entity_id,context_witness_id,attachment_state)
    VALUES (selected_token_id,selected_label_symbol_id,selected_world_entity_id,
            selected_context_witness_id,1)
    ON CONFLICT DO NOTHING;
    RETURN TRUE;
END;
$$;

-- ---------------------------------------------------------------------------
-- Consumer/query/policy sufficiency: stop work, never manufacture closure.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS execution.semantic_pnf_consumer_sufficiency_certificate (
    certificate_id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    demand_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_demand(demand_id) ON DELETE CASCADE,
    consumer_ref TEXT NOT NULL,
    query_ref TEXT NOT NULL,
    policy_ref TEXT NOT NULL DEFAULT '',
    horizon SMALLINT NOT NULL CHECK (horizon IN (3,6,9)),
    certificate_kind SMALLINT NOT NULL CHECK (certificate_kind IN (1,2,3)),
    -- 1 query-factorisation, 2 restricted-policy safety, 3 full future safety.
    residual_required BOOLEAN NOT NULL DEFAULT TRUE,
    certificate_ref TEXT NOT NULL,
    revision BIGINT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(demand_id,consumer_ref,query_ref,policy_ref,horizon,certificate_kind,revision),
    UNIQUE(certificate_ref)
);
CREATE INDEX IF NOT EXISTS semantic_pnf_consumer_sufficiency_lookup_idx
    ON execution.semantic_pnf_consumer_sufficiency_certificate
       (demand_id,consumer_ref,query_ref,policy_ref,horizon,revision DESC);

CREATE OR REPLACE FUNCTION execution.numeric_pnf_consumer_stop_at_horizon(
    selected_demand_id BIGINT,
    selected_consumer_ref TEXT,
    selected_query_ref TEXT,
    selected_policy_ref TEXT,
    selected_horizon SMALLINT
) RETURNS BOOLEAN LANGUAGE sql STABLE AS $$
SELECT EXISTS (
    SELECT 1
      FROM execution.semantic_pnf_consumer_sufficiency_certificate AS certificate
     WHERE certificate.demand_id=selected_demand_id
       AND certificate.consumer_ref=selected_consumer_ref
       AND certificate.query_ref=selected_query_ref
       AND certificate.policy_ref=selected_policy_ref
       AND certificate.horizon<=selected_horizon
);
$$;

CREATE OR REPLACE FUNCTION execution.advance_numeric_pnf_horizon_work_for_consumer(
    selected_run_id BIGINT,
    selected_document_id BIGINT,
    completed_horizon SMALLINT,
    selected_consumer_ref TEXT,
    selected_query_ref TEXT,
    selected_policy_ref TEXT DEFAULT ''
) RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE next_horizon SMALLINT; affected BIGINT := 0;
BEGIN
    IF completed_horizon NOT IN (3,6) THEN
        RAISE EXCEPTION 'completed_horizon must be 3 or 6';
    END IF;
    next_horizon := CASE completed_horizon WHEN 3 THEN 6 ELSE 9 END;

    UPDATE execution.semantic_pnf_horizon_work_queue AS work
       SET work_state=2, completed_at=CURRENT_TIMESTAMP
      FROM execution.semantic_pnf_demand AS demand
      JOIN execution.semantic_pnf_region AS region ON region.region_id=demand.source_region_id
     WHERE work.demand_id=demand.demand_id
       AND work.horizon=completed_horizon
       AND region.run_id=selected_run_id
       AND region.document_id=selected_document_id;

    INSERT INTO execution.semantic_pnf_horizon_work_queue(demand_id,horizon)
    SELECT demand.demand_id,next_horizon
      FROM execution.semantic_pnf_demand AS demand
      JOIN execution.semantic_pnf_region AS region ON region.region_id=demand.source_region_id
     WHERE region.run_id=selected_run_id
       AND region.document_id=selected_document_id
       AND NOT execution.numeric_pnf_consumer_stop_at_horizon(
            demand.demand_id,selected_consumer_ref,selected_query_ref,
            selected_policy_ref,completed_horizon)
       AND NOT EXISTS (
           SELECT 1 FROM execution.semantic_pnf_frontier_resolution AS proof
            WHERE proof.demand_id=demand.demand_id
              AND proof.outcome_state=2
              AND proof.candidate_count=1
       )
    ON CONFLICT DO NOTHING;
    GET DIAGNOSTICS affected=ROW_COUNT;
    RETURN affected;
END;
$$;

-- ---------------------------------------------------------------------------
-- Controlled workload identity.  Equal token count alone is not comparable.
-- ---------------------------------------------------------------------------
ALTER TABLE execution.semantic_pnf_corpus_reuse_measurement
    ADD COLUMN IF NOT EXISTS workload_digest BYTEA,
    ADD COLUMN IF NOT EXISTS consumer_ref TEXT,
    ADD COLUMN IF NOT EXISTS compiler_config_digest BYTEA;

CREATE UNIQUE INDEX IF NOT EXISTS semantic_pnf_reuse_controlled_sample_idx
    ON execution.semantic_pnf_corpus_reuse_measurement
       (workload_ref,workload_digest,consumer_ref,compiler_config_digest,measurement_id)
    WHERE workload_digest IS NOT NULL
      AND consumer_ref IS NOT NULL
      AND compiler_config_digest IS NOT NULL;

CREATE OR REPLACE FUNCTION execution.assert_numeric_pnf_learning_nonincrease(
    before_measurement_id BIGINT,
    after_measurement_id BIGINT
) RETURNS BOOLEAN LANGUAGE plpgsql STABLE AS $$
DECLARE before_row execution.semantic_pnf_corpus_reuse_measurement%ROWTYPE;
        after_row execution.semantic_pnf_corpus_reuse_measurement%ROWTYPE;
BEGIN
    SELECT * INTO STRICT before_row
      FROM execution.semantic_pnf_corpus_reuse_measurement
     WHERE measurement_id=before_measurement_id;
    SELECT * INTO STRICT after_row
      FROM execution.semantic_pnf_corpus_reuse_measurement
     WHERE measurement_id=after_measurement_id;

    IF before_row.workload_ref<>after_row.workload_ref
       OR before_row.workload_digest IS NULL
       OR after_row.workload_digest IS NULL
       OR before_row.workload_digest<>after_row.workload_digest
       OR before_row.consumer_ref IS NULL
       OR after_row.consumer_ref IS NULL
       OR before_row.consumer_ref<>after_row.consumer_ref
       OR before_row.compiler_config_digest IS NULL
       OR after_row.compiler_config_digest IS NULL
       OR before_row.compiler_config_digest<>after_row.compiler_config_digest THEN
        RAISE EXCEPTION 'learning comparison requires identical controlled workload, consumer, and compiler configuration';
    END IF;
    IF before_row.token_count<>after_row.token_count THEN
        RAISE EXCEPTION 'controlled workload token carrier changed';
    END IF;
    IF before_row.fixed_numeric_work<>after_row.fixed_numeric_work THEN
        RAISE EXCEPTION 'fixed numeric work changed';
    END IF;
    RETURN after_row.unresolved_resolution_work<=before_row.unresolved_resolution_work;
END;
$$;

-- ---------------------------------------------------------------------------
-- Rebuildable numeric observation tape projection.
-- ---------------------------------------------------------------------------
-- PostgreSQL remains the canonical row authority.  This table stores a physical
-- packed projection produced by Python; exact decoding is verified against the
-- authority digest before the tape may be marked valid.
CREATE TABLE IF NOT EXISTS execution.semantic_parser_numeric_tape (
    tape_id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    run_ref TEXT NOT NULL,
    document_ref TEXT NOT NULL,
    representation_version SMALLINT NOT NULL DEFAULT 2,
    codebook_revision BIGINT NOT NULL,
    token_count BIGINT NOT NULL CHECK (token_count>=0),
    authority_digest BYTEA NOT NULL,
    packed_digest BYTEA NOT NULL,
    packed_payload BYTEA NOT NULL,
    codec_version SMALLINT NOT NULL,
    exact_roundtrip_verified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(run_ref,document_ref,representation_version,codebook_revision,codec_version)
);
CREATE INDEX IF NOT EXISTS semantic_parser_numeric_tape_lookup_idx
    ON execution.semantic_parser_numeric_tape
       (run_ref,document_ref,representation_version,exact_roundtrip_verified,codec_version);

-- A tape is a compiled projection only.  It cannot substitute for parser rows
-- unless exact_roundtrip_verified is true; even then parser rows remain authority.
CREATE OR REPLACE VIEW execution.semantic_parser_numeric_tape_ready_v1 AS
SELECT tape_id,run_ref,document_ref,representation_version,codebook_revision,
       token_count,authority_digest,packed_digest,codec_version,created_at
  FROM execution.semantic_parser_numeric_tape
 WHERE exact_roundtrip_verified;

COMMIT;
