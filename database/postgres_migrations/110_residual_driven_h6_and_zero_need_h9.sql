BEGIN;

-- 110 closes the first empirically observed H3 -> H6 -> H9 execution gap.
--
-- Invariants:
--   * signed_residual=0 is a neutral evidence coordinate, never semantic closure;
--   * H6 adds only typed discourse/temporal evidence over represented candidates;
--   * missing H6 evidence is unknown, not refutation;
--   * queue completion is execution state, not consumer sufficiency/resolution;
--   * only an unresolved semantic residual advances to the next horizon;
--   * H9 provider work still requires an explicit consumer external need;
--   * zero explicit external needs is a successful zero-work plan.

-- Evidence classification is numeric and observational.  The fixed evidence_kind
-- text remains available for provenance inspection, but classification does not
-- string-match it.  In particular, the H3 planner-membership rows intentionally
-- have signed_residual=0: they say that a candidate is represented, not that the
-- demand's semantic residual vanished.
CREATE OR REPLACE VIEW execution.semantic_pnf_candidate_evidence_classification_v1 AS
SELECT evidence.evidence_id,
       evidence.demand_id,
       evidence.target_kind,
       evidence.target_id,
       evidence.evidence_family,
       evidence.horizon,
       evidence.signed_residual,
       CASE
           WHEN evidence.signed_residual < 0 THEN -1
           WHEN evidence.signed_residual > 0 THEN 1
           ELSE 0
       END::SMALLINT AS evidence_polarity,
       CASE
           WHEN evidence.signed_residual > 0 THEN 2  -- candidate-supporting pressure
           WHEN evidence.signed_residual < 0 THEN 3  -- explicit pressure against candidate
           WHEN universe.demand_id IS NOT NULL THEN 1 -- represented-neutral evidence
           ELSE 4                                    -- demand-level/other neutral evidence
       END::SMALLINT AS evidence_class,
       evidence.evidence_kind,
       evidence.provenance_ref,
       evidence.source_interface_id,
       evidence.source_region_id,
       evidence.created_at
  FROM execution.semantic_pnf_candidate_evidence AS evidence
  LEFT JOIN execution.semantic_pnf_candidate_universe AS universe
    ON universe.demand_id=evidence.demand_id
   AND universe.target_kind=evidence.target_kind
   AND universe.target_id=evidence.target_id;

CREATE OR REPLACE VIEW execution.semantic_pnf_candidate_evidence_classification_summary_v1 AS
SELECT horizon,evidence_family,evidence_class,evidence_polarity,evidence_kind,
       count(*)::BIGINT AS evidence_rows,
       count(DISTINCT demand_id)::BIGINT AS demand_count,
       count(DISTINCT (target_kind,target_id))::BIGINT AS target_count
  FROM execution.semantic_pnf_candidate_evidence_classification_v1
 GROUP BY horizon,evidence_family,evidence_class,evidence_polarity,evidence_kind;

-- Consumer horizon outcomes are a rebuildable current projection, not a new
-- proof authority.  Proof remains semantic_pnf_frontier_resolution and explicit
-- consumer stopping remains semantic_pnf_consumer_sufficiency_certificate.
-- outcome_state:
--   1 processed_no_evidence
--   2 evidence_observed_unresolved
--   3 consumer_sufficient
--   4 deductive_resolved
CREATE TABLE IF NOT EXISTS execution.semantic_pnf_consumer_horizon_outcome (
    demand_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_demand(demand_id) ON DELETE CASCADE,
    consumer_ref TEXT NOT NULL,
    query_ref TEXT NOT NULL,
    policy_ref TEXT NOT NULL DEFAULT '',
    horizon SMALLINT NOT NULL CHECK (horizon IN (3,6,9)),
    outcome_state SMALLINT NOT NULL CHECK (outcome_state BETWEEN 1 AND 4),
    evidence_count BIGINT NOT NULL CHECK (evidence_count>=0),
    nonneutral_evidence_count BIGINT NOT NULL CHECK (nonneutral_evidence_count>=0),
    represented_candidate_count BIGINT NOT NULL CHECK (represented_candidate_count>=0),
    preferred_candidate_count BIGINT NOT NULL CHECK (preferred_candidate_count>=0),
    proof_unique BOOLEAN NOT NULL,
    consumer_sufficient BOOLEAN NOT NULL,
    residual_required BOOLEAN NOT NULL,
    refreshed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(demand_id,consumer_ref,query_ref,policy_ref,horizon)
);
CREATE INDEX IF NOT EXISTS semantic_pnf_consumer_horizon_outcome_residual_idx
    ON execution.semantic_pnf_consumer_horizon_outcome
       (consumer_ref,query_ref,policy_ref,horizon,demand_id)
    WHERE residual_required;

