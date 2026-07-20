# Climate-GHG Policy Resolution Dry Run

Date: 2026-07-17
Status: next bounded governance tranche
Input: immutable `company_direct` V2 assessment

## Purpose

The V2 assessment has a 366-statement hold population, but the holds are not
one remediation class. This note defines the next fully offline dry run. It
may reinterpret supplied evidence under an explicitly versioned policy; it
must not retrieve Wikidata, rewrite replay artifacts, create edits, or approve
migration.

## Resolution inventory

### Candidate policy/evidence resolutions

| Cluster | Count | Resolution test |
|---|---:|---|
| Fiscal-year-only | 132 | Accept an exact 12-month `P580`/`P582` interval as a canonical annual reporting period. |
| Enterprise subject | 21 | Adjudicate the conflicting typed evidence for Q52579 once at family/entity level. |
| Reference adequacy | 4 | Review Q1476113 current-window P854 transferability. |
| Method | 12 | Test explicit approval of the existing missing-but-inferable method mappings. |
| Unit | 3 | Test explicit approval of the existing alternate-unit mappings. |

The fiscal cluster is deliberately narrow. There are 308 one-year fiscal
intervals in the unresolved-year population, but 176 also have ambiguous scope
and remain held. One additional statement has missing time evidence. Fiscal
normalization must not release those scope-ambiguous statements.

### Structurally hard remainder

- 176 fiscal-interval statements with ambiguous scope;
- 6 additional ambiguous scope coordinates;
- 1 ambiguous category coordinate;
- 1 missing-time statement;
- unsupported or unresolved semantic shapes outside the resolution tests.

The upper-bound candidate release is approximately 169 statements. This is a
scenario bound, not an approval count; each policy/evidence test can fail.

## Dry-run contract

The dry run applies the five tests in a fixed order:

1. canonicalize exact 12-month fiscal intervals;
2. apply one family-level Q52579 subject adjudication;
3. apply one Q1476113 reference-transfer adjudication;
4. evaluate the concentrated method mappings;
5. evaluate the concentrated unit mappings.

Every changed statement receives a transition receipt containing its original
assessment state, changed predicates/coordinates, resolution class, evidence
refs, policy ref, resulting V2 outcome, and authority `diagnostic_only`.

The output partitions are exclusive:

- `policy_resolved`;
- `evidence_resolved`;
- `still_held`;
- `newly_unsupported`.

The original V2 assessment and all replay inputs remain byte-for-byte
unchanged. A transition to `eligible` remains candidate-review eligibility and
does not create a canary, edit, promotion, or execution authority.

## Governance decision

The first decision required from reviewers is:

> Should an exact 12-month `P580`–`P582` interval be accepted as a canonical
> annual reporting period for P14143 review?

No fiscal resolution is enabled until that decision is recorded as versioned
policy.
