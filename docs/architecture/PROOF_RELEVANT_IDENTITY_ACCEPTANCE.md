# Proof-Relevant Identity Acceptance

This acceptance suite exercises the current identity layer through migration 075.
It is deliberately synthetic: the fixture controls the semantic evidence so the
expected proof state is known exactly, while all resolution, witness creation,
derivation and retraction use the production PostgreSQL functions.

## Apply migrations

```bash
export DATABASE_URL='postgresql://postgres@127.0.0.1:5433/sensiblaw_sparse_bench'
bash scripts/apply_pg_migrations.sh
```

For a benchmark database that already has migrations 069–074 applied, applying
`075_reference_mode_outcomes.sql` is sufficient.

## Run the acceptance suite

```bash
DATABASE_URL="$DATABASE_URL" \
uv run pytest -q \
  tests/storage/test_reference_mode_outcomes.py \
  tests/storage/test_proof_relevant_identity_postgres.py \
  tests/storage/test_proof_relevant_identity_acceptance.py
```

The fixture rows are transaction-local and rolled back after each test.

## Positive round trip

The positive fixture represents the structural situation:

```text
Ronald Reagan ...
He responded ...
```

without asking paragraph co-presence to prove anything. The target actor carries
typed person/role/factor evidence. The local `he` object carries a typed unresolved
demand and participates in an immutable Level-1 factor.

The test requires the production sparse frontier to establish:

```text
candidate_count = 1
outcome = resolved_unique
selected_target = Reagan-labelled local actor
```

Then `refresh_numeric_pnf_semantic_derivations` must produce:

```text
pi : he-object ==> document-derived entity anchored at target actor
F(he, ...)              -- immutable Level-1 premise retained
F(E, ...)               -- separate Level-3 identity substitution
```

The derived argument must retain the exact witness id used by `pi`.

Finally the test retracts that witness through:

```sql
SELECT execution.retract_numeric_pnf_identity_witness(witness_id);
```

and requires:

```text
historical witness row still exists
current witness admission = rejected
current source-object identity projection = absent
current Level-3 substitution = absent
original Level-1 premise factor = still present
```

This is the executable round trip:

```text
G_E^0 --(+ pi)--> G_E^1 --(- pi)--> G_E^0
```

for the current semantic surface, while proof history remains auditable.

## Singular ambiguity

The ambiguity fixture supplies two otherwise compatible actor profiles and one
explicitly singular `he` demand.

Required result:

```text
candidate_count = 2
reference_mode = singular
outcome = ambiguous
selected_target = NULL
identity witness = absent
identity projection = absent
```

Thus candidate multiplicity is not collapsed by rank or lexical proximity.

## Plural and generic separation

Migration 075 introduces an explicit demand-level `reference_mode`:

```text
1 singular
2 plural
3 generic
4 inapplicable
```

The sparse solver still constructs the bounded candidate set. A later frontier
classification trigger preserves the semantic mode supplied by the typed demand.
This is important because candidate count alone cannot distinguish:

```text
two candidates for singular "he"   -> ambiguous
two candidates for plural "they"   -> plural frontier
```

The acceptance fixture uses the same two compatible actors and requires:

```text
singular + several candidates -> ambiguous
plural   + several candidates -> plural
generic  + candidates         -> generic
```

Plural, generic and inapplicable outcomes clear any scalar resolved target and
can never feed the current scalar identity-witness materialiser, which accepts
only `resolved_unique`.

## Epistemic invariant

The complete acceptance boundary is therefore:

```text
surface occurrence
  != referent
  != document entity
  != world entity
```

and:

```text
successful semantic classification
  != scalar identity permission
```

Only an explicitly singular uniquely witnessed reference may enter the scalar
identity fibre. World identity remains a separate external-authority operation.
