CREATE TABLE IF NOT EXISTS contested_review_runs (
  review_run_id TEXT PRIMARY KEY,
  artifact_version TEXT NOT NULL,
  fixture_kind TEXT,
  source_kind TEXT,
  source_label TEXT,
  source_input_path TEXT,
  affidavit_input_path TEXT,
  source_row_count INTEGER NOT NULL DEFAULT 0,
  affidavit_proposition_count INTEGER NOT NULL DEFAULT 0,
  covered_count INTEGER NOT NULL DEFAULT 0,
  partial_count INTEGER NOT NULL DEFAULT 0,
  contested_affidavit_count INTEGER NOT NULL DEFAULT 0,
  unsupported_affidavit_count INTEGER NOT NULL DEFAULT 0,
  missing_review_count INTEGER NOT NULL DEFAULT 0,
  contested_source_count INTEGER NOT NULL DEFAULT 0,
  abstained_source_count INTEGER NOT NULL DEFAULT 0,
  semantic_basis_counts_json TEXT NOT NULL DEFAULT '{}',
  promotion_status_counts_json TEXT NOT NULL DEFAULT '{}',
  support_direction_counts_json TEXT NOT NULL DEFAULT '{}',
  conflict_state_counts_json TEXT NOT NULL DEFAULT '{}',
  evidentiary_state_counts_json TEXT NOT NULL DEFAULT '{}',
  operational_status_counts_json TEXT NOT NULL DEFAULT '{}',
  payload_sha256 TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS contested_review_affidavit_rows (
  review_run_id TEXT NOT NULL,
  proposition_id TEXT NOT NULL,
  paragraph_id TEXT,
  paragraph_order INTEGER NOT NULL DEFAULT 0,
  sentence_order INTEGER NOT NULL DEFAULT 0,
  proposition_text TEXT NOT NULL,
  coverage_status TEXT,
  best_source_row_id TEXT,
  best_match_score REAL,
  best_adjusted_match_score REAL,
  best_match_basis TEXT,
  best_match_excerpt TEXT,
  duplicate_match_excerpt TEXT,
  best_response_role TEXT,
  support_status TEXT,
  semantic_basis TEXT,
  promotion_status TEXT,
  promotion_basis TEXT,
  promotion_reason TEXT,
  support_direction TEXT,
  conflict_state TEXT,
  evidentiary_state TEXT,
  operational_status TEXT,
  semantic_candidate_json TEXT NOT NULL DEFAULT '{}',
  claim_json TEXT NOT NULL DEFAULT '{}',
  response_json TEXT NOT NULL DEFAULT '{}',
  justifications_json TEXT NOT NULL DEFAULT '[]',
  matched_source_rows_json TEXT NOT NULL DEFAULT '[]',
  PRIMARY KEY (review_run_id, proposition_id),
  FOREIGN KEY (review_run_id) REFERENCES contested_review_runs(review_run_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS contested_review_source_rows (
  review_run_id TEXT NOT NULL,
  source_row_id TEXT NOT NULL,
  source_kind TEXT,
  source_text TEXT NOT NULL,
  candidate_status TEXT,
  review_status TEXT,
  best_affidavit_proposition_id TEXT,
  best_match_score REAL,
  best_adjusted_match_score REAL,
  best_match_basis TEXT,
  best_match_excerpt TEXT,
  best_response_role TEXT,
  matched_affidavit_proposition_ids_json TEXT NOT NULL DEFAULT '[]',
  related_affidavit_proposition_ids_json TEXT NOT NULL DEFAULT '[]',
  reason_codes_json TEXT NOT NULL DEFAULT '[]',
  workload_classes_json TEXT NOT NULL DEFAULT '[]',
  candidate_anchors_json TEXT NOT NULL DEFAULT '[]',
  PRIMARY KEY (review_run_id, source_row_id),
  FOREIGN KEY (review_run_id) REFERENCES contested_review_runs(review_run_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS contested_review_zelph_facts (
  review_run_id TEXT NOT NULL,
  fact_id TEXT NOT NULL,
  proposition_id TEXT,
  best_source_row_id TEXT,
  fact_kind TEXT,
  semantic_basis TEXT,
  promotion_status TEXT,
  promotion_basis TEXT,
  support_direction TEXT,
  conflict_state TEXT,
  evidentiary_state TEXT,
  operational_status TEXT,
  fact_json TEXT NOT NULL DEFAULT '{}',
  PRIMARY KEY (review_run_id, fact_id),
  FOREIGN KEY (review_run_id) REFERENCES contested_review_runs(review_run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_contested_review_runs_created_at
  ON contested_review_runs(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_contested_review_runs_source_label
  ON contested_review_runs(source_label);

CREATE INDEX IF NOT EXISTS idx_contested_review_affidavit_rows_review_status
  ON contested_review_affidavit_rows(review_run_id, coverage_status, promotion_status);

CREATE INDEX IF NOT EXISTS idx_contested_review_source_rows_review_status
  ON contested_review_source_rows(review_run_id, review_status);
