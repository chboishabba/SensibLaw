BEGIN;

-- 180 / E0d: relation-valued delta projection for generic sentence anaphors.
--
-- DASHI's consumer/residual boundary requires this optimisation to preserve the
-- represented demand relation rather than quotient away surface/provenance
-- coordinates. SensibLaw migration 073 already uses the corresponding runtime
-- rule: transition deltas may change physical work, while authority identity is
-- preserved until parity is certified.
--
-- Migration 157 made anaphor production set-wise inside one trigger invocation,
-- but attached that projector directly to every UPDATE statement on
-- semantic_pnf_region. Region maintenance outside sentence closure therefore
-- invoked the full projector repeatedly even when its affected relation was
-- empty. The function also re-read the same parser-token fibre for each output
-- family.
--
-- E0d separates the semantic projector from its trigger adaptor:
--
--   changed sentence regions
--       -> one materialized pronoun-occurrence relation
--       -> mention/object/support/export/demand atoms
--       -> existing demand projection / candidate / authority triggers
--
-- The semantic projector is relation-valued (BIGINT[] sentence-region delta).
-- The region trigger remains only as a compatibility execution adaptor so its
-- historical trigger ordering relative to other region-close consumers is
-- unchanged. An empty/non-sentence region UPDATE performs one transition-table
-- key extraction and never enters the projector.
--
-- Important authority boundaries retained from 161/168:
--   * pronoun kind belongs to the source occurrence, not the referent;
--   * pronoun spelling is surface evidence, not an identity constraint;
--   * candidate evidence is not resolution;
--   * demand normalisation is BEFORE-row and performs no recursive self-write.

