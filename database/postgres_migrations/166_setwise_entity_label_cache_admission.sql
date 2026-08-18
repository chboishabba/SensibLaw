BEGIN;

-- 166: corpus entity/label reuse is a rebuildable projection of immutable
-- identity witnesses plus their current admission state. Migration 091 refreshed
-- one cache cell per witness-row trigger and rescanned all accepted witnesses in
-- that cell each time. A batch admission therefore paid repeated work for the
-- same (label,entity,authority) fibre.
--
-- Preserve the exact cache semantics while projecting only the distinct cells
-- touched by one INSERT/UPDATE statement. History/witness authority is unchanged.

DROP TRIGGER IF EXISTS semantic_pnf_identity_admission_refresh_label_cache
    ON execution.semantic_pnf_identity_witness_admission;

CREATE OR REPLACE FUNCTION execution.project_numeric_pnf_inserted_entity_label_cache()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    WITH affected_cell AS MATERIALIZED (
        SELECT DISTINCT
               object.head_symbol_id AS label_symbol_id,
               witness.target_entity_id AS canonical_entity_id,
               witness.authority_class
          FROM inserted_admission AS admission
          JOIN execution.semantic_pnf_identity_witness AS witness
            ON witness.witness_id=admission.witness_id
          JOIN execution.semantic_pnf_object AS object
            ON object.object_id=witness.source_object_id
         WHERE object.head_symbol_id IS NOT NULL
    ), support AS MATERIALIZED (
        SELECT cell.label_symbol_id,
               cell.canonical_entity_id,
               cell.authority_class,
               count(admission.witness_id)::BIGINT AS admitted_support_count,
               max(witness.witness_id)::BIGINT AS latest_witness_id
          FROM affected_cell AS cell
          LEFT JOIN execution.semantic_pnf_identity_witness AS witness
            ON witness.target_entity_id=cell.canonical_entity_id
           AND witness.authority_class=cell.authority_class
          LEFT JOIN execution.semantic_pnf_object AS object
            ON object.object_id=witness.source_object_id
           AND object.head_symbol_id=cell.label_symbol_id
          LEFT JOIN execution.semantic_pnf_identity_witness_admission AS admission
            ON admission.witness_id=witness.witness_id
           AND admission.admission_state=2
         WHERE object.object_id IS NOT NULL
         GROUP BY cell.label_symbol_id,
                  cell.canonical_entity_id,
                  cell.authority_class
    )
    DELETE FROM execution.semantic_pnf_corpus_entity_label_cache AS cache
     USING support
     WHERE cache.label_symbol_id=support.label_symbol_id
       AND cache.canonical_entity_id=support.canonical_entity_id
       AND cache.authority_class=support.authority_class
       AND support.admitted_support_count=0;

    WITH affected_cell AS MATERIALIZED (
        SELECT DISTINCT
               object.head_symbol_id AS label_symbol_id,
               witness.target_entity_id AS canonical_entity_id,
               witness.authority_class
          FROM inserted_admission AS admission
          JOIN execution.semantic_pnf_identity_witness AS witness
            ON witness.witness_id=admission.witness_id
          JOIN execution.semantic_pnf_object AS object
            ON object.object_id=witness.source_object_id
         WHERE object.head_symbol_id IS NOT NULL
    ), support AS MATERIALIZED (
        SELECT cell.label_symbol_id,
               cell.canonical_entity_id,
               cell.authority_class,
               count(admission.witness_id)::BIGINT AS admitted_support_count,
               max(witness.witness_id)::BIGINT AS latest_witness_id
          FROM affected_cell AS cell
          JOIN execution.semantic_pnf_identity_witness AS witness
            ON witness.target_entity_id=cell.canonical_entity_id
           AND witness.authority_class=cell.authority_class
          JOIN execution.semantic_pnf_object AS object
            ON object.object_id=witness.source_object_id
           AND object.head_symbol_id=cell.label_symbol_id
          JOIN execution.semantic_pnf_identity_witness_admission AS admission
            ON admission.witness_id=witness.witness_id
           AND admission.admission_state=2
         GROUP BY cell.label_symbol_id,
                  cell.canonical_entity_id,
                  cell.authority_class
    )
    INSERT INTO execution.semantic_pnf_corpus_entity_label_cache
        (label_symbol_id,canonical_entity_id,authority_class,
         admitted_support_count,latest_witness_id)
    SELECT support.label_symbol_id,
           support.canonical_entity_id,
           support.authority_class,
           support.admitted_support_count,
           support.latest_witness_id
      FROM support
     WHERE support.admitted_support_count>0
    ON CONFLICT(label_symbol_id,canonical_entity_id,authority_class) DO UPDATE SET
        admitted_support_count=EXCLUDED.admitted_support_count,
        latest_witness_id=EXCLUDED.latest_witness_id;

    RETURN NULL;
END;
$$;

CREATE TRIGGER semantic_pnf_identity_admission_refresh_label_cache_insert_batch
AFTER INSERT ON execution.semantic_pnf_identity_witness_admission
REFERENCING NEW TABLE AS inserted_admission
FOR EACH STATEMENT
EXECUTE FUNCTION execution.project_numeric_pnf_inserted_entity_label_cache();

