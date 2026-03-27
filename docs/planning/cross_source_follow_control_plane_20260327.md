# Cross-Source Follow Control Plane

Date: 2026-03-27

## Purpose

Keep parity across source families by standardizing the control plane for
follow/review work, not by forcing every source to share the same domain
semantics.

The shared ladder is:

1. `hint`
2. `receipt`
3. `substrate`
4. `follow-needed conjecture`
5. `operator queue`

Every source family may leave some stages empty or abstaining, but no family
should skip directly from raw text to confident downstream action.

## Shared contract

The first shared contract is `follow.control.v1`.

It applies to operator queues that tell a human what the next bounded action is.

### View-level fields

- `control_plane.version`
- `control_plane.source_family`
- `control_plane.hint_kind`
- `control_plane.receipt_kind`
- `control_plane.substrate_kind`
- `control_plane.conjecture_kind`
- `control_plane.route_targets[]`
- `control_plane.resolution_statuses[]`

### Queue item fields

- `item_id`
- `title`
- `subtitle`
- `description`
- `conjecture_kind`
- `route_target`
- `resolution_status`
- `chips[]`
- `detail_rows[]`

Queue items may also carry source-family-specific fields, but the fields above
are the minimum portable shape.

## Current rollout

The first concrete users are:

- AU `operator_views.authority_follow`
- generic fact-review `operator_views.intake_triage`
- generic fact-review `operator_views.contested_items`

This is enough to prove the control plane is broader than one AU-only queue.

## Governance

- The contract is for operator/workbench routing, not semantic promotion.
- `route_target` is not truth.
- `resolution_status` is workflow state, not semantic certainty.
- Source-family-specific fields may exist, but they should not replace the
  portable minimum shape.

## Next rollout candidates

- transcript/message follow-needed queues
- affidavit/source-review queues
- corpus/browser-side receipts that already produce operator queues

## Non-goals

- Do not force every source family into AU authority semantics.
- Do not auto-follow just because a parser saw a hint.
- Do not widen the persisted fact-review contract for every lane before a
  source family has a real queue to expose.
