ALTER TABLE semantic_refresh_runs ADD COLUMN started_at TEXT;
ALTER TABLE semantic_refresh_runs ADD COLUMN updated_at TEXT;
ALTER TABLE semantic_refresh_runs ADD COLUMN current_stage TEXT;
ALTER TABLE semantic_refresh_runs ADD COLUMN status_message TEXT;
