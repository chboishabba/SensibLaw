BEGIN;

-- Numeric incremental runtime economy ----------------------------------------
-- Instantiates the Agda numeric/incremental constitution from dashi_agda #533.
-- Strings may still cross explicit ingestion/external/rendering boundaries, but
-- ordinary post-tokenisation semantic execution uses integer ids.

-- Hot symbolic constants are resolved once when the vocabulary row appears.
-- Expensive parser/object joins below use only numeric symbol ids.
CREATE TABLE IF NOT EXISTS execution.semantic_pnf_hot_symbol_constant (
    constant_id SMALLINT PRIMARY KEY,
    constant_name TEXT NOT NULL UNIQUE,
    symbol_id BIGINT NOT NULL
        REFERENCES execution.semantic_symbol(symbol_id) ON DELETE RESTRICT,
    UNIQUE (constant_id, symbol_id)
);

CREATE OR REPLACE FUNCTION execution.refresh_numeric_pnf_hot_symbol_constants()
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE affected BIGINT := 0;
BEGIN
    INSERT INTO execution.semantic_pnf_hot_symbol_constant
        (constant_id, constant_name, symbol_id)
    SELECT definition.constant_id,
           definition.constant_name,
           symbol.symbol_id
      FROM (VALUES
          (1::SMALLINT, 'pos:PROPN'::TEXT, 3::SMALLINT, 'PROPN'::TEXT),
          (2::SMALLINT, 'pos:NOUN'::TEXT, 3::SMALLINT, 'NOUN'::TEXT),
          (3::SMALLINT, 'dependency:appos'::TEXT, 5::SMALLINT, 'appos'::TEXT),
          (4::SMALLINT, 'entity_type:PERSON'::TEXT, 8::SMALLINT, 'PERSON'::TEXT)
      ) AS definition(constant_id, constant_name, kind_id, symbol_text)
      JOIN execution.semantic_symbol AS symbol
        ON symbol.kind_id = definition.kind_id
       AND symbol.symbol_text = definition.symbol_text
    ON CONFLICT (constant_id) DO UPDATE SET
        constant_name = EXCLUDED.constant_name,
        symbol_id = EXCLUDED.symbol_id;
    GET DIAGNOSTICS affected = ROW_COUNT;
    RETURN affected;
END;
$$;

SELECT execution.refresh_numeric_pnf_hot_symbol_constants();

CREATE OR REPLACE FUNCTION execution.refresh_numeric_pnf_hot_symbol_constant_on_insert()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF (NEW.kind_id = 3 AND NEW.symbol_text IN ('PROPN', 'NOUN'))
       OR (NEW.kind_id = 5 AND NEW.symbol_text = 'appos')
       OR (NEW.kind_id = 8 AND NEW.symbol_text = 'PERSON') THEN
        PERFORM execution.refresh_numeric_pnf_hot_symbol_constants();
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS semantic_symbol_refresh_hot_constant
    ON execution.semantic_symbol;
CREATE TRIGGER semantic_symbol_refresh_hot_constant
AFTER INSERT OR UPDATE OF kind_id, symbol_text ON execution.semantic_symbol
FOR EACH ROW EXECUTE FUNCTION execution.refresh_numeric_pnf_hot_symbol_constant_on_insert();

