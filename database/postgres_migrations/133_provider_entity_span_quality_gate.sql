BEGIN;

-- 133: raw spaCy NER is parser evidence, not automatically a provider label.
--
-- Live GWB validation found exact doc.ents such as "GEORGE BUSH BELIEVED" and
-- "JFK May Drop Johnson" labelled PERSON/ORG/WORK_OF_ART.  The numeric
-- occurrence bridge in 130 is correct; the missing layer is an explicit
-- provider-admissible entity-span quality carrier.
--
-- This migration preserves every raw parser entity span.  It classifies spans
-- structurally and syntactically, then lets H9 consume only quality_state=1.
-- A rejected span is unresolved parser evidence, never negative world evidence.

CREATE TABLE IF NOT EXISTS execution.semantic_parser_provider_entity_type (
    entity_type_symbol_id BIGINT PRIMARY KEY
        REFERENCES execution.semantic_symbol(symbol_id) ON DELETE CASCADE,
    provider_world_bearing BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Resolve the finite spaCy NER class boundary once.  Runtime quality joins are
-- numeric.  Measurement/value classes (DATE, MONEY, CARDINAL, etc.) are
-- deliberately absent: H9 is an external entity authority, not a dictionary.
INSERT INTO execution.semantic_parser_provider_entity_type(entity_type_symbol_id)
SELECT symbol.symbol_id
  FROM execution.semantic_symbol AS symbol
 WHERE symbol.kind_id=8
   AND symbol.symbol_text IN (
       'PERSON','ORG','GPE','LOC','FAC','LAW',
       'EVENT','WORK_OF_ART','PRODUCT','LANGUAGE'
   )
ON CONFLICT(entity_type_symbol_id) DO UPDATE SET provider_world_bearing=TRUE;

CREATE TABLE IF NOT EXISTS execution.semantic_parser_entity_quality_pos (
    quality_role SMALLINT NOT NULL CHECK (quality_role IN (1,2)),
    pos_symbol_id BIGINT NOT NULL
        REFERENCES execution.semantic_symbol(symbol_id) ON DELETE CASCADE,
    PRIMARY KEY(quality_role,pos_symbol_id)
);
-- role 1: verbal/clausal token; role 2: nominal anchor.
INSERT INTO execution.semantic_parser_entity_quality_pos(quality_role,pos_symbol_id)
SELECT definition.quality_role,symbol.symbol_id
  FROM (VALUES
      (1::SMALLINT,'VERB'::TEXT),(1::SMALLINT,'AUX'::TEXT),
      (2::SMALLINT,'PROPN'::TEXT),(2::SMALLINT,'NOUN'::TEXT)
  ) AS definition(quality_role,symbol_text)
  JOIN execution.semantic_symbol AS symbol
    ON symbol.kind_id=3 AND symbol.symbol_text=definition.symbol_text
ON CONFLICT DO NOTHING;

CREATE OR REPLACE FUNCTION execution.refresh_semantic_parser_entity_quality_constants()
RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE affected BIGINT := 0; n BIGINT := 0;
BEGIN
    INSERT INTO execution.semantic_parser_provider_entity_type(entity_type_symbol_id)
    SELECT symbol.symbol_id
      FROM execution.semantic_symbol AS symbol
     WHERE symbol.kind_id=8
       AND symbol.symbol_text IN (
           'PERSON','ORG','GPE','LOC','FAC','LAW',
           'EVENT','WORK_OF_ART','PRODUCT','LANGUAGE'
       )
    ON CONFLICT(entity_type_symbol_id) DO UPDATE SET provider_world_bearing=TRUE;
    GET DIAGNOSTICS n=ROW_COUNT; affected:=affected+n;

    INSERT INTO execution.semantic_parser_entity_quality_pos(quality_role,pos_symbol_id)
    SELECT definition.quality_role,symbol.symbol_id
      FROM (VALUES
          (1::SMALLINT,'VERB'::TEXT),(1::SMALLINT,'AUX'::TEXT),
          (2::SMALLINT,'PROPN'::TEXT),(2::SMALLINT,'NOUN'::TEXT)
      ) AS definition(quality_role,symbol_text)
      JOIN execution.semantic_symbol AS symbol
        ON symbol.kind_id=3 AND symbol.symbol_text=definition.symbol_text
    ON CONFLICT DO NOTHING;
    GET DIAGNOSTICS n=ROW_COUNT; affected:=affected+n;
    RETURN affected;
END;
$$;
SELECT execution.refresh_semantic_parser_entity_quality_constants();

CREATE OR REPLACE FUNCTION execution.refresh_semantic_parser_entity_quality_constants_on_symbol()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF (NEW.kind_id=8 AND NEW.symbol_text IN (
            'PERSON','ORG','GPE','LOC','FAC','LAW',
            'EVENT','WORK_OF_ART','PRODUCT','LANGUAGE'))
       OR (NEW.kind_id=3 AND NEW.symbol_text IN ('VERB','AUX','PROPN','NOUN')) THEN
        PERFORM execution.refresh_semantic_parser_entity_quality_constants();
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS semantic_symbol_refresh_parser_entity_quality
    ON execution.semantic_symbol;
CREATE TRIGGER semantic_symbol_refresh_parser_entity_quality
AFTER INSERT OR UPDATE OF kind_id,symbol_text ON execution.semantic_symbol
FOR EACH ROW
EXECUTE FUNCTION execution.refresh_semantic_parser_entity_quality_constants_on_symbol();

-- quality_state:
--  1 valid provider entity span
-- 10 no owned sentence
-- 11 no covered parser tokens
-- 12 span is not exactly token-boundary aligned
-- 13 tokens are not one contiguous sentence token interval
-- 14 contains a parser VERB/AUX (clausal/headline fragment)
-- 15 oversized provider label (>16 tokens or >256 chars)
-- 16 entity type is not provider-world-bearing
-- 17 no nominal anchor (PROPN/NOUN)
CREATE OR REPLACE VIEW execution.semantic_parser_entity_span_quality_v1 AS
WITH token_geometry AS MATERIALIZED (
    SELECT entity.entity_id,entity.entity_type_symbol_id,entity.sentence_ref,
           entity.start_char,entity.end_char,
           count(token.token_id)::BIGINT AS token_count,
           min(token.start_char) AS token_start,
           max(token.end_char) AS token_end,
           min(token.local_token_ordinal) AS first_ordinal,
           max(token.local_token_ordinal) AS last_ordinal,
           count(*) FILTER (
               WHERE EXISTS (
                   SELECT 1
                     FROM execution.semantic_parser_entity_quality_pos AS q
                    WHERE q.quality_role=1
                      AND q.pos_symbol_id=token.pos_symbol_id
               )
           )::BIGINT AS verbal_token_count,
           count(*) FILTER (
               WHERE EXISTS (
                   SELECT 1
                     FROM execution.semantic_parser_entity_quality_pos AS q
                    WHERE q.quality_role=2
                      AND q.pos_symbol_id=token.pos_symbol_id
               )
           )::BIGINT AS nominal_token_count
      FROM execution.semantic_parser_entity_span AS entity
      LEFT JOIN execution.semantic_parser_token AS token
        ON token.run_ref=entity.run_ref
       AND token.document_ref=entity.document_ref
       AND token.sentence_ref=entity.sentence_ref
       AND token.representation_version=2
       AND token.start_char>=entity.start_char
       AND token.end_char<=entity.end_char
     WHERE entity.representation_version=2
     GROUP BY entity.entity_id,entity.entity_type_symbol_id,entity.sentence_ref,
              entity.start_char,entity.end_char
), classified AS (
    SELECT geometry.*,
           EXISTS (
               SELECT 1
                 FROM execution.semantic_parser_provider_entity_type AS allowed
                WHERE allowed.entity_type_symbol_id=geometry.entity_type_symbol_id
                  AND allowed.provider_world_bearing
           ) AS provider_world_bearing,
           CASE
             WHEN geometry.sentence_ref IS NULL THEN 10
             WHEN geometry.token_count=0 THEN 11
             WHEN geometry.token_start<>geometry.start_char
               OR geometry.token_end<>geometry.end_char THEN 12
             WHEN geometry.first_ordinal IS NULL OR geometry.last_ordinal IS NULL
               OR geometry.token_count<>(geometry.last_ordinal-geometry.first_ordinal+1)
               THEN 13
             WHEN geometry.verbal_token_count>0 THEN 14
             WHEN geometry.token_count>16
               OR geometry.end_char-geometry.start_char>256 THEN 15
             WHEN NOT EXISTS (
                 SELECT 1
                   FROM execution.semantic_parser_provider_entity_type AS allowed
                  WHERE allowed.entity_type_symbol_id=geometry.entity_type_symbol_id
                    AND allowed.provider_world_bearing
             ) THEN 16
             WHEN geometry.nominal_token_count=0 THEN 17
             ELSE 1
           END::SMALLINT AS quality_state
      FROM token_geometry AS geometry
)
SELECT classified.*,(classified.quality_state=1) AS provider_admissible
  FROM classified;

CREATE OR REPLACE VIEW execution.semantic_parser_provider_entity_span_v1 AS
SELECT entity.*,quality.token_count,quality.nominal_token_count
  FROM execution.semantic_parser_entity_span AS entity
  JOIN execution.semantic_parser_entity_span_quality_v1 AS quality
    ON quality.entity_id=entity.entity_id
 WHERE quality.provider_admissible;

CREATE OR REPLACE VIEW execution.semantic_parser_entity_span_quality_summary_v1 AS
SELECT quality_state,provider_admissible,count(*)::BIGINT AS entity_count
  FROM execution.semantic_parser_entity_span_quality_v1
 GROUP BY quality_state,provider_admissible;

-- Replace 130's raw-span occurrence bridge with the quality-gated provider span.
CREATE OR REPLACE VIEW execution.semantic_pnf_demand_parser_entity_occurrence_v1 AS
SELECT DISTINCT strong.demand_id,strong.object_id,
       entity.entity_id,entity.entity_type_symbol_id,label.label_symbol_id
  FROM execution.semantic_pnf_demand_strong_occurrence_support_v1 AS strong
  JOIN execution.semantic_pnf_object_token_support AS object_token
    ON object_token.object_id=strong.object_id
  JOIN execution.semantic_parser_token AS token
    ON token.token_id=object_token.token_id
   AND token.representation_version=2
  JOIN execution.semantic_parser_provider_entity_span_v1 AS entity
    ON entity.run_ref=token.run_ref
   AND entity.document_ref=token.document_ref
   AND entity.sentence_ref=token.sentence_ref
   AND entity.start_char<=token.start_char
   AND entity.end_char>=token.end_char
  JOIN execution.semantic_pnf_parser_entity_surface_label AS label
    ON label.entity_id=entity.entity_id;

-- Diagnostic companion: exact occurrence reachability before quality gating.
CREATE OR REPLACE VIEW execution.semantic_pnf_demand_raw_parser_entity_occurrence_v1 AS
SELECT DISTINCT strong.demand_id,strong.object_id,entity.entity_id,
       entity.entity_type_symbol_id,quality.quality_state
  FROM execution.semantic_pnf_demand_strong_occurrence_support_v1 AS strong
  JOIN execution.semantic_pnf_object_token_support AS object_token
    ON object_token.object_id=strong.object_id
  JOIN execution.semantic_parser_token AS token
    ON token.token_id=object_token.token_id
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

-- Existing H9 views depend on semantic_pnf_demand_parser_entity_occurrence_v1,
-- so recompilation automatically sees only provider-admissible spans.  Withdraw
-- any currently-active origins whose anchor disappeared under the quality gate;
-- retain the immutable receipt/origin rows for audit.
UPDATE execution.semantic_pnf_consumer_external_need_origin AS origin
   SET active=FALSE,updated_at=CURRENT_TIMESTAMP
  FROM execution.semantic_pnf_consumer_external_need AS need
 WHERE origin.need_id=need.need_id
   AND origin.active
   AND NOT EXISTS (
       SELECT 1
         FROM execution.semantic_pnf_h9_entity_bearing_v1 AS bearing
        WHERE bearing.demand_id=need.demand_id
          AND bearing.source_object_id=need.anchor_object_id
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
