-- Deduplicate remedy codes per legal system and enforce uniqueness
BEGIN;

-- Remove value_frame_remedies rows that would conflict once duplicate remedies are merged
WITH ranked AS (
    SELECT
        id,
        legal_system_id,
        remedy_code,
        MIN(id) OVER (PARTITION BY legal_system_id, remedy_code) AS keep_id,
        ROW_NUMBER() OVER (PARTITION BY legal_system_id, remedy_code ORDER BY id) AS rn
    FROM remedy
    WHERE remedy_code IS NOT NULL
), conflicting_vfr AS (
    SELECT vfr.ctid
    FROM value_frame_remedies vfr
    JOIN ranked r ON vfr.remedy_id = r.id AND r.rn > 1
    JOIN value_frame_remedies existing
        ON existing.value_frame_id = vfr.value_frame_id
       AND existing.remedy_id = r.keep_id
)
DELETE FROM value_frame_remedies
WHERE ctid IN (SELECT ctid FROM conflicting_vfr);

-- Re-point remaining references to the canonical remedy_id per (legal_system_id, remedy_code)
WITH ranked AS (
    SELECT
        id,
        legal_system_id,
        remedy_code,
        MIN(id) OVER (PARTITION BY legal_system_id, remedy_code) AS keep_id,
        ROW_NUMBER() OVER (PARTITION BY legal_system_id, remedy_code ORDER BY id) AS rn
    FROM remedy
    WHERE remedy_code IS NOT NULL
)
UPDATE value_frame_remedies vfr
SET remedy_id = r.keep_id
FROM ranked r
WHERE vfr.remedy_id = r.id AND r.rn > 1;

-- Remove duplicate remedy rows now that references have been consolidated
WITH ranked AS (
    SELECT
        id,
        ROW_NUMBER() OVER (PARTITION BY legal_system_id, remedy_code ORDER BY id) AS rn
    FROM remedy
    WHERE remedy_code IS NOT NULL
)
DELETE FROM remedy r
USING ranked d
WHERE r.id = d.id AND d.rn > 1;

-- Enforce a single remedy_code per legal system
CREATE UNIQUE INDEX IF NOT EXISTS idx_remedy_legal_system_code_unique
    ON remedy (legal_system_id, remedy_code)
    WHERE remedy_code IS NOT NULL;

COMMIT;