-- Re-declare the 083 parser/object anchor with numeric constant predicates.
CREATE OR REPLACE FUNCTION execution.numeric_pnf_document_parser_object_anchor(
    selected_run_id BIGINT,
    selected_document_id BIGINT
)
RETURNS TABLE(token_id BIGINT, sentence_id BIGINT, object_id BIGINT)
LANGUAGE sql
STABLE
AS $$
WITH identity AS (
    SELECT run_identity.run_ref,
           document_identity.document_ref
      FROM execution.semantic_pnf_run_identity AS run_identity
      CROSS JOIN execution.semantic_pnf_document_identity AS document_identity
     WHERE run_identity.run_id = selected_run_id
       AND document_identity.document_id = selected_document_id
), constant AS MATERIALIZED (
    SELECT max(symbol_id) FILTER (WHERE constant_id = 1) AS propn_id,
           max(symbol_id) FILTER (WHERE constant_id = 2) AS noun_id,
           max(symbol_id) FILTER (WHERE constant_id = 3) AS appos_id
      FROM execution.semantic_pnf_hot_symbol_constant
), doc_token AS MATERIALIZED (
    SELECT token.token_id,
           token.sentence_id,
           token.sentence_ref,
           token.start_char,
           token.end_char,
           token.orth_symbol_id,
           token.lemma_symbol_id,
           token.pos_symbol_id,
           token.dependency_symbol_id,
           token.head_token_id
      FROM execution.semantic_parser_token AS token
      JOIN identity ON TRUE
     WHERE token.run_ref = identity.run_ref
       AND token.document_ref = identity.document_ref
       AND token.representation_version = 2
), needed_token AS MATERIALIZED (
    SELECT DISTINCT token.*
      FROM doc_token AS token
      CROSS JOIN constant
     WHERE token.pos_symbol_id IN (constant.propn_id, constant.noun_id)
        OR token.dependency_symbol_id = constant.appos_id
        OR EXISTS (
            SELECT 1
              FROM doc_token AS child
             WHERE child.head_token_id = token.token_id
               AND child.dependency_symbol_id = constant.appos_id
        )
), exact_support AS MATERIALIZED (
    SELECT token.token_id,
           token.sentence_id,
           support.object_id
      FROM needed_token AS token
      JOIN execution.semantic_pnf_object_token_support AS support
        ON support.token_id = token.token_id
      JOIN execution.semantic_pnf_object AS object
        ON object.object_id = support.object_id
       AND object.head_symbol_id IN (token.lemma_symbol_id, token.orth_symbol_id)
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id = object.region_id
       AND region.run_id = selected_run_id
       AND region.document_id = selected_document_id
), exact_anchor AS (
    SELECT support.token_id,
           min(support.sentence_id) AS sentence_id,
           min(support.object_id) AS object_id
      FROM exact_support AS support
     GROUP BY support.token_id
    HAVING count(DISTINCT support.object_id) = 1
), token_with_any_support AS MATERIALIZED (
    SELECT DISTINCT token_id FROM exact_support
), fallback_candidate AS (
    SELECT token.token_id,
           token.sentence_id,
           object.object_id,
           (region.end_char - region.start_char) AS region_span,
           min(region.end_char - region.start_char)
               OVER (PARTITION BY token.token_id) AS minimum_region_span
      FROM needed_token AS token
      LEFT JOIN token_with_any_support AS has_support
        ON has_support.token_id = token.token_id
      JOIN execution.semantic_pnf_region AS region
        ON region.run_id = selected_run_id
       AND region.document_id = selected_document_id
       AND token.start_char >= region.start_char
       AND token.end_char <= region.end_char
      JOIN execution.semantic_pnf_object AS object
        ON object.region_id = region.region_id
       AND object.head_symbol_id IN (token.lemma_symbol_id, token.orth_symbol_id)
     WHERE has_support.token_id IS NULL
), fallback_smallest AS (
    SELECT token_id, sentence_id, object_id
      FROM fallback_candidate
     WHERE region_span = minimum_region_span
), fallback_anchor AS (
    SELECT token_id,
           min(sentence_id) AS sentence_id,
           min(object_id) AS object_id
      FROM fallback_smallest
     GROUP BY token_id
    HAVING count(DISTINCT object_id) = 1
)
SELECT token_id, sentence_id, object_id FROM exact_anchor
UNION ALL
SELECT token_id, sentence_id, object_id FROM fallback_anchor;
$$;

-- Bounded numeric dependency ancestry.  This is immutable parser observation
-- geometry and avoids rediscovering short dependency paths in later semantics.
CREATE TABLE IF NOT EXISTS execution.semantic_parser_token_ancestor (
    token_id BIGINT NOT NULL
        REFERENCES execution.semantic_parser_token(token_id) ON DELETE CASCADE,
    ancestor_token_id BIGINT NOT NULL
        REFERENCES execution.semantic_parser_token(token_id) ON DELETE CASCADE,
    distance SMALLINT NOT NULL CHECK (distance BETWEEN 1 AND 8),
    PRIMARY KEY (token_id, ancestor_token_id),
    UNIQUE (token_id, distance)
);
CREATE INDEX IF NOT EXISTS semantic_parser_token_ancestor_reverse_idx
    ON execution.semantic_parser_token_ancestor
       (ancestor_token_id, distance, token_id);