CREATE OR REPLACE FUNCTION execution.refresh_numeric_pnf_consumer_horizon_outcome(
    selected_run_id BIGINT,
    selected_document_id BIGINT,
    selected_horizon SMALLINT,
    selected_consumer_ref TEXT,
    selected_query_ref TEXT,
    selected_policy_ref TEXT DEFAULT ''
) RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE affected BIGINT := 0;
BEGIN
    IF selected_horizon NOT IN (3,6,9) THEN
        RAISE EXCEPTION 'selected_horizon must be 3, 6, or 9';
    END IF;

    WITH scoped AS MATERIALIZED (
        SELECT demand.demand_id
          FROM execution.semantic_pnf_demand AS demand
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id=demand.source_region_id
          JOIN execution.semantic_pnf_consumer_horizon_work_queue AS work
            ON work.demand_id=demand.demand_id
           AND work.consumer_ref=selected_consumer_ref
           AND work.query_ref=selected_query_ref
           AND work.policy_ref=selected_policy_ref
           AND work.horizon=selected_horizon
         WHERE region.run_id=selected_run_id
           AND region.document_id=selected_document_id
           AND work.work_state=2
    ), evidence_count AS MATERIALIZED (
        SELECT scoped.demand_id,
               count(evidence.evidence_id)::BIGINT AS evidence_count,
               count(evidence.evidence_id) FILTER (
                   WHERE evidence.signed_residual<>0
               )::BIGINT AS nonneutral_evidence_count
          FROM scoped
          LEFT JOIN execution.semantic_pnf_candidate_evidence AS evidence
            ON evidence.demand_id=scoped.demand_id
           AND evidence.horizon<=selected_horizon
         GROUP BY scoped.demand_id
    ), candidate_count AS MATERIALIZED (
        SELECT scoped.demand_id,count(universe.target_id)::BIGINT AS represented_candidate_count
          FROM scoped
          LEFT JOIN execution.semantic_pnf_candidate_universe AS universe
            ON universe.demand_id=scoped.demand_id
         GROUP BY scoped.demand_id
    ), preferred_count AS MATERIALIZED (
        SELECT scoped.demand_id,
               count(preference.target_id) FILTER (WHERE preference.preferred)::BIGINT
                   AS preferred_candidate_count
          FROM scoped
          LEFT JOIN execution.semantic_pnf_candidate_current_preference AS preference
            ON preference.demand_id=scoped.demand_id
           AND preference.horizon=selected_horizon
         GROUP BY scoped.demand_id
    ), state AS MATERIALIZED (
        SELECT scoped.demand_id,
               evidence_count.evidence_count,
               evidence_count.nonneutral_evidence_count,
               candidate_count.represented_candidate_count,
               preferred_count.preferred_candidate_count,
               EXISTS (
                   SELECT 1 FROM execution.semantic_pnf_frontier_resolution AS proof
                    WHERE proof.demand_id=scoped.demand_id
                      AND proof.outcome_state=2
                      AND proof.candidate_count=1
               ) AS proof_unique,
               execution.numeric_pnf_consumer_stop_at_horizon(
                   scoped.demand_id,selected_consumer_ref,selected_query_ref,
                   selected_policy_ref,selected_horizon
               ) AS consumer_sufficient
          FROM scoped
          JOIN evidence_count USING (demand_id)
          JOIN candidate_count USING (demand_id)
          JOIN preferred_count USING (demand_id)
    )
    INSERT INTO execution.semantic_pnf_consumer_horizon_outcome
        (demand_id,consumer_ref,query_ref,policy_ref,horizon,outcome_state,
         evidence_count,nonneutral_evidence_count,represented_candidate_count,
         preferred_candidate_count,proof_unique,consumer_sufficient,
         residual_required,refreshed_at)
    SELECT state.demand_id,selected_consumer_ref,selected_query_ref,selected_policy_ref,
           selected_horizon,
           CASE
               WHEN state.proof_unique THEN 4
               WHEN state.consumer_sufficient THEN 3
               WHEN state.evidence_count=0 THEN 1
               ELSE 2
           END::SMALLINT,
           state.evidence_count,state.nonneutral_evidence_count,
           state.represented_candidate_count,state.preferred_candidate_count,
           state.proof_unique,state.consumer_sufficient,
           NOT state.proof_unique AND NOT state.consumer_sufficient,
           CURRENT_TIMESTAMP
      FROM state
    ON CONFLICT(demand_id,consumer_ref,query_ref,policy_ref,horizon)
    DO UPDATE SET
        outcome_state=EXCLUDED.outcome_state,
        evidence_count=EXCLUDED.evidence_count,
        nonneutral_evidence_count=EXCLUDED.nonneutral_evidence_count,
        represented_candidate_count=EXCLUDED.represented_candidate_count,
        preferred_candidate_count=EXCLUDED.preferred_candidate_count,
        proof_unique=EXCLUDED.proof_unique,
        consumer_sufficient=EXCLUDED.consumer_sufficient,
        residual_required=EXCLUDED.residual_required,
        refreshed_at=EXCLUDED.refreshed_at;
    GET DIAGNOSTICS affected=ROW_COUNT;
    RETURN affected;
