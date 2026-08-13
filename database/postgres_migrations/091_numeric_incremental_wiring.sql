BEGIN;

-- Every new demand begins at H3.  Later horizons are enqueued only by the
-- explicit advance function from 089 after unresolved work survives.
CREATE OR REPLACE FUNCTION execution.seed_numeric_pnf_h3_on_demand_insert()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO execution.semantic_pnf_horizon_work_queue(demand_id,horizon)
    VALUES (NEW.demand_id,3) ON CONFLICT DO NOTHING;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS semantic_pnf_demand_seed_h3_work ON execution.semantic_pnf_demand;
CREATE TRIGGER semantic_pnf_demand_seed_h3_work
AFTER INSERT ON execution.semantic_pnf_demand
FOR EACH ROW EXECUTE FUNCTION execution.seed_numeric_pnf_h3_on_demand_insert();
INSERT INTO execution.semantic_pnf_horizon_work_queue(demand_id,horizon)
SELECT demand_id,3 FROM execution.semantic_pnf_demand ON CONFLICT DO NOTHING;

-- Reverse dependencies from existing numeric carriers.
INSERT INTO execution.semantic_pnf_reverse_dependency(source_kind,source_id,demand_id,dependency_kind)
SELECT 2,demand.source_object_id,demand.demand_id,1
  FROM execution.semantic_pnf_demand AS demand
 WHERE demand.source_object_id IS NOT NULL
ON CONFLICT DO NOTHING;
INSERT INTO execution.semantic_pnf_reverse_dependency(source_kind,source_id,demand_id,dependency_kind)
SELECT 5,demand.source_interface_id,demand.demand_id,1
  FROM execution.semantic_pnf_demand AS demand
 WHERE demand.source_interface_id IS NOT NULL
ON CONFLICT DO NOTHING;
INSERT INTO execution.semantic_pnf_reverse_dependency(source_kind,source_id,demand_id,dependency_kind)
SELECT 1,support.token_id,candidate.demand_id,2
  FROM execution.semantic_pnf_demand_candidate AS candidate
  JOIN execution.semantic_pnf_object_token_support AS support
    ON candidate.target_kind=1 AND support.object_id=candidate.target_id
ON CONFLICT DO NOTHING;

CREATE OR REPLACE FUNCTION execution.index_numeric_pnf_evidence_reverse_dependency()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO execution.semantic_pnf_reverse_dependency(source_kind,source_id,demand_id,dependency_kind)
    VALUES (6,NEW.evidence_id,NEW.demand_id,3) ON CONFLICT DO NOTHING;
    IF NEW.source_region_id IS NOT NULL THEN
        INSERT INTO execution.semantic_pnf_reverse_dependency(source_kind,source_id,demand_id,dependency_kind)
        VALUES (4,NEW.source_region_id,NEW.demand_id,3) ON CONFLICT DO NOTHING;
    END IF;
    IF NEW.source_interface_id IS NOT NULL THEN
        INSERT INTO execution.semantic_pnf_reverse_dependency(source_kind,source_id,demand_id,dependency_kind)
        VALUES (5,NEW.source_interface_id,NEW.demand_id,3) ON CONFLICT DO NOTHING;
    END IF;
    INSERT INTO execution.semantic_pnf_incremental_work_queue
        (source_kind,source_id,demand_id,horizon)
    VALUES (6,NEW.evidence_id,NEW.demand_id,NEW.horizon)
    ON CONFLICT DO NOTHING;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS semantic_pnf_candidate_evidence_reverse_dependency
    ON execution.semantic_pnf_candidate_evidence;
CREATE TRIGGER semantic_pnf_candidate_evidence_reverse_dependency
AFTER INSERT ON execution.semantic_pnf_candidate_evidence
FOR EACH ROW EXECUTE FUNCTION execution.index_numeric_pnf_evidence_reverse_dependency();