CREATE OR REPLACE FUNCTION execution.refresh_numeric_parser_token_ancestors(
    selected_run_ref TEXT,
    selected_document_ref TEXT,
    selected_max_depth SMALLINT DEFAULT 8
)
RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE affected BIGINT := 0;
BEGIN
    IF selected_max_depth < 1 OR selected_max_depth > 8 THEN
        RAISE EXCEPTION 'selected_max_depth must be in 1..8';
    END IF;
    DELETE FROM execution.semantic_parser_token_ancestor AS closure
     USING execution.semantic_parser_token AS token
     WHERE closure.token_id = token.token_id
       AND token.run_ref = selected_run_ref
       AND token.document_ref = selected_document_ref;

    WITH RECURSIVE walk(token_id, ancestor_token_id, distance) AS (
        SELECT token.token_id, token.head_token_id, 1::SMALLINT
          FROM execution.semantic_parser_token AS token
         WHERE token.run_ref = selected_run_ref
           AND token.document_ref = selected_document_ref
           AND token.representation_version = 2
           AND token.head_token_id IS NOT NULL
           AND token.head_token_id <> token.token_id
        UNION ALL
        SELECT walk.token_id, parent.head_token_id, (walk.distance + 1)::SMALLINT
          FROM walk
          JOIN execution.semantic_parser_token AS parent
            ON parent.token_id = walk.ancestor_token_id
         WHERE walk.distance < selected_max_depth
           AND parent.head_token_id IS NOT NULL
           AND parent.head_token_id <> parent.token_id
    )
    INSERT INTO execution.semantic_parser_token_ancestor
        (token_id, ancestor_token_id, distance)
    SELECT DISTINCT ON (token_id, ancestor_token_id)
           token_id, ancestor_token_id, distance
      FROM walk
     WHERE ancestor_token_id IS NOT NULL
     ORDER BY token_id, ancestor_token_id, distance
    ON CONFLICT (token_id, ancestor_token_id) DO UPDATE
       SET distance = LEAST(
           execution.semantic_parser_token_ancestor.distance,
           EXCLUDED.distance
       );
    GET DIAGNOSTICS affected = ROW_COUNT;
    RETURN affected;
END;
$$;

-- Sparse support fanout observatory and selective composite index.
CREATE INDEX IF NOT EXISTS semantic_pnf_object_token_support_object_token_idx
    ON execution.semantic_pnf_object_token_support(object_id, token_id);

CREATE OR REPLACE VIEW execution.semantic_pnf_structural_support_fanout_v1 AS
WITH argument AS (
    SELECT edge.object_id,
           count(*)::BIGINT AS factor_argument_occurrences
      FROM execution.semantic_pnf_hyperedge AS edge
     GROUP BY edge.object_id
), support AS (
    SELECT support.object_id,
           count(*)::BIGINT AS support_edges
      FROM execution.semantic_pnf_object_token_support AS support
     GROUP BY support.object_id
)
SELECT argument.object_id,
       argument.factor_argument_occurrences,
       COALESCE(support.support_edges, 0) AS support_edges,
       CASE WHEN argument.factor_argument_occurrences = 0 THEN NULL
            ELSE COALESCE(support.support_edges, 0)::NUMERIC
                 / argument.factor_argument_occurrences::NUMERIC
       END AS support_fanout
  FROM argument
  LEFT JOIN support USING (object_id);

-- Hot current-state projections.  Append-only event history remains authority;
-- these tables are rebuildable projections for the high-frequency read path.
CREATE TABLE IF NOT EXISTS execution.semantic_pnf_candidate_current_execution (
    demand_id BIGINT NOT NULL,
    target_kind SMALLINT NOT NULL,
    target_id BIGINT NOT NULL,
    event_id BIGINT NOT NULL,
    event_kind SMALLINT NOT NULL,
    active_budget INTEGER,
    reason_ref TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (demand_id, target_kind, target_id)
);
CREATE TABLE IF NOT EXISTS execution.semantic_pnf_candidate_current_admissibility (
    demand_id BIGINT NOT NULL,
    target_kind SMALLINT NOT NULL,
    target_id BIGINT NOT NULL,
    event_id BIGINT NOT NULL,
    event_kind SMALLINT NOT NULL,
    evidence_id BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (demand_id, target_kind, target_id)
);
CREATE TABLE IF NOT EXISTS execution.semantic_pnf_candidate_current_preference (
    demand_id BIGINT NOT NULL,
    target_kind SMALLINT NOT NULL,
    target_id BIGINT NOT NULL,
    horizon SMALLINT NOT NULL,
    revision BIGINT NOT NULL,
    preferred BOOLEAN NOT NULL,
    margin BIGINT NOT NULL,
    evidence_count BIGINT NOT NULL,
    preference_id BIGINT NOT NULL,
    PRIMARY KEY (demand_id, target_kind, target_id, horizon)
);

