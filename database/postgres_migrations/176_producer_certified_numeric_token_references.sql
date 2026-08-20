BEGIN;

-- 176: migration 175 removed the whole-fibre post-insert dependency rewrite.
-- A trigger-aware prefix profile then showed that the remaining strict-v2 token
-- INSERT spends roughly half of its wall time in row-level RI checks. Nine of
-- those checks are duplicated producer-known references: five numeric semantic
-- symbols plus four annotation-origin ids. The bounded strict producer already
-- owns those complete reference fibres before COPY.
--
-- Replace only those nine row FKs with an exact set-wise integrity realization.
-- Generic writers still validate every non-null reference against the authority
-- tables after each INSERT/UPDATE statement. The strict producer may bypass
-- those statement checks only after independently proving the complete bounded
-- symbol/origin reference sets against the same authority tables and enabling a
-- capability scoped to that one INSERT. Reverse delete / referenced-key-update
-- restriction remains explicit on the authority tables.
--
-- Legacy textual parser-symbol FKs, sentence/run/partition FKs, morph-set FK,
-- and token self-head FKs are intentionally untouched.

ALTER TABLE execution.semantic_parser_token
    DROP CONSTRAINT IF EXISTS semantic_parser_token_orth_symbol_id_fkey,
    DROP CONSTRAINT IF EXISTS semantic_parser_token_lemma_symbol_id_fkey,
    DROP CONSTRAINT IF EXISTS semantic_parser_token_pos_symbol_id_fkey,
    DROP CONSTRAINT IF EXISTS semantic_parser_token_tag_symbol_id_fkey,
    DROP CONSTRAINT IF EXISTS semantic_parser_token_dependency_symbol_id_fkey,
    DROP CONSTRAINT IF EXISTS semantic_parser_token_lemma_origin_id_fkey,
    DROP CONSTRAINT IF EXISTS semantic_parser_token_pos_origin_id_fkey,
    DROP CONSTRAINT IF EXISTS semantic_parser_token_tag_origin_id_fkey,
    DROP CONSTRAINT IF EXISTS semantic_parser_token_dependency_origin_id_fkey;

CREATE OR REPLACE FUNCTION execution.validate_numeric_parser_reference_set_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF current_setting(
        'sensiblaw.producer_certified_numeric_references',
        TRUE
    ) = 'on' THEN
        RETURN NULL;
    END IF;

    IF EXISTS (
        WITH requested(symbol_id) AS (
            SELECT orth_symbol_id FROM inserted_token WHERE orth_symbol_id IS NOT NULL
            UNION
            SELECT lemma_symbol_id FROM inserted_token WHERE lemma_symbol_id IS NOT NULL
            UNION
            SELECT pos_symbol_id FROM inserted_token WHERE pos_symbol_id IS NOT NULL
            UNION
            SELECT tag_symbol_id FROM inserted_token WHERE tag_symbol_id IS NOT NULL
            UNION
            SELECT dependency_symbol_id
              FROM inserted_token
             WHERE dependency_symbol_id IS NOT NULL
        )
        SELECT 1
          FROM requested
          LEFT JOIN execution.semantic_symbol AS authority
            ON authority.symbol_id = requested.symbol_id
         WHERE authority.symbol_id IS NULL
    ) THEN
        RAISE EXCEPTION USING
            ERRCODE = '23503',
            MESSAGE = 'numeric parser token references a missing semantic symbol';
    END IF;

    IF EXISTS (
        WITH requested(origin_id) AS (
            SELECT lemma_origin_id FROM inserted_token
            UNION
            SELECT pos_origin_id FROM inserted_token
            UNION
            SELECT tag_origin_id FROM inserted_token
            UNION
            SELECT dependency_origin_id FROM inserted_token
        )
        SELECT 1
          FROM requested
          LEFT JOIN execution.semantic_parser_annotation_origin AS authority
            ON authority.origin_id = requested.origin_id
         WHERE authority.origin_id IS NULL
    ) THEN
        RAISE EXCEPTION USING
            ERRCODE = '23503',
            MESSAGE = 'numeric parser token references a missing annotation origin';
    END IF;

    RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION execution.validate_numeric_parser_reference_set_update()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF current_setting(
        'sensiblaw.producer_certified_numeric_references',
        TRUE
    ) = 'on' THEN
        RETURN NULL;
    END IF;

    IF EXISTS (
        WITH requested(symbol_id) AS (
            SELECT orth_symbol_id FROM updated_token WHERE orth_symbol_id IS NOT NULL
            UNION
            SELECT lemma_symbol_id FROM updated_token WHERE lemma_symbol_id IS NOT NULL
            UNION
            SELECT pos_symbol_id FROM updated_token WHERE pos_symbol_id IS NOT NULL
            UNION
            SELECT tag_symbol_id FROM updated_token WHERE tag_symbol_id IS NOT NULL
            UNION
            SELECT dependency_symbol_id
              FROM updated_token
             WHERE dependency_symbol_id IS NOT NULL
        )
        SELECT 1
          FROM requested
          LEFT JOIN execution.semantic_symbol AS authority
            ON authority.symbol_id = requested.symbol_id
         WHERE authority.symbol_id IS NULL
    ) THEN
        RAISE EXCEPTION USING
            ERRCODE = '23503',
            MESSAGE = 'numeric parser token update references a missing semantic symbol';
    END IF;

    IF EXISTS (
        WITH requested(origin_id) AS (
            SELECT lemma_origin_id FROM updated_token
            UNION
            SELECT pos_origin_id FROM updated_token
            UNION
            SELECT tag_origin_id FROM updated_token
            UNION
            SELECT dependency_origin_id FROM updated_token
        )
        SELECT 1
          FROM requested
          LEFT JOIN execution.semantic_parser_annotation_origin AS authority
            ON authority.origin_id = requested.origin_id
         WHERE authority.origin_id IS NULL
    ) THEN
        RAISE EXCEPTION USING
            ERRCODE = '23503',
            MESSAGE = 'numeric parser token update references a missing annotation origin';
    END IF;

    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS semantic_parser_token_numeric_reference_set_insert
    ON execution.semantic_parser_token;
