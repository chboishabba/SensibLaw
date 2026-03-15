CREATE TABLE IF NOT EXISTS event_candidates (
    event_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES fact_intake_runs(run_id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    primary_actor TEXT,
    secondary_actor TEXT,
    object_text TEXT,
    location_text TEXT,
    instrument_text TEXT,
    time_start TEXT,
    time_end TEXT,
    confidence REAL NOT NULL DEFAULT 0.0,
    status TEXT NOT NULL DEFAULT 'candidate',
    assembler_version TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_event_candidates_run_id
    ON event_candidates(run_id);

CREATE INDEX IF NOT EXISTS idx_event_candidates_time_start
    ON event_candidates(time_start);

CREATE TABLE IF NOT EXISTS event_attributes (
    attribute_id INTEGER PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES event_candidates(event_id) ON DELETE CASCADE,
    attribute_type TEXT NOT NULL,
    attribute_value TEXT NOT NULL,
    source_observation_id TEXT REFERENCES fact_observations(observation_id) ON DELETE SET NULL,
    confidence REAL NOT NULL DEFAULT 0.0
);

CREATE INDEX IF NOT EXISTS idx_event_attributes_event_id
    ON event_attributes(event_id);

CREATE TABLE IF NOT EXISTS event_evidence (
    evidence_id INTEGER PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES event_candidates(event_id) ON DELETE CASCADE,
    observation_id TEXT NOT NULL REFERENCES fact_observations(observation_id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 0.0,
    UNIQUE(event_id, observation_id, role)
);

CREATE INDEX IF NOT EXISTS idx_event_evidence_event_id
    ON event_evidence(event_id);
