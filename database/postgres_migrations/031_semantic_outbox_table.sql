-- Durable outbox for transactional semantic execution events.
--
-- Migration 027 wires publication commits and migration 030 wires strict
-- delta admissions and work-item completions to this table through AFTER
-- triggers. The table was referenced before it existed; this migration
-- introduces it so those trigger transactions can commit.

CREATE TABLE IF NOT EXISTS execution.semantic_outbox (
    event_ref TEXT PRIMARY KEY,
    aggregate_ref TEXT NOT NULL,
    event_type_ref TEXT NOT NULL,
    payload JSONB NOT NULL,
    emitted_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
