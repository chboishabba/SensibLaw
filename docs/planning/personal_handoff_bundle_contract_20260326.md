# Personal Handoff Bundle Contract

Date: 2026-03-26

Purpose: define the first bounded implementation slice for the private
day-to-escalation story without pretending the full personal workflow already
exists.

## Scope

This first slice is:
- CLI-first
- artifact-first
- built on the existing `fact_intake` TextUnit/read-model stack
- intentionally narrow

This slice is not:
- a UI
- the metadata-only protected-disclosure envelope artifact
- a complete personal archive product
- a full SDK/API package

## Input contract

The builder consumes one JSON file containing:
- `source_label`
- optional `notes`
- `recipient_profile`
- optional bundle-level flags such as:
  - `local_only`
  - `do_not_sync`
  - `retention_policy`
  - `redaction_policy`
  - optional `protected_disclosure` scope metadata for stricter recipient
    handling inside the full-text handoff path
- `entries`: bounded text units with:
  - `unit_id`
  - `source_id`
  - `source_type`
  - `text`
  - optional `signal_classes`
  - optional `share_with`
  - optional `text_export_policy`
- optional `observations`
- optional `reviews`

The goal is to support:
- personal notes
- documentary records
- professional/support notes
- scoped recipient sharing

without requiring a full chat/database import on day one.

## Output contract

The builder emits one deterministic `personal.handoff.report.v1` artifact with:
- bundle/run metadata
- recipient profile metadata
- disclosure/scope flags
- fact-intake persistence summary
- read-model report/review summaries/operator views
- recipient-scoped export rows
- visible exclusions and text-redaction markers

Note: this full-text handoff artifact is not the same thing as the safe
metadata-only protected-disclosure envelope. That separate artifact exists to
avoid persisting or re-emitting raw statement/fact text in whistleblower-like
scenarios.

It also emits a markdown summary that makes the recipient-scoped handoff
legible without opening the raw JSON.

## Recipient profiles in scope

First-pass supported profiles:
- `lawyer`
- `doctor`
- `advocate`
- `regulator`

Profiles may select different default operator views, but they must all:
- preserve provenance
- preserve abstention/uncertainty
- preserve exclusions
- avoid silent promotion

## Governance

Promotion criteria for this slice:
- deterministic fixture-backed JSON output
- deterministic markdown summary
- recipient-scoped filtering works
- redaction/exclusion markers are explicit
- existing `fact_intake` invariants remain intact

## Explicitly deferred

- broad live/private archive ingestion beyond the bounded JSON, sample-DB,
  direct Messenger-export, and first OpenRecall-backed seams
- any claim that this full-text handoff report is itself a whistleblower-safe
  artifact
- multi-user collaboration or cloud sync
- role-specific UI surfaces
