# Lean Wikidata certificate bridge

## Purpose

SensibLaw can now ingest theorem-backed results from an external executable Lean
ontology kernel without copying that kernel into the repository or promoting its
output to truth/edit authority.

The immediate producer is the Wikidata Lean 4 work reported by James Michael
DuPont on 2026-08-16 (Aristotle request
`ae06ae06-2580-422a-8fc3-92aeaaca8762`). The reported surface includes
`RequestProject/ClassAlgebra.lean`, executable `unionOk` / `interOk` checkers,
and proof-backed Wikidata class/RDF semantics.

This repository does not currently contain a public checkout of that WIP source.
No Lean code is copied here. The bridge is an import contract for certificates
exported by that project once its source/export surface is available.

## Contract

`src/ontology/lean_wikidata_certificate.py` defines
`sensiblaw.lean_wikidata_certificate.v0_1`.

Each imported certificate records:

- Aristotle/request identity;
- Lean module, theorem and executable checker names;
- source snapshot/fragment identity;
- subject, predicate and object references;
- bounded relation kind;
- source references;
- the executable Boolean result;
- whether that result is covered by a theorem-backed checker contract.

A positive result is admitted as `supported` only when both
`checker_accepted == true` and `theorem_backed == true`.

Every other case is `unresolved`.

In particular:

```text
checker failure != negative ontology fact
missing edge     != contradiction
unbacked result  != proof
```

This is required for open-world ontology diagnostics.

## Cross-ontology comparison

A Lean-backed Wikidata relation can be compared with a separately sourced
external-ontology state:

```text
supported + supported     -> replicated
supported + contradicted  -> conflicting
anything involving unresolved -> unresolved
```

Only explicit opposition creates a
`cross_ontology_explicit_relation_conflict` review issue. Replication is evidence
but not an issue; unresolved comparison is never silently converted to negative
evidence.

This directly supports the Ontology Cleaning Task Force diagnostic idea of
walking mapped external ontologies and checking whether class relationships are
reproduced in Wikidata while preserving the possibility that sources disagree.

## Authority boundary

Every imported receipt explicitly carries:

```text
truth_authority = false
edit_authority  = false
```

The Lean kernel certifies a result relative to its encoded graph/semantics. It
does not thereby become the authority for legal meaning, real-world truth, or
Wikidata edits.

The matching Agda-side certificate semantics live in
`DASHI/Ontology/LeanWikidataCertificateBridge.agda` in `dashi_agda`.

## Worked fixture

`tests/fixtures/wikidata/lean_artist_union_certificate_v0_1.json` records the
reported worked fragment where `artist` is checked as the overlapping union of
`painter` and `sculptor`. It is a regression fixture for the import contract,
not a claim that the identifiers in the stylised fragment are a complete live
Wikidata snapshot.