CREATE OR REPLACE FUNCTION execution.rebuild_numeric_pnf_candidate_current_state()
RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE affected BIGINT := 0; n BIGINT := 0;
BEGIN
    TRUNCATE execution.semantic_pnf_candidate_current_execution,
             execution.semantic_pnf_candidate_current_admissibility,
             execution.semantic_pnf_candidate_current_preference;
    INSERT INTO execution.semantic_pnf_candidate_current_execution
    SELECT demand_id, target_kind, target_id, event_id, event_kind,
           active_budget, reason_ref, created_at
      FROM execution.semantic_pnf_candidate_latest_execution;
    GET DIAGNOSTICS n = ROW_COUNT; affected := affected + n;
    INSERT INTO execution.semantic_pnf_candidate_current_admissibility
    SELECT demand_id, target_kind, target_id, event_id, event_kind,
           evidence_id, created_at
      FROM execution.semantic_pnf_candidate_latest_admissibility;
    GET DIAGNOSTICS n = ROW_COUNT; affected := affected + n;
    INSERT INTO execution.semantic_pnf_candidate_current_preference
    SELECT demand_id, target_kind, target_id, horizon, revision,
           preferred, margin, evidence_count, preference_id
      FROM execution.semantic_pnf_candidate_latest_preference;
    GET DIAGNOSTICS n = ROW_COUNT; affected := affected + n;
    RETURN affected;
END;
$$;
SELECT execution.rebuild_numeric_pnf_candidate_current_state();

CREATE OR REPLACE FUNCTION execution.project_numeric_pnf_current_execution()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO execution.semantic_pnf_candidate_current_execution
        (demand_id,target_kind,target_id,event_id,event_kind,
         active_budget,reason_ref,created_at)
    VALUES (NEW.demand_id,NEW.target_kind,NEW.target_id,NEW.event_id,NEW.event_kind,
            NEW.active_budget,NEW.reason_ref,NEW.created_at)
    ON CONFLICT (demand_id,target_kind,target_id) DO UPDATE SET
        event_id=EXCLUDED.event_id,event_kind=EXCLUDED.event_kind,
        active_budget=EXCLUDED.active_budget,reason_ref=EXCLUDED.reason_ref,
        created_at=EXCLUDED.created_at
    WHERE execution.semantic_pnf_candidate_current_execution.event_id < EXCLUDED.event_id;
    RETURN NEW;
END;
$$;
CREATE OR REPLACE FUNCTION execution.project_numeric_pnf_current_admissibility()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO execution.semantic_pnf_candidate_current_admissibility
        (demand_id,target_kind,target_id,event_id,event_kind,evidence_id,created_at)
    VALUES (NEW.demand_id,NEW.target_kind,NEW.target_id,NEW.event_id,NEW.event_kind,
            NEW.evidence_id,NEW.created_at)
    ON CONFLICT (demand_id,target_kind,target_id) DO UPDATE SET
        event_id=EXCLUDED.event_id,event_kind=EXCLUDED.event_kind,
        evidence_id=EXCLUDED.evidence_id,created_at=EXCLUDED.created_at
    WHERE execution.semantic_pnf_candidate_current_admissibility.event_id < EXCLUDED.event_id;
    RETURN NEW;
END;
$$;
CREATE OR REPLACE FUNCTION execution.project_numeric_pnf_current_preference()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO execution.semantic_pnf_candidate_current_preference
        (demand_id,target_kind,target_id,horizon,revision,preferred,margin,
         evidence_count,preference_id)
    VALUES (NEW.demand_id,NEW.target_kind,NEW.target_id,NEW.horizon,NEW.revision,
            NEW.preferred,NEW.margin,NEW.evidence_count,NEW.preference_id)
    ON CONFLICT (demand_id,target_kind,target_id,horizon) DO UPDATE SET
        revision=EXCLUDED.revision,preferred=EXCLUDED.preferred,
        margin=EXCLUDED.margin,evidence_count=EXCLUDED.evidence_count,
        preference_id=EXCLUDED.preference_id
    WHERE execution.semantic_pnf_candidate_current_preference.preference_id
          < EXCLUDED.preference_id;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS semantic_pnf_project_current_execution
    ON execution.semantic_pnf_candidate_execution_event;
