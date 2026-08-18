BEGIN;

-- 157: replace migration-045's procedural mention compiler with the one live
-- semantic residue that later proof-relevant identity machinery still needs:
-- a source occurrence plus an anaphor_unresolved demand for parser pronouns.
--
-- The old trigger visited every noun/PROPN/pronoun/entity candidate on every
-- sentence closure and built mention/object/export/lookup state one candidate at
-- a time. Its second trigger recursively derived recurrence groups at every
-- non-sentence closure. Current H9 authority no longer consumes those derived
-- mention/recurrence projections: migrations 130/133/135 route world-facing
-- work through parser entity spans and producer-authored target occurrence
-- provenance. Recurrence groups have no production consumer outside 045.
--
-- Generic anaphor resolution is different: migration 045 was still the only
-- producer of anaphor_unresolved demands. Preserve that semantic obligation,
-- but project it directly from the numeric parser sentence fibre. Pronoun
-- spelling is stored as surface evidence, never as an identity key (064).

DROP TRIGGER IF EXISTS semantic_pnf_sentence_mention_derivation
    ON execution.semantic_pnf_region;
DROP TRIGGER IF EXISTS semantic_pnf_region_recurrence_derivation
    ON execution.semantic_pnf_region;

COMMENT ON FUNCTION execution.derive_numeric_sentence_mentions() IS
'Historical migration-045 procedural compiler retained for audit/schema compatibility. Automatic execution retired by migration 157.';
COMMENT ON FUNCTION execution.derive_numeric_region_recurrence() IS
'Historical migration-045 recurrence compiler retained for audit/schema compatibility. Automatic execution retired by migration 157.';

-- Resolve the tiny lexical/type boundary once. ensure_semantic_symbol gives the
-- same corpus-wide SymbolId the parser will later reuse; ordinary execution
-- below compares only numeric ids.
CREATE TABLE IF NOT EXISTS execution.semantic_pnf_anaphor_projection_constant (
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    pronoun_pos_symbol_id BIGINT NOT NULL
        REFERENCES execution.semantic_symbol(symbol_id) ON DELETE RESTRICT,
    pronoun_object_kind_symbol_id BIGINT NOT NULL
        REFERENCES execution.semantic_symbol(symbol_id) ON DELETE RESTRICT,
    anaphor_residual_type_symbol_id BIGINT NOT NULL
        REFERENCES execution.semantic_symbol(symbol_id) ON DELETE RESTRICT
);

INSERT INTO execution.semantic_pnf_anaphor_projection_constant
    (singleton,pronoun_pos_symbol_id,pronoun_object_kind_symbol_id,
     anaphor_residual_type_symbol_id)
VALUES (
    TRUE,
    execution.ensure_semantic_symbol(3::SMALLINT,'PRON'),
    execution.ensure_semantic_symbol(14::SMALLINT,'mention.pronoun'),
    execution.ensure_semantic_symbol(13::SMALLINT,'anaphor_unresolved')
)
ON CONFLICT(singleton) DO UPDATE SET
    pronoun_pos_symbol_id=EXCLUDED.pronoun_pos_symbol_id,
    pronoun_object_kind_symbol_id=EXCLUDED.pronoun_object_kind_symbol_id,
    anaphor_residual_type_symbol_id=EXCLUDED.anaphor_residual_type_symbol_id;

