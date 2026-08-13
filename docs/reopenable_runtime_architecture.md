# Consumer-indexed reopenable numeric PNF runtime

## Status

This document describes migrations 086-088 and the associated Python runtime,
observatory and benchmark surfaces.  The Agda layer remains the specification;
PostgreSQL is the persistent execution carrier.

## Constitutional separation

The runtime does not use one overloaded candidate status.  For a demand `u`, the
represented fibre is `F(u)`.  Its execution partition is:

- `P`: active bounded execution surface;
- `Q`: represented candidates not currently active, but reopenable;
- `R`: represented unresolved residual structure not captured as a candidate;
- `O`: explicitly represented outside-model/open-world ignorance.

Execution pruning is not semantic refutation.  Semantic refutation requires an
explicit evidence row and a separate admissibility event.  Inductive preference
is likewise separate from proof-producing identity witness admission.

Consumer/model-relative relevance accounting is exact integer accounting:

`mu_C(P) + mu_C(Q) + mu_C(R) + mu_C(O) = mu_C(F)`.

The masses are not probabilities and do not imply world completeness.  In
particular, `mu_C(P) = mu_C(F)` for a current consumer does not authorize deletion
of `Q/R/O`; later actions can expose terminalisation defects.

## One fibre, cumulative H3/H6/H9 evidence

`H3`, `H6` and `H9` are cumulative evidence horizons over one durable candidate
fibre, not three candidate generators:

- H3: local structural evidence;
- H6: H3 plus discourse/temporal evidence;
- H9: H6 plus external/authority evidence.

Fine evidence is stored as an exact signed integer residual.  The ternary
`-1/0/+1` phase is a projection of that fine residual.  Negative evidence is
therefore counterevidence/reweighting, not refutation.

Migration 088 exposes `semantic_pnf_horizon_escalation_v1`; its
`fibre_cardinality_invariant` is an executable check that changing evidence
horizon has not silently regenerated candidate identity.

## Progressive resolution

`semantic_pnf_progressive_preference_candidate_v1` chooses a preference only
when one admissible represented candidate has a strictly larger cumulative
signed residual than every other admissible represented candidate.  Ties remain
unresolved.

`semantic_pnf_progressive_resolution_v1` then places this preference beside the
existing `semantic_pnf_frontier_resolution` proof surface.  The key distinction
is explicit:

- `deductive_unique`: existing frontier resolver produced `outcome_state = 2`;
- `inductive_preference`: strict evidence winner but no unique proof;
- `resource_limited`;
- `unresolved`.

`refresh_numeric_pnf_progressive_preferences(...)` writes only revisioned
`semantic_pnf_candidate_preference` rows.  It cannot insert, update or delete
`semantic_pnf_frontier_resolution`, and therefore cannot turn ranking into an
identity witness.

## Parser observation -> argument support -> identity

Parser/name objects and factor arguments are not collapsed by identity.  The
runtime uses existing `semantic_pnf_object_token_support` as the structural
support seam.  Identity evidence may be transported to a factor argument only
through an exact support incidence, and the resulting Level-3 derivation records:

- the factor and slot;
- the identity source object;
- the exact support token when support is indirect;
- the canonical entity and authority class;
- the identity witness IDs.

This yields four identity->factor audit classes:

1. `direct_factor_participant`;
2. `exact_token_structural_support`;
3. `same_region_unbridged`;
4. `no_structural_bridge`.

The latter two are the unexplained alignment surface that should shrink as
representation support improves.

## Observability

Run:

```bash
python scripts/observe_reopenable_runtime.py \
  --database-url "$DATABASE_URL" \
  --run-id RUN --document-id DOCUMENT --pretty
```

The report contains:

- direct/support/unbridged/no-bridge identity-factor counts;
- unexplained identity->factor percentage;
- typed-demand funnel;
- H3/H6/H9 evidenced and preferred demand counts;
- `P/Q/R/O` counts;
- candidate compression and consumer relevance accounting;
- supported Level-3 derivation yield;
- latest measured spaCy/post-parser elapsed dominance ratio.

## Empirical query-shape benchmark

Run:

```bash
python scripts/benchmark_reopenable_runtime.py \
  --database-url "$DATABASE_URL" \
  --run-id RUN --document-id DOCUMENT \
  --workload-ref WORKLOAD
```

Add `--persist` to write measurements to the migration-086 measurement tables.
The stage tuple is:

`(N_input, N_generated, N_retained, N_output, W, M, T)`

where `M` is `null` until a process-level peak-memory observer supplies a value.
The same driver records PostgreSQL retrieval reduction as
`frontier_units / universe_units`, probe time, and downstream work units.  A
single benchmark point is an observation, not a scaling theorem; multi-point
affine-envelope validation lives in `src/policy/reopenable_runtime.py`.

## Source dependency audit

Run:

```bash
python scripts/audit_reopenable_runtime_migrations.py --show-provenance
```

The audit scans every PostgreSQL migration and requires each
`execution.<identifier>` referenced by migrations 086-088 to have a source-level
`CREATE TABLE`, `CREATE VIEW`, `CREATE MATERIALIZED VIEW`, `CREATE FUNCTION` or
`CREATE PROCEDURE` definition somewhere in the migration set.

The principal pre-086 dependencies are deliberately reused rather than cloned:

| Runtime dependency | Source lane |
| --- | --- |
| demand/candidate/interface/region/object/factor/hyperedge carriers | 040, 045-047 |
| global numeric lookup | 049 |
| numeric run/document IDs | 051 |
| set-based demand planning | 053 |
| sparse frontier resolution | 062, 067-068 |
| proof-relevant identity fibres and witnesses | 069 |
| factor derivations and premises | 070 |
| reference multiplicity | 075 |
| parser identity evidence | 077-081 |
| exact object-token support | 083 |
| bounded factor composition | 082, 084 |
| bounded proper-name evidence | 085 |

Migration 087 depends only on relations/views/functions introduced by 086 and
preserves the original `semantic_pnf_candidate_state_v1` column order before
appending `current_planner_member`, making `CREATE OR REPLACE VIEW` upgrade-safe.
Migration 088 consumes the 086/087 candidate/evidence surfaces plus the existing
frontier proof carrier; it does not replace either.

## Operational rule

The document graph remains the semantic object.  Chunks are execution fibres over
that shared graph.  Reconciliation may bound active execution, but unresolved
candidate/evidence history remains durable until explicit semantic evidence
refutes it or a coverage witness closes the relevant open-world surface.
