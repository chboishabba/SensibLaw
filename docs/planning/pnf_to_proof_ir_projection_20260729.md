# ITIR PNF to Proof IR projection

Date: 2026-07-29  
Status: planning contract; companion to
`unified_source_adapters_and_proof_fibres_20260729.md`; no runtime authority
change

## Purpose

This document refines the proof-language portion of the unified source-adapter
plan. It defines the relationship between the canonical ITIR partial-normal-form
(PNF) carrier and proof-oriented intermediate representations without creating a
second compiler, PNF implementation, lifecycle, graph authority, or CLI entry
point.

The central distinction is:

```text
PNF records what the source may mean and what remains unresolved.
Proof IR records what, under a named theory and explicit assumptions, is
sufficiently coherent to present to a proof checker or target realiser.
```

The proof path is therefore:

```text
source observations
-> one PNF carrier and fixed point
-> formal-role and theory-indexed candidates
-> proof-fibre assessment and admission
-> Proof IR plus typed obligations
-> target-native or logical-framework projections
-> external checking
-> evidence and demands returned to the same lifecycle
```

It is not:

```text
source text -> guessed theorem -> proof assistant
```

and it is not:

```text
proof source -> separate proof-specific PNF compiler
```

## Authority boundary

The existing SensibLaw/ITIR semantic lifecycle remains authoritative:

```text
observation
-> proposal
-> reduction
-> factor/constraint graph
-> fixed point
-> assessment
-> admissibility
-> resolution
-> projection applicability
-> execution/checking
-> receipts
```

Proof support extends that lifecycle with proof-domain declarations and
projection contracts. It does not add a parallel semantic flow.

The three representation levels are distinct:

1. `SourceObservationEnvelope`: what the selected frontend directly observed.
2. `PNFGraph`: branch-preserving semantic possibilities, constraints, residuals,
   demands, evidence, and authority state.
3. `ProofIRModule`: an applicability-backed, theory-indexed formal development
   containing declarations, judgments, definitions, holes, and obligations.

Target-specific Lean, Rocq, Dedukti, Lambdapi, or other IRs are downstream
realisations of `ProofIRModule`, not replacements for PNF.

## Canonical PNF object

For proof projection, treat the durable PNF state as:

\[
P = (F, A, C, R, D, E, \Pi)
\]

where:

- \(F\) is the factor set;
- \(A\) is the family of typed alternatives;
- \(C\) is the constraint set;
- \(R\) is the relation and residual set;
- \(D\) is the unresolved demand set;
- \(E\) is the evidence and derivation set;
- \(\Pi\) is provenance and authority metadata.

PNF remains partial and branch-preserving. It may contain several incompatible
formal interpretations at once. No ambiguity is silently converted into a
logical connective or a target declaration.

A proof-relevant factor may represent:

```text
theory
sort or universe
type
term
predicate
relation
definition
assumption
axiom
theorem claim
lemma claim
witness
constraint
computation rule
recursion scheme
equality notion
rewrite rule
module or namespace
alignment candidate
meta-claim about a proof
informal-only material
```

The presence of one of these factor kinds does not establish that its contents
are true, accepted assumptions, well typed, or proved.

## Proof IR object

An admitted proof module is:

\[
Q = (T, \Sigma, \Gamma, J, \Delta, \Omega, \mathcal{R}, \mathcal{X}, \Pi_Q)
\]

where:

- \(T\) is the selected object theory or explicitly retained theory alternative;
- \(\Sigma\) is the formal signature;
- \(\Gamma\) is the local context and assumptions;
- \(J\) is the set of judgments and theorem targets;
- \(\Delta\) is the set of definitions and declarations;
- \(\Omega\) is the typed proof/formalisation obligation graph;
- \(\mathcal{R}\) is recursion and computation evidence;
- \(\mathcal{X}\) is the extension, universe, and axiom boundary;
- \(\Pi_Q\) is source-to-proof provenance.

A `ProofIRModule` is not necessarily a completed proof. It may be:

```text
kernel-checked
externally checked
proved but not target-native
a theorem statement with typed holes
conditional on explicit axioms
encoded through a theory morphism
a family of competing formalisation candidates
bounded incomplete
unavailable for a requested theory or target
```

## Projection relation

For a proposed theory \(T\), define:

\[
\Phi_T : P \longrightarrow \mathcal{P}(Q_T \times \Omega_T)
\]

The powerset is deliberate. One PNF state may yield zero, one, or several
formalisation candidates. Competing candidates remain separate fibre elements
until the shared lifecycle has evidence sufficient to admit or reject them.

Operationally:

