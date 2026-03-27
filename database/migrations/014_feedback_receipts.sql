CREATE TABLE IF NOT EXISTS feedback_receipts (
  receipt_id TEXT PRIMARY KEY,
  schema_version TEXT NOT NULL,
  feedback_class TEXT NOT NULL,
  role_label TEXT NOT NULL,
  task_label TEXT NOT NULL,
  target_product TEXT,
  target_surface TEXT,
  workflow_label TEXT,
  source_kind TEXT NOT NULL,
  summary TEXT NOT NULL,
  quote_text TEXT NOT NULL,
  severity TEXT NOT NULL,
  desired_outcome TEXT,
  sentiment TEXT,
  captured_at TEXT NOT NULL,
  tags_json TEXT NOT NULL DEFAULT '[]',
  provenance_json TEXT NOT NULL DEFAULT '{}',
  payload_sha256 TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_feedback_receipts_created_at
  ON feedback_receipts(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_feedback_receipts_class_kind
  ON feedback_receipts(feedback_class, source_kind, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_feedback_receipts_target_product
  ON feedback_receipts(target_product, created_at DESC);
