PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS concepts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL,
    description TEXT,
    concept_type TEXT,
    source TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS concept_alias_texts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alias TEXT NOT NULL UNIQUE,
    language TEXT,
    normalized TEXT
);

CREATE TABLE IF NOT EXISTS concept_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    concept_id INTEGER NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    alias_text_id INTEGER NOT NULL REFERENCES concept_alias_texts(id) ON DELETE CASCADE,
    alias_kind TEXT,
    note TEXT,
    UNIQUE (concept_id, alias_text_id)
);

CREATE TABLE IF NOT EXISTS concept_alias_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alias_text_id INTEGER NOT NULL REFERENCES concept_alias_texts(id) ON DELETE CASCADE,
    token TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT -1,
    UNIQUE (alias_text_id, token, position)
);

CREATE TABLE IF NOT EXISTS concept_external_refs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    concept_id INTEGER NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    external_id TEXT NOT NULL,
    external_url TEXT,
    notes TEXT,
    UNIQUE (concept_id, provider, external_id)
);

CREATE TABLE IF NOT EXISTS actor_external_refs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id INTEGER NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    external_id TEXT NOT NULL,
    external_url TEXT,
    notes TEXT,
    UNIQUE (actor_id, provider, external_id)
);

CREATE INDEX IF NOT EXISTS idx_concepts_code ON concepts(code);
CREATE INDEX IF NOT EXISTS idx_alias_text ON concept_alias_texts(alias);
CREATE INDEX IF NOT EXISTS idx_alias_tokens_token ON concept_alias_tokens(token);
CREATE INDEX IF NOT EXISTS idx_concept_external_refs_provider_id ON concept_external_refs(provider, external_id);
CREATE INDEX IF NOT EXISTS idx_actor_external_refs_provider_id ON actor_external_refs(provider, external_id);

COMMIT;