```text
PNF graph
-> formal-role candidate generation
-> theory-profile candidate generation
-> signature synthesis
-> judgment synthesis
-> obligation generation
-> applicability assessment
-> zero or more admitted ProofIRModule values
```

A projection result may contain:

```text
admitted Proof IR
typed unresolved obligations
explicitly unavailable result
projection loss receipt
competing unselected candidates
```

Projection success is not proof success. Proof success is not semantic
correspondence. A target kernel may check a proof of the wrong theorem; that is a
translation failure.

## Six projection stages

### 1. Formal-role recognition

Each eligible PNF factor receives zero or more `FormalRoleCandidate` values:

```text
type
term
predicate
relation
definition
assumption
axiom
theorem
lemma
witness
constraint
computation_rule
meta_claim
informal_only
```

Examples:

```text
“Let G be a group”
  -> type/class declaration candidate plus structure assumptions

“Suppose f is continuous”
  -> local hypothesis candidate

“Then f is bounded”
  -> theorem-target candidate

“By compactness”
  -> proof-strategy/evidence reference, not automatically a proof term
```

Role recognition is candidate generation. It does not promote an observed claim
to an axiom or theorem.

### 2. Theory selection

A formalisation must be indexed by a named theory profile or retain several
theory alternatives.

Candidate profiles may include:

```text
agda_mltt
agda_cubical
lean4
rocq_cic
constructive_dependent_type_theory
classical_simple_type_theory
lambda_pi_modulo
first_order_logic
set_theory
domain_specific_theory
```

Theory selection may itself remain unresolved. The same semantic claim can
require different encodings, axioms, elimination rules, and computation
relations in different theories.

A theory profile declares at least:

```text
sort and universe policy
typing judgments
conversion/computation relation
inductive and elimination policy
recursion/productivity policy
equality families
proof relevance/irrelevance policy
available axioms
supported extension constructs
```

### 3. Signature synthesis

Eligible PNF factors and alignments produce candidate declarations:

```text
sort declarations
constant declarations
inductive blocks
record blocks
constructors
eliminators
definitions
rewrite declarations
module declarations
concept alignments
```

For example, a factor representing the natural numbers may be:

```text
aligned to a protected native concept
derived from an existing target library
encoded as a Peano inductive
retained as an unresolved external concept
unavailable in the requested theory
```

Every candidate declaration retains source factor, alternative, evidence, and
alignment references.

### 4. Judgment synthesis

PNF relations produce candidate theory-indexed judgments.

Examples:

```text
predication(x, P)
  -> Γ ⊢ P x : Prop

universal(x, A, P)
  -> Γ ⊢ Π (x : A), P x

existential(x, A, P)
  -> Γ ⊢ Σ (x : A), P x
  or a theory-specific existential proposition

same(x, y)
  -> Γ ⊢ Eq_e A x y
```

The equality family \(e\) remains explicit. Propositional equality,
heterogeneous equality, path equality, setoid equivalence, quotient equality,
and definitional conversion must not be collapsed by spelling.

Semantic parser ambiguity is not logical disjunction:

```text
candidate A versus candidate B
```

must remain separate proof fibres unless the source itself supports:

```text
A ∨ B
```

### 5. Obligation generation

Every required but unresolved distinction becomes a typed obligation.

Initial obligation kinds include:

```text
formal_role_selection
theory_selection
type_selection
reference_resolution
scope_resolution
quantifier_resolution
equality_kind
signature_alignment
universe_constraint
termination
productivity
constructivity
axiom_acceptance
computation_preservation
dependency_preservation
proof_completion
target_library_alignment
native_reconstruction
external_checker_correspondence
```

A PNF residual maps to a typed hole only when an expected proof-IR type or role is
known. Otherwise it remains a pre-IR formalisation obligation.

Typed hole classes include:

```text
unknown_type
unknown_term
unresolved_referent
missing_definition
missing_proof
missing_computation_law
missing_target_encoding
unsupported_theory_construct
```

No generic `sorry` may erase the distinction.

### 6. Applicability and admission

A candidate \(Q\) is admitted only with an applicability witness:

\[
\mathsf{Applicable}_T(P, Q, w)
\]

Admission means the module is coherent enough to present to a proof checker,
theorem search engine, logical-framework translator, or native target realiser.
It does not mean its theorem targets are proved.

The applicability witness records:

```text
source factors and alternatives consumed
formal-role selections
theory profile
declaration and judgment synthesis rules
constraints satisfied or retained
obligations emitted
material alternatives rejected or left competing
projection losses
axiom and universe delta
required target capabilities
```

