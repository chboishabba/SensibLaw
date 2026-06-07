# DASHI Carrier Motif Spine Local Implementation Note

Date: 2026-06-07
Status: local read-only metadata adapter implemented

## Purpose

Record how SensibLaw should consume the DASHI carrier motif spine in the local
non-Agda implementation.

This is a crosswalk for review artifacts and PNF metadata. It is not a theorem
claiming that legal text, parser observations, p-adic geometry, braids, waves,
weaves, knots, or political-system formalisms are identical. The link is a
non-promoting carrier discipline:

```text
raw motif / local doc / formal receipt
  -> bounded carrier vocabulary
  -> observation role vector or PredicatePNF atom
  -> residual comparison
  -> non-promoting review artifact
```

The shared idea is that each motif records how structure, pressure, defect,
memory, orientation, transport, binding, and admissibility are represented
without promotion.

## Local Anchors

The DASHI-side anchors observed for this bridge include:

- 3/6/9, voxel, and supervoxel:
  `Base369.agda`,
  `DASHI/Physics/Closure/LocalDocs369UnificationSupportReceipt.agda`,
  `Ontology/DNA/SupervoxelAdmissibility.agda`
- carry, dialectic, and braid:
  `DASHI/Reasoning/CarryMemorySubvoxelReceipt.agda`,
  `DASHI/Reasoning/DialecticalDepthAccumulationReceipt.agda`,
  `DASHI/Reasoning/UnifiedCarryBraidReceipt.agda`
- fascistic and antifascist operators:
  `FascisticSystem.agda`,
  `AntiFascistSystem.agda`,
  `FascisticContractionBridge.agda`
- Bruhat-Tits, p-adic, and braid lanes:
  `DASHI/Physics/Closure/BruhatTitsBraidKPReductionReceipt.agda`,
  `DASHI/Physics/Closure/CarrierBraidStructureReceipt.agda`,
  `DASHI/Physics/Closure/G3P2AdicNormMetricSurface.agda`
- wave, adelic, and transport lanes:
  `DASHI/Physics/Closure/AdelicSobolevWaveObservableTransportGeometryTheorem.agda`
  and its `Wave*` / `CanonicalWave*` consumers
- weave, knot, and fabric lanes:
  `DASHI/Culture/KnotWeaveTopologyCultureBridge.agda`,
  `DASHI/Physics/Closure/CarrierWeaveDefectOriginRemark.agda`

SensibLaw should treat these as local formal-context references and source
motif labels. They do not grant legal authority, semantic equivalence, or
Wikidata edit authority.

## Motif Crosswalk

The local implementation should start with a closed string vocabulary equivalent
to this Agda-facing shape:

```text
motif369
motifCarry
motifDialectic
motifBraid
motifBTTree
motifPAdic
motifSupervoxel
motifFascisticContraction
motifAntifascistInvertibility
motifWaveTransport
motifWeave
motifKnot
```

Local meanings:

- `motif369`: local ternary support, signed state, 3/6/9 evaluator discipline.
- `motifCarry`: carry memory and state propagation.
- `motifDialectic`: inclusion of counter-position, depth, and evaluator state.
- `motifBraid`: ordered tension / crossing bookkeeping, not automatic
  Yang-Baxter authority.
- `motifBTTree`: p-adic lane geometry and branching carrier.
- `motifPAdic`: valuation / norm lane support.
- `motifSupervoxel`: next-depth aggregate over local voxel state.
- `motifFascisticContraction`: entropy-decreasing contraction into a fixed
  attractor.
- `motifAntifascistInvertibility`: invertible or non-collapsing operator
  discipline.
- `motifWaveTransport`: Archimedean or adelic transport surface.
- `motifWeave`: warp depth, weft prime lane, and projection-defect binding.
- `motifKnot`: local binding and memory carrier.

`Sweetgrass` should remain a narrative or canonical thread label unless a
dedicated receipt later makes it a first-class motif.

## Carrier Roles

The local implementation should map motifs into a small role vocabulary:

```text
localState
orientation
memory
defect
pressure
admissibility
transport
binding
nonPromotionBoundary
```

These roles are not legal roles like subject/action/object. They are motif
metadata roles that can annotate a PNF atom, role-vector observation, or review
receipt.

Recommended local JSON shape:

```json
{
  "schema": "sl.dashi_carrier_motif_spine.v0_1",
  "motif": "motifBraid",
  "roles": ["orientation", "pressure", "defect", "nonPromotionBoundary"],
  "source_surface": {
    "kind": "dashi_formal_receipt",
    "path": "../dashi_agda/DASHI/Physics/Closure/CarrierBraidStructureReceipt.agda"
  },
  "projection_target": "modifier_diagnostic",
  "authority_boundary": {
    "non_authoritative": true,
    "promotion_authority": false,
    "legal_authority": false,
    "wikidata_live_edit_authority": false
  }
}
```

