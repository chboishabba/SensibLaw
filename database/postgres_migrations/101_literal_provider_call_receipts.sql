BEGIN;

-- 101: provider_call_count measures actual external/network calls, not
-- logical provider-boundary evaluations. A leased request may fail locally (for example,
-- no proof-producing identity adapter) with zero provider calls.
DO $$
DECLARE constraint_name TEXT;
BEGIN
    SELECT cons.conname INTO constraint_name
      FROM pg_constraint AS cons
     WHERE cons.conrelid=
           'execution.semantic_pnf_external_provider_batch_receipt'::regclass
       AND cons.contype='c'
       AND pg_get_constraintdef(cons.oid)
           LIKE '%leased_request_count = 0%provider_call_count > 0%'
     LIMIT 1;
    IF constraint_name IS NOT NULL THEN
        EXECUTE format(
            'ALTER TABLE execution.semantic_pnf_external_provider_batch_receipt DROP CONSTRAINT %I',
            constraint_name
        );
    END IF;
END;
$$;

COMMIT;