## PNF to Proof IR correspondence

| ITIR PNF | Proof IR |
| --- | --- |
| factor | declaration, term, judgment, or formal-role candidate |
| typed alternative | candidate formal encoding |
| constraint | typing condition, premise, side condition, or compatibility rule |
| relation | application, equality, dependency, logical connective, or module edge |
| residual | formalisation obligation or typed hole |
| demand | proof obligation, alignment lookup, theorem search, or external check |
| evidence | proof term, derivation, citation, checker result, or source witness |
| authority state | observed/assumed/axiomatic/derived/checked status |
| fibre element | one theory-indexed formalisation candidate |
| resolution | selected encoding or discharged obligation |
| domain projection | admitted `ProofIRModule` |
| execution result | checker/realiser evidence returned to PNF |

## Proof authority states

Introduce a proof-domain authority algebra that does not replace the generic
authority field but refines it:

```text
observed
candidate_formalisation
assumed
axiomatic
derived
kernel_checked
externally_checked
refuted
unresolved
```

Required separations:

```text
observed claim != assumption
assumption != axiom
axiom != theorem
well-typed statement != proved theorem
kernel-checked proof != semantically corresponding translation
external citation != locally checked proof
```

A paper saying “we prove P” yields an observed attribution and a candidate theorem
statement. It becomes `kernel_checked` only after a named checker validates the
corresponding proof object under a recorded theory and axiom surface.

## Realisation classes

For each source construct \(c\), theory \(T\), and target \(U\), a fibre
realisation is:

```text
native
derived
encoded
conditional
unavailable
```

These statuses are target-relative.

- `native`: realised by a canonical target primitive or library concept.
- `derived`: definable in the target with reviewed evidence of the intended laws.
- `encoded`: represented through an explicit encoding and adequacy claim.
- `conditional`: valid only under an explicit axiom or assumption delta.
- `unavailable`: no reviewed realisation exists.

Each realisation also records a computation relationship:

```text
definitional
propositional
observational
opaque
none
```

Logical preservation and computation preservation are independent axes.

## Formalisation assessment

Each candidate receives a tetralemma-style formalisation assessment:

```text
satisfied
violated
undetermined
inapplicable
```

Examples:

- `satisfied`: required source distinctions and typing constraints are preserved.
- `violated`: a material source assumption, quantifier, dependency, or equality
  distinction was lost or contradicted.
- `undetermined`: a required theory, scope, referent, alignment, or capability is
  unresolved.
- `inapplicable`: the requested property does not apply, such as definitional
  computation preservation for an intentionally opaque theorem.

Formalisation assessment is separate from proof completion:

```text
formalisation = satisfied
proof = unresolved
```

is valid, while:

```text
formalisation = violated
proof = kernel_checked
```

is a translation failure.

## Fixed-point and demand return

Projection is iterative:

\[
P_0 \xrightarrow{\Phi_T} (Q_0, \Omega_0)
\]

Unresolved obligations return as typed PNF demands:

\[
P_{n+1} = \mathsf{refine}(P_n, \Omega_n, E_{n+1})
\]

and projection may run again:

\[
P_{n+1} \xrightarrow{\Phi_T} (Q_{n+1}, \Omega_{n+1})
\]

Stop at:

```text
all required obligations discharged
bounded stable unresolved set
explicitly unavailable result
contradiction or violated formalisation
resource/policy stop with receipt
```

The target projection cannot mutate source observations or silently rewrite the
base PNF identity. New evidence produces immutable factor revisions through the
normal lifecycle.

## Required data contracts

### FormalRoleCandidate

```text
candidate_ref
factor_ref
alternative_ref
formal_role
theory_profile_ref?
evidence_refs
constraint_refs
authority_state
producer_declaration_ref
```

### TheoryProfile

```text
theory_ref
meta_theory_ref?
sort_universe_policy
judgment_declarations
conversion_policy
computation_policy
inductive_elimination_policy
recursion_policy
equality_families
axiom_surface
extension_capabilities
version_and_digest
```

### ProofProjectionCandidate

```text
candidate_ref
pnf_graph_ref
theory_ref
formal_role_candidate_refs
signature_candidate_refs
judgment_candidate_refs
obligation_refs
axiom_delta
universe_delta
computation_requirements
provenance_refs
```

### ProofIRModule

```text
module_ref
pnf_graph_ref
theory_ref
signature
context
declarations
definitions
judgments
theorem_targets
proof_terms
typed_holes
obligation_refs
recursion_computation_evidence
extension_axiom_boundary
applicability_witness_ref
provenance_refs
```

