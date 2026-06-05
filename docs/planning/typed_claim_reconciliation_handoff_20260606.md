# Typed Claim Reconciliation Handoff

Date: 2026-06-06

This handoff records the current state after aligning the SensibLaw Python
claim-reconciliation slice with the Agda carrier in `../dashi_agda`.

## Current State

SensibLaw now has a repo-local operational implementation at:

- `src/fact_intake/typed_claim_reconciliation.py`
- `tests/test_typed_claim_reconciliation.py`
- `docs/planning/affidavit_wikidata_typed_reconciliation_contract_20260606.md`

The implementation covers three example families:

- affidavit proposition/response reconciliation, including `Alex walked the
  dog` versus `Alex did not walk the dog`;
- object-type assertions such as `6 is a 1-morphism`, `6 is a 2-morphism`,
  `6 is a j-invariant`, and `6 is a dolphin`;
- Wikidata-style entity/property/value rows with qualifiers, references, rank,
  deprecation, and explicit non-authority fields.

No database migration was added. Existing affidavit persisted columns remain
the storage surface: `relation_type`, `relation_root`, `relation_leaf`,
`explanation_json`, and `missing_dimensions_json`.

## Formal Alignment

The Agda-side formal carrier lives in `../dashi_agda`:

- `ClaimReconciliationObjectLattice.agda`
- `LargerObjectClassificationLattice.agda`
- `DialecticalJourneyLoom.agda`
- `LoomRelationAlgebra.agda`

SensibLaw uses Python dictionary fields; Agda uses constructors and camel-case
record fields. The important concept mapping is:

| SensibLaw field | Agda-side concept |
| --- | --- |
| `kind = "proposition"` | `ClaimAtom` |
| `kind = "response_unit"` | `ResponseUnit` |
| `kind = "object_type_claim"` | `TypedObjectAssertion` |
| `kind = "wikidata_claim_row"` | `WikidataStatementRow` |
| `relation_type` | `LoomRelationType` / `relationType` |
| `relation_root` | relation root reading (`supports`, `invalidates`, `non_resolving`, `unanswered`) |
| `promotion_state.promoted = false` | `promotionFalse` witness |
| `truth_claimed = false` | `truthClaimed ≡ false` |
| `live_edit_authority = false` | `liveEditAuthority ≡ false` |
| `witness_status` | `TypedObjectWitnessStatus` |
| `review_status` | `ReviewStatus` |
| `relation_derivation = "caller_hint"` | caller-supplied evidence metadata, not derived reconciliation |

## Runtime Rules

The canonical affidavit relation labels remain:

- `exact_support`
- `equivalent_support`
- `explicit_dispute`
- `implicit_dispute`
- `partial_overlap`
- `adjacent_event`
- `substitution`
- `procedural_nonanswer`
- `unrelated`

Relation/support classification is evidence metadata. It does not promote a
claim to proof, truth, legal sufficiency, Wikidata authority, or theorem
status.

Object-type assertions are first-class but conservative:

- without a category/bicategory context, the default is
  `witness_status = "typing_context_missing"` and
  `review_status = "witness_pending"`;
- with a named context but no typing rule, the status remains witness-pending;
- with a named context and typing rule, the status can be
  `typing_witnessed`, but promotion is still false;
- different positive claimed types for the same subject are adjacent metadata,
  not contradiction, unless an explicit exclusion witness is supplied.

Wikidata rows are source substrate:

- normal and preferred ranks become observed evidence metadata;
- deprecated rank becomes `evidence_state = "held_for_review"` and
  `operational_status = "deprecated"`;
- all Wikidata claim rows materialize `truth_claimed = false` and
  `live_edit_authority = false`;
- Wikidata rank never becomes proof, truth, contradiction, or edit authority.

Relation hints may be accepted from callers only as evidence metadata. They are
machine-marked with `relation_derivation = "caller_hint"` so downstream code
can distinguish caller hints from derived reconciliation.

## Verification

SensibLaw verification passed:

```bash
cd /home/c/Documents/code/ITIR-suite/SensibLaw
../.venv/bin/python -m pytest tests/test_typed_claim_reconciliation.py -q
../.venv/bin/python -m pytest tests/test_affidavit_coverage_review.py tests/test_story_pnf_receipts.py -q
```

Observed results:

- `tests/test_typed_claim_reconciliation.py`: 11 passed
- `tests/test_affidavit_coverage_review.py tests/test_story_pnf_receipts.py`: 49 passed

Agda verification passed from `../dashi_agda`:

```bash
agda ClaimReconciliationObjectLattice.agda
agda LargerObjectClassificationLattice.agda
agda DialecticalJourneyLoom.agda
agda ClassificationDiscoveryLattice.agda
agda ITIRPNFAssessment.agda
agda LoomRelationAlgebra.agda
```

## Worktree Notes

At the time of this handoff, unrelated dirty files existed in both repos.
Do not include them in a scoped claim-reconciliation commit.

SensibLaw claim-reconciliation files to stage together:

- `src/fact_intake/typed_claim_reconciliation.py`
- `src/fact_intake/__init__.py`
- `tests/test_typed_claim_reconciliation.py`
- `docs/planning/affidavit_wikidata_typed_reconciliation_contract_20260606.md`
- `docs/planning/typed_claim_reconciliation_handoff_20260606.md`

Known pre-existing SensibLaw dirty files not touched for this slice:

- `src/sensiblaw/interfaces/story_pnf_receipts.py`
- `tests/test_story_pnf_receipts.py`

## Next Steps

1. Commit the SensibLaw Python/docs slice separately from unrelated dirty work.
2. Commit the `../dashi_agda` Agda carrier slice separately from unrelated
   YM/clay sprint files.
3. Add a small read-only fixture bridge:
   - export the SensibLaw dog, object-type, and Wikidata rows as JSON fixtures;
   - map each fixture to the corresponding Agda canonical example;
   - keep the fixture bridge non-promoting and non-authoritative.
4. Only after the fixture bridge exists, consider wiring the helpers into a
   higher-level review packet builder. Do not change the database surface until
   a concrete persisted consumer needs it.