CREATE TRIGGER semantic_pnf_project_current_execution
AFTER INSERT ON execution.semantic_pnf_candidate_execution_event
FOR EACH ROW EXECUTE FUNCTION execution.project_numeric_pnf_current_execution();
DROP TRIGGER IF EXISTS semantic_pnf_project_current_admissibility
    ON execution.semantic_pnf_candidate_admissibility_event;
CREATE TRIGGER semantic_pnf_project_current_admissibility
AFTER INSERT ON execution.semantic_pnf_candidate_admissibility_event
FOR EACH ROW EXECUTE FUNCTION execution.project_numeric_pnf_current_admissibility();
DROP TRIGGER IF EXISTS semantic_pnf_project_current_preference
    ON execution.semantic_pnf_candidate_preference;
CREATE TRIGGER semantic_pnf_project_current_preference
AFTER INSERT ON execution.semantic_pnf_candidate_preference
FOR EACH ROW EXECUTE FUNCTION execution.project_numeric_pnf_current_preference();

-- Repoint the hot candidate state at materialized current projections.
CREATE OR REPLACE VIEW execution.semantic_pnf_candidate_state_v1 AS
SELECT universe.demand_id,
       universe.target_kind,
       universe.target_id,
       TRUE AS represented_possible,
       COALESCE(execution_state.event_kind IN (1,3), FALSE) AS active,
       COALESCE(execution_state.event_kind IN (2,4,5), FALSE) AS execution_residual,
       COALESCE(admissibility.event_kind = 1, FALSE) AS refuted,
       NOT COALESCE(admissibility.event_kind = 1, FALSE) AS admissible,
       execution_state.reason_ref AS execution_reason_ref,
       admissibility.evidence_id AS admissibility_evidence_id,
       current_candidate.demand_id IS NOT NULL AS current_planner_member
  FROM execution.semantic_pnf_candidate_universe AS universe
  LEFT JOIN execution.semantic_pnf_demand_candidate AS current_candidate
    ON current_candidate.demand_id=universe.demand_id
   AND current_candidate.target_kind=universe.target_kind
   AND current_candidate.target_id=universe.target_id
  LEFT JOIN execution.semantic_pnf_candidate_current_execution AS execution_state
    ON execution_state.demand_id=universe.demand_id
   AND execution_state.target_kind=universe.target_kind
   AND execution_state.target_id=universe.target_id
  LEFT JOIN execution.semantic_pnf_candidate_current_admissibility AS admissibility
    ON admissibility.demand_id=universe.demand_id
   AND admissibility.target_kind=universe.target_kind
   AND admissibility.target_id=universe.target_id;

-- Lazy H3/H6/H9 work queue.  Preference never settles proof-required work.
CREATE TABLE IF NOT EXISTS execution.semantic_pnf_horizon_work_queue (
    demand_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_demand(demand_id) ON DELETE CASCADE,
    horizon SMALLINT NOT NULL CHECK (horizon IN (3,6,9)),
    work_state SMALLINT NOT NULL DEFAULT 1 CHECK (work_state IN (1,2,3)),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,
    PRIMARY KEY (demand_id,horizon)
);
CREATE INDEX IF NOT EXISTS semantic_pnf_horizon_work_ready_idx
    ON execution.semantic_pnf_horizon_work_queue(horizon,demand_id)
    WHERE work_state=1;

CREATE OR REPLACE FUNCTION execution.seed_numeric_pnf_h3_work(
    selected_run_id BIGINT, selected_document_id BIGINT
) RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE affected BIGINT := 0;
BEGIN
    INSERT INTO execution.semantic_pnf_horizon_work_queue(demand_id,horizon)
    SELECT demand.demand_id, 3
      FROM execution.semantic_pnf_demand AS demand
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id=demand.source_region_id
     WHERE region.run_id=selected_run_id AND region.document_id=selected_document_id
    ON CONFLICT DO NOTHING;
    GET DIAGNOSTICS affected=ROW_COUNT;
    RETURN affected;
END;
$$;