CREATE TRIGGER semantic_parser_token_numeric_reference_set_insert
AFTER INSERT ON execution.semantic_parser_token
REFERENCING NEW TABLE AS inserted_token
FOR EACH STATEMENT
EXECUTE FUNCTION execution.validate_numeric_parser_reference_set_insert();

-- PostgreSQL does not allow a transition relation on an UPDATE OF column-list
-- trigger. Validate the finite NEW transition relation after any UPDATE; this
-- is the exact generic fallback and avoids an illegal UPDATE OF + NEW TABLE
-- construction.
DROP TRIGGER IF EXISTS semantic_parser_token_numeric_reference_set_update
    ON execution.semantic_parser_token;
CREATE TRIGGER semantic_parser_token_numeric_reference_set_update
AFTER UPDATE ON execution.semantic_parser_token
REFERENCING NEW TABLE AS updated_token
FOR EACH STATEMENT
EXECUTE FUNCTION execution.validate_numeric_parser_reference_set_update();

CREATE OR REPLACE FUNCTION execution.restrict_numeric_parser_symbol_authority_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM execution.semantic_parser_token AS token
         WHERE token.orth_symbol_id = OLD.symbol_id
            OR token.lemma_symbol_id = OLD.symbol_id
            OR token.pos_symbol_id = OLD.symbol_id
            OR token.tag_symbol_id = OLD.symbol_id
            OR token.dependency_symbol_id = OLD.symbol_id
         LIMIT 1
    ) THEN
        RAISE EXCEPTION USING
            ERRCODE = '23503',
            MESSAGE = 'semantic symbol remains referenced by semantic_parser_token';
    END IF;
    IF TG_OP = 'UPDATE' THEN
        RETURN NEW;
    END IF;
    RETURN OLD;
END;
$$;

DROP TRIGGER IF EXISTS semantic_symbol_token_reference_delete_restrict
    ON execution.semantic_symbol;
CREATE TRIGGER semantic_symbol_token_reference_delete_restrict
BEFORE DELETE ON execution.semantic_symbol
FOR EACH ROW
EXECUTE FUNCTION execution.restrict_numeric_parser_symbol_authority_change();

DROP TRIGGER IF EXISTS semantic_symbol_token_reference_key_update_restrict
    ON execution.semantic_symbol;
CREATE TRIGGER semantic_symbol_token_reference_key_update_restrict
BEFORE UPDATE OF symbol_id ON execution.semantic_symbol
FOR EACH ROW
WHEN (OLD.symbol_id IS DISTINCT FROM NEW.symbol_id)
EXECUTE FUNCTION execution.restrict_numeric_parser_symbol_authority_change();

CREATE OR REPLACE FUNCTION execution.restrict_numeric_parser_origin_authority_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM execution.semantic_parser_token AS token
         WHERE token.lemma_origin_id = OLD.origin_id
            OR token.pos_origin_id = OLD.origin_id
            OR token.tag_origin_id = OLD.origin_id
            OR token.dependency_origin_id = OLD.origin_id
         LIMIT 1
    ) THEN
        RAISE EXCEPTION USING
            ERRCODE = '23503',
            MESSAGE = 'annotation origin remains referenced by semantic_parser_token';
    END IF;
    IF TG_OP = 'UPDATE' THEN
        RETURN NEW;
    END IF;
    RETURN OLD;
END;
$$;

DROP TRIGGER IF EXISTS semantic_parser_origin_token_reference_delete_restrict
    ON execution.semantic_parser_annotation_origin;
CREATE TRIGGER semantic_parser_origin_token_reference_delete_restrict
BEFORE DELETE ON execution.semantic_parser_annotation_origin
FOR EACH ROW
EXECUTE FUNCTION execution.restrict_numeric_parser_origin_authority_change();

DROP TRIGGER IF EXISTS semantic_parser_origin_token_reference_key_update_restrict
    ON execution.semantic_parser_annotation_origin;
CREATE TRIGGER semantic_parser_origin_token_reference_key_update_restrict
BEFORE UPDATE OF origin_id ON execution.semantic_parser_annotation_origin
FOR EACH ROW
WHEN (OLD.origin_id IS DISTINCT FROM NEW.origin_id)
EXECUTE FUNCTION execution.restrict_numeric_parser_origin_authority_change();

CREATE OR REPLACE FUNCTION execution.numeric_parser_producer_certified_references_ready()
RETURNS BOOLEAN
LANGUAGE sql
IMMUTABLE
AS $$
SELECT TRUE;
$$;

COMMIT;
