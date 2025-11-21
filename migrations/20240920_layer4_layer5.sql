-- Milestone 4 & 5 migrations: Events, Harms, Evidence, Value Frames, and Remedies
-- Tables assume prior milestones created LegalSystem, ActorClass, RoleMarker,
-- ProtectedInterestType (see schemas/migrations/004_protected_interest_type.sql),
-- CulturalRegister, and any WrongType scaffolding.

BEGIN;

CREATE TABLE IF NOT EXISTS event (
    id BIGSERIAL PRIMARY KEY,
    wrong_type_id BIGINT REFERENCES wrong_type(id),
    legal_system_id BIGINT NOT NULL REFERENCES legal_system(id),
    label TEXT NOT NULL,
    event_kind TEXT NOT NULL,
    occurred_at TIMESTAMPTZ,
    valid_from TIMESTAMPTZ,
    valid_to TIMESTAMPTZ,
    location TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS event_participant (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES event(id) ON DELETE CASCADE,
    actor_class_id BIGINT NOT NULL REFERENCES actor_class(id),
    role_marker_id BIGINT REFERENCES role_marker(id),
    role_label TEXT,
    participation_note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS harm_instance (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES event(id) ON DELETE CASCADE,
    protected_interest_type_id BIGINT NOT NULL REFERENCES protected_interest_type(id),
    severity TEXT,
    extent TEXT,
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS incident_evidence (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES event(id) ON DELETE CASCADE,
    evidence_uri TEXT,
    evidence_type TEXT,
    description TEXT,
    provenance JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS value_frame (
    id BIGSERIAL PRIMARY KEY,
    frame_code TEXT NOT NULL UNIQUE,
    label TEXT,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS remedy (
    id BIGSERIAL PRIMARY KEY,
    harm_instance_id BIGINT REFERENCES harm_instance(id) ON DELETE CASCADE,
    legal_system_id BIGINT NOT NULL REFERENCES legal_system(id),
    cultural_register_id BIGINT REFERENCES cultural_register(id),
    remedy_modality TEXT NOT NULL,
    remedy_code TEXT,
    terms TEXT,
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS value_frame_remedies (
    value_frame_id BIGINT NOT NULL REFERENCES value_frame(id) ON DELETE CASCADE,
    remedy_id BIGINT NOT NULL REFERENCES remedy(id) ON DELETE CASCADE,
    PRIMARY KEY (value_frame_id, remedy_id)
);

-- View: auto-link harms to their protected interests for downstream services
DROP VIEW IF EXISTS harm_interest_links;
CREATE VIEW harm_interest_links AS
SELECT
    h.id AS harm_instance_id,
    h.event_id,
    h.protected_interest_type_id,
    pit.label AS protected_interest_label,
    pit.description AS protected_interest_description,
    pit.value_dimension_id,
    pit.cultural_register_id,
    e.legal_system_id,
    e.event_kind,
    h.severity,
    h.extent,
    h.note
FROM harm_instance h
JOIN protected_interest_type pit ON pit.id = h.protected_interest_type_id
JOIN event e ON e.id = h.event_id;

-- View: rollup for harm counts by protected interest and legal system
DROP VIEW IF EXISTS harm_counts_by_interest;
CREATE VIEW harm_counts_by_interest AS
SELECT
    pit.id AS protected_interest_type_id,
    pit.description AS protected_interest_description,
    e.legal_system_id,
    COUNT(h.id) AS harm_count,
    COUNT(DISTINCT e.id) AS event_count
FROM harm_instance h
JOIN event e ON e.id = h.event_id
JOIN protected_interest_type pit ON pit.id = h.protected_interest_type_id
GROUP BY pit.id, pit.description, e.legal_system_id;

-- View: remedy library joined to value frames for quick lookup
DROP VIEW IF EXISTS remedy_library_by_value_frame;
CREATE VIEW remedy_library_by_value_frame AS
SELECT
    vf.id AS value_frame_id,
    vf.frame_code,
    vf.label AS value_frame_label,
    r.id AS remedy_id,
    r.remedy_modality,
    r.remedy_code,
    r.terms,
    r.note,
    r.legal_system_id,
    r.cultural_register_id
FROM value_frame vf
JOIN value_frame_remedies vfr ON vfr.value_frame_id = vf.id
JOIN remedy r ON r.id = vfr.remedy_id;

-- Seed a small library of value frames and remedies for reference builds
INSERT INTO value_frame (frame_code, label, description) VALUES
    ('gender_equality', 'Gender equality', 'Equity and bodily autonomy considerations'),
    ('tikanga_balance', 'Tikanga balance', 'Restoration and mana-enhancing remedies'),
    ('child_rights', 'Child rights', 'Best interests of the child and protective measures')
ON CONFLICT (frame_code) DO UPDATE SET
    label = EXCLUDED.label,
    description = EXCLUDED.description,
    updated_at = NOW();

INSERT INTO remedy (legal_system_id, cultural_register_id, remedy_modality, remedy_code, terms, note)
SELECT
    ls.id,
    NULL::BIGINT,
    seed.remedy_modality,
    seed.remedy_code,
    seed.terms,
    seed.note
FROM (
    VALUES
        ('MONETARY', 'COMPENSATION', 'Compensation for financial or reputational loss', 'gender_equality', NULL::TEXT),
        ('STRUCTURAL', 'INJUNCTION', 'Injunction or order to prevent ongoing harm', 'gender_equality', NULL::TEXT),
        ('RESTORATIVE_RITUAL', 'APOLOGY', 'Restorative apology anchored in tikanga', 'tikanga_balance', NULL::TEXT),
        ('STATUS_CHANGE', 'CUSTODY_ORDER', 'Custody or guardianship order prioritising welfare', 'child_rights', NULL::TEXT)
) AS seed(remedy_modality, remedy_code, terms, frame_code, note)
CROSS JOIN legal_system ls
WHERE NOT EXISTS (
    SELECT 1 FROM remedy r
    WHERE r.remedy_code = seed.remedy_code AND r.legal_system_id = ls.id
);

-- Map seeded remedies to their frames whenever both are present
WITH frame_ids AS (
    SELECT frame_code, id FROM value_frame WHERE frame_code IN ('gender_equality', 'tikanga_balance', 'child_rights')
), seed(remedy_code, frame_code) AS (
    VALUES
        ('COMPENSATION', 'gender_equality'),
        ('INJUNCTION', 'gender_equality'),
        ('APOLOGY', 'tikanga_balance'),
        ('CUSTODY_ORDER', 'child_rights')
)
INSERT INTO value_frame_remedies (value_frame_id, remedy_id)
SELECT DISTINCT
    f.id,
    r.id
FROM seed s
JOIN frame_ids f ON f.frame_code = s.frame_code
JOIN remedy r ON r.remedy_code = s.remedy_code
WHERE NOT EXISTS (
    SELECT 1 FROM value_frame_remedies vfr
    WHERE vfr.value_frame_id = f.id AND vfr.remedy_id = r.id
);

COMMIT;
