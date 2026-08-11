# Identity Evidence Execution Optimisation

This note records the execution-topology changes after proof-relevant identity
semantics were established. The epistemic contract is unchanged: candidate
evidence is not identity authority, and execution budgets never create semantic
permission.

## Migration 081: document-scoped parser anchor

The original generic parser/object anchor used a minimum-region-span window over
all parser tokens. An outer document predicate could not reliably push through
that grouped/window surface, so a document refresh could evaluate the entire
corpus before discarding unrelated rows.

Migration 081 moves run/document restriction before the window and shares one
`MATERIALIZED doc_anchor` among apposition, proper-name and alias evidence lanes.

```text
corpus tokens -> global window -> document filter       [removed]

document tokens
  -> document regions
  -> one shared anchor
  -> {apposition, name expansion, alias}
```

## Migrations 082 and 084: bounded factor-composition work

The original composition generator bounded retained output but ranked the full
pair relation first. For bridge degree `n`, that still allowed `O(n^2)` pair
construction even when only `K=16` candidates survived.

Migration 082 adds deterministic per-bridge pair bounds and
`semantic_pnf_factor_composition_overflow`. Migration 084 tightens the SQL
execution shape so `LIMIT K` occurs in an inner raw-pair query and `row_number()`
ranks only those retained K rows. This avoids a window sort over the complete
pair relation before the limit.

The overflow relation records bridge identity, participant count, theoretical
pair count and retained pair limit. Overflow is an execution receipt. It neither
rejects a relation nor licenses a derived proposition.

## Migration 083: exact object-token support fast path

Strict numeric sentence closure already persists:

```text
semantic_pnf_object_token_support(object_id, token_id)
```

for local PNF objects. Migration 083 therefore makes this exact support relation
the primary parser-token -> local-object bridge and adds the reverse index:

```text
(token_id, object_id)
```

The minimum-span containment search remains only as a fail-closed fallback for
identity-relevant tokens (`PROPN`, `NOUN`, apposition source/head) with no exact
support row at all.

If exact support exists but is non-unique or inconsistent with the token head,
the system does not fall back to proximity; it yields no anchor.

## Migration 085: bounded proper-name evidence

The real-corpus phase benchmark showed parser evidence dominating while typed
identity, admission, substitution and bounded factor composition were already
cheap. Inspection showed that proper-name expansion joined every proper-name
mention to every multi-token PERSON head sharing its family lemma.

Migration 085 changes the execution carrier to:

```text
PERSON spans
  -> one token-membership join
  -> one head per multi-token PERSON
  -> one ranked family carrier per lemma

standalone surname mention
  -> at most K family targets
  -> candidate evidence
  -> overflow receipt when family cardinality > K
```

`semantic_pnf_proper_name_evidence_overflow` stores the full observed family
cardinality and retained target limit. The retained representative set is not a
claim that omitted targets are false or rejected.

A proper-name token already contained inside a PERSON span is deliberately not a
surname-expansion source. The full-name structure is already present, and
self-excluding one full-name anchor could otherwise make another person with the
same surname look spuriously unique.

Proper-name expansion remains candidate-only and still requires an independently
admitted corroborating identity before it can enter the identity projection.

## Transaction topology

The identity refresh benchmark and yield reporter commit one document at a time.
This matches ordered semantic publication and prevents one tranche-wide
transaction from retaining locks, undoing earlier documents after a later
failure, or obscuring the document responsible for a timeout.

The benchmark times these production phases separately:

```text
typed_identity
parser_evidence
parser_admission
identity_substitution
factor_composition
```

## Yield accounting

Raw admitted-witness counts are not enough to describe semantic gain. The yield
report therefore distinguishes:

```text
parser evidence candidates
parser source -> entity proofs
parser anchor/base witnesses
typed-demand source -> entity proofs
current identity projections
factor-bearing identity projections
Level-3 identity substitutions
world-authority entities
```

This matters because a valid source identity proof may land on a local object
that participates in no extracted factor. Such a proof is real identity evidence,
but it does not yet enrich the factor graph. In particular:

```text
admitted source proof != factor-bearing projection
factor-bearing projection != Level-3 substitution count by itself
```

The next semantic coverage question after parser-evidence performance is solved is
therefore whether admitted identity fibres intersect the factor-participant
carrier often enough to produce useful substitutions.

## Next measured optimisation surface

`semantic_pnf_identity_projection` remains a grouped view over accepted identity
witnesses. It is deliberately not materialised yet because accepted identity is
still sparse. If `identity_substitution` or identity-bridged composition becomes
dominant as witness yield grows, the next candidate is a document-scoped
projection function or retractable current-projection table maintained from
witness admission changes.

If parser evidence remains dominant after migration 085, the next query-plan
inspection should split the remaining cost among:

- exact token-support anchoring;
- PERSON span/token membership;
- apposition evidence;
- alias cue pairing.

No further optimisation should be inferred from candidate count alone.

## Epistemic invariant

```text
execution truncation       != semantic rejection
execution overflow         != domain-rule authority
exact token support        != entity identity
candidate evidence         != admitted identity witness
admitted identity witness  != factor derivation
```

Optimisation may change how bounded evidence is found, but not what counts as a
proof.