CREATE OR REPLACE FUNCTION execution.advance_numeric_pnf_horizon_work(
    selected_run_id BIGINT, selected_document_id BIGINT,
    completed_horizon SMALLINT
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
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id=demand.source_region_id
     WHERE work.demand_id=demand.demand_id
       AND work.horizon=completed_horizon
       AND region.run_id=selected_run_id
       AND region.document_id=selected_document_id;

    INSERT INTO execution.semantic_pnf_horizon_work_queue(demand_id,horizon)
    SELECT demand.demand_id,next_horizon
      FROM execution.semantic_pnf_demand AS demand
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id=demand.source_region_id
     WHERE region.run_id=selected_run_id AND region.document_id=selected_document_id
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

-- Reverse dependency graph and incremental wake queue.  Source kind is a small
-- runtime enum: 1 token, 2 object, 3 factor, 4 region, 5 interface, 6 evidence,
-- 7 external entity.  The normal update path wakes demands; whole-document
-- rebuilds remain explicit recovery/audit functions elsewhere.
CREATE TABLE IF NOT EXISTS execution.semantic_pnf_reverse_dependency (
    source_kind SMALLINT NOT NULL CHECK (source_kind BETWEEN 1 AND 7),
    source_id BIGINT NOT NULL,
    demand_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_demand(demand_id) ON DELETE CASCADE,
    dependency_kind SMALLINT NOT NULL DEFAULT 1,
    PRIMARY KEY(source_kind,source_id,demand_id,dependency_kind)
);
CREATE INDEX IF NOT EXISTS semantic_pnf_reverse_dependency_demand_idx
    ON execution.semantic_pnf_reverse_dependency(demand_id,source_kind,source_id);

CREATE TABLE IF NOT EXISTS execution.semantic_pnf_incremental_work_queue (
    work_id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    source_kind SMALLINT NOT NULL,
    source_id BIGINT NOT NULL,
    demand_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_demand(demand_id) ON DELETE CASCADE,
    horizon SMALLINT NOT NULL DEFAULT 3 CHECK (horizon IN (3,6,9)),
    work_state SMALLINT NOT NULL DEFAULT 1 CHECK (work_state IN (1,2,3)),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_kind,source_id,demand_id,horizon,work_state)
);
CREATE INDEX IF NOT EXISTS semantic_pnf_incremental_work_ready_idx
    ON execution.semantic_pnf_incremental_work_queue(demand_id,horizon,work_id)
    WHERE work_state=1;

CREATE OR REPLACE FUNCTION execution.enqueue_numeric_pnf_affected_demands(
    selected_source_kind SMALLINT, selected_source_id BIGINT,
    selected_horizon SMALLINT DEFAULT 3
) RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE affected BIGINT := 0;
BEGIN
    INSERT INTO execution.semantic_pnf_incremental_work_queue
        (source_kind,source_id,demand_id,horizon)
    SELECT selected_source_kind,selected_source_id,dependency.demand_id,selected_horizon
      FROM execution.semantic_pnf_reverse_dependency AS dependency
     WHERE dependency.source_kind=selected_source_kind
       AND dependency.source_id=selected_source_id
    ON CONFLICT DO NOTHING;
    GET DIAGNOSTICS affected=ROW_COUNT;
    RETURN affected;
END;
$$;

-- Frequency-adaptive physical codebook.  Canonical symbol_id never changes.
CREATE TABLE IF NOT EXISTS execution.semantic_symbol_frequency_codebook (
    codebook_revision BIGINT NOT NULL,
    symbol_id BIGINT NOT NULL
        REFERENCES execution.semantic_symbol(symbol_id) ON DELETE CASCADE,
    occurrence_count BIGINT NOT NULL CHECK (occurrence_count >= 0),
    physical_code BIGINT NOT NULL CHECK (physical_code >= 0),
    PRIMARY KEY(codebook_revision,symbol_id),
    UNIQUE(codebook_revision,physical_code)
);
CREATE INDEX IF NOT EXISTS semantic_symbol_frequency_hot_idx
    ON execution.semantic_symbol_frequency_codebook
       (codebook_revision,physical_code,symbol_id);

CREATE OR REPLACE FUNCTION execution.build_numeric_symbol_frequency_codebook(
    selected_revision BIGINT
) RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE affected BIGINT := 0;
BEGIN
    DELETE FROM execution.semantic_symbol_frequency_codebook
     WHERE codebook_revision=selected_revision;
    WITH frequency AS (
        SELECT symbol_id,count(*)::BIGINT AS occurrence_count
          FROM (
              SELECT orth_symbol_id AS symbol_id FROM execution.semantic_parser_token
               WHERE representation_version=2 AND orth_symbol_id IS NOT NULL
              UNION ALL
              SELECT lemma_symbol_id FROM execution.semantic_parser_token
               WHERE representation_version=2 AND lemma_symbol_id IS NOT NULL
          ) AS observed
         GROUP BY symbol_id
    )
    INSERT INTO execution.semantic_symbol_frequency_codebook
        (codebook_revision,symbol_id,occurrence_count,physical_code)
    SELECT selected_revision,symbol_id,occurrence_count,
           (row_number() OVER (ORDER BY occurrence_count DESC,symbol_id)-1)::BIGINT
      FROM frequency;
    GET DIAGNOSTICS affected=ROW_COUNT;
    RETURN affected;