-- Current-state projection must equal a rebuild from append-only history.
CREATE OR REPLACE FUNCTION execution.verify_numeric_pnf_candidate_current_state()
RETURNS BOOLEAN LANGUAGE sql STABLE AS $$
SELECT NOT EXISTS (
    SELECT 1 FROM (
        SELECT demand_id,target_kind,target_id,event_id,event_kind,active_budget,reason_ref,created_at
        FROM execution.semantic_pnf_candidate_latest_execution
        EXCEPT
        SELECT demand_id,target_kind,target_id,event_id,event_kind,active_budget,reason_ref,created_at
        FROM execution.semantic_pnf_candidate_current_execution
    ) AS diff1
    UNION ALL
    SELECT 1 FROM (
        SELECT demand_id,target_kind,target_id,event_id,event_kind,active_budget,reason_ref,created_at
        FROM execution.semantic_pnf_candidate_current_execution
        EXCEPT
        SELECT demand_id,target_kind,target_id,event_id,event_kind,active_budget,reason_ref,created_at
        FROM execution.semantic_pnf_candidate_latest_execution
    ) AS diff2
    UNION ALL
    SELECT 1 FROM (
        SELECT demand_id,target_kind,target_id,event_id,event_kind,evidence_id,created_at
        FROM execution.semantic_pnf_candidate_latest_admissibility
        EXCEPT
        SELECT demand_id,target_kind,target_id,event_id,event_kind,evidence_id,created_at
        FROM execution.semantic_pnf_candidate_current_admissibility
    ) AS diff3
    UNION ALL
    SELECT 1 FROM (
        SELECT demand_id,target_kind,target_id,horizon,revision,preferred,margin,evidence_count,preference_id
        FROM execution.semantic_pnf_candidate_latest_preference
        EXCEPT
        SELECT demand_id,target_kind,target_id,horizon,revision,preferred,margin,evidence_count,preference_id
        FROM execution.semantic_pnf_candidate_current_preference
    ) AS diff4
);
$$;

-- Incremental corpus-label cache maintenance.  Same label may map to many
-- canonical entities; admission state only changes the support count of one
-- label/entity cell.
CREATE OR REPLACE FUNCTION execution.refresh_numeric_pnf_entity_label_cache_cell(
    selected_witness_id BIGINT
) RETURNS BOOLEAN LANGUAGE plpgsql AS $$
DECLARE label_id BIGINT; entity_id BIGINT; authority SMALLINT; support_count BIGINT; latest BIGINT;
BEGIN
    SELECT object.head_symbol_id,witness.target_entity_id,witness.authority_class
      INTO label_id,entity_id,authority
      FROM execution.semantic_pnf_identity_witness AS witness
      JOIN execution.semantic_pnf_object AS object ON object.object_id=witness.source_object_id
     WHERE witness.witness_id=selected_witness_id;
    IF label_id IS NULL THEN RETURN FALSE; END IF;

    SELECT count(*),max(witness.witness_id)
      INTO support_count,latest
      FROM execution.semantic_pnf_identity_witness AS witness
      JOIN execution.semantic_pnf_identity_witness_admission AS admission
        ON admission.witness_id=witness.witness_id AND admission.admission_state=2
      JOIN execution.semantic_pnf_object AS object ON object.object_id=witness.source_object_id
     WHERE object.head_symbol_id=label_id
       AND witness.target_entity_id=entity_id
       AND witness.authority_class=authority;

    IF support_count=0 THEN
        DELETE FROM execution.semantic_pnf_corpus_entity_label_cache
         WHERE label_symbol_id=label_id AND canonical_entity_id=entity_id AND authority_class=authority;
    ELSE
        INSERT INTO execution.semantic_pnf_corpus_entity_label_cache
            (label_symbol_id,canonical_entity_id,authority_class,admitted_support_count,latest_witness_id)
        VALUES (label_id,entity_id,authority,support_count,latest)
        ON CONFLICT(label_symbol_id,canonical_entity_id,authority_class) DO UPDATE SET
            admitted_support_count=EXCLUDED.admitted_support_count,
            latest_witness_id=EXCLUDED.latest_witness_id;
    END IF;
    RETURN TRUE;
END;
$$;

CREATE OR REPLACE FUNCTION execution.refresh_numeric_pnf_entity_label_cache_on_admission()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM execution.refresh_numeric_pnf_entity_label_cache_cell(NEW.witness_id);
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS semantic_pnf_identity_admission_refresh_label_cache
    ON execution.semantic_pnf_identity_witness_admission;
CREATE TRIGGER semantic_pnf_identity_admission_refresh_label_cache
AFTER INSERT OR UPDATE OF admission_state ON execution.semantic_pnf_identity_witness_admission
FOR EACH ROW EXECUTE FUNCTION execution.refresh_numeric_pnf_entity_label_cache_on_admission();
SELECT execution.refresh_numeric_pnf_corpus_entity_label_cache();

