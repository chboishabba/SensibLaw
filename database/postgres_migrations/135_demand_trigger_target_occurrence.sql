BEGIN;

-- 135: demand occurrence provenance has distinct semantic roles.
--
-- Historical demand rows were created before trigger and target occurrences
-- were distinguished. They are intentionally NOT backfilled by this migration
-- from lexical symbols, object heads, dependency neighbours, or region
-- proximity. Missing target provenance is an unresolved state and cannot
-- authorize H9 provider work.
--
-- New/recompiled demands are different: the demand producer has the exact
-- factor, typed slots and parser-token support available in the same
-- transaction. Producer provenance is recorded only when those existing
-- coordinates uniquely license it.
CREATE TABLE IF NOT EXISTS execution.semantic_pnf_demand_occurrence_provenance (
    demand_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_demand(demand_id) ON DELETE CASCADE,
    occurrence_role SMALLINT NOT NULL CHECK (occurrence_role IN (1,2,3)),
    token_id BIGINT NOT NULL
        REFERENCES execution.semantic_parser_token(token_id) ON DELETE CASCADE,
    object_id BIGINT
        REFERENCES execution.semantic_pnf_object(object_id) ON DELETE SET NULL,
    ordinal SMALLINT NOT NULL DEFAULT 0 CHECK (ordinal >= 0),
    producer_ref TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(demand_id,occurrence_role,token_id,ordinal)
);

-- occurrence_role:
--   1 trigger  token whose parser/factor relation caused the demand to exist
--   2 target   token/object the unresolved semantic question is actually about
--   3 evidence other producer-licensed support token
CREATE INDEX IF NOT EXISTS semantic_pnf_demand_occurrence_role_idx
    ON execution.semantic_pnf_demand_occurrence_provenance
       (occurrence_role,token_id,demand_id);
CREATE INDEX IF NOT EXISTS semantic_pnf_demand_target_object_idx
    ON execution.semantic_pnf_demand_occurrence_provenance
       (object_id,demand_id)
    WHERE occurrence_role=2 AND object_id IS NOT NULL;