END;
$$;

-- Context-qualified world cache.  Labels cache fibres of candidates rather than
-- a global label->entity scalar. Provider-local numeric ids are the hot key;
-- authority_namespace/identifier text stays in the existing external boundary.
CREATE TABLE IF NOT EXISTS execution.semantic_pnf_world_provider (
    provider_id SMALLINT PRIMARY KEY,
    provider_name TEXT NOT NULL UNIQUE
);
INSERT INTO execution.semantic_pnf_world_provider(provider_id,provider_name)
VALUES (1,'wikidata') ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS execution.semantic_pnf_world_entity_numeric (
    world_entity_id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    provider_id SMALLINT NOT NULL
        REFERENCES execution.semantic_pnf_world_provider(provider_id),
    provider_numeric_id BIGINT NOT NULL CHECK (provider_numeric_id >= 0),
    canonical_entity_id BIGINT
        REFERENCES execution.semantic_pnf_canonical_entity(entity_id) ON DELETE SET NULL,
    UNIQUE(provider_id,provider_numeric_id)
);
CREATE TABLE IF NOT EXISTS execution.semantic_pnf_label_world_candidate (
    label_symbol_id BIGINT NOT NULL
        REFERENCES execution.semantic_symbol(symbol_id) ON DELETE CASCADE,
    world_entity_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_world_entity_numeric(world_entity_id) ON DELETE CASCADE,
    candidate_ordinal INTEGER NOT NULL CHECK (candidate_ordinal >= 0),
    cache_revision BIGINT NOT NULL DEFAULT 1,
    evidence_count BIGINT NOT NULL DEFAULT 0 CHECK (evidence_count >= 0),
    PRIMARY KEY(label_symbol_id,world_entity_id),
    UNIQUE(label_symbol_id,candidate_ordinal,cache_revision)
);
CREATE INDEX IF NOT EXISTS semantic_pnf_label_world_candidate_lookup_idx
    ON execution.semantic_pnf_label_world_candidate
       (label_symbol_id,cache_revision,candidate_ordinal,world_entity_id);