CREATE OR REPLACE FUNCTION execution.project_numeric_pnf_updated_entity_label_cache()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    WITH changed_witness AS MATERIALIZED (
        SELECT current.witness_id
          FROM updated_admission AS current
          JOIN prior_admission AS prior USING(witness_id)
         WHERE current.admission_state IS DISTINCT FROM prior.admission_state
    ), affected_cell AS MATERIALIZED (
        SELECT DISTINCT
               object.head_symbol_id AS label_symbol_id,
               witness.target_entity_id AS canonical_entity_id,
               witness.authority_class
          FROM changed_witness AS changed
          JOIN execution.semantic_pnf_identity_witness AS witness
            ON witness.witness_id=changed.witness_id
          JOIN execution.semantic_pnf_object AS object
            ON object.object_id=witness.source_object_id
         WHERE object.head_symbol_id IS NOT NULL
    ), support AS MATERIALIZED (
        SELECT cell.label_symbol_id,
               cell.canonical_entity_id,
               cell.authority_class,
               count(admission.witness_id)::BIGINT AS admitted_support_count,
               max(witness.witness_id)::BIGINT AS latest_witness_id
          FROM affected_cell AS cell
          LEFT JOIN execution.semantic_pnf_identity_witness AS witness
            ON witness.target_entity_id=cell.canonical_entity_id
           AND witness.authority_class=cell.authority_class
          LEFT JOIN execution.semantic_pnf_object AS object
            ON object.object_id=witness.source_object_id
           AND object.head_symbol_id=cell.label_symbol_id
          LEFT JOIN execution.semantic_pnf_identity_witness_admission AS admission
            ON admission.witness_id=witness.witness_id
           AND admission.admission_state=2
         WHERE object.object_id IS NOT NULL
         GROUP BY cell.label_symbol_id,
                  cell.canonical_entity_id,
                  cell.authority_class
    )
    DELETE FROM execution.semantic_pnf_corpus_entity_label_cache AS cache
     USING support
     WHERE cache.label_symbol_id=support.label_symbol_id
       AND cache.canonical_entity_id=support.canonical_entity_id
       AND cache.authority_class=support.authority_class
       AND support.admitted_support_count=0;

    WITH changed_witness AS MATERIALIZED (
        SELECT current.witness_id
          FROM updated_admission AS current
          JOIN prior_admission AS prior USING(witness_id)
         WHERE current.admission_state IS DISTINCT FROM prior.admission_state
    ), affected_cell AS MATERIALIZED (
        SELECT DISTINCT
               object.head_symbol_id AS label_symbol_id,
               witness.target_entity_id AS canonical_entity_id,
               witness.authority_class
          FROM changed_witness AS changed
          JOIN execution.semantic_pnf_identity_witness AS witness
            ON witness.witness_id=changed.witness_id
          JOIN execution.semantic_pnf_object AS object
            ON object.object_id=witness.source_object_id
         WHERE object.head_symbol_id IS NOT NULL
    ), support AS MATERIALIZED (
        SELECT cell.label_symbol_id,
               cell.canonical_entity_id,
               cell.authority_class,
               count(admission.witness_id)::BIGINT AS admitted_support_count,
               max(witness.witness_id)::BIGINT AS latest_witness_id
          FROM affected_cell AS cell
          JOIN execution.semantic_pnf_identity_witness AS witness
            ON witness.target_entity_id=cell.canonical_entity_id
           AND witness.authority_class=cell.authority_class
          JOIN execution.semantic_pnf_object AS object
            ON object.object_id=witness.source_object_id
           AND object.head_symbol_id=cell.label_symbol_id
          JOIN execution.semantic_pnf_identity_witness_admission AS admission
            ON admission.witness_id=witness.witness_id
           AND admission.admission_state=2
         GROUP BY cell.label_symbol_id,
                  cell.canonical_entity_id,
                  cell.authority_class
    )
    INSERT INTO execution.semantic_pnf_corpus_entity_label_cache
        (label_symbol_id,canonical_entity_id,authority_class,
         admitted_support_count,latest_witness_id)
    SELECT support.label_symbol_id,
           support.canonical_entity_id,
           support.authority_class,
           support.admitted_support_count,
           support.latest_witness_id
      FROM support
     WHERE support.admitted_support_count>0
    ON CONFLICT(label_symbol_id,canonical_entity_id,authority_class) DO UPDATE SET
        admitted_support_count=EXCLUDED.admitted_support_count,
        latest_witness_id=EXCLUDED.latest_witness_id;

    RETURN NULL;
END;
$$;

CREATE TRIGGER semantic_pnf_identity_admission_refresh_label_cache_update_batch
AFTER UPDATE ON execution.semantic_pnf_identity_witness_admission
REFERENCING OLD TABLE AS prior_admission NEW TABLE AS updated_admission
FOR EACH STATEMENT
EXECUTE FUNCTION execution.project_numeric_pnf_updated_entity_label_cache();

COMMIT;
