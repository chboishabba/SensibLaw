BEGIN;

-- v0.8 invalidates document-build reuse when media normalization changes the
-- canonical text coordinate system. Raw source bytes remain immutable source
-- evidence; all parser, token, span, annotation and PNF rows address the
-- canonical projection produced by the declared media adapter.
INSERT INTO execution.operation (operation_ref, operation_version)
VALUES ('compiler.document.local-binding', 'v0_8')
ON CONFLICT DO NOTHING;

COMMIT;