-- Generic producer API. Producers must state the occurrence role explicitly.
-- The database validates that the token is actually inside the demand's source
-- region and that any claimed object is an exact support object for that token
-- in the same region. This API never searches for a nearby object.
CREATE OR REPLACE FUNCTION execution.register_numeric_pnf_demand_occurrence(
    selected_demand_id BIGINT,
    selected_occurrence_role SMALLINT,
    selected_token_id BIGINT,
    selected_object_id BIGINT,
    selected_ordinal SMALLINT,
    selected_producer_ref TEXT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    selected_source_region_id BIGINT;
    selected_token_start BIGINT;
    selected_token_end BIGINT;
    selected_region_start BIGINT;
    selected_region_end BIGINT;
    existing_object_count BIGINT := 0;
BEGIN
    IF selected_occurrence_role NOT IN (1,2,3) THEN
        RAISE EXCEPTION 'invalid demand occurrence role %',selected_occurrence_role;
    END IF;
    IF selected_ordinal<0 THEN
        RAISE EXCEPTION 'negative demand occurrence ordinal %',selected_ordinal;
    END IF;
    IF selected_producer_ref IS NULL OR selected_producer_ref='' THEN
        RAISE EXCEPTION 'demand occurrence producer_ref must be non-empty';
    END IF;

    SELECT demand.source_region_id,region.start_char,region.end_char,
           token.start_char,token.end_char
      INTO selected_source_region_id,selected_region_start,selected_region_end,
           selected_token_start,selected_token_end
      FROM execution.semantic_pnf_demand AS demand
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id=demand.source_region_id
      JOIN execution.semantic_parser_token AS token
        ON token.token_id=selected_token_id
       AND token.representation_version=2
     WHERE demand.demand_id=selected_demand_id;

    IF selected_source_region_id IS NULL THEN
        RAISE EXCEPTION 'unknown demand/token pair %, %',
            selected_demand_id,selected_token_id;
    END IF;
    IF selected_token_start<selected_region_start
       OR selected_token_end>selected_region_end THEN
        RAISE EXCEPTION 'demand occurrence token % is outside source region %',
            selected_token_id,selected_source_region_id;
    END IF;

    IF selected_object_id IS NOT NULL THEN
        SELECT count(*) INTO existing_object_count
          FROM execution.semantic_pnf_object_token_support AS support
          JOIN execution.semantic_pnf_object AS object
            ON object.object_id=support.object_id
         WHERE support.object_id=selected_object_id
           AND support.token_id=selected_token_id
           AND object.region_id=selected_source_region_id;
        IF existing_object_count<>1 THEN
            RAISE EXCEPTION
                'object % does not exactly support demand occurrence token % in region %',
                selected_object_id,selected_token_id,selected_source_region_id;
        END IF;
    END IF;

    INSERT INTO execution.semantic_pnf_demand_occurrence_provenance
        (demand_id,occurrence_role,token_id,object_id,ordinal,producer_ref)
    VALUES (
        selected_demand_id,selected_occurrence_role,selected_token_id,
        selected_object_id,selected_ordinal,selected_producer_ref
    )
    ON CONFLICT(demand_id,occurrence_role,token_id,ordinal) DO UPDATE SET
        object_id=EXCLUDED.object_id,
        producer_ref=EXCLUDED.producer_ref;
    RETURN 1;
END;
$$;

-- Explicit factor-producer semantics: only residuals whose meaning identifies
-- a typed factor slot receive an entity/object target. Absence of a rule means
-- factor-level/unlocated residual, not permission to select a nearby noun.
CREATE TABLE IF NOT EXISTS execution.semantic_pnf_demand_target_role_rule (
    residual_type_symbol_id BIGINT PRIMARY KEY
        REFERENCES execution.semantic_symbol(symbol_id) ON DELETE CASCADE,
    target_role_symbol_id BIGINT NOT NULL
        REFERENCES execution.semantic_symbol(symbol_id) ON DELETE RESTRICT,
    rule_ref TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO execution.semantic_pnf_demand_target_role_rule
    (residual_type_symbol_id,target_role_symbol_id,rule_ref)
VALUES
    (execution.ensure_semantic_symbol(13::SMALLINT,'legal_object_identity_unresolved'),
     execution.ensure_semantic_symbol(19::SMALLINT,'legal_object'),
     'producer-target:legal-object-identity:v1'),
    (execution.ensure_semantic_symbol(13::SMALLINT,'condition_attachment_unresolved'),
     execution.ensure_semantic_symbol(19::SMALLINT,'host'),
     'producer-target:condition-host:v1'),
    (execution.ensure_semantic_symbol(13::SMALLINT,'exception_attachment_unresolved'),
     execution.ensure_semantic_symbol(19::SMALLINT,'host'),
     'producer-target:exception-host:v1'),
    (execution.ensure_semantic_symbol(13::SMALLINT,'norm_bearer_unresolved'),
     execution.ensure_semantic_symbol(19::SMALLINT,'bearer'),
     'producer-target:norm-bearer:v1')
ON CONFLICT(residual_type_symbol_id) DO UPDATE SET
    target_role_symbol_id=EXCLUDED.target_role_symbol_id,
    rule_ref=EXCLUDED.rule_ref;

CREATE OR REPLACE FUNCTION execution.record_numeric_pnf_demand_occurrence_provenance()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    selected_factor_id BIGINT;
    selected_trigger_token_id BIGINT;
    selected_trigger_object_id BIGINT;
    selected_target_role_id BIGINT;
    selected_target_token_id BIGINT;
    selected_target_object_id BIGINT;
    producer_match_count BIGINT := 0;
    target_match_count BIGINT := 0;
    evidence_row RECORD;
    evidence_ordinal SMALLINT := 0;
BEGIN
    -- lexical_symbol_id remains a candidate-planning coordinate. It may locate
    -- the producer trigger, but never the semantic target by itself.
    IF NEW.expected_factor_type_symbol_id IS NULL
       OR NEW.lexical_symbol_id IS NULL THEN
        RETURN NEW;
    END IF;

    -- Recover the exact current producer factor and trigger token from the
    -- factor's own support carrier. Fail closed unless exactly one pair matches.
    SELECT count(*),min(match.factor_id),min(match.token_id)
      INTO producer_match_count,selected_factor_id,selected_trigger_token_id
      FROM (
          SELECT DISTINCT factor.factor_id,support.token_id
            FROM execution.semantic_pnf_factor AS factor
            JOIN execution.semantic_pnf_factor_token_support AS support
              ON support.factor_id=factor.factor_id
            JOIN execution.semantic_parser_token AS token
              ON token.token_id=support.token_id
             AND token.representation_version=2
           WHERE factor.region_id=NEW.source_region_id
             AND factor.factor_type_symbol_id=NEW.expected_factor_type_symbol_id
             AND token.lemma_symbol_id=NEW.lexical_symbol_id
      ) AS match;

    IF producer_match_count<>1
       OR selected_factor_id IS NULL
       OR selected_trigger_token_id IS NULL THEN
        RETURN NEW;
    END IF;

    -- Object attachment on a trigger is audit context only. If representation
    -- is ambiguous, record the exact trigger token with no object rather than
    -- choosing one.
    SELECT min(support.object_id)
      INTO selected_trigger_object_id
      FROM execution.semantic_pnf_object_token_support AS support
      JOIN execution.semantic_pnf_object AS object
        ON object.object_id=support.object_id
     WHERE support.token_id=selected_trigger_token_id
       AND object.region_id=NEW.source_region_id
    HAVING count(DISTINCT support.object_id)=1;

    PERFORM execution.register_numeric_pnf_demand_occurrence(
        NEW.demand_id,1::SMALLINT,selected_trigger_token_id,
        selected_trigger_object_id,0::SMALLINT,
        'numeric-factor:'||selected_factor_id::TEXT
    );

    -- Preserve all other exact factor-support tokens as evidence. They never
    -- become target candidates merely because they support the factor.
    FOR evidence_row IN
        SELECT support.token_id,
               (
                   SELECT min(object_support.object_id)
                     FROM execution.semantic_pnf_object_token_support AS object_support
                     JOIN execution.semantic_pnf_object AS object
                       ON object.object_id=object_support.object_id
                    WHERE object_support.token_id=support.token_id
                      AND object.region_id=NEW.source_region_id
                   HAVING count(DISTINCT object_support.object_id)=1
               ) AS object_id
          FROM execution.semantic_pnf_factor_token_support AS support
         WHERE support.factor_id=selected_factor_id
           AND support.token_id<>selected_trigger_token_id
         ORDER BY support.ordinal,support.token_id
    LOOP
        PERFORM execution.register_numeric_pnf_demand_occurrence(
            NEW.demand_id,3::SMALLINT,evidence_row.token_id,evidence_row.object_id,
            evidence_ordinal,'numeric-factor:'||selected_factor_id::TEXT
        );
        evidence_ordinal:=evidence_ordinal+1;
    END LOOP;

    SELECT rule.target_role_symbol_id
      INTO selected_target_role_id
      FROM execution.semantic_pnf_demand_target_role_rule AS rule
     WHERE rule.residual_type_symbol_id=NEW.residual_type_symbol_id;

    -- No target-role rule means the producer knows only a factor-level
    -- residual. Do not manufacture an entity occurrence.
    IF selected_target_role_id IS NULL THEN
        RETURN NEW;
    END IF;

    -- A semantic target exists only when the typed factor role selects exactly
    -- one object and that object carries exactly one parser-token occurrence.
    SELECT count(*),min(match.token_id),min(match.object_id)
      INTO target_match_count,selected_target_token_id,selected_target_object_id
      FROM (
          SELECT DISTINCT support.token_id,edge.object_id
            FROM execution.semantic_pnf_hyperedge AS edge
            JOIN execution.semantic_pnf_object_token_support AS support
              ON support.object_id=edge.object_id
           WHERE edge.factor_id=selected_factor_id
             AND edge.role_symbol_id=selected_target_role_id
      ) AS match;

    IF target_match_count<>1
       OR selected_target_token_id IS NULL
       OR selected_target_object_id IS NULL THEN
        RETURN NEW;
    END IF;

    PERFORM execution.register_numeric_pnf_demand_occurrence(
        NEW.demand_id,2::SMALLINT,selected_target_token_id,
        selected_target_object_id,0::SMALLINT,
        'numeric-factor:'||selected_factor_id::TEXT
    );
    RETURN NEW;
END;
$$;

-- Existing rows are not touched by migration installation. A genuine compiler
-- replay hits INSERT or ON CONFLICT UPDATE and derives provenance against the
-- newly/currently materialized factor graph.
DROP TRIGGER IF EXISTS semantic_pnf_demand_occurrence_producer
    ON execution.semantic_pnf_demand;
CREATE TRIGGER semantic_pnf_demand_occurrence_producer
AFTER INSERT OR UPDATE OF
    state,source_region_id,expected_factor_type_symbol_id,
    lexical_symbol_id,residual_type_symbol_id
ON execution.semantic_pnf_demand
FOR EACH ROW
EXECUTE FUNCTION execution.record_numeric_pnf_demand_occurrence_provenance();

CREATE OR REPLACE VIEW execution.semantic_pnf_demand_trigger_occurrence_v1 AS
SELECT provenance.demand_id,provenance.token_id,provenance.object_id,
       provenance.ordinal,provenance.producer_ref
  FROM execution.semantic_pnf_demand_occurrence_provenance AS provenance
 WHERE provenance.occurrence_role=1;

CREATE OR REPLACE VIEW execution.semantic_pnf_demand_target_occurrence_v1 AS
SELECT provenance.demand_id,provenance.token_id,provenance.object_id,
       provenance.ordinal,provenance.producer_ref
  FROM execution.semantic_pnf_demand_occurrence_provenance AS provenance
 WHERE provenance.occurrence_role=2;

CREATE OR REPLACE VIEW execution.semantic_pnf_demand_evidence_occurrence_v1 AS
SELECT provenance.demand_id,provenance.token_id,provenance.object_id,
       provenance.ordinal,provenance.producer_ref
  FROM execution.semantic_pnf_demand_occurrence_provenance AS provenance
 WHERE provenance.occurrence_role=3;

CREATE OR REPLACE VIEW execution.semantic_pnf_demand_occurrence_provenance_audit_v1 AS
SELECT demand.demand_id,
       count(*) FILTER (WHERE provenance.occurrence_role=1)::BIGINT
           AS trigger_occurrence_count,
       count(*) FILTER (WHERE provenance.occurrence_role=2)::BIGINT
           AS target_occurrence_count,
       count(*) FILTER (WHERE provenance.occurrence_role=3)::BIGINT
           AS evidence_occurrence_count,
       (rule.target_role_symbol_id IS NOT NULL) AS has_explicit_target_rule,
       CASE
         WHEN count(*) FILTER (WHERE provenance.occurrence_role=2)=1 THEN 1
         WHEN count(*) FILTER (WHERE provenance.occurrence_role=2)>1 THEN 2
         WHEN count(*) FILTER (WHERE provenance.occurrence_role=1)>0
              AND rule.target_role_symbol_id IS NULL THEN 11
         WHEN count(*) FILTER (WHERE provenance.occurrence_role=1)>0 THEN 12
         ELSE 10
       END::SMALLINT AS provenance_state
  FROM execution.semantic_pnf_demand AS demand
  LEFT JOIN execution.semantic_pnf_demand_occurrence_provenance AS provenance
    ON provenance.demand_id=demand.demand_id
  LEFT JOIN execution.semantic_pnf_demand_target_role_rule AS rule
    ON rule.residual_type_symbol_id=demand.residual_type_symbol_id
 GROUP BY demand.demand_id,rule.target_role_symbol_id;

-- H9-specific structural support. The older generic strong-occurrence view is
-- retained for non-H9 audit/compatibility. World-entity work is licensed only
-- by producer-authored target occurrences with the exact PNF object selected by
-- the producer's typed factor slot.
CREATE OR REPLACE VIEW execution.semantic_pnf_demand_h9_target_support_v1 AS
SELECT target.demand_id,target.token_id,target.object_id,
       target.ordinal,target.producer_ref
  FROM execution.semantic_pnf_demand_target_occurrence_v1 AS target
 WHERE target.object_id IS NOT NULL;

-- Rewire raw and quality-gated parser-entity occurrence bridges to semantic
-- target tokens. Trigger/evidence occurrences are deliberately invisible here.
CREATE OR REPLACE VIEW execution.semantic_pnf_demand_parser_entity_occurrence_v1 AS
SELECT DISTINCT target.demand_id,target.object_id,
       entity.entity_id,entity.entity_type_symbol_id,label.label_symbol_id
  FROM execution.semantic_pnf_demand_h9_target_support_v1 AS target
  JOIN execution.semantic_parser_token AS token
    ON token.token_id=target.token_id
   AND token.representation_version=2
  JOIN execution.semantic_parser_provider_entity_span_v1 AS entity
    ON entity.run_ref=token.run_ref
   AND entity.document_ref=token.document_ref
   AND entity.sentence_ref=token.sentence_ref
   AND entity.start_char<=token.start_char
   AND entity.end_char>=token.end_char
  JOIN execution.semantic_pnf_parser_entity_surface_label AS label
    ON label.entity_id=entity.entity_id;

CREATE OR REPLACE VIEW execution.semantic_pnf_demand_raw_parser_entity_occurrence_v1 AS
SELECT DISTINCT target.demand_id,target.object_id,entity.entity_id,
       entity.entity_type_symbol_id,quality.quality_state
  FROM execution.semantic_pnf_demand_h9_target_support_v1 AS target
  JOIN execution.semantic_parser_token AS token
    ON token.token_id=target.token_id
   AND token.representation_version=2
  JOIN execution.semantic_parser_entity_span AS entity
    ON entity.representation_version=2
   AND entity.run_ref=token.run_ref
   AND entity.document_ref=token.document_ref
   AND entity.sentence_ref=token.sentence_ref
   AND entity.start_char<=token.start_char
   AND entity.end_char>=token.end_char
  JOIN execution.semantic_parser_entity_span_quality_v1 AS quality
    ON quality.entity_id=entity.entity_id;

-- Historical/current provider origins whose demand lacks exact producer target
-- provenance are withdrawn, never deleted. This does not resolve or refute the
-- demand; it only removes permission to cross the external boundary.
UPDATE execution.semantic_pnf_consumer_external_need_origin AS origin
   SET active=FALSE,updated_at=CURRENT_TIMESTAMP
  FROM execution.semantic_pnf_consumer_external_need AS need
 WHERE origin.need_id=need.need_id
   AND origin.active
   AND NOT EXISTS (
       SELECT 1
         FROM execution.semantic_pnf_demand_h9_target_support_v1 AS target
        WHERE target.demand_id=need.demand_id
          AND target.object_id=need.anchor_object_id
   );

WITH state AS MATERIALIZED (
    SELECT need.need_id,COALESCE(bool_or(origin.active),FALSE) AS any_active,
           min(origin.priority) FILTER (WHERE origin.active) AS min_priority,
           max(origin.minimum_source_epoch) FILTER (WHERE origin.active) AS max_floor
      FROM execution.semantic_pnf_consumer_external_need AS need
      LEFT JOIN execution.semantic_pnf_consumer_external_need_origin AS origin
        ON origin.need_id=need.need_id
     GROUP BY need.need_id
)
UPDATE execution.semantic_pnf_consumer_external_need AS need
   SET active=state.any_active,
       priority=COALESCE(state.min_priority,need.priority),
       minimum_source_epoch=state.max_floor
  FROM state
 WHERE state.need_id=need.need_id;

SELECT execution.refresh_numeric_pnf_external_request_observer_state();
SELECT execution.refresh_numeric_pnf_external_request_cache_state();

COMMIT;
