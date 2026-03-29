ALTER TABLE contested_review_affidavit_rows
  ADD COLUMN relation_root TEXT;

ALTER TABLE contested_review_affidavit_rows
  ADD COLUMN relation_leaf TEXT;

ALTER TABLE contested_review_affidavit_rows
  ADD COLUMN primary_target_component TEXT;

ALTER TABLE contested_review_affidavit_rows
  ADD COLUMN explanation_json TEXT NOT NULL DEFAULT '{}';

ALTER TABLE contested_review_affidavit_rows
  ADD COLUMN missing_dimensions_json TEXT NOT NULL DEFAULT '[]';
