# Proof-Relevant Identity Acceptance

This acceptance surface now covers the proof kernel and the first real-text
identity-evidence producers through migrations 075–079.  Synthetic fixtures keep
expected proof states exact; corpus-yield reporting measures what the same runtime
produces over an existing numeric PNF corpus.

## Apply migrations

```bash
export DATABASE_URL='postgresql://postgres@127.0.0.1:5433/sensiblaw_sparse_bench'
bash scripts/apply_pg_migrations.sh
```

For a benchmark database already migrated through 076, apply 077, 078 and 079 in
order.

## Kernel acceptance

```bash
DATABASE_URL="$DATABASE_URL" \
uv run pytest -q \
  tests/storage/test_reference_mode_outcomes.py \
  tests/storage/test_factor_participation_actor_profiles.py \
  tests/storage/test_identity_evidence_production_v1.py \
  tests/storage/test_proof_relevant_identity_postgres.py \
  tests/storage/test_proof_relevant_identity_acceptance.py
```

The reversible identity fixtures are transaction-local and rolled back.

## Real-text evidence production v1

Migration 077 introduces a separate
`semantic_pnf_identity_evidence_candidate` relation. Parser observations can
produce candidate evidence without rewriting local objects or asserting identity.

The first evidence lanes are:

```text
spaCy appos dependency              -> apposition
PERSON <-> nominal apposition       -> title_role_closure
multi-token PERSON + family lemma   -> proper_name_expansion candidate
explicit aka / alias / known as cue -> explicit_alias
resolved typed anaphor demand       -> anaphor_demand_resolution (existing path)
```

Migration 078 makes sentence identity use persisted parser `sentence_ref`
throughout and orients title/apposition evidence toward a PERSON anchor when
exactly one side of the dependency lies inside a PERSON entity span.

No lane uses paragraph co-presence, nearest-person search, generic string
similarity, n-grams, or the global lookup as identity evidence.

### Parser token to local object bridge

`semantic_pnf_parser_object_anchor` maps a parser token to a PNF object only when:

1. the object lies in a smallest PNF region containing that exact token span;
2. the object head equals the token orthographic or lemma symbol; and
3. exactly one object survives at that smallest region size.

Failure of uniqueness yields no anchor and therefore no parser identity evidence.

## Evidence strength and admission

Candidate evidence is not automatically authority.

Migration 079 distinguishes strong local structural evidence from useful but
insufficient lexical evidence:

```text
apposition                    candidate_count=1 -> may establish document identity
title/role apposition         candidate_count=1 -> may establish document identity
explicit alias/equivalence    candidate_count=1 -> may establish document identity
proper-name expansion         candidate only until independently corroborated
anaphoric typed-hole result   admitted only through resolved_unique demand proof
```

A document-unique surname therefore does **not** bootstrap identity by itself.
A `proper_name_expansion` witness can be admitted only when its target entity
already has an accepted non-anchor proof from apposition, title-role closure,
explicit alias, anaphor resolution, or another uniquely resolved typed demand.

All admissions remain subject to migration 074's write-boundary invariant:

```text
candidate_count = 1
witness.authority_class = target_entity.authority_class
```

World identity remains impossible without explicit `external_authority` evidence.

## Positive reversible round trip

The controlled positive fixture requires the production sparse frontier to
establish one typed actor target and then materialise:

```text
pi : he-object ==> document-derived entity
F(he, ...)  -- immutable Level-1 premise
F(E, ...)   -- separate Level-3 substitution carrying pi
```

Retraction must restore the current semantic surface while retaining historical
proof evidence:

```text
G_E^0 --(+ pi)--> G_E^1 --(- pi)--> G_E^0
```

## Ambiguity / plural / generic fixtures

The same bounded frontier distinguishes:

```text
singular + one witness       -> resolved_unique
singular + several witnesses -> ambiguous
plural   + witnesses         -> plural
generic  + witnesses         -> generic
```

Only `singular + one witness` can feed scalar identity projection.

## GWB / corpus identity-yield benchmark

To run the real evidence producers over the selected numeric PNF run and measure
what survives the proof boundary:

```bash
PYTHONPATH=. uv run python scripts/report_identity_evidence_yield.py \
  --database-url "$DATABASE_URL" \
  --refresh \
  --surface reagan \
  --surface bush \
  --surface cia \
  --output .tmp/gwb-identity-yield.md
```

Use `--run-id N` to select a particular numeric run and repeat `--document-id N`
to constrain the corpus slice.

The report measures:

```text
local PNF objects
factor-participating objects
parser-grounded identity candidates
admitted parser candidates
currently admitted identity witnesses
Level-3 identity substitutions
world-authority entities
candidate/admitted/ambiguous counts by witness kind
requested-surface object/factor/entity/witness counts
```

The useful sparsification series is therefore observable directly:

```text
|local objects|
  >> |factor participants|
  >> |identity candidates|
  >= |accepted identity witnesses|
```

A high candidate count with a low admission count is not itself failure: the
central acceptance criterion is that uncorroborated or ambiguous evidence remains
outside the admitted identity fibre.

## Epistemic boundary

```text
mention
  != referent
  != document entity
  != world entity
```

and:

```text
candidate identity evidence
  != admitted identity proof
  != world identity authority
```

Every promotion must retain an inspectable witness; no proximity shortcut can
manufacture one.
