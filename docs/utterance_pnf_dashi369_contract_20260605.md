# Utterance PNF / DASHI-369 Contract

Date: 2026-06-05

This note records how ITIR utterance PNF maps to the adjacent DASHI/369
formalism. It is an implementation contract for evidence carriers, not a claim
that parser output is truth.

## Carrier Mapping

DASHI models a balanced ternary carrier over indexed support:

- `0`: no support at that coordinate
- `+1`: support with positive sign
- `-1`: support with negative sign

For utterance PNF, the support coordinates are the predicate/action fibre,
bound typed roles, and explicitly bound non-polar qualifiers.

```text
utterance text
  -> parser/reducer evidence
  -> PredicatePNF(
       predicate/action,
       structural_signature,
       roles,
       qualifiers,
       provenance,
       wrapper=evidence_only
     )
  -> residual meet
```

Polarity is the sign. Subject, action, object, tense, modality, temporal scope,
and similar fields are support coordinates when they are explicitly bound.

## Example

`I walked the dog` and `I did not walk the dog` share support:

```text
domain: utterance_event
signature: utterance_event:walk
subject: i
action: walk
object: dog
```

The first carrier has positive sign. The second has negative sign plus negation
provenance. Their meet is therefore a polarity contradiction over the same
support.

If the second utterance lacked an object, the meet would be partial. If two
carriers bind incompatible non-polar qualifier support, such as different
explicit temporal scopes, the runtime should not collapse them into a polarity
contest without a temporal-family proof that they share the same scope.

## Relation To DASHI / 369

The correspondence is:

- `PredicatePNF` carrier = symbolic receipt-bearing carrier field.
- role/qualifier support = active coordinates.
- polarity = sign over a supported coordinate.
- missing role/qualifier = zero or absent support.
- residual contradiction = defect over a comparable support fibre.
- residual partial = support gap, not negative evidence.
- no typed meet = outside the bounded comparable fibre.

This mirrors the local DASHI materials:

- `../dashi_agda/Kernel/Algebra.agda`: ternary carrier and involution.
- `../dashi_agda/Base369.agda`: triadic/hexadic/nonary truth rotations.
- `/home/c/Documents/20260604_070337_allm_20260604_070337.txt`: balanced
  ternary support/sign factorisation, carrier negation, and defect notes.

The mapping is formal guidance for ITIR carriers. It does not make GPU hashes,
parser fragments, Tree-sitter syntax, or dashiCORE adapter timings into PNF
truth.

## Runtime Boundary

The utterance projector is parser-first and evidence-only:

- spaCy/dependency morphology is used when available.
- deterministic fallback may preserve structural support when parser metadata
  is unavailable, but it must not invent domain truth.
- regex and suffix rules are not semantic authority.
- every emitted carrier must keep provenance spans or source receipts.
- downstream promotion remains governed by the residual/admissibility layer.

Conversation VM compatibility is maintained by deriving legacy `arguments`
from formal roles while preserving `roles`, `qualifiers`,
`structural_signature`, and `domain` on the atom and PNF payloads.
