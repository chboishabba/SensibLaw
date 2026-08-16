# Lean Wikidata certificate bridge

## Concrete source snapshot

The bridge is now pinned to the Aristotle archive supplied on 2026-08-16 for request
`ae06ae06-2580-422a-8fc3-92aeaaca8762`, attributed to James Michael DuPont. The archive
contains the actual Lean 4 `RequestProject/` development rather than only the earlier
status image.

The source snapshot confirms the exact executable/proof surface used here:

- `Wikidata.KB.unionOk` with soundness theorem `Wikidata.KB.isUnion_of_unionOk`;
- `Wikidata.KB.interOk` with soundness theorem `Wikidata.KB.isIntersection_of_interOk`;
- `Wikidata.Rdf.entails_sound`, `entails_sub_iff`, `entails_inst_iff`, and
  `entails_iff_isSubclassOf` for the RDF/class-hierarchy layer;
- `Wikidata.Diagnostics.errors_eq_nil_iff_valid` and witness-bearing diagnostics in the
  source archive.

`third_party/jmdupont_wikidata_lean/RequestProject/ClassAlgebra.lean` is a verbatim
vendor snapshot of the imported class-algebra source. Its SHA-256 is
`6ee3b2371498d67c159fe97389c9ca1e06144ad530e17554cb3f87968c9f899a`.
`SOURCE_SNAPSHOT.md` also pins the RDF source hash.

The archive contains no license file, so this repository does not claim to relicense the
source. The snapshot is retained with explicit provenance, and commits importing it carry
the Aristotle co-author attribution requested by the archive README.

## Certificate contract

`src/ontology/lean_wikidata_certificate.py` defines
`sensiblaw.lean_wikidata_certificate.v0_1`. `theorem_backed=true` is no longer a free
Boolean assertion: for the imported executable class-algebra lane the module,
checker, theorem, relation kind, and Aristotle request ID must match the pinned source
registry in `lean_wikidata_source_contract.py`.

Thus a packet claiming `unionOk_sound`/`unionOk` is rejected as forged metadata; the
source-faithful pair is:

```text
RequestProject.ClassAlgebra
Wikidata.KB.unionOk
Wikidata.KB.isUnion_of_unionOk
```

The positive projection remains deliberately one-way:

```text
source-backed theorem contract + checker accepted -> supported
failed checker / absent edge / unbacked result     -> unresolved
```

A failed Boolean checker does not mean the negation of the ontology relation.

## Cross-ontology comparison

A Lean-backed relation can then be compared with separately sourced ontology evidence:

```text
supported + supported     -> replicated
supported + contradicted  -> conflicting
anything unresolved       -> unresolved
```

Only explicit opposition creates a `cross_ontology_explicit_relation_conflict` review
issue. This is the operational hook for walking SIO/BFO/other mappings without treating
open-world absence as contradiction.

## Authority boundary

Every receipt keeps `truth_authority=false` and `edit_authority=false`. The Lean theorem
certifies the encoded fragment relative to its formal semantics; it does not promote that
fragment to global real-world, legal, or Wikidata edit authority.

The matching proof-side interpretation remains in
`DASHI/Ontology/LeanWikidataCertificateBridge.agda` in `dashi_agda`.
