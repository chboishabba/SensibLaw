BEGIN;

-- 111 keeps immutable identity witnesses demand-agnostic while exposing the
-- demand attribution that can actually be justified by existing structure.
-- It deliberately does NOT backfill semantic_pnf_identity_witness.demand_id.
--
-- support_kind:
--   1 explicit witness.demand_id provenance
--   2 demand source_object_id is the witness source object
--   3 demand source object and witness source object share the exact parser token
--
-- Kind 3 reuses the same exact representation bridge accepted elsewhere in the
-- PNF runtime. Paragraph co-presence, lexical similarity, and region proximity
-- are absent by construction.
CREATE OR REPLACE VIEW execution.semantic_pnf_identity_witness_demand_support_v1 AS
WITH direct_support AS (
    SELECT witness.witness_id,witness.demand_id,1::SMALLINT AS support_kind,
           NULL::BIGINT AS support_token_id
      FROM execution.semantic_pnf_identity_witness AS witness
     WHERE witness.demand_id IS NOT NULL
), source_object_support AS (
    SELECT witness.witness_id,demand.demand_id,2::SMALLINT AS support_kind,
           NULL::BIGINT AS support_token_id
      FROM execution.semantic_pnf_identity_witness AS witness
      JOIN execution.semantic_pnf_demand AS demand
        ON demand.source_object_id=witness.source_object_id
), token_support AS (
    SELECT DISTINCT witness.witness_id,demand.demand_id,
           3::SMALLINT AS support_kind,demand_support.token_id AS support_token_id
      FROM execution.semantic_pnf_identity_witness AS witness
      JOIN execution.semantic_pnf_object_token_support AS witness_support
        ON witness_support.object_id=witness.source_object_id
      JOIN execution.semantic_pnf_object_token_support AS demand_support
        ON demand_support.token_id=witness_support.token_id
       AND demand_support.object_id<>witness.source_object_id
      JOIN execution.semantic_pnf_demand AS demand
        ON demand.source_object_id=demand_support.object_id
), combined AS (
    SELECT * FROM direct_support
    UNION ALL
    SELECT * FROM source_object_support
    UNION ALL
    SELECT * FROM token_support
)
SELECT DISTINCT ON (combined.witness_id,combined.demand_id)
       combined.witness_id,combined.demand_id,combined.support_kind,
       combined.support_token_id,
       witness.source_object_id,witness.target_entity_id,witness.witness_kind,
       witness.authority_class,
       admission.admission_state
  FROM combined
  JOIN execution.semantic_pnf_identity_witness AS witness
    ON witness.witness_id=combined.witness_id
  LEFT JOIN execution.semantic_pnf_identity_witness_admission AS admission
    ON admission.witness_id=witness.witness_id
 ORDER BY combined.witness_id,combined.demand_id,combined.support_kind,
          combined.support_token_id NULLS FIRST;

CREATE OR REPLACE VIEW execution.semantic_pnf_accepted_identity_witness_demand_support_v1 AS
SELECT *
  FROM execution.semantic_pnf_identity_witness_demand_support_v1
 WHERE admission_state=2;

CREATE OR REPLACE VIEW execution.semantic_pnf_identity_witness_demand_support_summary_v1 AS
SELECT support_kind,admission_state,
       count(*)::BIGINT AS support_rows,
       count(DISTINCT witness_id)::BIGINT AS witness_count,
       count(DISTINCT demand_id)::BIGINT AS demand_count
  FROM execution.semantic_pnf_identity_witness_demand_support_v1
 GROUP BY support_kind,admission_state;

COMMIT;