-- Numeric Wikidata boundary.  Q<number> is represented internally as provider=1
-- plus BIGINT payload. Existing external identity proof machinery remains the
-- canonical admission path; text is reconstructed only inside this boundary.
CREATE OR REPLACE FUNCTION execution.cache_numeric_pnf_wikidata_candidate(
    selected_label_symbol_id BIGINT,
    selected_qid BIGINT,
    selected_candidate_ordinal INTEGER,
    selected_cache_revision BIGINT DEFAULT 1
) RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE resolved_world_entity_id BIGINT;
BEGIN
    IF selected_qid<=0 THEN RAISE EXCEPTION 'Wikidata Q id must be positive'; END IF;
    INSERT INTO execution.semantic_pnf_world_entity_numeric(provider_id,provider_numeric_id)
    VALUES (1,selected_qid) ON CONFLICT(provider_id,provider_numeric_id) DO NOTHING;
    SELECT world_entity_id INTO resolved_world_entity_id
      FROM execution.semantic_pnf_world_entity_numeric
     WHERE provider_id=1 AND provider_numeric_id=selected_qid;
    INSERT INTO execution.semantic_pnf_label_world_candidate
        (label_symbol_id,world_entity_id,candidate_ordinal,cache_revision)
    VALUES (selected_label_symbol_id,resolved_world_entity_id,
            selected_candidate_ordinal,selected_cache_revision)
    ON CONFLICT(label_symbol_id,world_entity_id) DO UPDATE SET
        candidate_ordinal=EXCLUDED.candidate_ordinal,
        cache_revision=EXCLUDED.cache_revision;
    RETURN resolved_world_entity_id;
END;
$$;

CREATE OR REPLACE FUNCTION execution.admit_numeric_pnf_wikidata_identity_alignment(
    selected_source_object_id BIGINT,
    selected_qid BIGINT,
    selected_canonical_symbol_id BIGINT DEFAULT NULL,
    selected_source_interface_id BIGINT DEFAULT NULL
) RETURNS TABLE(entity_id BIGINT,witness_id BIGINT)
LANGUAGE sql AS $$
SELECT * FROM execution.admit_numeric_pnf_external_identity_alignment(
    selected_source_object_id,
    'wikidata',
    'Q'||selected_qid::TEXT,
    selected_canonical_symbol_id,
    selected_source_interface_id
);
$$;

-- Context-qualified attachment refuses a label/world pair not already present
-- in that label's cached candidate fibre. Lack of such evidence leaves the
-- candidate unresolved; it is not a refutation.
CREATE OR REPLACE FUNCTION execution.attach_numeric_pnf_world_candidate(
    selected_token_id BIGINT,
    selected_label_symbol_id BIGINT,
    selected_world_entity_id BIGINT,
    selected_context_witness_id BIGINT
) RETURNS BOOLEAN LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM execution.semantic_pnf_label_world_candidate AS candidate
         WHERE candidate.label_symbol_id=selected_label_symbol_id
           AND candidate.world_entity_id=selected_world_entity_id
    ) THEN
        RAISE EXCEPTION 'world candidate is not cached for this label';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM execution.semantic_pnf_world_context_witness AS witness
         WHERE witness.context_witness_id=selected_context_witness_id
           AND witness.token_id=selected_token_id
    ) THEN
        RAISE EXCEPTION 'context witness does not belong to mention token';
    END IF;
    INSERT INTO execution.semantic_pnf_mention_world_attachment
        (token_id,label_symbol_id,world_entity_id,context_witness_id,attachment_state)
    VALUES (selected_token_id,selected_label_symbol_id,selected_world_entity_id,
            selected_context_witness_id,1)
    ON CONFLICT DO NOTHING;
    RETURN TRUE;
END;
$$;

-- Persist an empirical per-document learning measurement.  Work quantities are
-- explicit numeric proxies; the theorem-level monotone comparison is available
-- only for same-token workloads via assert_numeric_pnf_learning_nonincrease.
CREATE OR REPLACE FUNCTION execution.record_numeric_pnf_corpus_reuse_measurement(
    selected_run_id BIGINT,
    selected_document_id BIGINT,
    selected_workload_ref TEXT
) RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE run_ref_value TEXT; document_ref_value TEXT; tokens BIGINT; objects BIGINT;
        factors BIGINT; unresolved BIGINT; lexical_reuse BIGINT; entity_reuse BIGINT;
        external_reuse BIGINT; elapsed_us BIGINT; new_id BIGINT;
