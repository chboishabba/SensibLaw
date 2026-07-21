-- Structural, declaration-owned binding accessibility and build reuse.
-- This migration extends the normalized candidate-set schema without changing
-- migration 008, which may already be ledgered in development databases.

ALTER TABLE pnf.factor_anchor
    ADD COLUMN IF NOT EXISTS discourse_unit_ref TEXT,
    ADD COLUMN IF NOT EXISTS paragraph_index INTEGER,
    ADD COLUMN IF NOT EXISTS quotation_depth INTEGER,
    ADD COLUMN IF NOT EXISTS reporting_scope_ref TEXT,
    ADD COLUMN IF NOT EXISTS coordination_group_ref TEXT,
    ADD COLUMN IF NOT EXISTS parser_pos_ref TEXT,
    ADD COLUMN IF NOT EXISTS parser_dependency_ref TEXT;

CREATE INDEX IF NOT EXISTS factor_anchor_structural_accessibility_idx
    ON pnf.factor_anchor
        (document_ref, paragraph_index, sentence_index, start_token, pnf_kind_ref);
CREATE INDEX IF NOT EXISTS factor_anchor_clause_idx
    ON pnf.factor_anchor (document_ref, clause_ref, start_token)
    WHERE clause_ref IS NOT NULL;
CREATE INDEX IF NOT EXISTS factor_anchor_reporting_scope_idx
    ON pnf.factor_anchor (document_ref, reporting_scope_ref, start_token)
    WHERE reporting_scope_ref IS NOT NULL;

CREATE TABLE IF NOT EXISTS pnf.factor_morphology (
    factor_revision_ref TEXT NOT NULL
        REFERENCES algebra.factor_revision(factor_revision_ref) ON DELETE CASCADE,
    feature_ref TEXT NOT NULL,
    value_ref TEXT NOT NULL,
    PRIMARY KEY (factor_revision_ref, feature_ref, value_ref)
);

CREATE INDEX IF NOT EXISTS factor_morphology_lookup_idx
    ON pnf.factor_morphology (feature_ref, value_ref, factor_revision_ref);

