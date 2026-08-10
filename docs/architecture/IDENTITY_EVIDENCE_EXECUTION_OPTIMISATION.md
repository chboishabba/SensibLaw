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

The overflow relation records:

- bridge object/entity;
- participant count;
- theoretical pair count;
- retained pair limit.

Overflow is an execution receipt. It neither rejects a relation nor licenses a
derived proposition.

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

## Transaction topology

The identity refresh benchmark and yield reporter now commit one document at a
time. This matches ordered semantic publication and prevents one tranche-wide
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

and reports composition overflow bridges per document.

## Next measured optimisation surface

`semantic_pnf_identity_projection` remains a grouped view over accepted identity
witnesses. It is deliberately not materialised yet because accepted identity is
currently sparse. The phase benchmark will show whether the projection view
becomes material.

If `identity_substitution` or `factor_composition` becomes dominant as identity
yield grows, the next candidate is a document-scoped projection function or a
retractable current-projection table maintained from witness admission changes.
That change should be justified by observed query plans rather than applied in
advance.

A secondary surface to watch is proper-name ambiguity fan-out: common surnames
can generate multiple candidate rows even though `candidate_count > 1` prevents
admission. If that becomes material, candidate targets should receive their own
bounded/overflow carrier rather than silently truncating the ambiguity set.

## Epistemic invariant

```text
execution truncation != semantic rejection
execution overflow   != domain-rule authority
exact token support  != entity identity
candidate evidence   != admitted identity witness
```

Optimisation may change how bounded evidence is found, but not what counts as a
proof.
