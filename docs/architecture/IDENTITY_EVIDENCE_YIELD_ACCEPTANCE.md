# Identity Evidence Yield Acceptance

The first real-corpus identity run established that parser evidence can produce
admitted document-local source proofs. The next acceptance gate separates proof
production from semantic utilisation.

For one document `D`, define:

```text
O_D = local PNF objects
F_D = objects participating in at least one Level-1 factor
C_D = parser identity evidence candidates
P_D = admitted source -> entity identity proofs
I_D = current identity projection members
B_D = projected objects that also belong to F_D
S_D = admitted Level-3 identity-substitution derivations
```

The expected sparsification relation is:

```text
|O_D| >= |F_D|
|C_D| >= |P_D|
|I_D| >= |B_D|
```

No required ordering is asserted between `|P_D|` and `|I_D|` because multiple
proofs may support one projected object, and projection disappears if accepted
proofs conflict on the target entity.

The key semantic-utilisation ratio is not raw witness yield. It is:

```text
factor_identity_coverage(D) = |B_D| / |F_D|
```

and the corresponding derivation yield is:

```text
substitution_yield(D) = |S_D| / max(1, |B_D|)
```

A high `|P_D|` with `|B_D| = 0` means identity evidence is working but landing
outside the extracted factor neighbourhood. That should lead to factor-coverage
analysis, not weaker identity admission.

A low `|P_D|` with many strong parser candidates means evidence admission or
parser/PFN anchoring should be inspected.

Proper-name overflow and factor-composition overflow are execution receipts only.
Neither enters these semantic ratios as a rejected fact.

## Current acceptance sequence

1. Apply migrations through 085.
2. Run the focused PostgreSQL/static tests.
3. Run the per-phase identity benchmark over the GWB document set.
4. Require parser evidence to stay within the configured statement timeout for
   every document.
5. Generate the stratified yield report.
6. Inspect `factor_identity_coverage` before adding more identity evidence rules.
7. Only if factor-bearing projections are non-trivial should Level-3 composition
   or richer factor rules become the next semantic tranche.

The benchmark/report must distinguish source proofs, anchor witnesses,
projections, factor-bearing projections and Level-3 substitutions. A combined
"identity witness" number is not an acceptance metric by itself.
