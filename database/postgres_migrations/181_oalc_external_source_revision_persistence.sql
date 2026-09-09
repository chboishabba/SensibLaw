BEGIN;

-- 181: governed external legal-source revision persistence for OALC/LegalFollow.
--
-- This migration adds provenance/persistence identity around the existing generic
-- compiler substrate.  It deliberately does NOT duplicate canonical document
-- text, parser annotations, PNF graphs, legal authority, or Atomic outcomes.
--
-- Runtime ownership:
--
--   LegalFollow demand
--     -> governed OALC resolver
--     -> corpus.document (canonical retained text)
--     -> corpus.external_source_revision (provider/dataset/version identity)
--     -> evidence.external_source_resolution (exact-demand acquisition receipt)
--     -> corpus.span
--     -> corpus.external_source_slice (statutory locator/source-span weld)
--     -> existing language.annotation_* / pnf.graph pipeline.
--
-- Important boundaries:
--   * latest_known_only is parser-admissible but does not prove historical
--     equivalence to any requested point-in-time date;
--   * provider/source residuals are acquisition state, never negative legal
--     evidence;
--   * resolution path records how bytes were found, not legal authority;
--   * one source revision may support many section/locator spans without
--     duplicating the underlying canonical document.

CREATE TABLE IF NOT EXISTS corpus.external_source_revision (
    external_source_revision_ref text PRIMARY KEY,
    document_ref text NOT NULL REFERENCES corpus.document(document_ref) ON DELETE RESTRICT,
    provider_ref text NOT NULL,
    dataset_ref text NOT NULL,
    dataset_revision_ref text NOT NULL,
    external_version_ref text NOT NULL,
    citation text NOT NULL,
    source_ref text NOT NULL,
    jurisdiction_ref text NOT NULL,
    document_type_ref text NOT NULL,
    temporal_coverage_ref text NOT NULL CHECK (
        temporal_coverage_ref IN ('latest_known_only', 'historically_verified')
    ),
    resolution_path_ref text NOT NULL CHECK (
        resolution_path_ref IN (
            'filter_exact',
            'native_parquet_scan',
            'offline_jsonl_replay',
            'revision_pinned_streaming_legacy'
        )
    ),
    source_url text,
    source_observed_at timestamptz,
    receipt_sha256 bytea NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (
        provider_ref,
        dataset_ref,
        dataset_revision_ref,
        external_version_ref,
        citation,
        jurisdiction_ref
    )
);

CREATE INDEX IF NOT EXISTS external_source_revision_citation_idx
    ON corpus.external_source_revision (jurisdiction_ref, citation);
CREATE INDEX IF NOT EXISTS external_source_revision_dataset_idx
    ON corpus.external_source_revision (dataset_ref, dataset_revision_ref);
CREATE INDEX IF NOT EXISTS external_source_revision_document_idx
    ON corpus.external_source_revision (document_ref);

CREATE TABLE IF NOT EXISTS evidence.external_source_resolution (
    source_resolution_ref text PRIMARY KEY,
    external_source_revision_ref text NOT NULL
        REFERENCES corpus.external_source_revision(external_source_revision_ref)
        ON DELETE RESTRICT,
    demand_ref text NOT NULL,
    consumer_ref text,
    requested_citation text NOT NULL,
    requested_jurisdiction_ref text NOT NULL,
    requested_source_role_ref text NOT NULL,
    requested_authority_level_ref text NOT NULL,
    requested_temporal_ref text,
    exact_demand_match boolean NOT NULL,
    acquisition_authority_ref text NOT NULL,
    receipt_authority_ref text NOT NULL,
    network_request_count bigint NOT NULL CHECK (network_request_count >= 0),
    resolver_ref text NOT NULL,
    resolution_evidence_ref text NOT NULL,
    receipt_sha256 bytea NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (demand_ref, external_source_revision_ref)
);

CREATE INDEX IF NOT EXISTS external_source_resolution_demand_idx
    ON evidence.external_source_resolution (demand_ref);
CREATE INDEX IF NOT EXISTS external_source_resolution_revision_idx
    ON evidence.external_source_resolution (external_source_revision_ref);

CREATE TABLE IF NOT EXISTS corpus.external_source_slice (
    source_slice_ref text PRIMARY KEY,
    external_source_revision_ref text NOT NULL
        REFERENCES corpus.external_source_revision(external_source_revision_ref)
        ON DELETE CASCADE,
    span_ref text NOT NULL REFERENCES corpus.span(span_ref) ON DELETE CASCADE,
    locator_ref text NOT NULL,
    projection_ref text NOT NULL,
    slice_sha256 bytea NOT NULL,
    parser_authority_ref text NOT NULL DEFAULT 'source_observation_only',
    receipt_sha256 bytea NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (external_source_revision_ref, locator_ref, span_ref)
);

CREATE INDEX IF NOT EXISTS external_source_slice_revision_locator_idx
    ON corpus.external_source_slice (external_source_revision_ref, locator_ref);
CREATE INDEX IF NOT EXISTS external_source_slice_span_idx
    ON corpus.external_source_slice (span_ref);

-- Exact source/document/span projection used by parser/PNF adapters.  This view
-- exposes provenance coordinates only. It creates no semantic or legal status.
CREATE OR REPLACE VIEW corpus.v_external_source_slice AS
SELECT
    slice.source_slice_ref,
    slice.external_source_revision_ref,
    revision.document_ref,
    revision.provider_ref,
    revision.dataset_ref,
    revision.dataset_revision_ref,
    revision.external_version_ref,
    revision.citation,
    revision.source_ref,
    revision.jurisdiction_ref,
    revision.document_type_ref,
    revision.temporal_coverage_ref,
    revision.resolution_path_ref,
    slice.locator_ref,
    slice.span_ref,
    span.start_char,
    span.end_char,
    slice.slice_sha256,
    slice.projection_ref,
    slice.parser_authority_ref
FROM corpus.external_source_slice AS slice
JOIN corpus.external_source_revision AS revision
  ON revision.external_source_revision_ref = slice.external_source_revision_ref
JOIN corpus.span AS span
  ON span.span_ref = slice.span_ref;

COMMENT ON TABLE corpus.external_source_revision IS
    'External legal-source revision identity attached to canonical corpus.document; no legal authority or semantic status.';
COMMENT ON TABLE evidence.external_source_resolution IS
    'Governed exact-demand acquisition receipt; source resolution is not negative evidence, truth, or legal authority.';
COMMENT ON TABLE corpus.external_source_slice IS
    'Source-preserving statutory/document locator mapped to canonical corpus.span for parser/PNF handoff.';
COMMENT ON COLUMN corpus.external_source_revision.temporal_coverage_ref IS
    'latest_known_only does not establish point-in-time historical equivalence.';
COMMENT ON COLUMN corpus.external_source_revision.resolution_path_ref IS
    'Acquisition path only: filter, native shard scan, offline replay, or legacy streaming fallback.';

COMMIT;
