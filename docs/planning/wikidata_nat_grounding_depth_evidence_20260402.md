# Wikidata Nat Grounding-Depth Evidence Plan

Date: 2026-04-02

## Purpose

The Nat grounding-depth lane exists to deepen the revision-locked evidence that
reviewers already rely on for representative hard packets. This note records a
bounded plan for generating and curating grounded evidence bundles for those
packets rather than adding yet another packet shape.

## Context

- `SensibLaw/docs/planning/wikidata_nat_gap_to_moonshot_program_20260402.md`
  calls out evidence grounding as the top gap toward the blind migration moonshot.
- `SensibLaw/docs/planning/wikidata_nat_review_packet_attachment_coverage_20260401.md`
  already pins the packetized surface that this lane uses as its testbed.
- The grounding lane stays focused on reviewer packets and evidence depth; it
  does not touch coverage count work, helper docs outside this scope, or shared
  root doc TODO/changelog/status files.

## Strategy

1. Pick a handful of representative hard Nat packets (split-heavy rows,
   high-profile business families, mix of held/live) and capture:
   - the revision-locked source URL and follow receipts
   - bounded evidence excerpts (any follow receipt or page snippet marked as
     grounded to the locked revision)
   - a short handoff summary explaining why the snippet is trustworthy
2. Store those bundles in
   `SensibLaw/tests/fixtures/wikidata/wikidata_nat_grounding_depth_packets_20260402.json`
   so downstream helpers/tests can verify the evidence depth.
3. Surface the bundles alongside a textual plan so reviewers can reference
   both the doc and fixture when evaluating grounding readiness.

## Evidence Bundle Outline

- `packet_id`: the locked review packet (matching the pinned packet IDs in the
  coverage fixture)
- `qid`: the reviewed entity
- `revision_evidence`: list of objects containing `follow_receipt_url`,
  `excerpt`, and `excerpt_summary`
- `source_notes`: text explaining how the excerpt ties back to the locked
  revision and why it stops uncertainty

## Operator Attachment Surface

- The helper `build_grounding_depth_attachment` (under
  `SensibLaw/src/ontology/wikidata_grounding_depth.py`) builds a fail-closed
  attachment for Nat reviewer packets using the grounding summary fixture.
- Each attachment exposes the grounding status, revision URL, and the evidence
  excerpts that validate the hard packet's revision-locked claims.
- Sample attachment output is stored in
  `SensibLaw/tests/fixtures/wikidata/wikidata_nat_grounding_depth_operator_surface_20260402.json`.

## Operator Batch Surface

- The new `build_grounding_depth_batch` helper aggregates multiple attachments
  into a single operator-facing surface that can be consumed alongside the
  Nat review packets in a review queue.
- The batch surface is fail-closed: packets without grounding data simply show
  `grounding_status: no_grounding_data` in their entry.
- A representative batch fixture lives at
  `SensibLaw/tests/fixtures/wikidata/wikidata_nat_grounding_depth_batch_20260402.json`
  so automation or reviewer tooling can verify the entire grounding bundle before
  presenting packets to operators.

## Evidence Report Surface

- The new `build_grounding_depth_evidence_report` helper produces a packet list
  that summarizes the evidence depth per representative packet, including counts
  and missing-field markers, so reviewers can quickly gauge where deeper digging
  is still needed.
- Pin the report fixture at
  `SensibLaw/tests/fixtures/wikidata/wikidata_nat_grounding_depth_evidence_report_20260402.json`
  and regenerate it via the CLI when evidence inputs change.

## Comparison Surface

- The latest helper `build_grounding_depth_comparison` joins multiple grounding
  batches into a deterministic comparison table, showing attachment counts,
  grounded counts, and qid lists per batch index.
- We pin the comparison fixture at
  `SensibLaw/tests/fixtures/wikidata/wikidata_nat_grounding_depth_comparison_20260402.json`.
- The CLI now accepts `--compare` files and `--comparison-out` so operators can
  reproduce the comparison surface across batches when reviewing new grounding
  evidence.

## Scorecard Surface

- `build_grounding_depth_scorecard` aggregates multiple comparison runs into a
  repeatable scorecard, tracking per-run grounding counts and attachment totals
  so operators can spot drift over repeated grounding-depth inspections.
- Each run is referenced by `run_id` in the `--scorecard-run` CLI argument, and
  the resulting artifact is written under `--scorecard-out`.
- The pinned scorecard fixture lives at
  `SensibLaw/tests/fixtures/wikidata/wikidata_nat_grounding_depth_scorecard_20260402.json`.

## Operator CLI

- The new CLI command `SensibLaw.cli.grounding_depth` builds the grounding batch
  by combining the summary fixture with a list of packets that should receive
  grounding evidence attachments.
- It writes JSON to the provided `--outfile` (or stdout) for operators to
  consume or checkpoint.
- Running the CLI against the grounding fixtures reproduces the pinned batch
  surface, ensuring the operator artifact stays deterministic and review-first.


## Next Steps

1. Run the grounding helper against the fixture to produce an auditable
   summary (e.g., using `enrich_review_packet_follow_depth` or a similar helper).
2. Review the sample packets with the grounding-depth evidence to confirm the
   extra revision-locked context is sufficient.
3. Expand the fixture incrementally only when new hard-row patterns need the
   same depth; keep the sample bounded so it stays reviewable.

## Validation

- `SensibLaw/tests/test_wikidata_nat_grounding_depth.py` validates the fixture
  to ensure it lists packets, evidence snippets, and summaries for the
  representative qids.

## Links

- Evidence sample fixture:
  `SensibLaw/tests/fixtures/wikidata/wikidata_nat_grounding_depth_packets_20260402.json`
