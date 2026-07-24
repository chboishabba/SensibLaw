# PNF Admissibility, Resolution, Projection, and Execution

## Status

This document defines SensibLaw's pre-memory semantic lifecycle. It imports the
formal separation established in DASHI without copying DASHI's cognition,
memory, learning, NASHI, or attractor layers into the deterministic compiler.

The governing invariant is:

```text
reduction != admissibility != resolution != projection != execution
```

Each stage has a separate content-addressed receipt and authority ceiling.

## Product boundary

SensibLaw remains a deterministic compiler for one declared source and context
snapshot. Its output is:

```text
resolved PNF
+ Legal / Timeline / Retrieval IR projections
+ residual and projection demands
+ explicit execution or refusal receipts
```

It does not update valuation, salience, confidence, trust, behavioural policy,
or any other memory state.

## Pipeline

```text
source
-> parser observations
-> immutable FactorProposal candidates
-> CandidateAssessment
-> AdmissibilityReceipt
-> fibrewise deterministic ProposalReduction
-> ResolutionReceipt
-> declared DomainIRProjectionContract
-> DomainIRProjection or ProjectionDemand
-> applicability gate
-> IRExecutionReceipt
```

The deterministic reducer answers:

> What is the canonical summary of this fibre?

The semantic resolver answers:

> Which admitted interpretation, if any, may this consumer use?

Those are intentionally different questions.

## Candidate assessment

`CandidateAssessment` preserves the existing five-way fibre semantics:

```text
satisfied
violated
both
undetermined
inapplicable
```

Its inputs include proposal evidence, provenance, derivation polarity,
constraints, residuals, required coverage, and observed coverage.

`both` remains first-class. Positive support and contradiction are not collapsed
into an arbitrary winner.

## Admissibility

`AdmissibilityReceipt` returns:

```text
admitted
rejected
blocked
```

A positively invalid candidate is rejected. An underdetermined candidate is
blocked, retained, and exposed as an unresolved alternative; it is not silently
rejected and cannot become an operational interpretation.

Named invalidation grounds include:

```text
missing_span
incompatible_role
impossible_temporal_scope
incompatible_entity_type
wrong_jurisdiction
excess_authority
failed_typed_meet
invalid_translation_transport
constraint_violation
```

Admissibility never promotes identity, applicability, legal conclusion, or
world truth.

## Resolution

`ResolutionReceipt` records one of:

```text
resolved_unique
resolved_preferred
retained_plural
blocked_insufficient_coverage
blocked_conflict
inapplicable
```

A preferred selection is permitted only when the declared deterministic
evidence ordering has a strict winner. Ties remain plural. Every retained
alternative and residual remains inspectable.

## Domain IR projections

SensibLaw currently declares only:

```text
Legal IR
Timeline IR
Retrieval IR
```

Each `DomainIRProjectionContract` states:

```text
accepted factor families
required ontology axes
required statement roles
preserved fields
forgotten fields
authority ceiling
residual policy
```

Every successful projection has both a projection receipt and a loss receipt.
The loss receipt makes the quotient explicit:

```text
same Domain IR != same PNF
```

Two PNF interpretations may project to an equal consumer payload because the
contract deliberately forgot the axis on which they differed.

## Projection back-demands

Missing operational coordinates never receive guessed defaults. Projection may
return typed demands including:

```text
missing_jurisdiction
missing_temporal_force
unresolved_exception_host
unresolved_actor_role
unresolved_conduct_role
missing_authority_source
conflicting_modality
missing_temporal_coordinate
missing_source_binding
conflicting_interpretations
insufficient_semantic_coverage
```

These demands enter the existing `resolution.demand` frontier and may trigger
new evidence, ontology-axis work, source selection, or human review.

## Execution

`IRExecutionReceipt` records:

```text
executed
refused_invalid_ir
refused_missing_applicability
blocked_missing_evidence
superseded
```

Execution requires:

```text
operationally valid Domain IR
+ explicit applicability witness
+ all declared execution evidence
```

Semantic similarity, a typed meet, or successful projection is never an
applicability witness. A refusal referencing a missing IR is itself durable and
must not be discarded merely because the requested IR row does not exist.

## PostgreSQL

Migration `023_pnf_semantic_lifecycle.sql` stores:

```text
pnf_candidate_assessment
pnf_admissibility_receipt
pnf_resolution_receipt
pnf_domain_ir_projection_contract
pnf_projection_demand
pnf_projection_loss_receipt
pnf_domain_ir_projection_receipt
pnf_domain_ir
pnf_ir_execution_receipt
```

The complete lifecycle is inserted inside the same immutable document
transaction and measured as `postgres.semantic_lifecycle`.

## Deferred ITIR work

The following are deliberately absent from this compiler contract:

```text
MemoryFibre
valuation / salience / confidence evolution
learning transitions
habituation / reinforcement / extinction
recursive belief
trust formation
memory / expectation / action braid
attractor inference
NASHI decision learning
ASR-lattice memory persistence
```

SensibLaw retains stable source, proposal, assessment, resolution, projection,
and execution references so ITIR can consume them later. SensibLaw does not
mutate previous semantic builds in response to learning.
