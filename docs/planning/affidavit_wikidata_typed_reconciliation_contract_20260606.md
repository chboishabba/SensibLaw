# Affidavit/Wikidata Typed Reconciliation Contract

Date: 2026-06-06

This contract defines the first repo-local Python surface for typed claim
reconciliation across affidavit response rows, object-type claims, and
Wikidata claim rows. It is an operational contract for
`src/fact_intake/typed_claim_reconciliation.py`; it is not an Agda lane and
does not introduce a database migration.

## Shared Objects

- `Proposition`: a typed assertion with `subject`, `predicate`, optional
  `object`, `polarity`, `text`, `context`, `source`, `sequence`, and metadata.
- `ResponseUnit`: a proposition-like response record with an additional
  `response_role`, including procedural/non-answer roles.
- `ObjectTypeClaim`: a typed classification assertion with `subject`,
  `claimed_type`, `context`, `polarity`, `source`, `sequence`,
  `witness_status`, `review_status`, non-promoting `promotion_state`, and
  optional witness metadata. Without a named category/bicategory context and
  typing rule, examples such as `6 is a 1-morphism` remain witness-pending.
- `WikidataClaimRow`: a normalized source row with `subject`, `property`,
  `value`, `qualifiers`, `references`, `rank`, operational status, evidence
  state, promotion state, `truth_claimed = false`, and
  `live_edit_authority = false`.
- `TypedRelation`: a relation envelope that carries the canonical affidavit
  relation type, root, leaf, bucket, evidence state, explanation, and promotion
  state. Caller-supplied relation hints must be marked with
  `relation_derivation = caller_hint`.
- `RelationRoot`: one of `supports`, `invalidates`, `non_resolving`,
  `unanswered`.
- `Bucket`: one of `supported`, `disputed`, `partial_support`,
  `adjacent_event`, `substitution`, `non_substantive_response`, `missing`.
- `EvidenceState`: operational metadata such as `observed` or
  `held_for_review`.
- `PromotionState`: explicit proof-promotion metadata. In this slice it is
  always `not_promoted`.

## Canonical Relation Labels

Existing affidavit relation labels remain canonical:

- `exact_support`
- `equivalent_support`
- `explicit_dispute`
- `implicit_dispute`
- `partial_overlap`
- `adjacent_event`
- `substitution`
- `procedural_nonanswer`
- `unrelated`

The reducer maps these labels to relation roots and buckets, but it does not
promote claims to proof. Support and dispute classification are evidence
metadata only.

## Demonstrations

1. `Alex walked the dog` compared with `Alex did not walk the dog` reduces to
   `explicit_dispute`, root `invalidates`, bucket `disputed`, with promotion
   false.
2. `Alex walked the dog` compared with `Alex walked the dog` reduces to
   support, with promotion false.
3. Adjacent or procedural response examples reduce to `adjacent_event` or
   `procedural_nonanswer`, not support.
4. `6 is a 1-morphism`, `6 is a 2-morphism`, `6 is a j-invariant`, and
   `6 is a dolphin` normalize as four positive object-type claims. Different
   positive claimed types are not contradictory without an explicit exclusion
   witness.
5. `6 is a dolphin` compared with `6 is not a dolphin` reduces to a
   same-subject/same-type dispute.
6. Wikidata entity/property/value rows normalize as provenance-bearing claim
   rows. Qualifiers and references remain source substrate.

## PNF Boundary

`src/sensiblaw/interfaces/story_pnf_receipts.py` remains the classification
lattice surface for classification/type residuals. The typed reconciliation
module may emit object-type claim dictionaries compatible with that surface,
but it does not rewrite residual lattice semantics or PNF relation labels.

## Wikidata Boundary

Wikidata is treated as a source substrate. Its claim rows carry provenance and
operational state only:

- deprecated rank maps to `held_for_review` evidence metadata and deprecated
  operational status;
- preferred and normal rank remain observed evidence metadata;
- `truth_claimed` and `live_edit_authority` are materialized as false fields,
  not omitted;
- no rank becomes truth, contradiction, proof, edit authority, or promotion.

Existing persisted affidavit columns remain the database surface:
`relation_type`, `relation_root`, `relation_leaf`, `explanation_json`, and
`missing_dimensions_json`.

## DASHI Formalism Alignment Review

This slice was checked against the current DASHI Agda formal surfaces:

- `LoomRelationAlgebra.agda`: finite relation labels, roots, buckets,
  evidence status, and promotion state remain separate objects.
- `ClaimReconciliationObjectLattice.agda`: claim atoms, response units,
  typed-object assertions, Wikidata qualifiers, references, revision windows,
  and statement rows are carriers, not truth decisions.
- `LargerObjectClassificationLattice.agda`: claim atoms, contested claims,
  typed-object assertions, and Wikidata row geometry are classified object
  families; morphism typing claims are still witness/runtime pending without
  explicit context and typing witnesses.

The review conclusion is:

- relation vocabulary, root projection, bucket projection, and non-promotion
  behavior match the formal relation algebra;
- the dog fixture is correctly an `explicit_dispute` relation and does not
  decide which side is true;
- object-type assertions now expose `witness_status`, `review_status`, and
  non-promoting `promotion_state`, matching the `6 is a 1-morphism`
  witness-pending boundary;
- Wikidata rows now materialize `truth_claimed = false` and
  `live_edit_authority = false`, rather than relying on omission;
- caller hints now carry `relation_derivation = caller_hint`, preserving the
  distinction between derived reconciliation and supplied evidence metadata.

Remaining boundary: this is still a Python operational contract. It mirrors
the Agda object grammar closely enough for lane discipline, but it is not an
Agda proof and does not replace the persisted affidavit review tables.
