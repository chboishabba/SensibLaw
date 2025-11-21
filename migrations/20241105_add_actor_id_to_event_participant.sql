-- Add actor_id to event_participant and enforce uniqueness
BEGIN;

-- Add the column as nullable for backfill, then enforce NOT NULL
ALTER TABLE event_participant
    ADD COLUMN IF NOT EXISTS actor_id BIGINT REFERENCES actor(id) ON DELETE CASCADE;

-- Prefer any existing actor linkage for classification alignment
UPDATE event_participant ep
SET actor_class_id = COALESCE(ep.actor_class_id, a.actor_class_id)
FROM actor a
WHERE ep.actor_id = a.id
  AND (ep.actor_class_id IS NULL OR ep.actor_class_id <> a.actor_class_id);

-- Attempt to backfill actor_id from role labels when an actor already exists with the same label
UPDATE event_participant ep
SET actor_id = a.id,
    actor_class_id = COALESCE(ep.actor_class_id, a.actor_class_id)
FROM actor a
WHERE ep.actor_id IS NULL
  AND a.label = ep.role_label;

-- Create placeholder actors for any remaining participants so we can enforce NOT NULL
INSERT INTO actor (kind, label, actor_class_id)
SELECT DISTINCT
    'event_participant'::text,
    COALESCE(ep.role_label, CONCAT('participant:', ep.id)),
    ep.actor_class_id
FROM event_participant ep
LEFT JOIN actor a ON a.id = ep.actor_id
WHERE ep.actor_id IS NULL;

-- Bind the newly created actors back to the participant rows
UPDATE event_participant ep
SET actor_id = a.id
FROM actor a
WHERE ep.actor_id IS NULL
  AND a.kind = 'event_participant'
  AND a.label = COALESCE(ep.role_label, CONCAT('participant:', ep.id))
  AND a.actor_class_id = ep.actor_class_id;

-- Finalise constraints
ALTER TABLE event_participant
    ALTER COLUMN actor_id SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_event_participant_unique
    ON event_participant (event_id, actor_id, COALESCE(role_marker_id, -1));

COMMIT;
