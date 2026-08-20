# Typed eventual-consistency fibre scheduling

The numeric PNF runtime distinguishes semantic fibres from physical queue
orchestration.

The governing execution model is not "batch everything".  It is:

```text
commute where exact independence is proved
join where an idempotent/commutative/associative merge is the semantic law
braid where ordering, provenance or residual obligations remain observable
```

This mirrors `DASHI.Cognition.PNF.TypedEventuallyConsistentFibreSystemExact` in
`dashi_agda`.

## Eventual-consistency boundary

Local fibres may close independently.  Cross-fibre effects are represented as
explicit join or braid obligations and are reconciled fairly until the declared
fixed-point criterion is reached.

Local commutation laws do **not** by themselves prove global convergence.  A
convergence claim additionally needs a fairness/fixed-point certificate.  A
braid is never silently weakened to an unordered join.

The durable queue is therefore a recovery/fairness carrier, not semantic proof
that every microscopic transition needs its own claim transaction.

## Current production specialization

Live `pg_stat_statements` evidence on the current strict serial frontier exposed
N+1 queue orchestration:

```text
claim one work item
-> commit lease
-> execute one fibre
-> close/update one region
-> complete one work item
-> commit
-> repeat
```

The first implementation deliberately attacks only the claim side.

`src/storage/postgres/bounded_work_batch.py` leases a bounded ordered relation of
work items in one transaction.  Every member retains its own:

- `work_id`;
- `region_id`;
- operation;
- lease token;
- incremented lease epoch;
- retry/failure identity.

Sentence closure installs this through
`src/policy/bounded_sentence_batch_leasing.py`.  Adjacent reconciliation consumes
the same batch-lease primitive directly.

Execution is still one semantic fibre per existing transaction.  In particular,
adjacent reconciliation remains braid-sensitive; the runtime does not claim that
neighbouring adjacent fibres commute merely because their queue rows were leased
together.

If an in-process failure occurs after a batch was leased, every not-yet-started
member is returned to READY only when its exact `(work_id, lease_token,
lease_epoch)` fence still matches.  Process death continues to use ordinary lease
expiry.

## Orchestration amplification

For a measured operation family define

```text
A_orchestration =
  (claim statements + lifecycle statements + transaction boundaries)
  / semantic work fibres.
```

The current tranche reduces the claim component while holding semantic work
cardinality fixed.  It does not yet claim lower lifecycle-update or execution
transaction counts.

A later set-wise lifecycle transition is admissible only if it preserves the
same individual semantic observations/fences.  A later shared execution batch is
stronger again and requires an explicit commuting/join certificate; braid-linked
work remains ordered/reconciled.

## Sin-bin pattern

### N+1 durable work-item orchestration

Bad physical shape:

```text
for each semantic fibre:
    claim one durable queue row
    commit
    execute one bounded fibre
    update lifecycle rows
    commit
```

Symptom:

- high `claim_work` call count;
- high region/work lifecycle update count;
- Python mostly blocked in `psycopg`;
- no corresponding increase in semantic fibre count.

Legal replacements, in increasing semantic strength:

1. bounded set-wise lease acquisition while retaining per-fibre execution;
2. set-wise fenced completion/region lifecycle projection with exact parity;
3. shared execution only for a certified commuting/join fibre;
4. explicit braid reconciliation for order/provenance-sensitive interactions.

An index can reduce the cost of one claim but cannot remove N+1 orchestration.
Migration 174's operation-aware work index and bounded batch leasing therefore
solve different layers of the same measured hotspot.
