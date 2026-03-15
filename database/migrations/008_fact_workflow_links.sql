CREATE TABLE IF NOT EXISTS fact_workflow_links (
    workflow_kind TEXT NOT NULL,
    workflow_run_id TEXT NOT NULL,
    fact_run_id TEXT NOT NULL REFERENCES fact_intake_runs(run_id) ON DELETE CASCADE,
    source_label TEXT,
    adapter_version TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workflow_kind, workflow_run_id),
    UNIQUE (fact_run_id)
);

CREATE INDEX IF NOT EXISTS idx_fact_workflow_links_fact_run_id
    ON fact_workflow_links(fact_run_id);

CREATE INDEX IF NOT EXISTS idx_fact_workflow_links_source_label
    ON fact_workflow_links(source_label);
