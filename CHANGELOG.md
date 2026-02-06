# Changelog

## Unreleased
- Docs: publish S7–S9 roadmaps (span authority, cross-doc topology, read-only UI).
- Docs: add human tools integration guidance + multi-modal system doctrine.
- Docs: update span-signal/promotion/IR invariants to require revision-scoped spans.
- TextSpan: add canonical `TextSpan(revision_id, start_char, end_char)` model.
- Storage: persist TextSpan for rule atoms/elements (span_start/span_end/span_source).
- Ingestion: attach TextSpan to new rule atoms/elements; hard-error on missing spans.
- Cross-doc: upgrade topology schema to `obligation.crossdoc.v2` with `repeals/modifies/references/cites`.
- UI: add read-only Obligations tab with span inspector + fixtures.
- Tests: update cross-doc snapshots + add TextSpan attachment test.
- Docs: add lawyer/psychologist user stories and link from README.
- Docs: extend user stories with additional roles (banker/CEO/manager/etc.).
- Docs: add organization-level user story layer (teams/admins/regulators).
- Docs: add public sector user stories (police/EMS/health/government guardrails).
- Docs: add modern org stack user stories (dev/team/CEO/finance).
- Docs: add air-gapped/battlefield/interop user story layer.
- Docs: add "Against Victor's Memory" doctrine to multimodal system notes.
- Docs: add panopticon refusal manifesto.
- Docs: add state power/structural violence note to panopticon refusal.
- Docs: add activist coordination user story layer.
- Docs: add trauma/authoritarian pressure user story layer.
- Docs: add access-scope and legal reconstruction user story layer.
- Docs: add judicial-context user story layer (judges/staff/bailiffs/family).
- Docs: add lexeme layer contract + tokenizer/corpus updates.
- Docs: add media ethics UI guidelines + hostile cross-exam script.
- Storage: add lexeme/phrase tables to versioned store schema.
- Ingestion: persist lexeme occurrences per revision (span-anchored).
- Tests: add lexeme occurrence span anchoring coverage.
