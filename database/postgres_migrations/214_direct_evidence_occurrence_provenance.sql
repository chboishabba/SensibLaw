BEGIN;

-- Direct sentence publication has stable source-evidence ids rather than
-- semantic_parser_token ids.  Keep the parser-token occurrence carrier as the
-- compatibility/reference authority and add the same producer-authored roles
-- over the direct carrier; neither representation may masquerade as the other.
CREATE TABLE IF NOT EXISTS execution.semantic_source_token_evidence_annotation (
    evidence_id BIGINT PRIMARY KEY
        REFERENCES execution.semantic_source_token_evidence(evidence_id)
            ON DELETE CASCADE,
    orth_symbol_id BIGINT NOT NULL
        REFERENCES execution.semantic_symbol(symbol_id) ON DELETE RESTRICT,
    lemma_symbol_id BIGINT NOT NULL
        REFERENCES execution.semantic_symbol(symbol_id) ON DELETE RESTRICT,
    pos_symbol_id BIGINT NOT NULL
        REFERENCES execution.semantic_symbol(symbol_id) ON DELETE RESTRICT,
    tag_symbol_id BIGINT NOT NULL
        REFERENCES execution.semantic_symbol(symbol_id) ON DELETE RESTRICT,
    dependency_symbol_id BIGINT NOT NULL
        REFERENCES execution.semantic_symbol(symbol_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS semantic_source_token_evidence_annotation_lemma_idx
    ON execution.semantic_source_token_evidence_annotation
       (lemma_symbol_id,evidence_id);

CREATE TABLE IF NOT EXISTS execution.semantic_pnf_demand_evidence_occurrence_provenance (
    demand_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_demand(demand_id) ON DELETE CASCADE,
    occurrence_role SMALLINT NOT NULL CHECK (occurrence_role IN (1,2,3)),
    evidence_id BIGINT NOT NULL
        REFERENCES execution.semantic_source_token_evidence(evidence_id)
            ON DELETE RESTRICT,
    object_id BIGINT
        REFERENCES execution.semantic_pnf_object(object_id) ON DELETE SET NULL,
    ordinal SMALLINT NOT NULL DEFAULT 0 CHECK (ordinal >= 0),
    producer_ref TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(demand_id,occurrence_role,evidence_id,ordinal)
);

CREATE INDEX IF NOT EXISTS semantic_pnf_demand_evidence_occurrence_role_idx
    ON execution.semantic_pnf_demand_evidence_occurrence_provenance
       (occurrence_role,evidence_id,demand_id);
CREATE INDEX IF NOT EXISTS semantic_pnf_demand_evidence_target_object_idx
    ON execution.semantic_pnf_demand_evidence_occurrence_provenance
       (object_id,demand_id)
    WHERE occurrence_role=2 AND object_id IS NOT NULL;

CREATE OR REPLACE VIEW execution.semantic_pnf_demand_direct_evidence_trigger_occurrence_v1 AS
SELECT provenance.demand_id,provenance.evidence_id,provenance.object_id,
       provenance.ordinal,provenance.producer_ref
  FROM execution.semantic_pnf_demand_evidence_occurrence_provenance AS provenance
 WHERE provenance.occurrence_role=1;

CREATE OR REPLACE VIEW execution.semantic_pnf_demand_direct_evidence_target_occurrence_v1 AS
SELECT provenance.demand_id,provenance.evidence_id,provenance.object_id,
       provenance.ordinal,provenance.producer_ref
  FROM execution.semantic_pnf_demand_evidence_occurrence_provenance AS provenance
 WHERE provenance.occurrence_role=2;

CREATE OR REPLACE VIEW execution.semantic_pnf_demand_direct_evidence_support_occurrence_v1 AS
SELECT provenance.demand_id,provenance.evidence_id,provenance.object_id,
       provenance.ordinal,provenance.producer_ref
  FROM execution.semantic_pnf_demand_evidence_occurrence_provenance AS provenance
 WHERE provenance.occurrence_role=3;

CREATE OR REPLACE VIEW execution.semantic_pnf_demand_direct_evidence_occurrence_audit_v1 AS
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
  LEFT JOIN execution.semantic_pnf_demand_evidence_occurrence_provenance AS provenance
    ON provenance.demand_id=demand.demand_id
  LEFT JOIN execution.semantic_pnf_demand_target_role_rule AS rule
    ON rule.residual_type_symbol_id=demand.residual_type_symbol_id
 GROUP BY demand.demand_id,rule.target_role_symbol_id;

-- Migration 171 is the normal statement-level parser-token projection.  The
-- direct producer has the same bounded fibre but a different durable source
-- carrier, so the normalizer must not attempt parser-token reconstruction.
CREATE OR REPLACE FUNCTION execution.compile_numeric_pnf_inserted_demand_occurrences()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    selected_ids BIGINT[];
BEGIN
    IF current_setting('sensiblaw.direct_evidence_demand_provenance',TRUE)='on' THEN
        RETURN NULL;
    END IF;
    SELECT array_agg(demand_id ORDER BY demand_id)
      INTO selected_ids
      FROM inserted_demand;
    PERFORM execution.compile_numeric_pnf_demand_occurrence_batch(selected_ids);
    RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION execution.compile_numeric_pnf_updated_demand_occurrences()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    selected_ids BIGINT[];
BEGIN
    IF current_setting('sensiblaw.direct_evidence_demand_provenance',TRUE)='on' THEN
        RETURN NULL;
    END IF;
    SELECT array_agg(current.demand_id ORDER BY current.demand_id)
      INTO selected_ids
      FROM updated_demand AS current
      JOIN prior_demand AS prior USING(demand_id)
     WHERE current.state IS DISTINCT FROM prior.state
        OR current.source_region_id IS DISTINCT FROM prior.source_region_id
        OR current.expected_factor_type_symbol_id
             IS DISTINCT FROM prior.expected_factor_type_symbol_id
        OR current.lexical_symbol_id IS DISTINCT FROM prior.lexical_symbol_id
        OR current.residual_type_symbol_id
             IS DISTINCT FROM prior.residual_type_symbol_id;
    PERFORM execution.compile_numeric_pnf_demand_occurrence_batch(selected_ids);
    RETURN NULL;
END;
$$;

COMMIT;