CREATE OR REPLACE FUNCTION execution.project_numeric_sentence_anaphor_delta(
    selected_region_ids BIGINT[]
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    projected_occurrences BIGINT := 0;
BEGIN
    IF selected_region_ids IS NULL
       OR cardinality(selected_region_ids)=0 THEN
        RETURN 0;
    END IF;

    -- Materialize the delta source exactly once per trigger/tranche invocation.
    -- pg_temp is session-local, so concurrent parser workers do not share this
    -- execution carrier. It is projection scratch, never semantic authority.
    CREATE TEMP TABLE IF NOT EXISTS semantic_pnf_anaphor_delta_source (
        region_id BIGINT NOT NULL,
        sentence_id BIGINT NOT NULL,
        token_id BIGINT NOT NULL,
        start_char BIGINT NOT NULL,
        end_char BIGINT NOT NULL,
        lemma_symbol_id BIGINT NOT NULL,
        pronoun_object_kind_symbol_id BIGINT NOT NULL,
        anaphor_residual_type_symbol_id BIGINT NOT NULL,
        PRIMARY KEY(region_id,token_id)
    ) ON COMMIT DELETE ROWS;

    TRUNCATE TABLE pg_temp.semantic_pnf_anaphor_delta_source;

    INSERT INTO pg_temp.semantic_pnf_anaphor_delta_source
        (region_id,sentence_id,token_id,start_char,end_char,lemma_symbol_id,
         pronoun_object_kind_symbol_id,anaphor_residual_type_symbol_id)
    SELECT region.region_id,
           sentence.sentence_id,
           token.token_id,
           token.start_char,
           token.end_char,
           token.lemma_symbol_id,
           constant.pronoun_object_kind_symbol_id,
           constant.anaphor_residual_type_symbol_id
      FROM execution.semantic_pnf_region AS region
      JOIN execution.semantic_pnf_sentence_region AS link
        ON link.region_id=region.region_id
      JOIN execution.semantic_parser_sentence AS sentence
        ON sentence.sentence_id=link.sentence_id
      JOIN execution.semantic_parser_token AS token
        ON token.sentence_id=sentence.sentence_id
       AND token.representation_version=2
      JOIN execution.semantic_pnf_anaphor_projection_constant AS constant
        ON constant.singleton
       AND token.pos_symbol_id=constant.pronoun_pos_symbol_id
     WHERE region.region_id=ANY(selected_region_ids)
       AND region.region_kind=1
       AND region.closure_state IN (2,3)
    ON CONFLICT(region_id,token_id) DO UPDATE SET
        sentence_id=EXCLUDED.sentence_id,
        start_char=EXCLUDED.start_char,
        end_char=EXCLUDED.end_char,
        lemma_symbol_id=EXCLUDED.lemma_symbol_id,
        pronoun_object_kind_symbol_id=EXCLUDED.pronoun_object_kind_symbol_id,
        anaphor_residual_type_symbol_id=EXCLUDED.anaphor_residual_type_symbol_id;

    GET DIAGNOSTICS projected_occurrences=ROW_COUNT;
    IF projected_occurrences=0 THEN
        RETURN 0;
    END IF;

    -- Historical mention/source occurrence: exact migration-157 digest and
    -- coordinates, now driven from the one delta-source relation.
    INSERT INTO execution.semantic_pnf_mention
        (mention_digest,region_id,sentence_id,mention_kind,start_char,end_char,
         head_token_id,head_symbol_id,entity_type_symbol_id,
         grammatical_role_symbol_id,information_gain,representation_cost,
         ambiguity_cost,promotion_score,active)
    SELECT digest(
               int8send(source.region_id)
               || int8send(source.token_id)
               || int8send(source.start_char)
               || int8send(source.end_char)
               || int2send(4::SMALLINT),
               'sha256'
           ),
           source.region_id,source.sentence_id,4::SMALLINT,
           source.start_char,source.end_char,source.token_id,
           source.lemma_symbol_id,NULL,NULL,
           1.0,1.0,2.0,0.0,TRUE
      FROM pg_temp.semantic_pnf_anaphor_delta_source AS source
    ON CONFLICT(region_id,start_char,end_char,mention_kind) DO UPDATE SET
        active=TRUE,
        head_token_id=EXCLUDED.head_token_id,
        head_symbol_id=EXCLUDED.head_symbol_id;

    INSERT INTO execution.semantic_pnf_object
        (object_digest,region_id,object_kind_symbol_id,head_symbol_id,
         scope_region_id,promotion_level,information_gain,representation_cost,
         ambiguity_cost,promotion_score,active)
    SELECT digest(
               int8send(mention.mention_id)
               || int8send(source.region_id)
               || int8send(source.pronoun_object_kind_symbol_id),
               'sha256'
           ),
           source.region_id,
           source.pronoun_object_kind_symbol_id,
           source.lemma_symbol_id,
           source.region_id,0,1.0,1.0,2.0,0.0,TRUE
      FROM pg_temp.semantic_pnf_anaphor_delta_source AS source
      JOIN execution.semantic_pnf_mention AS mention
        ON mention.region_id=source.region_id
       AND mention.start_char=source.start_char
       AND mention.end_char=source.end_char
       AND mention.mention_kind=4
    ON CONFLICT(object_digest) DO UPDATE SET active=TRUE;

    -- Exact source supports. All three carriers are monotone/idempotent.
    INSERT INTO execution.semantic_pnf_mention_token(mention_id,token_id,ordinal)
    SELECT mention.mention_id,source.token_id,0
      FROM pg_temp.semantic_pnf_anaphor_delta_source AS source
      JOIN execution.semantic_pnf_mention AS mention
        ON mention.region_id=source.region_id
       AND mention.start_char=source.start_char
       AND mention.end_char=source.end_char
       AND mention.mention_kind=4
    ON CONFLICT DO NOTHING;

    INSERT INTO execution.semantic_pnf_object_token_support(object_id,token_id,ordinal)
    SELECT object.object_id,source.token_id,0
      FROM pg_temp.semantic_pnf_anaphor_delta_source AS source
      JOIN execution.semantic_pnf_mention AS mention
        ON mention.region_id=source.region_id
       AND mention.start_char=source.start_char
       AND mention.end_char=source.end_char
       AND mention.mention_kind=4
      JOIN execution.semantic_pnf_object AS object
        ON object.object_digest=digest(
            int8send(mention.mention_id)
            || int8send(source.region_id)
            || int8send(source.pronoun_object_kind_symbol_id),
            'sha256'
        )
    ON CONFLICT DO NOTHING;

    INSERT INTO execution.semantic_pnf_object_mention_support(object_id,mention_id)
    SELECT object.object_id,mention.mention_id
      FROM pg_temp.semantic_pnf_anaphor_delta_source AS source
      JOIN execution.semantic_pnf_mention AS mention
        ON mention.region_id=source.region_id
       AND mention.start_char=source.start_char
       AND mention.end_char=source.end_char
       AND mention.mention_kind=4
      JOIN execution.semantic_pnf_object AS object
        ON object.object_digest=digest(
            int8send(mention.mention_id)
            || int8send(source.region_id)
            || int8send(source.pronoun_object_kind_symbol_id),
            'sha256'
        )
    ON CONFLICT DO NOTHING;

    UPDATE execution.semantic_pnf_mention AS mention
       SET object_id=object.object_id
      FROM pg_temp.semantic_pnf_anaphor_delta_source AS source,
           execution.semantic_pnf_object AS object
     WHERE mention.region_id=source.region_id
       AND mention.start_char=source.start_char
       AND mention.end_char=source.end_char
       AND mention.mention_kind=4
       AND object.object_digest=digest(
           int8send(mention.mention_id)
           || int8send(source.region_id)
           || int8send(source.pronoun_object_kind_symbol_id),
           'sha256'
       )
       AND mention.object_id IS DISTINCT FROM object.object_id;

    -- Preserve the source-object interface export exactly. This remains a
    -- pronoun occurrence export, not a claim about referent identity.
    INSERT INTO execution.semantic_pnf_interface_export
        (interface_id,export_kind,target_kind,target_id,key_symbol_id,
         role_symbol_id,rank,promotion_score)
    SELECT interface.interface_id,1,1,object.object_id,
           source.lemma_symbol_id,NULL,source.start_char,0
      FROM pg_temp.semantic_pnf_anaphor_delta_source AS source
      JOIN execution.semantic_pnf_mention AS mention
        ON mention.region_id=source.region_id
       AND mention.start_char=source.start_char
       AND mention.end_char=source.end_char
       AND mention.mention_kind=4
      JOIN execution.semantic_pnf_object AS object
        ON object.object_digest=digest(
            int8send(mention.mention_id)
            || int8send(source.region_id)
            || int8send(source.pronoun_object_kind_symbol_id),
            'sha256'
        )
      JOIN execution.semantic_pnf_interface AS interface
        ON interface.region_id=source.region_id
    ON CONFLICT DO NOTHING;

    -- Directly write the canonical post-161/post-168 demand shape. The BEFORE
    -- normalizers remain installed as authority guards for every other caller.
    -- Existing demand statement triggers derive position/export/lookup,
    -- occurrence/candidate and downstream wake surfaces from this one write.
    INSERT INTO execution.semantic_pnf_demand
        (demand_digest,source_interface_id,source_region_id,source_object_id,
         expected_target_kind,expected_object_kind_symbol_id,
         lexical_symbol_id,surface_lexical_symbol_id,role_symbol_id,
         residual_type_symbol_id,recency_class,state,max_candidates)
    SELECT digest(
               int8send(mention.mention_id)
               || int8send(source.anaphor_residual_type_symbol_id),
               'sha256'
           ),
           interface.interface_id,source.region_id,object.object_id,
           1,NULL,
           NULL,source.lemma_symbol_id,NULL,
           source.anaphor_residual_type_symbol_id,3,1,16
      FROM pg_temp.semantic_pnf_anaphor_delta_source AS source
      JOIN execution.semantic_pnf_mention AS mention
        ON mention.region_id=source.region_id
       AND mention.start_char=source.start_char
       AND mention.end_char=source.end_char
       AND mention.mention_kind=4
      JOIN execution.semantic_pnf_object AS object
        ON object.object_digest=digest(
            int8send(mention.mention_id)
            || int8send(source.region_id)
            || int8send(source.pronoun_object_kind_symbol_id),
            'sha256'
        )
      JOIN execution.semantic_pnf_interface AS interface
        ON interface.region_id=source.region_id
    ON CONFLICT(demand_digest) DO UPDATE SET
        source_interface_id=EXCLUDED.source_interface_id,
        source_object_id=EXCLUDED.source_object_id,
        surface_lexical_symbol_id=EXCLUDED.surface_lexical_symbol_id,
        state=LEAST(execution.semantic_pnf_demand.state,1);

    -- Recompute only the affected consumer keys (sentence interfaces). This is
    -- the DeltaFedLocalReducer shape: exact local reconciliation is preferable
    -- to maintaining a second global cardinality authority.
    WITH affected_interface AS MATERIALIZED (
        SELECT DISTINCT interface.interface_id
          FROM pg_temp.semantic_pnf_anaphor_delta_source AS source
          JOIN execution.semantic_pnf_interface AS interface
            ON interface.region_id=source.region_id
    ), counts AS (
        SELECT affected.interface_id,
               count(export.target_id)::BIGINT AS total_count,
               count(export.target_id) FILTER (WHERE export.target_kind=1)::BIGINT
                   AS object_count,
               count(export.target_id) FILTER (WHERE export.target_kind=3)::BIGINT
                   AS demand_count
          FROM affected_interface AS affected
          LEFT JOIN execution.semantic_pnf_interface_export AS export
            ON export.interface_id=affected.interface_id
         GROUP BY affected.interface_id
    )
    UPDATE execution.semantic_pnf_interface AS interface
       SET interface_cardinality=counts.total_count,
           promoted_object_count=counts.object_count,
           unresolved_count=counts.demand_count
      FROM counts
     WHERE interface.interface_id=counts.interface_id;

    RETURN projected_occurrences;
END;
$$;

COMMENT ON FUNCTION execution.project_numeric_sentence_anaphor_delta(BIGINT[]) IS
'E0d relation-valued anaphor delta projector. Materializes selected closed-sentence PRON occurrences once, preserves migration-157 identities plus 161/168 authority boundaries, and locally reconciles only affected sentence interfaces.';

-- Keep the historical trigger function name as a thin execution adaptor. This
-- preserves trigger ordering while ensuring non-sentence region UPDATEs never
-- enter the semantic projector.
CREATE OR REPLACE FUNCTION execution.project_numeric_sentence_anaphors_setwise()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    selected_region_ids BIGINT[];
BEGIN
    SELECT array_agg(current.region_id ORDER BY current.region_id)
      INTO selected_region_ids
      FROM updated_region AS current
      JOIN prior_region AS prior USING(region_id)
     WHERE current.region_kind=1
       AND current.closure_state IN (2,3)
       AND prior.closure_state IS DISTINCT FROM current.closure_state;

    IF selected_region_ids IS NOT NULL
       AND cardinality(selected_region_ids)>0 THEN
        PERFORM execution.project_numeric_sentence_anaphor_delta(
            selected_region_ids
        );
    END IF;
    RETURN NULL;
END;
$$;

COMMENT ON FUNCTION execution.project_numeric_sentence_anaphors_setwise() IS
'E0d compatibility adaptor for semantic_pnf_setwise_anaphor_projection. Extracts the changed sentence-region relation from transition tables and invokes the relation-valued delta projector only when non-empty.';

-- Recreate the trigger under its existing identity so alphabetical ordering
-- relative to other AFTER UPDATE region consumers is unchanged.
DROP TRIGGER IF EXISTS semantic_pnf_setwise_anaphor_projection
    ON execution.semantic_pnf_region;
CREATE TRIGGER semantic_pnf_setwise_anaphor_projection
AFTER UPDATE ON execution.semantic_pnf_region
REFERENCING OLD TABLE AS prior_region NEW TABLE AS updated_region
FOR EACH STATEMENT
EXECUTE FUNCTION execution.project_numeric_sentence_anaphors_setwise();

COMMIT;