END;
$$;

-- Real H6 evidence producer.  It compares a demand's proof-neutral structural
-- source object with represented object candidates through typed PNF factor
-- participation.  Mere co-presence, lexical equality, and missing relations are
-- not evidence.
--
-- A matching (factor type,predicate,role) signature contributes +1 discourse
-- pressure.  If both occurrences additionally carry the same explicit nonzero
-- temporal state, that contributes a separate +1 temporal witness.  Distinct
-- signatures are collapsed before insertion so repeated factor occurrences do
-- not create a factor-pair Cartesian explosion.
CREATE OR REPLACE FUNCTION execution.refresh_numeric_pnf_h6_discourse_temporal_evidence_for_consumer(
    selected_run_id BIGINT,
    selected_document_id BIGINT,
    selected_consumer_ref TEXT,
    selected_query_ref TEXT,
    selected_policy_ref TEXT DEFAULT '',
    selected_reprocess_completed BOOLEAN DEFAULT FALSE
) RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE affected BIGINT := 0;
BEGIN
    WITH ready AS MATERIALIZED (
        SELECT demand.demand_id,demand.source_object_id,demand.source_interface_id,
               demand.source_region_id,demand.expected_factor_type_symbol_id,
               demand.role_symbol_id
          FROM execution.semantic_pnf_consumer_horizon_work_queue AS work
          JOIN execution.semantic_pnf_demand AS demand
            ON demand.demand_id=work.demand_id
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id=demand.source_region_id
         WHERE work.consumer_ref=selected_consumer_ref
           AND work.query_ref=selected_query_ref
           AND work.policy_ref=selected_policy_ref
           AND work.horizon=6
           AND (work.work_state=1 OR (selected_reprocess_completed AND work.work_state=2))
           AND region.run_id=selected_run_id
           AND region.document_id=selected_document_id
           AND demand.source_object_id IS NOT NULL
           AND NOT execution.numeric_pnf_consumer_stop_at_horizon(
               demand.demand_id,selected_consumer_ref,selected_query_ref,
               selected_policy_ref,3
           )
           AND NOT EXISTS (
               SELECT 1 FROM execution.semantic_pnf_frontier_resolution AS proof
                WHERE proof.demand_id=demand.demand_id
                  AND proof.outcome_state=2 AND proof.candidate_count=1
           )
    ), source_signature AS MATERIALIZED (
        SELECT DISTINCT ready.demand_id,ready.source_object_id,
               ready.source_interface_id,ready.source_region_id,
               factor.factor_type_symbol_id,factor.predicate_symbol_id,
               edge.role_symbol_id,factor.temporal_state
          FROM ready
          JOIN execution.semantic_pnf_hyperedge AS edge
            ON edge.object_id=ready.source_object_id
          JOIN execution.semantic_pnf_factor AS factor
            ON factor.factor_id=edge.factor_id AND factor.active
         WHERE (ready.expected_factor_type_symbol_id IS NULL
                OR factor.factor_type_symbol_id=ready.expected_factor_type_symbol_id)
           AND (ready.role_symbol_id IS NULL
                OR edge.role_symbol_id=ready.role_symbol_id)
    ), candidate AS MATERIALIZED (
        SELECT DISTINCT state.demand_id,state.target_kind,state.target_id
          FROM execution.semantic_pnf_candidate_state_v1 AS state
          JOIN ready ON ready.demand_id=state.demand_id
         WHERE state.target_kind=1
           AND state.represented_possible
           AND state.admissible
           AND state.target_id<>ready.source_object_id
    ), matched AS MATERIALIZED (
        SELECT DISTINCT candidate.demand_id,candidate.target_kind,candidate.target_id,
               source_signature.source_interface_id,source_signature.source_region_id,
               source_signature.factor_type_symbol_id,
               source_signature.predicate_symbol_id,source_signature.role_symbol_id,
               source_signature.temporal_state AS source_temporal_state,
               candidate_factor.temporal_state AS candidate_temporal_state
          FROM candidate
          JOIN execution.semantic_pnf_hyperedge AS candidate_edge
            ON candidate_edge.object_id=candidate.target_id
          JOIN execution.semantic_pnf_factor AS candidate_factor
            ON candidate_factor.factor_id=candidate_edge.factor_id
           AND candidate_factor.active
          JOIN source_signature
            ON source_signature.demand_id=candidate.demand_id
           AND source_signature.role_symbol_id=candidate_edge.role_symbol_id
           AND source_signature.factor_type_symbol_id=candidate_factor.factor_type_symbol_id
           AND source_signature.predicate_symbol_id=candidate_factor.predicate_symbol_id
    ), evidence_rows AS (
        SELECT matched.demand_id,matched.target_kind,matched.target_id,
               'h6:discourse:' || matched.factor_type_symbol_id::TEXT || ':' ||
                   matched.predicate_symbol_id::TEXT || ':' || matched.role_symbol_id::TEXT
                   AS evidence_ref,
               1::BIGINT AS signed_residual,
               'h6_discourse_factor_role_signature'::TEXT AS evidence_kind,
               'numeric-factor-signature'::TEXT AS provenance_ref,
               matched.source_interface_id,matched.source_region_id
          FROM matched
        UNION ALL
        SELECT matched.demand_id,matched.target_kind,matched.target_id,
               'h6:temporal:' || matched.factor_type_symbol_id::TEXT || ':' ||
                   matched.predicate_symbol_id::TEXT || ':' || matched.role_symbol_id::TEXT || ':' ||
                   matched.source_temporal_state::TEXT AS evidence_ref,
               1::BIGINT AS signed_residual,
               'h6_temporal_factor_role_signature'::TEXT AS evidence_kind,
               'numeric-temporal-state'::TEXT AS provenance_ref,
               matched.source_interface_id,matched.source_region_id
          FROM matched
         WHERE matched.source_temporal_state<>0
           AND matched.candidate_temporal_state=matched.source_temporal_state
    )
    INSERT INTO execution.semantic_pnf_candidate_evidence
        (demand_id,target_kind,target_id,evidence_ref,evidence_family,horizon,
         signed_residual,evidence_kind,provenance_ref,source_interface_id,
         source_region_id)
    SELECT DISTINCT evidence_rows.demand_id,evidence_rows.target_kind,
           evidence_rows.target_id,evidence_rows.evidence_ref,2,6,
           evidence_rows.signed_residual,evidence_rows.evidence_kind,
           evidence_rows.provenance_ref,evidence_rows.source_interface_id,
           evidence_rows.source_region_id
      FROM evidence_rows
    ON CONFLICT(demand_id,target_kind,target_id,evidence_ref) DO NOTHING;
    GET DIAGNOSTICS affected=ROW_COUNT;
    RETURN affected;
