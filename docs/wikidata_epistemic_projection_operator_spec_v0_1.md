# Wikidata Epistemic Projection Operator Spec v0.1

## Goal
Define a deterministic projection from a Wikidata statement bundle
(claim + qualifiers + references + rank) to a ternary epistemic state, and
measure instability over time without prescribing fixes. This is a
control-plane semantics layer: it observes and projects; it does not alter
Wikidata data.

## Data model
- Universe:
  - `E`: items (QIDs)
  - `P`: properties (PIDs)
  - `v`: value (entity, literal, or structured value)
- Statement bundle:
  - `b = (s, p, v, Q, R, rho)`
  - `s in E`, `p in P`, `Q` qualifiers (property -> values), `R` references
    (multiset of reference blocks), `rho` rank in `{preferred, normal, deprecated}`
- Slot:
  - For a fixed `(s, p)`, define `B_{s,p}` as all bundles for that slot.

## Epistemic state space
- Carrier: `T = {-1, 0, +1}`
  - `+1` supported
  - `0` unresolved / insufficient evidence
  - `-1` contradicted / dispreferred
- Information order (paraconsistent flavor): `0 <= +1` and `0 <= -1`, with `+1`
  and `-1` incomparable.

## Projection operator
Define a deterministic projection:

`Pi: b -> (tau, chi)`

- `tau in T` is the ternary epistemic state.
- `chi` is a structured audit trace (rule ids + features), not free text.

### Intermediate record
`x = (tau, e, c, a)`

- `tau`: ternary state
- `e`: evidence score (monotone counter)
- `c`: conflict score (monotone counter)
- `a`: audit payload (applied rule ids + features)

### Operator decomposition
`Pi = O_rank o O_refs o O_quals o O_base`

#### Base
`O_base(b) = (0, 0, 0, [base])`

#### Qualifiers
Qualifiers constrain scope (context lens). They do not increase truth by default.

- Define context signature: `kappa(Q) = canonical_hash(Q)`
- Update:
  - `tau` unchanged
  - `a += [kappa(Q)]`
  - optional `e += delta_q` (small, fixed) if you want specificity to count

#### References
References are evidence presence before evidence quality.

Let:
- `n_R` = count of reference blocks
- `n_src` = number of distinct `P248` sources
- `n_time` = presence of retrieval/publication date (binary)

Define `Delta_e = f(n_R, n_src, n_time)` where `f` is fixed, monotone, capped.

Update:
- `e += Delta_e`
- `a += [refs:Delta_e]`

#### Rank
Rank is a native epistemic hint, but it is gated by evidence.

Let `g(e) = 1` if `e >= e0`, else `0`.

- `preferred`: `tau = +1` if `g(e) = 1`, else `0`
- `deprecated`: `tau = -1` if `g(e) = 1`, else `0`
- `normal`: no change

Update:
- `a += [rho]`

## Slot-level aggregation
For a fixed `(s, p)`, compute `X_{s,p} = { Pi(b) : b in B_{s,p} }`.

Define aggregate operator `A(X_{s,p}) = (tau*, sum_e, sum_c, audit*)`:
- If any `+1` and none `-1`: `tau* = +1`
- If any `-1` and none `+1`: `tau* = -1`
- If both `+1` and `-1`: `tau* = 0` and mark conflict
- If all `0`: `tau* = 0`

This preserves paraconsistency: conflict is explicit, not collapsed.

## Instability metrics
### Claim Stability Invariant (CSI)
At dump time `t`, define:

`CSI_t(s,p) = tau*_t`

### Epistemic Instability Index (EII)
Given `t1 < t2`:

`EII(s,p; t1, t2) = 1[tau*_t1 != tau*_t2] + lambda * Delta(sum_c) + mu * Delta(sum_e)`

For v0, the indicator alone is sufficient; add the deltas only if needed.

## Structural coupling to class-order diagnostics
Compute EII over subclass/type edges (e.g., `P279`/`P31`) and correlate
instability with SCCs or class-order hotspots. This yields a list of
"epistemically volatile" regions without prescribing fixes.

## Assumptions (explicit, falsifiable)
- A1 Determinism: identical bundles yield identical `Pi` output.
- A2 Paraconsistency: contradictory support yields unresolved, not explosion.
- A3 Rank is not truth: rank only moves state when evidence-gated.
- A4 Qualifiers constrain scope; they do not inherently increase truth.
- A5 No source-trust semantics in v0; references contribute via presence only.

## Non-goals (v0)
- No automated fix suggestions.
- No source reliability scoring.
- No language model inference.
- No forced resolution of contested meanings.
