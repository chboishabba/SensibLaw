-- First-class set-valued PNF binding candidates.
-- Candidate membership is local, typed, and non-identifying. Empty candidate
-- sets do not imply expletivity or identity closure.

CREATE TABLE IF NOT EXISTS pnf.factor_anchor (
    factor_revision_ref TEXT PRIMARY KEY REFERENCES algebra.factor_revision(factor_revision_ref),
    document_ref TEXT NOT NULL REFERENCES compiler_document(document_ref),
    sentence_index INTEGER,
    clause_ref TEXT,
    start_token INTEGER,
    end_token INTEGER,
    pnf_kind_ref TEXT NOT NULL,
    morphology_sha256 TEXT,
    CHECK (start_token IS NULL OR start_token >= 0),
    CHECK (end_token IS NULL OR end_token > start_token)
);

CREATE INDEX IF NOT EXISTS factor_anchor_document_position_idx
    ON pnf.factor_anchor (document_ref, sentence_index, start_token, pnf_kind_ref);
CREATE INDEX IF NOT EXISTS factor_anchor_kind_idx
    ON pnf.factor_anchor (document_ref, pnf_kind_ref, sentence_index);
CREATE INDEX IF NOT EXISTS factor_anchor_morphology_idx
    ON pnf.factor_anchor (document_ref, morphology_sha256)
    WHERE morphology_sha256 IS NOT NULL;

CREATE TABLE IF NOT EXISTS resolution.binding_candidate_set (
    candidate_set_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL REFERENCES compiler_document(document_ref),
    reference_factor_ref TEXT NOT NULL REFERENCES algebra.factor(factor_ref),
    reference_factor_revision_ref TEXT NOT NULL
        REFERENCES algebra.factor_revision(factor_revision_ref),
    referential_type_ref TEXT NOT NULL,
    accessibility_declaration_ref TEXT NOT NULL,
    compatibility_declaration_ref TEXT NOT NULL,
    generator_build_ref TEXT NOT NULL,
    compatibility_state_ref TEXT NOT NULL,
    member_count INTEGER NOT NULL CHECK (member_count >= 0),
    candidate_set_sha256 TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (
        reference_factor_revision_ref,
        referential_type_ref,
        accessibility_declaration_ref,
        compatibility_declaration_ref,
        generator_build_ref
    )
);

CREATE INDEX IF NOT EXISTS binding_candidate_set_reference_idx
    ON resolution.binding_candidate_set
        (reference_factor_revision_ref, referential_type_ref);
CREATE INDEX IF NOT EXISTS binding_candidate_set_document_idx
    ON resolution.binding_candidate_set (document_ref, referential_type_ref);

CREATE TABLE IF NOT EXISTS resolution.binding_compatibility_assessment (
    compatibility_assessment_ref TEXT PRIMARY KEY,
    candidate_set_ref TEXT NOT NULL
        REFERENCES resolution.binding_candidate_set(candidate_set_ref) ON DELETE CASCADE,
    candidate_factor_ref TEXT NOT NULL REFERENCES algebra.factor(factor_ref),
    compatibility_state_ref TEXT NOT NULL,
    accessibility_path_ref TEXT NOT NULL,
    assessment_sha256 TEXT NOT NULL,
    UNIQUE (candidate_set_ref, candidate_factor_ref)
);

CREATE TABLE IF NOT EXISTS resolution.binding_candidate_member (
    candidate_set_ref TEXT NOT NULL
        REFERENCES resolution.binding_candidate_set(candidate_set_ref) ON DELETE CASCADE,
    candidate_factor_ref TEXT NOT NULL REFERENCES algebra.factor(factor_ref),
    compatibility_assessment_ref TEXT NOT NULL
        REFERENCES resolution.binding_compatibility_assessment(
            compatibility_assessment_ref
        ),
    accessibility_path_ref TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    PRIMARY KEY (candidate_set_ref, candidate_factor_ref),
    UNIQUE (candidate_set_ref, ordinal)
);

CREATE INDEX IF NOT EXISTS binding_candidate_member_candidate_idx
    ON resolution.binding_candidate_member (candidate_factor_ref, candidate_set_ref);

CREATE TABLE IF NOT EXISTS resolution.binding_exclusion_summary (
    candidate_set_ref TEXT NOT NULL
        REFERENCES resolution.binding_candidate_set(candidate_set_ref) ON DELETE CASCADE,
    reason_ref TEXT NOT NULL,
    excluded_count INTEGER NOT NULL CHECK (excluded_count >= 0),
    generator_build_ref TEXT NOT NULL,
    PRIMARY KEY (candidate_set_ref, reason_ref)
);

CREATE TABLE IF NOT EXISTS resolution.refinement_candidate_set (
    refinement_ref TEXT NOT NULL REFERENCES resolution.refinement(refinement_ref),
    candidate_set_ref TEXT NOT NULL
        REFERENCES resolution.binding_candidate_set(candidate_set_ref),
    PRIMARY KEY (refinement_ref, candidate_set_ref)
);

CREATE OR REPLACE VIEW resolution.v_binding_candidate_set_summary AS
SELECT
    candidate_set.document_ref,
    candidate_set.reference_factor_ref,
    candidate_set.reference_factor_revision_ref,
    candidate_set.referential_type_ref,
    candidate_set.candidate_set_ref,
    candidate_set.member_count,
    COALESCE(SUM(exclusion.excluded_count), 0)::BIGINT AS excluded_count,
    candidate_set.compatibility_state_ref,
    candidate_set.generator_build_ref
FROM resolution.binding_candidate_set AS candidate_set
LEFT JOIN resolution.binding_exclusion_summary AS exclusion
    ON exclusion.candidate_set_ref = candidate_set.candidate_set_ref
GROUP BY
    candidate_set.document_ref,
    candidate_set.reference_factor_ref,
    candidate_set.reference_factor_revision_ref,
    candidate_set.referential_type_ref,
    candidate_set.candidate_set_ref,
    candidate_set.member_count,
    candidate_set.compatibility_state_ref,
    candidate_set.generator_build_ref;
