# Cross-ontology contradiction attribution

This lane connects the existing Wikidata `P2738` disjointness diagnostics to a
proof-relevant source/transcription/alignment/target attribution packet.

It deliberately does **not** treat a detected structural anomaly as an immediate
claim that two ontologies contradict one another.

## 1. Full finite-KB disjoint-union semantics

Run:

```bash
python scripts/run_wikidata_disjoint_union_report.py \
  --input tests/fixtures/wikidata/disjointness_p2738_pilot_pack_v1/slice.json \
  --output /tmp/disjoint-union.json
```

`src/ontology/wikidata_disjoint_union.py` evaluates the same three obligations
used by the later JMD/Aristotle `Wikidata.dunOk_iff` theorem surface:

1. every listed `P11260` member is a subclass of the `P2738` holder;
2. every **known** instance of the holder in the bounded KB slice is covered by
   at least one listed member;
3. distinct listed members are pairwise disjoint on the known carrier.

The second point is intentionally finite/open-world.  A passing or failing
bounded slice is not a claim about every possible real-world instance.

The report separates:

- `component_not_subclass_of_union`;
- `union_exhaustivity_failures`;
- `pairwise_disjointness_failures`.

The old `wikidata_disjointness_report/v1` output remains unchanged and is reused
for overlap witnesses and culprit localization.

## 2. Four-layer attribution

`src/ontology/wikidata_contradiction_attribution.py` carries one support square
per layer:

- `source`;
- `transcription`;
- `alignment`;
- `target`.

Each square is `(supports, refutes)`, so the four corners remain distinct:

- `(false,false)` — neither / missing evidence;
- `(true,false)` — support only;
- `(false,true)` — refutation only;
- `(true,true)` — conflict.

Squares merge by coordinatewise OR.  The lossy three-valued presentation is
computed only afterwards; both conflict and ignorance project to `unresolved`,
so the support square is the authoritative diagnostic carrier.

Required-axis resolution is computed separately from pooled evidence.  This
prevents source support from making an end-to-end claim look resolved while a
required transcription/alignment/target axis is still empty.

## 3. Acquisition is not semantic authority

A bounded SensibLaw/WDQS/Zelph report is candidate evidence by default.
`target_evidence_from_disjoint_union_report` returns the `neither` corner unless
`bounded_result_authoritative=True` is supplied for the scoped claim.

The corresponding script flag is deliberately explicit:

```bash
--target-report-authoritative
```

Use it only after acquisition completeness has been established for the relevant
`P2738`, `P11260`, `P279`, and `P31` facts.  A missing fact in a partial slice
must not become an ontology refutation.

## 4. Literal BFO/Wikidata control

The repo pins:

`data/ontology/bfo_wikidata_continuant_occurrent_attribution_v1.json`

Source side:

- **Basic Formal Ontology (BFO 2020)**;
- repository `BFO-ontology/BFO-2020`;
- commit `0900316ea9d330f599bd110f7f6504ed33a87fc8`;
- `BFO_0000002` continuant is a subclass of entity and is `owl:disjointWith`
  `BFO_0000003` occurrent;
- standard context: ISO/IEC 21838-2:2021;
- no DOI is asserted for the source TTL/standard artifact.

Mapped Wikidata identifiers:

- entity `Q35120` -> BFO `0000001`;
- continuant `Q103940464` -> BFO `0000002`;
- occurrent `Q67518978` -> BFO `0000003`.

The current control result is intentionally:

- source: support-only;
- transcription: support-only;
- alignment: neither;
- target: neither;
- required resolution: `unresolved-required-axis`.

That is a useful result.  It says the source disjointness is real and the mapped
identifiers are established, while the stronger disjointness transport has not
been licensed by the explicit instance-transport and target-disjointness
premises required by JMD's `Wikidata.Alignment.disjoint_reflect` theorem.

It does **not** manufacture the claim "BFO contradicts Wikidata" from missing
alignment evidence.

Run the packet directly with:

```bash
python scripts/run_wikidata_cross_ontology_attribution.py \
  --evidence data/ontology/bfo_wikidata_continuant_occurrent_attribution_v1.json
```

## 5. DASHI handoff

The corresponding `dashi_agda` tranche reuses:

- `DASHI.Algebra.DisagreementFourViewBoundary.PolarAssessment`;
- `DASHI.Interop.WikidataDerivationFibreBridge`;
- source/input/alignment theorem receipts already present in the Lean/Wikidata
  bridge;
- the later JMD support-square, class-algebra and alignment theorem surfaces.

The runtime and proof layers therefore share the same non-collapse rule:

> locate a structural candidate at runtime; preserve source/transcription/
> alignment/target evidence separately; pool support/refutation before any
> lossy trit display; and keep missing required axes unresolved.
