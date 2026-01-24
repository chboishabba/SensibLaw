-- Layer 3: Wrong types, protected interests, and source links (PostgreSQL)
-- Depends on: 001_layer1_normative.sql, 002_layer2_actors.sql
BEGIN;

CREATE TABLE IF NOT EXISTS value_dimension (
    id BIGSERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    family TEXT,
    aspect TEXT,
    description TEXT
);

CREATE TABLE IF NOT EXISTS protected_interest_type (
    id BIGSERIAL PRIMARY KEY,
    legal_system_id BIGINT NOT NULL REFERENCES legal_system(id),
    code TEXT NOT NULL,
    label TEXT NOT NULL,
    description TEXT,
    value_dimension_id BIGINT REFERENCES value_dimension(id),
    cultural_register_id BIGINT REFERENCES cultural_register(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (legal_system_id, code)
);

CREATE TABLE IF NOT EXISTS wrong_type (
    id BIGSERIAL PRIMARY KEY,
    legal_system_id BIGINT NOT NULL REFERENCES legal_system(id),
    norm_source_category_id BIGINT NOT NULL REFERENCES norm_source_category(id),
    code TEXT NOT NULL,
    label TEXT NOT NULL,
    version TEXT NOT NULL DEFAULT 'v1',
    summary TEXT,
    authoring_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (legal_system_id, code, version),
    UNIQUE (id, legal_system_id)
);

CREATE TABLE IF NOT EXISTS wrong_type_protected_interest_type (
    wrong_type_id BIGINT NOT NULL REFERENCES wrong_type(id),
    protected_interest_type_id BIGINT NOT NULL REFERENCES protected_interest_type(id),
    PRIMARY KEY (wrong_type_id, protected_interest_type_id)
);

CREATE TABLE IF NOT EXISTS wrong_type_source (
    wrong_type_id BIGINT NOT NULL REFERENCES wrong_type(id),
    legal_source_id BIGINT NOT NULL REFERENCES legal_source(id),
    relation_type TEXT NOT NULL,
    pinpoint TEXT,
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (wrong_type_id, legal_source_id, relation_type)
);

CREATE TABLE IF NOT EXISTS mental_state (
    id BIGSERIAL PRIMARY KEY,
    wrong_type_id BIGINT NOT NULL REFERENCES wrong_type(id),
    state_code TEXT NOT NULL,
    label TEXT NOT NULL,
    description TEXT,
    severity INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (wrong_type_id, state_code),
    CHECK (state_code IN ('intent', 'recklessness', 'negligence', 'strict'))
);

CREATE OR REPLACE FUNCTION ensure_wrong_type_has_interest()
RETURNS TRIGGER AS $$
DECLARE
    target_id BIGINT;
BEGIN
    IF TG_TABLE_NAME = 'wrong_type' THEN
        target_id := NEW.id;
    ELSE
        target_id := COALESCE(NEW.wrong_type_id, OLD.wrong_type_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM wrong_type_protected_interest_type wpi
        WHERE wpi.wrong_type_id = target_id
    ) THEN
        RAISE EXCEPTION 'wrong_type % must reference at least one protected_interest_type', target_id;
    END IF;

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

CREATE CONSTRAINT TRIGGER wrong_type_requires_interest
AFTER INSERT OR UPDATE ON wrong_type
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION ensure_wrong_type_has_interest();

CREATE CONSTRAINT TRIGGER wrong_type_interest_bridge_guard
AFTER INSERT OR UPDATE OR DELETE ON wrong_type_protected_interest_type
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION ensure_wrong_type_has_interest();

COMMIT;
