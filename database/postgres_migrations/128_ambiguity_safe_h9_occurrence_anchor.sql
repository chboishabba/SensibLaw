BEGIN;

CREATE OR REPLACE VIEW execution.semantic_pnf_h9_preferred_entity_anchor_v1 AS
WITH cardinality AS (
    SELECT demand_id,count(DISTINCT source_object_id)::BIGINT AS object_count
      FROM execution.semantic_pnf_h9_entity_label_anchor_v1
     GROUP BY demand_id
), unique_object AS (
    SELECT anchor.*
      FROM execution.semantic_pnf_h9_entity_label_anchor_v1 AS anchor
      JOIN cardinality USING(demand_id)
     WHERE cardinality.object_count=1
)
SELECT DISTINCT ON (anchor.demand_id)
       anchor.demand_id,anchor.source_object_id,anchor.label_symbol_id,
       anchor.anchor_kind,anchor.anchor_strength
  FROM unique_object AS anchor
 ORDER BY anchor.demand_id,anchor.anchor_strength DESC,
          anchor.label_symbol_id,anchor.source_object_id;

CREATE OR REPLACE VIEW execution.semantic_pnf_h9_occurrence_ambiguity_v1 AS
SELECT support.demand_id,
       count(DISTINCT support.object_id)::BIGINT AS strong_object_count,
       count(DISTINCT label.source_object_id)::BIGINT AS labelled_object_count,
       (count(DISTINCT label.source_object_id)>1) AS label_anchor_ambiguous
  FROM execution.semantic_pnf_demand_strong_occurrence_support_v1 AS support
  LEFT JOIN execution.semantic_pnf_h9_entity_label_anchor_v1 AS label
    ON label.demand_id=support.demand_id
   AND label.source_object_id=support.object_id
 GROUP BY support.demand_id;

COMMIT;
