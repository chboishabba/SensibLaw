BEGIN;

-- 124: provider labels are occurrence-derived over strong support objects.
CREATE OR REPLACE VIEW execution.semantic_pnf_h9_entity_label_anchor_v1 AS
WITH attached AS (
    SELECT DISTINCT s.demand_id,s.object_id AS source_object_id,
           a.label_symbol_id,3::SMALLINT AS anchor_kind,300::SMALLINT AS anchor_strength
      FROM execution.semantic_pnf_demand_strong_occurrence_support_v1 s
      JOIN execution.semantic_pnf_object_token_support ot ON ot.object_id=s.object_id
      JOIN execution.semantic_pnf_mention_world_attachment a
        ON a.token_id=ot.token_id AND a.attachment_state=1
), one_token AS (
    SELECT s.demand_id,s.object_id AS source_object_id,min(ot.token_id) AS token_id
      FROM execution.semantic_pnf_demand_strong_occurrence_support_v1 s
      JOIN execution.semantic_pnf_object_token_support ot ON ot.object_id=s.object_id
     GROUP BY s.demand_id,s.object_id
    HAVING count(DISTINCT ot.token_id)=1
), admitted_identity AS (
    SELECT DISTINCT o.demand_id,o.source_object_id,t.orth_symbol_id AS label_symbol_id,
           2::SMALLINT AS anchor_kind,200::SMALLINT AS anchor_strength
      FROM one_token o
      JOIN execution.semantic_pnf_identity_projection ip
        ON ip.source_object_id=o.source_object_id
      JOIN execution.semantic_parser_token t
        ON t.token_id=o.token_id AND t.representation_version=2
     WHERE t.orth_symbol_id IS NOT NULL
), parser_entity AS (
    SELECT DISTINCT o.demand_id,o.source_object_id,t.orth_symbol_id AS label_symbol_id,
           1::SMALLINT AS anchor_kind,100::SMALLINT AS anchor_strength
      FROM one_token o
      JOIN execution.semantic_pnf_object_mention_support os
        ON os.object_id=o.source_object_id
      JOIN execution.semantic_pnf_mention m
        ON m.mention_id=os.mention_id AND m.mention_kind=1 AND m.active
      JOIN execution.semantic_pnf_mention_token mt
        ON mt.mention_id=m.mention_id AND mt.token_id=o.token_id
      JOIN execution.semantic_parser_token t
        ON t.token_id=o.token_id AND t.representation_version=2
     WHERE t.orth_symbol_id IS NOT NULL
       AND NOT EXISTS (
           SELECT 1 FROM execution.semantic_pnf_mention_token extra
            WHERE extra.mention_id=m.mention_id AND extra.token_id<>o.token_id
       )
)
SELECT * FROM attached
UNION SELECT * FROM admitted_identity
UNION SELECT * FROM parser_entity;

CREATE OR REPLACE VIEW execution.semantic_pnf_h9_preferred_entity_anchor_v1 AS
SELECT DISTINCT ON (a.demand_id)
       a.demand_id,a.source_object_id,a.label_symbol_id,a.anchor_kind,a.anchor_strength
  FROM execution.semantic_pnf_h9_entity_label_anchor_v1 a
 ORDER BY a.demand_id,a.anchor_strength DESC,a.label_symbol_id,a.source_object_id;

COMMIT;
