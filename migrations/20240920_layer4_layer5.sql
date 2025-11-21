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
    actor_id BIGINT NOT NULL REFERENCES actor(id) ON DELETE CASCADE,
    actor_class_id BIGINT NOT NULL REFERENCES actor_class(id),
    role_marker_id BIGINT REFERENCES role_marker(id),
    role_label TEXT,
    participation_note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_event_participant_unique
    ON event_participant (event_id, actor_id, COALESCE(role_marker_id, -1));

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

CREATE TABLE IF NOT EXISTS remedy_modality (
    id BIGSERIAL PRIMARY KEY,
    modality_code TEXT NOT NULL UNIQUE,
    label TEXT,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS remedy_catalog (
    id BIGSERIAL PRIMARY KEY,
    legal_system_id BIGINT NOT NULL REFERENCES legal_system(id),
    cultural_register_id BIGINT REFERENCES cultural_register(id),
    remedy_modality_id BIGINT NOT NULL REFERENCES remedy_modality(id),
    remedy_code TEXT,
    terms TEXT,
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS event_remedy (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES event(id) ON DELETE CASCADE,
    harm_instance_id BIGINT REFERENCES harm_instance(id) ON DELETE CASCADE,
    remedy_catalog_id BIGINT REFERENCES remedy_catalog(id),
    value_frame_id BIGINT REFERENCES value_frame(id),
    terms TEXT,
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS value_frame_remedies (
    value_frame_id BIGINT NOT NULL REFERENCES value_frame(id) ON DELETE CASCADE,
    remedy_catalog_id BIGINT NOT NULL REFERENCES remedy_catalog(id) ON DELETE CASCADE,
    PRIMARY KEY (value_frame_id, remedy_catalog_id)
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

-- View: event remedies enriched with modality metadata sourced from the catalog
DROP VIEW IF EXISTS event_remedy_with_modality;
CREATE VIEW event_remedy_with_modality AS
SELECT
    er.id,
    er.event_id,
    er.harm_instance_id,
    er.remedy_catalog_id,
    er.value_frame_id,
    er.terms,
    er.note,
    er.created_at,
    er.updated_at,
    rc.remedy_modality_id,
    rm.modality_code,
    rm.label AS remedy_modality_label,
    rm.description AS remedy_modality_description
FROM event_remedy er
LEFT JOIN remedy_catalog rc ON rc.id = er.remedy_catalog_id
LEFT JOIN remedy_modality rm ON rm.id = rc.remedy_modality_id;

-- View: remedy library joined to value frames for quick lookup
DROP VIEW IF EXISTS remedy_library_by_value_frame;
CREATE VIEW remedy_library_by_value_frame AS
SELECT
    vf.id AS value_frame_id,
    vf.frame_code,
    vf.label AS value_frame_label,
    rc.id AS remedy_catalog_id,
    rc.remedy_code,
    rc.terms,
    rc.note,
    rc.legal_system_id,
    rc.cultural_register_id,
    rm.modality_code,
    rm.label AS remedy_modality_label,
    rm.description AS remedy_modality_description
FROM value_frame vf
JOIN value_frame_remedies vfr ON vfr.value_frame_id = vf.id
JOIN remedy_catalog rc ON rc.id = vfr.remedy_catalog_id
JOIN remedy_modality rm ON rm.id = rc.remedy_modality_id;

-- Seed a small library of value frames and remedies for reference builds
INSERT INTO value_frame (frame_code, label, description) VALUES
    ('gender_equality', 'Gender equality', 'Equity and bodily autonomy considerations'),
    ('tikanga_balance', 'Tikanga balance', 'Restoration and mana-enhancing remedies'),
    ('child_rights', 'Child rights', 'Best interests of the child and protective measures')
ON CONFLICT (frame_code) DO UPDATE SET
    label = EXCLUDED.label,
    description = EXCLUDED.description,
    updated_at = NOW();

INSERT INTO remedy_modality (modality_code, label, description) VALUES
    ('MONETARY', 'Monetary compensation', 'Payments, fines, or other financial transfer remedies'),
    ('STRUCTURAL', 'Structural or injunctive', 'Orders that change ongoing behaviour or conditions'),
    ('RESTORATIVE_RITUAL', 'Restorative ritual', 'Symbolic or tikanga-based restorative actions'),
    ('STATUS_CHANGE', 'Status change', 'Orders that alter legal status or custody arrangements')
ON CONFLICT (modality_code) DO UPDATE SET
    label = EXCLUDED.label,
    description = EXCLUDED.description,
    updated_at = NOW();

WITH modality_ids AS (
    SELECT modality_code, id FROM remedy_modality WHERE modality_code IN ('MONETARY', 'STRUCTURAL', 'RESTORATIVE_RITUAL', 'STATUS_CHANGE')
), seed_remedies(frame_code, modality_code, remedy_code, terms, note) AS (
    VALUES
        ('gender_equality', 'MONETARY', 'COMPENSATION', 'Compensation for financial or reputational loss', 'Seeded compensation template'),
        ('gender_equality', 'STRUCTURAL', 'INJUNCTION', 'Injunction or order to prevent ongoing harm', 'Seeded injunction template'),
        ('tikanga_balance', 'RESTORATIVE_RITUAL', 'APOLOGY', 'Restorative apology anchored in tikanga', 'Seeded apology template'),
        ('child_rights', 'STATUS_CHANGE', 'CUSTODY_ORDER', 'Custody or guardianship order prioritising welfare', 'Seeded custody order template')
)
INSERT INTO remedy_catalog (legal_system_id, cultural_register_id, remedy_modality_id, remedy_code, terms, note)
SELECT
    ls.id,
    NULL::BIGINT,
    m.id,
    s.remedy_code,
    s.terms,
    s.note
FROM seed_remedies s
JOIN modality_ids m ON m.modality_code = s.modality_code
CROSS JOIN legal_system ls
WHERE NOT EXISTS (
    SELECT 1 FROM remedy_catalog rc
    WHERE rc.remedy_code = s.remedy_code AND rc.legal_system_id = ls.id
);

WITH modality_ids AS (
    SELECT modality_code, id FROM remedy_modality WHERE modality_code IN ('MONETARY', 'STRUCTURAL', 'RESTORATIVE_RITUAL', 'STATUS_CHANGE')
), frame_ids AS (
    SELECT frame_code, id FROM value_frame WHERE frame_code IN ('gender_equality', 'tikanga_balance', 'child_rights')
), seed_remedies(frame_code, modality_code, remedy_code, terms, note) AS (
    VALUES
        ('gender_equality', 'MONETARY', 'COMPENSATION', 'Compensation for financial or reputational loss', 'Seeded compensation template'),
        ('gender_equality', 'STRUCTURAL', 'INJUNCTION', 'Injunction or order to prevent ongoing harm', 'Seeded injunction template'),
        ('tikanga_balance', 'RESTORATIVE_RITUAL', 'APOLOGY', 'Restorative apology anchored in tikanga', 'Seeded apology template'),
        ('child_rights', 'STATUS_CHANGE', 'CUSTODY_ORDER', 'Custody or guardianship order prioritising welfare', 'Seeded custody order template')
)
INSERT INTO value_frame_remedies (value_frame_id, remedy_catalog_id)
SELECT DISTINCT
    f.id,
    rc.id
FROM seed_remedies s
JOIN frame_ids f ON f.frame_code = s.frame_code
JOIN modality_ids m ON m.modality_code = s.modality_code
JOIN remedy_catalog rc ON rc.remedy_code = s.remedy_code AND rc.remedy_modality_id = m.id
WHERE NOT EXISTS (
    SELECT 1 FROM value_frame_remedies vfr
    WHERE vfr.value_frame_id = f.id AND vfr.remedy_catalog_id = rc.id
);

COMMIT;
