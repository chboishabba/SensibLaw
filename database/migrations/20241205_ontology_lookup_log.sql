-- Log ontology provider lookups for auditing and debugging
BEGIN;

CREATE TABLE IF NOT EXISTS ontology_lookup_log (
    id INTEGER PRIMARY KEY,
    term TEXT NOT NULL,
    provider TEXT NOT NULL,
    external_id TEXT,
    label TEXT,
    description TEXT,
    confidence REAL,
    looked_up_at TEXT DEFAULT CURRENT_TIMESTAMP
);

COMMIT;
