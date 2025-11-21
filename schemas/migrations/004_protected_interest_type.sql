-- Milestone 3 extension: Protected Interest Types with value dimensions
-- Depends on: protected_interest (Milestone 3)
BEGIN;

CREATE TABLE IF NOT EXISTS protected_interest_type (
    id BIGSERIAL PRIMARY KEY,
    legal_system_id BIGINT NOT NULL REFERENCES legal_system(id),
    code TEXT NOT NULL,
    label TEXT NOT NULL,
    description TEXT,
    value_dimension_id BIGINT,
    cultural_register_id BIGINT REFERENCES cultural_register(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (legal_system_id, code)
);

-- Backfill the type table from any existing protected_interest rows
INSERT INTO protected_interest_type (
    id, legal_system_id, code, label, description, value_dimension_id, cultural_register_id, created_at, updated_at
)
SELECT
    pi.id,
    pi.legal_system_id,
    pi.code,
    pi.label,
    pi.description,
    NULL::BIGINT AS value_dimension_id,
    pi.cultural_register_id,
    pi.created_at,
    pi.updated_at
FROM protected_interest pi
ON CONFLICT (legal_system_id, code) DO UPDATE SET
    label = EXCLUDED.label,
    description = COALESCE(EXCLUDED.description, protected_interest_type.description),
    value_dimension_id = COALESCE(EXCLUDED.value_dimension_id, protected_interest_type.value_dimension_id),
    cultural_register_id = COALESCE(EXCLUDED.cultural_register_id, protected_interest_type.cultural_register_id),
    updated_at = NOW();

SELECT setval(
    pg_get_serial_sequence('protected_interest_type', 'id'),
    COALESCE((SELECT MAX(id) FROM protected_interest_type), 0),
    true
);

-- Bridge view allows legacy protected_interest records to map to the new type table
CREATE OR REPLACE VIEW protected_interest_type_bridge AS
SELECT
    pi.id AS protected_interest_id,
    pit.id AS protected_interest_type_id,
    pi.legal_system_id,
    pi.code,
    pi.label,
    COALESCE(pit.description, pi.description) AS description,
    pit.value_dimension_id,
    COALESCE(pit.cultural_register_id, pi.cultural_register_id) AS cultural_register_id,
    pi.created_at,
    pi.updated_at
FROM protected_interest pi
JOIN protected_interest_type pit
    ON pit.legal_system_id = pi.legal_system_id
   AND pit.code = pi.code;

COMMIT;