CREATE TABLE IF NOT EXISTS execution.semantic_pnf_world_context_witness (
    context_witness_id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    token_id BIGINT NOT NULL
        REFERENCES execution.semantic_parser_token(token_id) ON DELETE CASCADE,
    region_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_region(region_id) ON DELETE CASCADE,
    evidence_ref TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS execution.semantic_pnf_world_context_symbol (
    context_witness_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_world_context_witness(context_witness_id) ON DELETE CASCADE,
    symbol_id BIGINT NOT NULL
        REFERENCES execution.semantic_symbol(symbol_id) ON DELETE RESTRICT,
    polarity SMALLINT NOT NULL DEFAULT 1 CHECK (polarity IN (-1,0,1)),
    PRIMARY KEY(context_witness_id,symbol_id,polarity)
);
CREATE TABLE IF NOT EXISTS execution.semantic_pnf_mention_world_attachment (
    token_id BIGINT NOT NULL
        REFERENCES execution.semantic_parser_token(token_id) ON DELETE CASCADE,
    label_symbol_id BIGINT NOT NULL
        REFERENCES execution.semantic_symbol(symbol_id) ON DELETE RESTRICT,
    world_entity_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_world_entity_numeric(world_entity_id) ON DELETE RESTRICT,
    context_witness_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_world_context_witness(context_witness_id) ON DELETE RESTRICT,
    attachment_state SMALLINT NOT NULL DEFAULT 1 CHECK (attachment_state IN (1,2,3)),
    PRIMARY KEY(token_id,world_entity_id,context_witness_id)
);

-- Corpus-local proof-bearing reuse: multiple entities may share a label.  This
-- is a candidate/evidence cache only and never manufactures identity admission.
CREATE TABLE IF NOT EXISTS execution.semantic_pnf_corpus_entity_label_cache (
    label_symbol_id BIGINT NOT NULL
        REFERENCES execution.semantic_symbol(symbol_id) ON DELETE CASCADE,
    canonical_entity_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_canonical_entity(entity_id) ON DELETE CASCADE,
    authority_class SMALLINT NOT NULL,
    admitted_support_count BIGINT NOT NULL CHECK (admitted_support_count > 0),
    latest_witness_id BIGINT NOT NULL,
    PRIMARY KEY(label_symbol_id,canonical_entity_id,authority_class)
);
CREATE INDEX IF NOT EXISTS semantic_pnf_corpus_entity_label_lookup_idx
    ON execution.semantic_pnf_corpus_entity_label_cache
       (label_symbol_id,authority_class,admitted_support_count DESC,canonical_entity_id);

CREATE OR REPLACE FUNCTION execution.refresh_numeric_pnf_corpus_entity_label_cache()
RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE affected BIGINT := 0;
BEGIN
    TRUNCATE execution.semantic_pnf_corpus_entity_label_cache;
    INSERT INTO execution.semantic_pnf_corpus_entity_label_cache
        (label_symbol_id,canonical_entity_id,authority_class,
         admitted_support_count,latest_witness_id)
    SELECT object.head_symbol_id,
           witness.target_entity_id,
           witness.authority_class,
           count(*)::BIGINT,
           max(witness.witness_id)
      FROM execution.semantic_pnf_identity_witness AS witness
      JOIN execution.semantic_pnf_identity_witness_admission AS admission
        ON admission.witness_id=witness.witness_id AND admission.admission_state=2
      JOIN execution.semantic_pnf_object AS object
        ON object.object_id=witness.source_object_id
     WHERE object.head_symbol_id IS NOT NULL
     GROUP BY object.head_symbol_id,witness.target_entity_id,witness.authority_class;
    GET DIAGNOSTICS affected=ROW_COUNT;
    RETURN affected;
END;
$$;

-- Runtime learning-economy and token-normalised throughput measurements.
CREATE TABLE IF NOT EXISTS execution.semantic_pnf_corpus_reuse_measurement (
    measurement_id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    workload_ref TEXT NOT NULL,
    run_id BIGINT,
    document_id BIGINT,
    token_count BIGINT NOT NULL CHECK (token_count > 0),
    fixed_numeric_work BIGINT NOT NULL CHECK (fixed_numeric_work >= 0),
    unresolved_resolution_work BIGINT NOT NULL CHECK (unresolved_resolution_work >= 0),
    reused_lexical_units BIGINT NOT NULL DEFAULT 0 CHECK (reused_lexical_units >= 0),
    reused_entity_units BIGINT NOT NULL DEFAULT 0 CHECK (reused_entity_units >= 0),
    reused_external_units BIGINT NOT NULL DEFAULT 0 CHECK (reused_external_units >= 0),
    elapsed_microseconds BIGINT NOT NULL CHECK (elapsed_microseconds >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS semantic_pnf_corpus_reuse_workload_idx
    ON execution.semantic_pnf_corpus_reuse_measurement
       (workload_ref,measurement_id);

CREATE OR REPLACE VIEW execution.semantic_pnf_token_normalised_throughput_v1 AS
SELECT measurement.workload_ref,
       measurement.run_id,
       measurement.document_id,
       measurement.token_count,
       measurement.fixed_numeric_work + measurement.unresolved_resolution_work
           AS total_semantic_work,
       CASE WHEN measurement.elapsed_microseconds=0 THEN NULL
            ELSE measurement.token_count::NUMERIC * 1000000
                 / measurement.elapsed_microseconds::NUMERIC
       END AS semantic_tokens_per_second,
       measurement.unresolved_resolution_work::NUMERIC
           / measurement.token_count::NUMERIC AS unresolved_work_per_token,
       measurement.reused_lexical_units,
       measurement.reused_entity_units,
       measurement.reused_external_units
  FROM execution.semantic_pnf_corpus_reuse_measurement AS measurement;

CREATE OR REPLACE VIEW execution.semantic_pnf_partition_readiness_v1 AS
SELECT relation.relname AS relation_name,
       relation.reltuples::BIGINT AS estimated_rows,
       pg_total_relation_size(relation.oid) AS total_bytes
  FROM pg_class AS relation
  JOIN pg_namespace AS namespace ON namespace.oid=relation.relnamespace
 WHERE namespace.nspname='execution'
   AND relation.relname IN (
       'semantic_pnf_candidate_evidence',
       'semantic_pnf_candidate_execution_event',
       'semantic_pnf_object_token_support'
   );

COMMIT;