CREATE OR REPLACE FUNCTION execution.project_numeric_sentence_anaphors_setwise()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    -- Preserve the historical mention occurrence only for PRON sources. This is
    -- now a provenance/source coordinate, not a general semantic candidate
    -- compiler. All candidate selection remains in the typed demand planner.
    WITH affected AS MATERIALIZED (
        SELECT current.region_id
          FROM updated_region AS current
          JOIN prior_region AS prior USING(region_id)
         WHERE current.region_kind=1
           AND current.closure_state IN (2,3)
           AND prior.closure_state IS DISTINCT FROM current.closure_state
    ), pronoun AS MATERIALIZED (
        SELECT affected.region_id,sentence.sentence_id,
               token.token_id,token.start_char,token.end_char,token.lemma_symbol_id,
               constant.pronoun_object_kind_symbol_id,
               constant.anaphor_residual_type_symbol_id
          FROM affected
          JOIN execution.semantic_pnf_sentence_region AS link
            ON link.region_id=affected.region_id
          JOIN execution.semantic_parser_sentence AS sentence
            ON sentence.sentence_id=link.sentence_id
          JOIN execution.semantic_pnf_anaphor_projection_constant AS constant
            ON constant.singleton
          JOIN execution.semantic_parser_token AS token
            ON token.sentence_id=sentence.sentence_id
           AND token.representation_version=2
           AND token.pos_symbol_id=constant.pronoun_pos_symbol_id
    )
    INSERT INTO execution.semantic_pnf_mention
        (mention_digest,region_id,sentence_id,mention_kind,start_char,end_char,
         head_token_id,head_symbol_id,entity_type_symbol_id,
         grammatical_role_symbol_id,information_gain,representation_cost,
         ambiguity_cost,promotion_score,active)
    SELECT digest(
               int8send(pronoun.region_id)
               || int8send(pronoun.token_id)
               || int8send(pronoun.start_char)
               || int8send(pronoun.end_char)
               || int2send(4::SMALLINT),
               'sha256'
           ),
           pronoun.region_id,pronoun.sentence_id,4::SMALLINT,
           pronoun.start_char,pronoun.end_char,pronoun.token_id,
           pronoun.lemma_symbol_id,NULL,NULL,
           1.0,1.0,2.0,0.0,TRUE
      FROM pronoun
    ON CONFLICT(region_id,start_char,end_char,mention_kind) DO UPDATE SET
        active=TRUE,
        head_token_id=EXCLUDED.head_token_id,
        head_symbol_id=EXCLUDED.head_symbol_id;

    WITH affected AS MATERIALIZED (
        SELECT current.region_id
          FROM updated_region AS current
          JOIN prior_region AS prior USING(region_id)
         WHERE current.region_kind=1
           AND current.closure_state IN (2,3)
           AND prior.closure_state IS DISTINCT FROM current.closure_state
    ), pronoun AS MATERIALIZED (
        SELECT affected.region_id,sentence.sentence_id,
               token.token_id,token.start_char,token.end_char,token.lemma_symbol_id,
               constant.pronoun_object_kind_symbol_id,
               constant.anaphor_residual_type_symbol_id
          FROM affected
          JOIN execution.semantic_pnf_sentence_region AS link
            ON link.region_id=affected.region_id
          JOIN execution.semantic_parser_sentence AS sentence
            ON sentence.sentence_id=link.sentence_id
          JOIN execution.semantic_pnf_anaphor_projection_constant AS constant
            ON constant.singleton
          JOIN execution.semantic_parser_token AS token
            ON token.sentence_id=sentence.sentence_id
           AND token.representation_version=2
           AND token.pos_symbol_id=constant.pronoun_pos_symbol_id
    ), source AS MATERIALIZED (
        SELECT pronoun.*,
               mention.mention_id,
               digest(
                   int8send(mention.mention_id)
                   || int8send(pronoun.region_id)
                   || int8send(pronoun.pronoun_object_kind_symbol_id),
                   'sha256'
               ) AS object_digest
          FROM pronoun
          JOIN execution.semantic_pnf_mention AS mention
            ON mention.region_id=pronoun.region_id
           AND mention.start_char=pronoun.start_char
           AND mention.end_char=pronoun.end_char
           AND mention.mention_kind=4
    )
    INSERT INTO execution.semantic_pnf_object
        (object_digest,region_id,object_kind_symbol_id,head_symbol_id,
         scope_region_id,promotion_level,information_gain,representation_cost,
         ambiguity_cost,promotion_score,active)
    SELECT source.object_digest,source.region_id,
           source.pronoun_object_kind_symbol_id,source.lemma_symbol_id,
           source.region_id,0,1.0,1.0,2.0,0.0,TRUE
      FROM source
    ON CONFLICT(object_digest) DO UPDATE SET active=TRUE;

    WITH affected AS MATERIALIZED (
        SELECT current.region_id
          FROM updated_region AS current
          JOIN prior_region AS prior USING(region_id)
         WHERE current.region_kind=1
           AND current.closure_state IN (2,3)
           AND prior.closure_state IS DISTINCT FROM current.closure_state
    ), source AS MATERIALIZED (
        SELECT affected.region_id,sentence.sentence_id,
               token.token_id,token.start_char,token.end_char,token.lemma_symbol_id,
               constant.pronoun_object_kind_symbol_id,
               constant.anaphor_residual_type_symbol_id,
               mention.mention_id,
               object.object_id
          FROM affected
          JOIN execution.semantic_pnf_sentence_region AS link
            ON link.region_id=affected.region_id
          JOIN execution.semantic_parser_sentence AS sentence
            ON sentence.sentence_id=link.sentence_id
          JOIN execution.semantic_pnf_anaphor_projection_constant AS constant
            ON constant.singleton
          JOIN execution.semantic_parser_token AS token
            ON token.sentence_id=sentence.sentence_id
           AND token.representation_version=2
           AND token.pos_symbol_id=constant.pronoun_pos_symbol_id
          JOIN execution.semantic_pnf_mention AS mention
            ON mention.region_id=affected.region_id
           AND mention.start_char=token.start_char
           AND mention.end_char=token.end_char
           AND mention.mention_kind=4
          JOIN execution.semantic_pnf_object AS object
            ON object.object_digest=digest(
                int8send(mention.mention_id)
                || int8send(affected.region_id)
                || int8send(constant.pronoun_object_kind_symbol_id),
                'sha256'
            )
    )
    INSERT INTO execution.semantic_pnf_mention_token(mention_id,token_id,ordinal)
    SELECT mention_id,token_id,0 FROM source
    ON CONFLICT DO NOTHING;

    WITH affected AS MATERIALIZED (
        SELECT current.region_id
          FROM updated_region AS current
          JOIN prior_region AS prior USING(region_id)
         WHERE current.region_kind=1
           AND current.closure_state IN (2,3)
           AND prior.closure_state IS DISTINCT FROM current.closure_state
    ), source AS MATERIALIZED (
        SELECT affected.region_id,token.token_id,token.start_char,token.end_char,
               token.lemma_symbol_id,constant.pronoun_object_kind_symbol_id,
               constant.anaphor_residual_type_symbol_id,mention.mention_id,
               object.object_id,interface.interface_id
          FROM affected
          JOIN execution.semantic_pnf_sentence_region AS link
            ON link.region_id=affected.region_id
          JOIN execution.semantic_parser_token AS token
            ON token.sentence_id=link.sentence_id
           AND token.representation_version=2
          JOIN execution.semantic_pnf_anaphor_projection_constant AS constant
            ON constant.singleton
           AND token.pos_symbol_id=constant.pronoun_pos_symbol_id
          JOIN execution.semantic_pnf_mention AS mention
            ON mention.region_id=affected.region_id
           AND mention.start_char=token.start_char
           AND mention.end_char=token.end_char
           AND mention.mention_kind=4
          JOIN execution.semantic_pnf_object AS object
            ON object.object_digest=digest(
                int8send(mention.mention_id)
                || int8send(affected.region_id)
                || int8send(constant.pronoun_object_kind_symbol_id),
                'sha256'
            )
          JOIN execution.semantic_pnf_interface AS interface
            ON interface.region_id=affected.region_id
    )
    INSERT INTO execution.semantic_pnf_object_token_support(object_id,token_id,ordinal)
    SELECT object_id,token_id,0 FROM source
    ON CONFLICT DO NOTHING;

    WITH affected AS MATERIALIZED (
        SELECT current.region_id
          FROM updated_region AS current
          JOIN prior_region AS prior USING(region_id)
         WHERE current.region_kind=1
           AND current.closure_state IN (2,3)
           AND prior.closure_state IS DISTINCT FROM current.closure_state
    ), source AS MATERIALIZED (
        SELECT affected.region_id,token.token_id,token.start_char,token.end_char,
               token.lemma_symbol_id,constant.pronoun_object_kind_symbol_id,
               constant.anaphor_residual_type_symbol_id,mention.mention_id,
               object.object_id,interface.interface_id
          FROM affected
          JOIN execution.semantic_pnf_sentence_region AS link
            ON link.region_id=affected.region_id
          JOIN execution.semantic_parser_token AS token
            ON token.sentence_id=link.sentence_id
           AND token.representation_version=2
          JOIN execution.semantic_pnf_anaphor_projection_constant AS constant
            ON constant.singleton
           AND token.pos_symbol_id=constant.pronoun_pos_symbol_id
          JOIN execution.semantic_pnf_mention AS mention
            ON mention.region_id=affected.region_id
           AND mention.start_char=token.start_char
           AND mention.end_char=token.end_char
           AND mention.mention_kind=4
          JOIN execution.semantic_pnf_object AS object
            ON object.object_digest=digest(
                int8send(mention.mention_id)
                || int8send(affected.region_id)
                || int8send(constant.pronoun_object_kind_symbol_id),
                'sha256'
            )
          JOIN execution.semantic_pnf_interface AS interface
            ON interface.region_id=affected.region_id
    )
    INSERT INTO execution.semantic_pnf_object_mention_support(object_id,mention_id)
    SELECT object_id,mention_id FROM source
    ON CONFLICT DO NOTHING;

    WITH affected AS MATERIALIZED (
        SELECT current.region_id
          FROM updated_region AS current
          JOIN prior_region AS prior USING(region_id)
         WHERE current.region_kind=1
           AND current.closure_state IN (2,3)
           AND prior.closure_state IS DISTINCT FROM current.closure_state
    ), source AS MATERIALIZED (
        SELECT affected.region_id,token.token_id,token.start_char,token.end_char,
               token.lemma_symbol_id,constant.pronoun_object_kind_symbol_id,
               constant.anaphor_residual_type_symbol_id,mention.mention_id,
               object.object_id,interface.interface_id
          FROM affected
          JOIN execution.semantic_pnf_sentence_region AS link
            ON link.region_id=affected.region_id
          JOIN execution.semantic_parser_token AS token
            ON token.sentence_id=link.sentence_id
           AND token.representation_version=2
          JOIN execution.semantic_pnf_anaphor_projection_constant AS constant
            ON constant.singleton
           AND token.pos_symbol_id=constant.pronoun_pos_symbol_id
          JOIN execution.semantic_pnf_mention AS mention
            ON mention.region_id=affected.region_id
           AND mention.start_char=token.start_char
           AND mention.end_char=token.end_char
           AND mention.mention_kind=4
          JOIN execution.semantic_pnf_object AS object
            ON object.object_digest=digest(
                int8send(mention.mention_id)
                || int8send(affected.region_id)
                || int8send(constant.pronoun_object_kind_symbol_id),
                'sha256'
            )
          JOIN execution.semantic_pnf_interface AS interface
            ON interface.region_id=affected.region_id
    )
    UPDATE execution.semantic_pnf_mention AS mention
       SET object_id=source.object_id
      FROM source
     WHERE mention.mention_id=source.mention_id
       AND mention.object_id IS DISTINCT FROM source.object_id;

    WITH affected AS MATERIALIZED (
        SELECT current.region_id
          FROM updated_region AS current
          JOIN prior_region AS prior USING(region_id)
         WHERE current.region_kind=1
           AND current.closure_state IN (2,3)
           AND prior.closure_state IS DISTINCT FROM current.closure_state
    ), source AS MATERIALIZED (
        SELECT affected.region_id,token.token_id,token.start_char,token.end_char,
               token.lemma_symbol_id,constant.pronoun_object_kind_symbol_id,
               constant.anaphor_residual_type_symbol_id,mention.mention_id,
               object.object_id,interface.interface_id
          FROM affected
          JOIN execution.semantic_pnf_sentence_region AS link
            ON link.region_id=affected.region_id
          JOIN execution.semantic_parser_token AS token
            ON token.sentence_id=link.sentence_id
           AND token.representation_version=2
          JOIN execution.semantic_pnf_anaphor_projection_constant AS constant
            ON constant.singleton
           AND token.pos_symbol_id=constant.pronoun_pos_symbol_id
          JOIN execution.semantic_pnf_mention AS mention
            ON mention.region_id=affected.region_id
           AND mention.start_char=token.start_char
           AND mention.end_char=token.end_char
           AND mention.mention_kind=4
          JOIN execution.semantic_pnf_object AS object
            ON object.object_digest=digest(
                int8send(mention.mention_id)
                || int8send(affected.region_id)
                || int8send(constant.pronoun_object_kind_symbol_id),
                'sha256'
            )
          JOIN execution.semantic_pnf_interface AS interface
            ON interface.region_id=affected.region_id
    )
    INSERT INTO execution.semantic_pnf_interface_export
        (interface_id,export_kind,target_kind,target_id,key_symbol_id,
         role_symbol_id,rank,promotion_score)
    SELECT interface_id,1,1,object_id,lemma_symbol_id,NULL,start_char,0
      FROM source
    ON CONFLICT DO NOTHING;

    -- The demand carries the source object directly. The pronoun lemma remains
    -- surface evidence only; lexical_symbol_id is intentionally NULL so it can
    -- never constrain candidate identity.
    WITH affected AS MATERIALIZED (
        SELECT current.region_id
          FROM updated_region AS current
          JOIN prior_region AS prior USING(region_id)
         WHERE current.region_kind=1
           AND current.closure_state IN (2,3)
           AND prior.closure_state IS DISTINCT FROM current.closure_state
    ), source AS MATERIALIZED (
        SELECT affected.region_id,token.token_id,token.start_char,
               token.lemma_symbol_id,constant.pronoun_object_kind_symbol_id,
               constant.anaphor_residual_type_symbol_id,mention.mention_id,
               object.object_id,interface.interface_id
          FROM affected
          JOIN execution.semantic_pnf_sentence_region AS link
            ON link.region_id=affected.region_id
          JOIN execution.semantic_parser_token AS token
            ON token.sentence_id=link.sentence_id
           AND token.representation_version=2
          JOIN execution.semantic_pnf_anaphor_projection_constant AS constant
            ON constant.singleton
           AND token.pos_symbol_id=constant.pronoun_pos_symbol_id
          JOIN execution.semantic_pnf_mention AS mention
            ON mention.region_id=affected.region_id
           AND mention.start_char=token.start_char
           AND mention.end_char=token.end_char
           AND mention.mention_kind=4
          JOIN execution.semantic_pnf_object AS object
            ON object.object_digest=digest(
                int8send(mention.mention_id)
                || int8send(affected.region_id)
                || int8send(constant.pronoun_object_kind_symbol_id),
                'sha256'
            )
          JOIN execution.semantic_pnf_interface AS interface
            ON interface.region_id=affected.region_id
    )
    INSERT INTO execution.semantic_pnf_demand
        (demand_digest,source_interface_id,source_region_id,source_object_id,
         expected_target_kind,expected_object_kind_symbol_id,
         lexical_symbol_id,surface_lexical_symbol_id,role_symbol_id,
         residual_type_symbol_id,recency_class,state,max_candidates)
    SELECT digest(
               int8send(source.mention_id)
               || int8send(source.anaphor_residual_type_symbol_id),
               'sha256'
           ),
           source.interface_id,source.region_id,source.object_id,
           1,source.pronoun_object_kind_symbol_id,
           NULL,source.lemma_symbol_id,NULL,
           source.anaphor_residual_type_symbol_id,3,1,16
      FROM source
    ON CONFLICT(demand_digest) DO UPDATE SET
        source_interface_id=EXCLUDED.source_interface_id,
        source_object_id=EXCLUDED.source_object_id,
        surface_lexical_symbol_id=EXCLUDED.surface_lexical_symbol_id,
        state=LEAST(execution.semantic_pnf_demand.state,1);

    -- Keep interface cardinalities exact after adding the sparse pronoun source
    -- projection. This is one grouped update per affected sentence fibre, not a
    -- per-candidate update inside a procedural loop.
    WITH affected_interface AS MATERIALIZED (
        SELECT interface.interface_id
          FROM updated_region AS current
          JOIN prior_region AS prior USING(region_id)
          JOIN execution.semantic_pnf_interface AS interface
            ON interface.region_id=current.region_id
         WHERE current.region_kind=1
           AND current.closure_state IN (2,3)
           AND prior.closure_state IS DISTINCT FROM current.closure_state
    ), counts AS (
        SELECT interface.interface_id,
               count(export.target_id)::BIGINT AS total_count,
               count(export.target_id) FILTER (WHERE export.target_kind=1)::BIGINT
                   AS object_count,
               count(export.target_id) FILTER (WHERE export.target_kind=3)::BIGINT
                   AS demand_count
          FROM affected_interface AS interface
          LEFT JOIN execution.semantic_pnf_interface_export AS export
            ON export.interface_id=interface.interface_id
         GROUP BY interface.interface_id
    )
    UPDATE execution.semantic_pnf_interface AS interface
       SET interface_cardinality=counts.total_count,
           promoted_object_count=counts.object_count,
           unresolved_count=counts.demand_count
      FROM counts
     WHERE interface.interface_id=counts.interface_id;

    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_setwise_anaphor_projection
    ON execution.semantic_pnf_region;
CREATE TRIGGER semantic_pnf_setwise_anaphor_projection
AFTER UPDATE ON execution.semantic_pnf_region
REFERENCING OLD TABLE AS prior_region NEW TABLE AS updated_region
FOR EACH STATEMENT
EXECUTE FUNCTION execution.project_numeric_sentence_anaphors_setwise();

COMMIT;