END;
$$;

-- Supersede the 094 queue transition: processing and semantic stopping are now
-- explicitly separated.  The current horizon is marked processed, its outcome
-- projection is rebuilt, and only rows whose outcome still carries a semantic
-- residual are present as ready work at the next horizon.
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

    UPDATE execution.semantic_pnf_consumer_horizon_work_queue AS work
       SET work_state=2,completed_at=CURRENT_TIMESTAMP
      FROM execution.semantic_pnf_demand AS demand
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id=demand.source_region_id
     WHERE work.demand_id=demand.demand_id
       AND work.consumer_ref=selected_consumer_ref
       AND work.query_ref=selected_query_ref
       AND work.policy_ref=selected_policy_ref
       AND work.horizon=completed_horizon
       AND work.work_state=1
       AND region.run_id=selected_run_id
       AND region.document_id=selected_document_id;

    PERFORM execution.refresh_numeric_pnf_consumer_horizon_outcome(
        selected_run_id,selected_document_id,completed_horizon,
        selected_consumer_ref,selected_query_ref,selected_policy_ref
    );

    -- Remove only the rebuildable next-horizon execution projection for demands
    -- that no longer have a residual.  Evidence, proofs, certificates, and the
    -- completed current-horizon row remain untouched.
    DELETE FROM execution.semantic_pnf_consumer_horizon_work_queue AS next_work
     USING execution.semantic_pnf_consumer_horizon_outcome AS outcome,
           execution.semantic_pnf_demand AS demand,
           execution.semantic_pnf_region AS region
     WHERE next_work.demand_id=outcome.demand_id
       AND demand.demand_id=outcome.demand_id
       AND region.region_id=demand.source_region_id
       AND next_work.consumer_ref=selected_consumer_ref
       AND next_work.query_ref=selected_query_ref
       AND next_work.policy_ref=selected_policy_ref
       AND next_work.horizon=next_horizon
       AND outcome.consumer_ref=selected_consumer_ref
       AND outcome.query_ref=selected_query_ref
       AND outcome.policy_ref=selected_policy_ref
       AND outcome.horizon=completed_horizon
       AND NOT outcome.residual_required
       AND region.run_id=selected_run_id
       AND region.document_id=selected_document_id;

    INSERT INTO execution.semantic_pnf_consumer_horizon_work_queue
        (demand_id,consumer_ref,query_ref,policy_ref,horizon,work_state,completed_at)
    SELECT outcome.demand_id,selected_consumer_ref,selected_query_ref,
           selected_policy_ref,next_horizon,1,NULL
      FROM execution.semantic_pnf_consumer_horizon_outcome AS outcome
      JOIN execution.semantic_pnf_demand AS demand ON demand.demand_id=outcome.demand_id
      JOIN execution.semantic_pnf_region AS region ON region.region_id=demand.source_region_id
     WHERE outcome.consumer_ref=selected_consumer_ref
       AND outcome.query_ref=selected_query_ref
       AND outcome.policy_ref=selected_policy_ref
       AND outcome.horizon=completed_horizon
       AND outcome.residual_required
       AND region.run_id=selected_run_id
       AND region.document_id=selected_document_id
    ON CONFLICT(demand_id,consumer_ref,query_ref,policy_ref,horizon)
    DO UPDATE SET work_state=1,completed_at=NULL;
    GET DIAGNOSTICS affected=ROW_COUNT;
    RETURN affected;
