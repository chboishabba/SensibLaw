CREATE TABLE IF NOT EXISTS authority_ingest_runs (
  ingest_run_id TEXT PRIMARY KEY,
  ingest_version TEXT NOT NULL,
  authority_kind TEXT NOT NULL,
  ingest_mode TEXT NOT NULL,
  citation TEXT,
  query_text TEXT,
  selection_reason TEXT,
  resolved_url TEXT NOT NULL,
  content_type TEXT,
  content_length INTEGER NOT NULL DEFAULT 0,
  content_sha256 TEXT NOT NULL,
  paragraph_request_json TEXT NOT NULL DEFAULT '[]',
  paragraph_window INTEGER NOT NULL DEFAULT 0,
  segment_count INTEGER NOT NULL DEFAULT 0,
  body_preview_text TEXT,
  fetch_metadata_json TEXT NOT NULL DEFAULT '{}',
  payload_sha256 TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS authority_ingest_segments (
  ingest_run_id TEXT NOT NULL,
  segment_id TEXT NOT NULL,
  segment_order INTEGER NOT NULL DEFAULT 0,
  segment_kind TEXT NOT NULL,
  paragraph_number INTEGER,
  segment_text TEXT NOT NULL,
  char_count INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (ingest_run_id, segment_id),
  FOREIGN KEY (ingest_run_id) REFERENCES authority_ingest_runs(ingest_run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_authority_ingest_runs_created_at
  ON authority_ingest_runs(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_authority_ingest_runs_authority_kind
  ON authority_ingest_runs(authority_kind, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_authority_ingest_segments_run_order
  ON authority_ingest_segments(ingest_run_id, segment_order ASC);