## Projection Targets

The motif spine should reuse the parser-observation projection boundary planned
for the PNF role-vector algebra:

```text
predicateTarget
subjectTarget
actionTarget
objectTarget
qualifierTarget
modifierDiagnosticTarget
provenanceTarget
droppedTarget
```

Most carrier motifs should project to `modifierDiagnosticTarget` or
`provenanceTarget`. They should project to predicate or role targets only when
the source lane has a dedicated bounded adapter that emits a concrete
`PredicatePNF` predicate with role values.

Default rule:

```text
CarrierMotif -> CarrierRole -> modifierDiagnosticTarget
```

Allowed special cases:

- `motifFascisticContraction` may support a review predicate about contraction
  pressure when the source explicitly observes collapse / forced-attractor
  behavior.
- `motifAntifascistInvertibility` may support a review predicate about
  non-collapsing operator discipline when the source explicitly observes
  reversible / plurality-preserving behavior.
- `motifWaveTransport` may support a transport predicate only inside a bounded
  physics or formal-receipt lane.
- `motifWeave` and `motifKnot` may support binding / memory predicates only
  where a source receipt identifies the local binding.

All special cases still remain evidence-only.

## PNF Attachment

When attached to a `PredicatePNF`, the motif spine should live under
`modifiers` or `latent_grounding`, not as a role value unless a downstream
adapter has explicitly defined that role.

Example:

```json
{
  "predicate": "observes_projection_pressure",
  "structural_signature": "carrier_motif:projection_pressure",
  "roles": {
    "source": {"value": "local-doc:example", "entity_type": "source_surface"},
    "phenomenon": {"value": "contraction", "entity_type": "carrier_observation"}
  },
  "qualifiers": {"polarity": "positive"},
  "wrapper": {"status": "carrier_motif_review", "evidence_only": true},
  "modifiers": {
    "dashi_carrier_motif_spine": {
      "schema": "sl.dashi_carrier_motif_spine.v0_1",
      "motif": "motifFascisticContraction",
      "roles": ["pressure", "defect", "nonPromotionBoundary"],
      "projection_target": "modifier_diagnostic"
    }
  },
  "provenance": ["../dashi_agda/FascisticContractionBridge.agda"],
  "domain": "carrier_motif_review"
}
```

This says that the source observation uses a DASHI-like carrier discipline. It
does not say the legal or parser source is literally a braid, wave, p-adic
object, or political theorem.

## Interaction With Legal / Parser PNF

For legal text and spaCy-derived observations, the motif spine should be a
secondary annotation:

```text
legal/parser/source observation
  -> typed observation classification
  -> role vector / PredicatePNF
  -> optional carrier motif modifier
  -> residual meet
  -> review artifact
```

The motif modifier must not change:

- structural signature comparability;
- role-value equality;
- missing-role partiality;
- polarity contradiction;
- wrapper evidence-only status;
- Wikidata truth / edit authority flags.

If a motif annotation is absent, residual comparison should behave exactly as
it does today.

## Required Local Invariants

The implementation should eventually pin tests for these invariants:

- motif annotations are optional and cannot make two PNF atoms comparable;
- motif annotations cannot turn `partial` into `exact`;
- motif annotations cannot suppress `contradiction`;
- motif annotations cannot set `wrapper.evidence_only = false`;
- motif annotations cannot set legal authority or Wikidata live edit authority;
- unknown motif labels are held as diagnostics or rejected by schema validation;
- Sweetgrass remains a thread label until a dedicated receipt exists;
- parser observations and legal extraction continue to use role vectors and
  PNF slots as their primary comparison carrier.

## Local Implementation

The local implementation point is:

```text
SensibLaw/src/text/dashi_carrier_motif_spine.py
```

Implemented contents:

- `CarrierMotif` enum;
- `CarrierRole` enum;
- `ProjectionTarget` enum aligned with the PNF role-vector lane;
- `CarrierMotifAnnotation` dataclass;
- `coerce_carrier_motif_annotation(...)`;
- `attach_carrier_motif_modifier(atom, annotation)`;
- schema validation for `sl.dashi_carrier_motif_spine.v0_1`.

Regression coverage is in:

```text
SensibLaw/tests/test_dashi_carrier_motif_spine.py
```

The implementation does not run live DASHI proofs, infer motif identity from
raw text, or promote motif annotations into legal truth. It is a read-only
metadata adapter with fixture-style tests.