CREATE TABLE IF NOT EXISTS execution.binding_candidate_set_build (
    generator_build_ref TEXT PRIMARY KEY,
    candidate_set_ref TEXT NOT NULL UNIQUE,
    reference_factor_revision_ref TEXT NOT NULL
        REFERENCES algebra.factor_revision(factor_revision_ref),
    document_pnf_index_ref TEXT NOT NULL,
    accessibility_declaration_ref TEXT NOT NULL,
    compatibility_declaration_ref TEXT NOT NULL,
    referential_type_ref TEXT NOT NULL,
    build_key_sha256 TEXT NOT NULL UNIQUE,
    build_state_ref TEXT NOT NULL DEFAULT 'completed',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS resolution.meet_candidate_set (
    meet_ref TEXT NOT NULL REFERENCES resolution.typed_meet(meet_ref) ON DELETE CASCADE,
    candidate_set_ref TEXT NOT NULL
        REFERENCES resolution.binding_candidate_set(candidate_set_ref) ON DELETE CASCADE,
    PRIMARY KEY (meet_ref, candidate_set_ref)
);

CREATE TABLE IF NOT EXISTS resolution.binding_referential_kind (
    compatibility_declaration_ref TEXT NOT NULL,
    referential_type_ref TEXT NOT NULL,
    pnf_kind_ref TEXT NOT NULL,
    PRIMARY KEY (
        compatibility_declaration_ref,
        referential_type_ref,
        pnf_kind_ref
    )
);

INSERT INTO resolution.binding_referential_kind
    (compatibility_declaration_ref, referential_type_ref, pnf_kind_ref)
VALUES
    ('binding-compatibility:pnf-kind-morphology:v0_3',
     'entity_reference', 'semantic.mention_identity'),
    ('binding-compatibility:pnf-kind-morphology:v0_3',
     'eventuality_reference', 'semantic.eventuality'),
    ('binding-compatibility:pnf-kind-morphology:v0_3',
     'proposition_reference', 'semantic.embedded_proposition'),
    ('binding-compatibility:pnf-kind-morphology:v0_3',
     'proposition_reference', 'semantic.proposition')
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS resolution.binding_accessibility_path (
    accessibility_declaration_ref TEXT NOT NULL,
    referential_type_ref TEXT NOT NULL,
    accessibility_path_ref TEXT NOT NULL,
    PRIMARY KEY (
        accessibility_declaration_ref,
        referential_type_ref,
        accessibility_path_ref
    )
);

INSERT INTO resolution.binding_accessibility_path
    (accessibility_declaration_ref, referential_type_ref, accessibility_path_ref)
SELECT
    'binding-accessibility:document-structural:v0_3',
    referential_type_ref,
    accessibility_path_ref
FROM (
    VALUES
        ('entity_reference', 'same_clause'),
        ('entity_reference', 'governing_clause'),
        ('entity_reference', 'preceding_coordinated_clause'),
        ('entity_reference', 'same_sentence'),
        ('entity_reference', 'preceding_discourse_unit'),
        ('entity_reference', 'preceding_paragraph'),
        ('entity_reference', 'preceding_document_unit'),
        ('eventuality_reference', 'same_clause'),
        ('eventuality_reference', 'governing_clause'),
        ('eventuality_reference', 'preceding_coordinated_clause'),
        ('eventuality_reference', 'same_sentence'),
        ('eventuality_reference', 'preceding_discourse_unit'),
        ('eventuality_reference', 'reporting_content_boundary'),
        ('eventuality_reference', 'preceding_paragraph'),
        ('eventuality_reference', 'preceding_document_unit'),
        ('proposition_reference', 'same_clause'),
        ('proposition_reference', 'governing_clause'),
        ('proposition_reference', 'preceding_coordinated_clause'),
        ('proposition_reference', 'same_sentence'),
        ('proposition_reference', 'preceding_discourse_unit'),
        ('proposition_reference', 'reporting_content_boundary'),
        ('proposition_reference', 'preceding_paragraph'),
        ('proposition_reference', 'preceding_document_unit')
) AS declared(referential_type_ref, accessibility_path_ref)
ON CONFLICT DO NOTHING;

CREATE OR REPLACE FUNCTION resolution.query_binding_candidates(
    p_reference_factor_revision_ref TEXT,
    p_referential_type_ref TEXT,
    p_accessibility_declaration_ref TEXT,
    p_compatibility_declaration_ref TEXT,
    p_candidate_limit INTEGER DEFAULT 64
)
RETURNS TABLE (
    candidate_factor_revision_ref TEXT,
    candidate_factor_ref TEXT,
    accessibility_path_ref TEXT,
    distance_tokens INTEGER
)
LANGUAGE SQL
STABLE
AS $$
WITH reference_anchor AS (
    SELECT anchor.*
    FROM pnf.factor_anchor AS anchor
    WHERE anchor.factor_revision_ref = p_reference_factor_revision_ref
),
kind_candidates AS (
    SELECT
        candidate.*,
        reference.start_token - candidate.start_token AS distance_tokens,
        CASE
            WHEN candidate.start_token >= reference.start_token
                THEN 'not_preceding_reference'
            WHEN reference.quotation_depth IS NOT NULL
                 AND candidate.quotation_depth IS NOT NULL
                 AND reference.quotation_depth <> candidate.quotation_depth
                 AND (reference.reporting_scope_ref IS NOT NULL
                      OR candidate.reporting_scope_ref IS NOT NULL)
                THEN 'reporting_content_boundary'
            WHEN reference.quotation_depth IS NOT NULL
                 AND candidate.quotation_depth IS NOT NULL
                 AND reference.quotation_depth <> candidate.quotation_depth
                THEN 'quotation_boundary_crossed'
            WHEN reference.clause_ref IS NOT NULL
                 AND reference.clause_ref = candidate.clause_ref
                THEN 'same_clause'
            WHEN reference.reporting_scope_ref IS NOT NULL
                 AND reference.reporting_scope_ref = candidate.reporting_scope_ref
                THEN 'governing_clause'
            WHEN reference.coordination_group_ref IS NOT NULL
                 AND reference.coordination_group_ref = candidate.coordination_group_ref
                THEN 'preceding_coordinated_clause'
            WHEN reference.sentence_index IS NOT NULL
                 AND reference.sentence_index = candidate.sentence_index
                THEN 'same_sentence'
            WHEN reference.paragraph_index IS NOT NULL
                 AND reference.paragraph_index = candidate.paragraph_index
                THEN 'preceding_discourse_unit'
            WHEN reference.paragraph_index IS NOT NULL
                 AND candidate.paragraph_index IS NOT NULL
                 AND candidate.paragraph_index < reference.paragraph_index
                THEN 'preceding_paragraph'
            ELSE 'preceding_document_unit'
        END AS accessibility_path_ref
    FROM reference_anchor AS reference
    JOIN pnf.factor_anchor AS candidate
      ON candidate.document_ref = reference.document_ref
     AND candidate.factor_revision_ref <> reference.factor_revision_ref
    JOIN resolution.binding_referential_kind AS kind
      ON kind.compatibility_declaration_ref = p_compatibility_declaration_ref
     AND kind.referential_type_ref = p_referential_type_ref
     AND kind.pnf_kind_ref = candidate.pnf_kind_ref
    WHERE p_referential_type_ref <> 'entity_reference'
       OR candidate.parser_pos_ref IN ('NOUN', 'PROPN')
),
accessible AS (
    SELECT candidate.*
    FROM kind_candidates AS candidate
    JOIN resolution.binding_accessibility_path AS path
      ON path.accessibility_declaration_ref = p_accessibility_declaration_ref
     AND path.referential_type_ref = p_referential_type_ref
     AND path.accessibility_path_ref = candidate.accessibility_path_ref
),
morphologically_compatible AS (
    SELECT candidate.*
    FROM accessible AS candidate
    WHERE NOT EXISTS (
        SELECT 1
        FROM (
            SELECT feature_ref
            FROM pnf.factor_morphology
            WHERE factor_revision_ref = p_reference_factor_revision_ref
              AND feature_ref IN ('Number', 'Gender', 'Person')
            INTERSECT
            SELECT feature_ref
            FROM pnf.factor_morphology
            WHERE factor_revision_ref = candidate.factor_revision_ref
              AND feature_ref IN ('Number', 'Gender', 'Person')
        ) AS shared_feature
        WHERE NOT EXISTS (
            SELECT 1
            FROM pnf.factor_morphology AS reference_morphology
            JOIN pnf.factor_morphology AS candidate_morphology
              ON candidate_morphology.factor_revision_ref = candidate.factor_revision_ref
             AND candidate_morphology.feature_ref = reference_morphology.feature_ref
             AND candidate_morphology.value_ref = reference_morphology.value_ref
            WHERE reference_morphology.factor_revision_ref =
                  p_reference_factor_revision_ref
              AND reference_morphology.feature_ref = shared_feature.feature_ref
        )
    )
)
SELECT
    candidate.factor_revision_ref,
    revision.factor_ref,
    candidate.accessibility_path_ref,
    candidate.distance_tokens
FROM morphologically_compatible AS candidate
JOIN algebra.factor_revision AS revision
  ON revision.factor_revision_ref = candidate.factor_revision_ref
ORDER BY candidate.distance_tokens, revision.factor_ref
LIMIT GREATEST(p_candidate_limit, 0);
$$;

CREATE OR REPLACE VIEW resolution.v_binding_candidate_build_reuse AS
SELECT
    build.generator_build_ref,
    build.candidate_set_ref,
    build.reference_factor_revision_ref,
    build.referential_type_ref,
    build.build_key_sha256,
    build.build_state_ref,
    candidate_set.member_count,
    build.created_at
FROM execution.binding_candidate_set_build AS build
JOIN resolution.binding_candidate_set AS candidate_set
  ON candidate_set.candidate_set_ref = build.candidate_set_ref;
