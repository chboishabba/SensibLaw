-- Append-only materialisation for bounded local world buckets.
--
-- This schema persists inquiry state and selected logical projections only.
-- It does not create semantic authority, truth promotion, browsing-history
-- publication, or live eRDFa/IPFS publication.

CREATE TABLE IF NOT EXISTS sl_world_bucket (
    bucket_id TEXT PRIMARY KEY,
    schema_version TEXT NOT NULL,
    walk_schema_version TEXT NOT NULL,
    seed TEXT NOT NULL,
    hop_budget BIGINT NOT NULL CHECK (hop_budget >= 0),
    actual_hop_count BIGINT NOT NULL CHECK (actual_hop_count >= 0),
    candidate_only BOOLEAN NOT NULL CHECK (candidate_only),
    semantic_promotion BOOLEAN NOT NULL CHECK (NOT semantic_promotion),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sl_world_bucket_node (
    bucket_id TEXT NOT NULL REFERENCES sl_world_bucket(bucket_id),
    node_id TEXT NOT NULL,
    ordinal BIGINT NOT NULL CHECK (ordinal >= 0),
    PRIMARY KEY (bucket_id, node_id),
    UNIQUE (bucket_id, ordinal)
);

CREATE TABLE IF NOT EXISTS sl_world_growth_receipt (
    bucket_id TEXT NOT NULL REFERENCES sl_world_bucket(bucket_id),
    hop BIGINT NOT NULL CHECK (hop > 0),
    source_node_id TEXT NOT NULL,
    target_node_id TEXT NOT NULL,
    edge_family TEXT NOT NULL,
    relation TEXT NOT NULL,
    priority BIGINT NOT NULL,
    cycle BOOLEAN NOT NULL,
    PRIMARY KEY (bucket_id, hop)
);

CREATE TABLE IF NOT EXISTS sl_world_bucket_projection (
    projection_id TEXT PRIMARY KEY,
    bucket_id TEXT NOT NULL REFERENCES sl_world_bucket(bucket_id),
    schema_version TEXT NOT NULL,
    compiler_version TEXT NOT NULL,
    logical_shard_id TEXT NOT NULL,
    packaging_target TEXT NOT NULL,
    manifest_format TEXT NOT NULL,
    content_addressing TEXT NOT NULL,
    content_digest BYTEA NOT NULL,
    candidate_only BOOLEAN NOT NULL CHECK (candidate_only),
    semantic_promotion BOOLEAN NOT NULL CHECK (NOT semantic_promotion),
    live_ipfs_publication_performed BOOLEAN NOT NULL CHECK (NOT live_ipfs_publication_performed),
    publication_projection_is_browsing_history BOOLEAN NOT NULL,
    CHECK (NOT publication_projection_is_browsing_history),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sl_world_bucket_projection_member (
    projection_id TEXT NOT NULL REFERENCES sl_world_bucket_projection(projection_id),
    node_id TEXT NOT NULL,
    ordinal BIGINT NOT NULL CHECK (ordinal >= 0),
    PRIMARY KEY (projection_id, node_id),
    UNIQUE (projection_id, ordinal)
);

CREATE TABLE IF NOT EXISTS sl_world_materialisation_receipt (
    receipt_id TEXT PRIMARY KEY,
    bucket_id TEXT NOT NULL REFERENCES sl_world_bucket(bucket_id),
    object_id TEXT NOT NULL,
    materialisation_state TEXT NOT NULL CHECK (
        materialisation_state IN (
            'skeleton',
            'reference_only',
            'full_local',
            'cold_local',
            'federated_only'
        )
    ),
    content_digest BYTEA,
    source_locator TEXT,
    reason TEXT NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    candidate_only BOOLEAN NOT NULL CHECK (candidate_only),
    semantic_promotion BOOLEAN NOT NULL CHECK (NOT semantic_promotion)
);

CREATE INDEX IF NOT EXISTS sl_world_growth_receipt_source_idx
    ON sl_world_growth_receipt (source_node_id, edge_family);
CREATE INDEX IF NOT EXISTS sl_world_growth_receipt_target_idx
    ON sl_world_growth_receipt (target_node_id, edge_family);
CREATE INDEX IF NOT EXISTS sl_world_materialisation_object_idx
    ON sl_world_materialisation_receipt (bucket_id, object_id, observed_at);

CREATE OR REPLACE FUNCTION sl_reject_world_bucket_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'append-only world bucket table % rejects %', TG_TABLE_NAME, TG_OP;
END;
$$;

DROP TRIGGER IF EXISTS sl_world_bucket_append_only ON sl_world_bucket;
CREATE TRIGGER sl_world_bucket_append_only
    BEFORE UPDATE OR DELETE ON sl_world_bucket
    FOR EACH ROW EXECUTE FUNCTION sl_reject_world_bucket_mutation();

DROP TRIGGER IF EXISTS sl_world_bucket_node_append_only ON sl_world_bucket_node;
CREATE TRIGGER sl_world_bucket_node_append_only
    BEFORE UPDATE OR DELETE ON sl_world_bucket_node
    FOR EACH ROW EXECUTE FUNCTION sl_reject_world_bucket_mutation();

DROP TRIGGER IF EXISTS sl_world_growth_receipt_append_only ON sl_world_growth_receipt;
CREATE TRIGGER sl_world_growth_receipt_append_only
    BEFORE UPDATE OR DELETE ON sl_world_growth_receipt
    FOR EACH ROW EXECUTE FUNCTION sl_reject_world_bucket_mutation();

DROP TRIGGER IF EXISTS sl_world_bucket_projection_append_only ON sl_world_bucket_projection;
CREATE TRIGGER sl_world_bucket_projection_append_only
    BEFORE UPDATE OR DELETE ON sl_world_bucket_projection
    FOR EACH ROW EXECUTE FUNCTION sl_reject_world_bucket_mutation();

DROP TRIGGER IF EXISTS sl_world_bucket_projection_member_append_only ON sl_world_bucket_projection_member;
CREATE TRIGGER sl_world_bucket_projection_member_append_only
    BEFORE UPDATE OR DELETE ON sl_world_bucket_projection_member
    FOR EACH ROW EXECUTE FUNCTION sl_reject_world_bucket_mutation();

DROP TRIGGER IF EXISTS sl_world_materialisation_receipt_append_only ON sl_world_materialisation_receipt;
CREATE TRIGGER sl_world_materialisation_receipt_append_only
    BEFORE UPDATE OR DELETE ON sl_world_materialisation_receipt
    FOR EACH ROW EXECUTE FUNCTION sl_reject_world_bucket_mutation();