BEGIN
    SELECT run_ref INTO run_ref_value FROM execution.semantic_pnf_run_identity WHERE run_id=selected_run_id;
    SELECT document_ref INTO document_ref_value FROM execution.semantic_pnf_document_identity WHERE document_id=selected_document_id;
    SELECT count(*) INTO tokens FROM execution.semantic_parser_token
     WHERE run_ref=run_ref_value AND document_ref=document_ref_value AND representation_version=2;
    IF tokens=0 THEN RAISE EXCEPTION 'document has no numeric parser tokens'; END IF;
    SELECT count(*) INTO objects FROM execution.semantic_pnf_object AS object
      JOIN execution.semantic_pnf_region AS region ON region.region_id=object.region_id
     WHERE region.run_id=selected_run_id AND region.document_id=selected_document_id;
    SELECT count(*) INTO factors FROM execution.semantic_pnf_factor AS factor
      JOIN execution.semantic_pnf_region AS region ON region.region_id=factor.region_id
     WHERE region.run_id=selected_run_id AND region.document_id=selected_document_id;
    SELECT COALESCE(sum(funnel.represented_candidate_count),0) INTO unresolved
      FROM execution.semantic_pnf_demand_funnel_v1 AS funnel
     WHERE funnel.run_id=selected_run_id AND funnel.document_id=selected_document_id
       AND funnel.admitted_identity_witness_count=0;
    SELECT count(*) INTO lexical_reuse
      FROM execution.semantic_parser_token AS token
     WHERE token.run_ref=run_ref_value AND token.document_ref=document_ref_value
       AND token.representation_version=2
       AND EXISTS (
           SELECT 1 FROM execution.semantic_parser_token AS prior
            WHERE prior.orth_symbol_id=token.orth_symbol_id
              AND prior.token_id<token.token_id
              AND prior.document_ref<>token.document_ref
       );
    SELECT count(*) INTO entity_reuse
      FROM execution.semantic_pnf_object AS object
      JOIN execution.semantic_pnf_region AS region ON region.region_id=object.region_id
     WHERE region.run_id=selected_run_id AND region.document_id=selected_document_id
       AND EXISTS (SELECT 1 FROM execution.semantic_pnf_corpus_entity_label_cache AS cache
                    WHERE cache.label_symbol_id=object.head_symbol_id);
    SELECT count(*) INTO external_reuse
      FROM execution.semantic_parser_token AS token
     WHERE token.run_ref=run_ref_value AND token.document_ref=document_ref_value
       AND EXISTS (SELECT 1 FROM execution.semantic_pnf_label_world_candidate AS candidate
                    WHERE candidate.label_symbol_id=token.orth_symbol_id);
    SELECT COALESCE(sum((receipt.elapsed_ms*1000)::BIGINT),0) INTO elapsed_us
      FROM execution.semantic_pnf_frontier_stage_receipt AS receipt
     WHERE receipt.run_id=selected_run_id AND receipt.document_id=selected_document_id;

    INSERT INTO execution.semantic_pnf_corpus_reuse_measurement
        (workload_ref,run_id,document_id,token_count,fixed_numeric_work,
         unresolved_resolution_work,reused_lexical_units,reused_entity_units,
         reused_external_units,elapsed_microseconds)
    VALUES (selected_workload_ref,selected_run_id,selected_document_id,tokens,
            tokens+objects+factors,unresolved,lexical_reuse,entity_reuse,external_reuse,elapsed_us)
    RETURNING measurement_id INTO new_id;
    RETURN new_id;
END;
$$;

CREATE OR REPLACE VIEW execution.semantic_pnf_corpus_learning_curve_v1 AS
SELECT measurement.*,
       (measurement.fixed_numeric_work+measurement.unresolved_resolution_work)::NUMERIC
           / measurement.token_count::NUMERIC AS total_work_per_token,
       measurement.unresolved_resolution_work::NUMERIC
           / measurement.token_count::NUMERIC AS unresolved_work_per_token,
       lag(measurement.unresolved_resolution_work::NUMERIC
           / measurement.token_count::NUMERIC)
           OVER (PARTITION BY measurement.workload_ref ORDER BY measurement.measurement_id)
           AS previous_unresolved_work_per_token,
       CASE WHEN lag(measurement.unresolved_resolution_work::NUMERIC
                      / measurement.token_count::NUMERIC)
                      OVER (PARTITION BY measurement.workload_ref ORDER BY measurement.measurement_id) IS NULL
            THEN NULL
            ELSE measurement.unresolved_resolution_work::NUMERIC
                 / measurement.token_count::NUMERIC
                 <= lag(measurement.unresolved_resolution_work::NUMERIC
                         / measurement.token_count::NUMERIC)
                         OVER (PARTITION BY measurement.workload_ref ORDER BY measurement.measurement_id)
       END AS unresolved_work_per_token_nonincreasing
  FROM execution.semantic_pnf_corpus_reuse_measurement AS measurement;

COMMIT;