END;
$$;

CREATE OR REPLACE FUNCTION execution.process_numeric_pnf_h6_for_consumer(
    selected_run_id BIGINT,
    selected_document_id BIGINT,
    selected_consumer_ref TEXT,
    selected_query_ref TEXT,
    selected_policy_ref TEXT DEFAULT '',
    selected_reprocess_completed BOOLEAN DEFAULT FALSE
) RETURNS TABLE(
    inserted_h6_evidence BIGINT,
    h9_residual_work BIGINT
) LANGUAGE plpgsql AS $$
BEGIN
    inserted_h6_evidence := execution.refresh_numeric_pnf_h6_discourse_temporal_evidence_for_consumer(
        selected_run_id,selected_document_id,selected_consumer_ref,selected_query_ref,
        selected_policy_ref,selected_reprocess_completed
    );

    -- Preference is inductive only.  This call does not write proof authority.
    PERFORM execution.refresh_numeric_pnf_progressive_preferences(
        selected_run_id,selected_document_id,6
    );

    h9_residual_work := execution.advance_numeric_pnf_horizon_work_for_consumer(
        selected_run_id,selected_document_id,6,selected_consumer_ref,
        selected_query_ref,selected_policy_ref
    );
    RETURN NEXT;
END;
$$;

-- Final 096 planner replacement.  The old PL/pgSQL RECORD variable had the
-- same identifier as the table alias; an empty result exposed an unassigned
-- record path on PostgreSQL.  Use distinct names and make zero explicit needs a
-- first-class zero-work result.
CREATE OR REPLACE FUNCTION execution.plan_numeric_pnf_external_demands_for_consumer(
    selected_run_id BIGINT,
    selected_document_id BIGINT,
    selected_consumer_ref TEXT,
    selected_query_ref TEXT,
    selected_policy_ref TEXT DEFAULT ''
) RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE need_row RECORD; candidate_row RECORD; attachment_row RECORD;
        request_id_value BIGINT; affected BIGINT := 0;
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM execution.semantic_pnf_consumer_external_need AS external_need
          JOIN execution.semantic_pnf_consumer_horizon_work_queue AS work
            ON work.demand_id=external_need.demand_id
           AND work.consumer_ref=external_need.consumer_ref
           AND work.query_ref=external_need.query_ref
           AND work.policy_ref=external_need.policy_ref
           AND work.horizon=9 AND work.work_state=1
          JOIN execution.semantic_pnf_demand AS demand
            ON demand.demand_id=external_need.demand_id
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id=demand.source_region_id
         WHERE external_need.active
           AND external_need.consumer_ref=selected_consumer_ref
           AND external_need.query_ref=selected_query_ref
           AND external_need.policy_ref=selected_policy_ref
           AND region.run_id=selected_run_id
           AND region.document_id=selected_document_id
           AND NOT execution.numeric_pnf_consumer_stop_at_horizon(
               external_need.demand_id,external_need.consumer_ref,
               external_need.query_ref,external_need.policy_ref,6
           )
    ) THEN
        PERFORM execution.refresh_numeric_pnf_external_request_cache_state();
        RETURN 0;
    END IF;

    FOR need_row IN
        SELECT external_need.*,demand.lexical_symbol_id,demand.source_object_id
          FROM execution.semantic_pnf_consumer_external_need AS external_need
          JOIN execution.semantic_pnf_consumer_horizon_work_queue AS work
            ON work.demand_id=external_need.demand_id
           AND work.consumer_ref=external_need.consumer_ref
           AND work.query_ref=external_need.query_ref
           AND work.policy_ref=external_need.policy_ref
           AND work.horizon=9 AND work.work_state=1
          JOIN execution.semantic_pnf_demand AS demand
            ON demand.demand_id=external_need.demand_id
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id=demand.source_region_id
         WHERE external_need.active
           AND external_need.consumer_ref=selected_consumer_ref
           AND external_need.query_ref=selected_query_ref
           AND external_need.policy_ref=selected_policy_ref
           AND region.run_id=selected_run_id
           AND region.document_id=selected_document_id
           AND NOT execution.numeric_pnf_consumer_stop_at_horizon(
               external_need.demand_id,external_need.consumer_ref,
               external_need.query_ref,external_need.policy_ref,6
           )
         ORDER BY external_need.priority,external_need.demand_id
    LOOP
        IF need_row.lexical_symbol_id IS NULL AND need_row.need_kind IN (1,2) THEN
            CONTINUE;
        END IF;

        IF need_row.need_kind IN (1,2)
           AND NOT EXISTS (
               SELECT 1 FROM execution.semantic_pnf_label_world_candidate AS cached
                WHERE cached.label_symbol_id=need_row.lexical_symbol_id
           ) THEN
            request_id_value := execution.ensure_numeric_pnf_external_request(
                need_row.provider_id,1,need_row.lexical_symbol_id,NULL,NULL,NULL,
                need_row.need_revision,need_row.priority
            );
            INSERT INTO execution.semantic_pnf_external_request_member
                (request_id,demand_id,consumer_ref,query_ref,policy_ref,need_kind)
            VALUES (request_id_value,need_row.demand_id,need_row.consumer_ref,
                    need_row.query_ref,need_row.policy_ref,need_row.need_kind)
            ON CONFLICT DO NOTHING;
            affected:=affected+1;
            CONTINUE;
        END IF;

        IF need_row.need_kind=1 THEN
            CONTINUE;
        ELSIF need_row.need_kind=2 THEN
            FOR candidate_row IN
                SELECT cached.world_entity_id
                  FROM execution.semantic_pnf_label_world_candidate AS cached
                 WHERE cached.label_symbol_id=need_row.lexical_symbol_id
                 ORDER BY cached.candidate_ordinal,cached.world_entity_id
            LOOP
                request_id_value := execution.ensure_numeric_pnf_external_request(
                    need_row.provider_id,2,need_row.lexical_symbol_id,
                    candidate_row.world_entity_id,
                    need_row.provider_property_numeric_id,need_row.axis_kind,
                    need_row.need_revision,need_row.priority
                );
                INSERT INTO execution.semantic_pnf_external_request_member
                    (request_id,demand_id,consumer_ref,query_ref,policy_ref,need_kind)
                VALUES (request_id_value,need_row.demand_id,need_row.consumer_ref,
                        need_row.query_ref,need_row.policy_ref,need_row.need_kind)
                ON CONFLICT DO NOTHING;
                affected:=affected+1;
            END LOOP;
        ELSE
            IF need_row.source_object_id IS NULL THEN
                CONTINUE;
            END IF;
            FOR attachment_row IN
                SELECT DISTINCT attachment.world_entity_id,attachment.label_symbol_id
                  FROM execution.semantic_pnf_object_token_support AS support
                  JOIN execution.semantic_pnf_mention_world_attachment AS attachment
                    ON attachment.token_id=support.token_id
                 WHERE support.object_id=need_row.source_object_id
                   AND attachment.attachment_state=1
            LOOP
                request_id_value := execution.ensure_numeric_pnf_external_request(
                    need_row.provider_id,3,attachment_row.label_symbol_id,
                    attachment_row.world_entity_id,NULL,NULL,
                    need_row.need_revision,need_row.priority
                );
                INSERT INTO execution.semantic_pnf_external_request_member
                    (request_id,demand_id,consumer_ref,query_ref,policy_ref,need_kind)
                VALUES (request_id_value,need_row.demand_id,need_row.consumer_ref,
                        need_row.query_ref,need_row.policy_ref,need_row.need_kind)
                ON CONFLICT DO NOTHING;
                affected:=affected+1;
            END LOOP;
        END IF;
    END LOOP;

    PERFORM execution.refresh_numeric_pnf_external_request_cache_state();
    RETURN affected;
