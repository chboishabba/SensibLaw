# James Michael DuPont / Aristotle Wikidata Lean source snapshot

Source supplied directly by the user as `ae06ae06-2580-422a-8fc3-92aeaaca8762-aristotle.tar.gz` on 2026-08-16.

Aristotle request: `ae06ae06-2580-422a-8fc3-92aeaaca8762`.

The archive contains a full Lean 4 project under `RequestProject/` (36+ modules in the status report) plus Lake configuration. This directory vendors the theorem surfaces consumed directly by SensibLaw. The first imported source is `RequestProject/ClassAlgebra.lean`.

Exact source SHA-256:

- `RequestProject/ClassAlgebra.lean`: `6ee3b2371498d67c159fe97389c9ca1e06144ad530e17554cb3f87968c9f899a`
- `RequestProject/Rdf.lean`: `11a4d3fc6b152a022016d7c8639b89805d45352c9e08c16ec2a8172a2610f3cf`

The source project README asks that Aristotle be cited by tagging `@Aristotle-Harmonic` on GitHub PRs/issues or by using:

`Co-authored-by: Aristotle (Harmonic) <aristotle-harmonic@harmonic.fun>`

The source archive does not contain a license file. The vendored snapshot is therefore provenance material for this integration, not a claim of relicensing.

The exact checker/theorem pairs used by the current bridge are:

- `Wikidata.KB.unionOk` → `Wikidata.KB.isUnion_of_unionOk`
- `Wikidata.KB.interOk` → `Wikidata.KB.isIntersection_of_interOk`

The RDF source additionally supplies `Wikidata.Rdf.entails_sound`, `entails_sub_iff`, `entails_inst_iff`, and `entails_iff_isSubclassOf`; its source hash is pinned above even before the complete dependency closure is vendored.
