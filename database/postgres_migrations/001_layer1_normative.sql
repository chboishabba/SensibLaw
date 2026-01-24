-- Layer 1: Normative systems and sources (PostgreSQL)
BEGIN;

CREATE TABLE IF NOT EXISTS legal_system (
    id BIGSERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    tradition TEXT,
    region TEXT,
    description TEXT,
    valid_from DATE,
    valid_to DATE,
    priority INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS norm_source_category (
    id BIGSERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS legal_source (
    id BIGSERIAL PRIMARY KEY,
    legal_system_id BIGINT NOT NULL REFERENCES legal_system(id) ON DELETE CASCADE,
    norm_source_category_id BIGINT NOT NULL REFERENCES norm_source_category(id) ON DELETE RESTRICT,
    citation TEXT NOT NULL,
    title TEXT,
    source_url TEXT,
    promulgation_date DATE,
    summary TEXT,
    notes TEXT,
    UNIQUE (legal_system_id, citation)
);

CREATE TABLE IF NOT EXISTS source_text_segment (
    id BIGSERIAL PRIMARY KEY,
    legal_source_id BIGINT NOT NULL REFERENCES legal_source(id) ON DELETE CASCADE,
    segment_ref TEXT NOT NULL,
    heading TEXT,
    text TEXT,
    start_position INTEGER,
    end_position INTEGER
);

-- Seed priority legal systems
INSERT INTO legal_system (code, name, tradition, region, description, priority) VALUES
    ('AU.COMMON', 'Australia (Common Law)', 'COMMON', 'AU', 'Federated common law system across Australian jurisdictions.', 1),
    ('AU.STATE.QLD', 'Australia — Queensland', 'COMMON', 'AU', 'Queensland state system drawing on AU common law.', 1),
    ('PK.ISLAM.HANAFI', 'Pakistan — Hanafi Interpretation', 'ISLAMIC', 'PK', 'Hanafi jurisprudence applied within Pakistan.', 1),
    ('NZ.TIKANGA', 'Aotearoa New Zealand — Tikanga', 'CUSTOM', 'NZ', 'Tikanga Māori custom sources and community rules.', 1),
    ('US.STATE', 'United States — State Systems', 'COMMON', 'US', 'Representative US state jurisdictions.', 1),
    ('EU', 'European Union', 'CIVIL/INTEGRATION', 'EU', 'European Union regulations, directives, and case law.', 1)
ON CONFLICT (code) DO NOTHING;

-- Seed norm source categories
INSERT INTO norm_source_category (code, label, description) VALUES
    ('STATUTE', 'Statute or Act', 'Primary legislation enacted by a parliament or legislature.'),
    ('REGULATION', 'Regulation', 'Delegated legislation or rules issued under statutory authority.'),
    ('CASE', 'Case Law', 'Judicial decisions with precedential weight.'),
    ('TREATY', 'Treaty', 'International treaties or conventions.'),
    ('CUSTOM', 'Customary or Community Rule', 'Non-codified custom or tikanga sources.'),
    ('RELIGIOUS_TEXT', 'Religious Text', 'Faith-based sources with normative content.'),
    ('COMMUNITY_RULE', 'Community Rule', 'Community-authored protocols or bylaws.')
ON CONFLICT (code) DO NOTHING;

COMMIT;
