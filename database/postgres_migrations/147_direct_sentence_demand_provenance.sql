BEGIN;

-- 147: strict numeric sentence admission already owns the complete bounded
-- producer fibre (factor, factor support, typed slots and demand specification).
-- It may therefore project exact occurrence provenance set-wise instead of
-- invoking the generic row-at-a-time reconstruction trigger for every demand.
--
-- The generic trigger remains authoritative for every other producer. A strict
-- sentence transaction opts into producer-native projection explicitly with a
-- transaction-local custom GUC. The flag is execution state only and never
-- participates in semantic identity.

DROP TRIGGER IF EXISTS semantic_pnf_demand_occurrence_producer
    ON execution.semantic_pnf_demand;
CREATE TRIGGER semantic_pnf_demand_occurrence_producer
AFTER INSERT OR UPDATE OF
    state,source_region_id,expected_factor_type_symbol_id,
    lexical_symbol_id,residual_type_symbol_id
ON execution.semantic_pnf_demand
FOR EACH ROW
WHEN (
    current_setting(
        'sensiblaw.direct_sentence_demand_provenance',
        TRUE
    ) IS DISTINCT FROM 'on'
)
EXECUTE FUNCTION execution.record_numeric_pnf_demand_occurrence_provenance();

COMMIT;