END;
$$;

-- One compact funnel surface for empirical reruns.  H9-ready is not external
-- work: external_need_count remains an independent explicit consumer decision.
CREATE OR REPLACE VIEW execution.semantic_pnf_consumer_horizon_funnel_v1 AS
SELECT work.consumer_ref,work.query_ref,work.policy_ref,work.horizon,
       work.work_state,
       count(*)::BIGINT AS work_rows,
       count(outcome.demand_id)::BIGINT AS classified_rows,
       count(*) FILTER (WHERE outcome.outcome_state=1)::BIGINT AS processed_no_evidence,
       count(*) FILTER (WHERE outcome.outcome_state=2)::BIGINT AS evidence_observed_unresolved,
       count(*) FILTER (WHERE outcome.outcome_state=3)::BIGINT AS consumer_sufficient,
       count(*) FILTER (WHERE outcome.outcome_state=4)::BIGINT AS deductive_resolved,
       count(*) FILTER (WHERE outcome.residual_required)::BIGINT AS residual_rows,
       count(*) FILTER (
           WHERE EXISTS (
               SELECT 1 FROM execution.semantic_pnf_consumer_external_need AS need
                WHERE need.demand_id=work.demand_id
                  AND need.consumer_ref=work.consumer_ref
                  AND need.query_ref=work.query_ref
                  AND need.policy_ref=work.policy_ref
                  AND need.active
           )
       )::BIGINT AS explicit_external_need_rows
  FROM execution.semantic_pnf_consumer_horizon_work_queue AS work
  LEFT JOIN execution.semantic_pnf_consumer_horizon_outcome AS outcome
    ON outcome.demand_id=work.demand_id
   AND outcome.consumer_ref=work.consumer_ref
   AND outcome.query_ref=work.query_ref
   AND outcome.policy_ref=work.policy_ref
   AND outcome.horizon=work.horizon
 GROUP BY work.consumer_ref,work.query_ref,work.policy_ref,work.horizon,work.work_state;

COMMIT;