### ProofObligation

```text
obligation_ref
obligation_kind
source_factor_refs
proof_ir_subject_refs
expected_type_or_judgment?
required_evidence
admissible_solver_classes
status
provenance_refs
```

### ProofApplicabilityWitness

```text
witness_ref
projection_candidate_ref
consumed_factor_revisions
selected_alternatives
satisfied_constraints
retained_constraints
rejected_alternatives
projection_losses
required_capabilities
axiom_delta
universe_delta
computation_relation
```

### ProofProjectionReceipt

```text
receipt_ref
source_artifact_ref
source_envelope_ref
pnf_graph_ref
proof_ir_module_ref?
theory_ref
target_ref?
morphism_path
formalisation_assessment
proof_status
realisation_status
computation_relation
axiom_delta
universe_delta
obligation_refs
checker_receipt_refs
loss_receipt_refs
```

All contracts are immutable, deterministic, revisioned, and content addressed.

## Placement of existing agda2lean components

The current agda2lean IR spans several future layers and should be separated by
role rather than discarded.

| Current component | PNF-to-Proof-IR role |
| --- | --- |
| Agda compiler backend | elaborated source observation producer |
| snapshot/CBOR | immutable Agda source-fibre payload |
| canonical names and declarations | source identity and signature observations |
| typed DAG terms | proof observation payload and initial proof-term algebra |
| `BuiltinId` | protected proof concept identity |
| `Feature` | source capability observation and demand trigger |
| `MappingMode` | early target realisation classification |
| `body = Nothing` | reconstruction/formalisation residual |
| support survey | factor/capability proposal producer |
| platform registry | target alignment declaration |
| checked Lean emitter | Lean target realiser |
| correspondence harness | formalisation and target validation evidence |
| receipts | source/projection/target provenance |

The migration boundary should be:

```text
Agda elaboration
-> agda2lean source snapshot
-> proof PNF factors and constraints
-> ProofProjectionCandidate
-> admitted ProofIRModule
-> Lean/Dedukti/Rocq target fibre
```

The existing typed DAG remains useful, but it must not be treated simultaneously
as source observation, canonical PNF, and every target IR.

## External proof systems

### Dedukti, Lambdapi, and Logipedia

These remain external logical-framework and translation substrates:

```text
ProofIRModule
-> applicable λΠ-modulo projection
-> external check or theory translation
-> checker evidence, target proposals, and obligations
-> ITIR reconciliation
```

Reuse their object-theory encodings and translation paths. Do not implement a
second universal proof kernel inside SensibLaw.

Persist:

```text
source theory
target theory
morphism path
checker and version
axiom delta
universe delta
computation relation
translation obligations
```

### Lean and Rocq

Native reconstruction occurs after Proof IR admission:

```text
ProofIRModule
-> target capability assessment
-> target fibre
-> native source or checked target object
-> target diagnostics and correspondence receipt
```

A target may accept a generic encoded proof while native reconstruction remains
unresolved. These are different outcomes.

### Zelph

Zelph may consume applicable graph/rule projections and return proposals or
evidence. It does not establish proof validity unless a declared proof obligation
explicitly accepts the relevant Zelph result class, and even then the authority
effect must be recorded.

## Revised implementation tranches

### P0: authority and terminology

- adopt this document as the normative proof-projection companion;
- retain one compiler and one CLI;
- define the terminology `observation`, `PNF`, `formalisation candidate`,
  `Proof IR`, and `target IR`;
- prohibit treating the current agda2lean IR as all layers at once.

Acceptance:

- documentation uses the three-level distinction consistently;
- no proof-specific PNF compiler or CLI appears;
- no runtime behaviour changes.

### P1: source-kind and observation envelope

Retain P1 from the unified source-adapter plan.

Acceptance additions:

- source observations have no target-realisation status except source capability
  and omission reports;
- an Agda source artifact can be compiled without requesting a target.

### P2: proof PNF domain signature

- define proof factor, relation, constraint, residual, and demand declarations;
- ingest agda2lean CBOR as source observations;
- reduce observations into proof PNF without selecting a target;
- define proof authority-state refinements;
- preserve branch alternatives for equality, theory, recursion, and alignment.

Acceptance:

- deterministic proof PNF hashes;
- no target registry required to build the source PNF;
- unsupported source constructs become typed residuals;
- parser ambiguity is not emitted as logical disjunction.

### P3: PNF-to-Proof-IR candidate synthesis

- implement `FormalRoleCandidate`;
- implement theory-profile declarations;
- implement signature and judgment synthesis declarations;
- generate typed formalisation obligations;
- add formalisation assessments;
- do not invoke target emitters yet.

