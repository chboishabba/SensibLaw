# Sparse-frontier transition work diagnostic

The M178/M179 replay falsified the assumption that extensional candidate parity plus unary-key indexing is sufficient to make sparse-frontier transition work physically sparse.

The current diagnostic round therefore makes no production SQL change.  It measures the physical work funnel needed to choose the next optimization from evidence.

## Formal contract

The companion DASHI Agda module `ConjunctiveExposureLocalityExact` separates four obligations:

```text
semantic parity
+ bounded intermediate exposure
+ bounded materialization
+ bounded rewrite
```

For an observation with final admitted rows `A`, wildcard residual `R`, and intermediate exposure `E`, the runtime target is represented schematically as:

```text
E <= c * A + R
```

The wildcard residual is explicit.  Missing constraints are not negative evidence and may not be pruned merely to make an execution bound look better.

Object-candidate matching has four nullable axes and therefore sixteen masks:

```text
factor / object-kind / role / lexical
2^4 = 16
```

Actor retention deliberately omits lexical identity and therefore has eight masks:

```text
factor / object-kind / role
2^3 = 8
```

## Combined probe

Run the combined read-only probe against the exact adaptive or document interface under investigation:

```bash
python scripts/diagnose_sparse_frontier_transition_work.py \
  --database-url "$DATABASE_URL" \
  --interface-id <interface-id> \
  --plan-mode analyze \
  --output .tmp/sparse-frontier-transition-work.json
```

`--plan-mode analyze` is the decision-grade mode.  It records actual rows, shared-buffer traffic and temp spill for the expensive stages through `EXPLAIN (ANALYZE, BUFFERS, WAL, FORMAT JSON)`.  `estimate` is available for a cheap planner-only preview and `none` records only cardinalities.

The transaction is read-only.  The probe does not install indexes, functions, migrations, or mutate frontier authority.

## Candidate exposure / ranking / rewrite receipt

`scripts/diagnose_sparse_frontier_candidate_work.py` records:

- unresolved object-demand count;
- actor-profile count;
- required-key rows;
- profile-key rows;
- unary key-match rows before conjunction;
- distinct partially matched demand/profile rows;
- post-hoc unary conjunctive rows;
- exact legacy static conjunction cardinality;
- exact recency-qualified object-candidate cardinality;
- current M178 helper cardinality and parity with the literal conjunction;
- factor-candidate rows;
- raw candidate rows;
- deduplicated/ranked rows;
- `maxCandidates` survivors;
- current persistent candidate rows;
- rows the canonical delete-all/reinsert path would rewrite;
- exact candidate-row semantic symmetric difference via `EXCEPT ALL`;
- current resolution rewrite population;
- candidate constraint-mask distribution;
- required-key-count, recency and `maxCandidates` histograms;
- unary fanout by key kind;
- the broadest profile postings and demand postings;
- actual planner/buffer/temp metrics for the exposure and ranking stages.

It emits the decision ratios:

```text
beta_unary = unary partial-key matches / final object candidates
beta_partial = partially matched demand/profile rows / final object candidates
beta_rank = raw candidates / maxCandidates survivors
beta_write = canonical candidate rows rewritten / semantic candidate-row delta
```

If the semantic delta is zero while the canonical reducer would still rewrite rows, `beta_write_is_unbounded_for_zero_delta` is reported explicitly instead of fabricating a finite ratio.

The literal direct-conjunction SQL exists only to determine exact relation cardinality and to cross-check M178 helper semantics.  Its execution plan is not treated as the proposed composite-signature implementation.

## Actor-retention receipt

`scripts/diagnose_sparse_frontier_actor_retention_work.py` separately measures M179 because actor retention can own the pathological spill independently of candidate generation.

It records:

- unresolved child object demands;
- actor profiles;
- factor/kind/role required-key rows;
- profile-key rows;
- unary partial-key match rows;
- distinct partially matched demand/profile rows;
- post-hoc conjunctive rows;
- eight-mask profile-signature projection size;
- exact composite-signature demand/profile match cardinality;
- distinct retained profiles;
- current M179 helper retained-profile cardinality;
- mask and wildcard population;
- fanout by key kind;
- broadest profile postings;
- actual planner/buffer/temp metrics for both unary and finite-mask forms.

The lexical axis is intentionally absent from this probe because the historical migration-062 actor-retention predicate did not use lexical identity.

## Next-round decision rule

Do not choose another SQL migration from final relation cardinality alone.

Use the combined receipt as follows:

```text
large retention unary fanout
    -> actor-retention conjunctive exposure

large candidate unary fanout
    -> object-candidate conjunctive exposure

large raw/survivor ratio
    -> bounded top-k / ranking work

large rewrite/semantic-delta ratio
    -> incremental candidate lifecycle

wildcard work dominates
    -> inspect upstream constraint quality;
       if genuinely unconstrained, retain the broad cost as semantic residual
```

Multiple targets may be true simultaneously.  The next implementation round should attack the measured dominant term(s), then rerun the same receipt before promotion.

## Interpretation boundary

The diagnostic distinguishes three things that must not be conflated:

```text
retained-state sparsity
transition-relation exactness
physical transition-work sparsity
```

M178/M179 already demonstrate that the first two do not imply the third.  This receipt exists to measure the missing physical obligation directly.