Acceptance:

- one PNF may produce multiple competing proof candidates;
- candidates preserve source factor and alternative provenance;
- observed claims cannot become axioms or theorems without an authority transition;
- typed holes distinguish missing type, term, proof, alignment, and capability.

### P4: Proof IR admission and Lean target fibre

- implement `ProofIRModule` and applicability witnesses;
- represent Lean capability/alignment declarations downstream of Proof IR;
- invoke the existing checked Lean emitter as an external target realiser;
- compare target elaboration with the admitted source judgment;
- preserve fail-on-reconstruction and axiom-delta policy.

Acceptance:

- an admitted Proof IR can exist without Lean output;
- target failure does not invalidate source PNF or a target-neutral Proof IR;
- kernel success and formalisation correspondence are independently assessed;
- all native/derived/encoded/conditional/unavailable statuses are receipted.

### P5: Dedukti/Lambdapi differential projection

- project admitted Proof IR into the existing logical-framework ecosystem;
- compare with Agda2Dedukti on shared fixtures;
- record theory and morphism paths;
- return checker disagreement as typed obligations;
- retain Logipedia exports as semantic or fallback target fibres rather than
  automatically native reconstructions.

Acceptance:

- independent semantic path exists for shared fixtures;
- checker success cannot bypass Proof IR applicability;
- axiom, universe, and computation deltas are explicit.

### P6: Zelph and mixed-domain evidence

Retain the existing Zelph tranche, but require proof-obligation declarations to
state whether and how a graph result can contribute evidence.

Acceptance additions:

- no Zelph result directly sets `kernel_checked`;
- cross-domain evidence retains source and theory scope.

### P7: consolidation and promotion

- consolidate operational/fibred execution strategies after parity;
- make source adapters, domain signatures, theory profiles, and target
  capabilities declarative;
- add end-to-end promotion cases for natural language to Proof IR and Agda to
  Proof IR to Lean/Dedukti;
- retire proof-of-concept surfaces that bypass the generic envelope or PNF;
- document versioning and migration for agda2lean CBOR and Proof IR schemas.

## Required tests and invariants

### Layer separation

- source observations contain no silently selected target interpretation;
- PNF preserves material alternatives and unresolved distinctions;
- Proof IR requires an applicability witness;
- target IR is downstream of Proof IR admission.

### No silent semantic change

- semantic ambiguity is not logical disjunction;
- observed claims are not assumptions or theorems;
- every introduced axiom is in the axiom delta;
- every material discarded branch has assessment or loss evidence;
- equality and universe distinctions remain explicit.

### Demand conservation

- every required unrepresented distinction produces an obligation or loss;
- failed projection obligations return to PNF;
- target failure does not erase valid source compilation;
- bounded stop conditions are receipted.

### Provenance and determinism

- every Proof IR declaration and judgment traces to source factor revisions;
- identical source, declarations, theory profiles, and versions produce identical
  projection hashes;
- external checker versions and morphism paths are recorded;
- independent projections may disagree without one silently becoming canonical.

### Validation independence

- formalisation assessment and proof status are separate fields;
- a kernel-checked proof of a violated formalisation fails correspondence;
- an unproved but satisfied formalisation remains a valid theorem-engineering
  artifact;
- `inapplicable` is not treated as failure or success.

## Explicit non-goals

- no natural-language claim is promoted directly to a theorem;
- no universal proof kernel is implemented inside SensibLaw;
- no flattening of PNF ambiguity into one proof term;
- no use of target libraries during source observation;
- no generic `sorry` for all residual classes;
- no claim that Dedukti/Logipedia transport is native target reconstruction;
- no second PNF flow for proof languages;
- no coupling between file extension and proof target;
- no target result mutates source observations or PNF identity.

## Decision

Proceed with proof support as a promotion:

\[
\text{PNF}
\rightarrow
\text{formalisation candidates}
\rightarrow
\text{theory-indexed proof fibres}
\rightarrow
\text{admitted Proof IR} + \text{typed obligations}
\]

over the one existing ITIR semantic lifecycle.

PNF is the canonical branch-preserving semantic IR. `ProofIRModule` is an
applicability-backed projection stating what, under a named theory and explicit
assumptions, may lawfully be presented to a proof checker. Lean, Rocq,
Dedukti/Lambdapi, and other target IRs are subsequent fibre realisations.

The concise contract is:

```text
PNF says what the source may mean.
Proof IR says what we are prepared to ask a named proof theory to check.
Target IR says how one selected system will realise that admitted request.
```
