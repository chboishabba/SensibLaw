# Unified source adapters and proof fibres

Date: 2026-07-29
Status: planning contract; no runtime authority change

## Authority decision

SensibLaw must retain one semantic compiler flow. Proof-language support must not
create a second parser, PNF builder, compiler, lifecycle, graph authority, or CLI
entry point.

The governing shape is:

```text
source artifact
-> source admission and source-kind resolution
-> one source-adapter contract
-> canonical anchored observation envelope
-> one factor/proposal/constraint carrier
-> one PNF reduction and fixed-point flow
-> one assessment/admission/resolution lifecycle
-> zero or more typed domain projections/fibres
-> external execution/checking adapters
-> one receipt family
```

Variation by file type, source language, external checker, persistence mode,
concurrency, or target output belongs in declarations, strategies, profiles, and
capability gates over that flow.

## Why this fits the current PNF architecture

The current operational and fibred compilers already establish the useful
invariants:

- immutable source observations and proposals;
- branch-preserving typed alternatives;
- explicit factors, constraints, residuals, and closure demands;
- revision-bound fixed-point work;
- fibre materialisation before downstream assessment;
- assessment, admissibility, resolution, projection, and execution as separate
  authority stages;
- projection demands returning to the PNF carrier;
- external execution results remaining evidence or proposals rather than
  automatic truth or promotion.

Proof-language integration should therefore extend the observation and domain-IR
surfaces, not bypass them.

## Required correction to the current media abstraction

`MediaType` is useful for ingestion mechanics but is too coarse to select semantic
compilation. `STRUCTURED` cannot safely mean RDF, Agda, Lean, Rocq, JSON evidence,
or a precompiled ITIR object at once.

Introduce a separate source-language identity:

```text
SourceKind
  natural_language_text
  legal_document
  agda
  lean4
  rocq
  dedukti
  lambdapi
  rdf
  wikibase_slice
  zelph_graph
  itir_compiled
```

`MediaType` continues to describe physical adaptation. `SourceKind` selects the
source observation declaration. Neither selects a different compiler.

The source kind may be obtained from:

1. explicit `--source-kind`;
2. a revisioned extension/MIME resolver;
3. bounded content inspection;
4. otherwise a fail-closed ambiguity diagnostic.

Explicit CLI choice wins, but the receipt records both declared and detected
source kinds and any disagreement. No source adapter may silently reinterpret an
ambiguous file.

## One public CLI flow

Extend only the canonical gateway:

```bash
python -m src.cli compile INPUT \
  [--source-kind agda] \
  [--target lean4] \
  [--projection proof] \
  [--checker lambdapi]
```

The durable command is `compile`. Do not add `compile-agda`, `compile-proof`, or a
second package entry point.

Suggested semantics:

- `INPUT` selects one artifact or directory inventory;
- `--source-kind` overrides deterministic source-kind detection;
- `--target` requests a target fibre/projection, not a different compiler;
- `--projection` requests an admitted output surface;
- `--checker` selects an external validation strategy;
- absence of `--target` still builds the canonical carrier and demands;
- unsupported source/target capabilities emit typed residuals and receipts;
- no target request may alter source observation or base PNF identity.

Directory compilation resolves a source kind per artifact. Mixed directories are
permitted only when every artifact is independently admitted and the corpus
policy permits the resulting adapter set. Directory traversal remains inventory
and scheduling, not semantic authority.

## Source-adapter contract

Add one revisioned interface, conceptually:

```python
class SourceObservationAdapter(Protocol):
    declaration_ref: str
    supported_source_kinds: frozenset[str]

    def observe(
        self,
        artifact: SourceArtifact,
        context: SourceObservationContext,
    ) -> SourceObservationEnvelope: ...
```

The envelope must contain:

```text
artifact identity and content digest
source kind and adapter declaration
canonical source coordinates
anchored observations
relations between observations
source capabilities and omissions
source-local declarations or symbol identities
provenance and toolchain versions
warnings and explicit losses
```

Adapters observe; they do not resolve, promote, target-lower, or execute.

### Natural-language adapter

The existing canonical text, parsed envelope, annotation graph, mention licensing,
and parser-relational projection remain the natural-language implementation of
this contract.

### Agda adapter

The existing agda2lean backend should become the first proof-language adapter. It
contributes elaborated observations such as:

- module and declaration identities;
- source spans;
- binders, terms, universes, declarations, constructors, and dependencies;
- active semantic builtin identities;
- relevance and visibility;
- feature/capability observations;
- source elaboration and toolchain receipts.

Its typed CBOR object may be admitted directly as `SourceKind.agda` evidence or
through a dedicated sidecar invocation of the pinned Agda backend. SensibLaw must
not parse Agda surface syntax itself.

## Shared carrier versus domain algebra

Do not flatten proof terms into natural-language predicates. Reuse the generic
carrier lifecycle while allowing a domain signature on factor and relation kinds.

```text
Generic carrier
  anchor
  observation
  factor
  alternative
  relation
  constraint
  residual
  demand
  evidence
  authority state
  receipt

Natural-language signature
  mention, predicate, argument, eventuality, modality, time, place, claim

Proof signature
  theory, module, declaration, binder, universe, term, inductive, constructor,
  eliminator, clause, recursion, equality, rewrite, builtin, axiom
```

The proof domain should initially project agda2lean declarations and terms into
proof-specific factors without changing the generic `Factor`, `TypedAlternative`,
`FactorConstraint`, residual, and demand lifecycle.

## Fibre placement

A fibre is a typed projection or derivation over durable carrier factors. Proof
fibres should include:

```text
Agda source fibre
proof-theory capability fibre
Dedukti/Lambdapi semantic projection fibre
Lean native-reconstruction fibre
Rocq native-reconstruction fibre
computation-correspondence fibre
axiom/universe-delta fibre
```

The current fibred operational ordering remains authoritative:

```text
base carrier
-> fibre materialisation
-> constraint worklist
-> proposal assessment
-> admissibility
-> resolution
-> domain-IR applicability
-> optional execution
-> projection and receipts
```

A proof target fibre may be materialised only from admitted source observations
and applicable alignments. A checker result may satisfy an obligation, but cannot
rewrite source observations or bypass admission.

## External systems

### Dedukti, Lambdapi, and Logipedia

Treat these as proof-semantic projection, translation, and checking backends.
They should not become a second SensibLaw compiler.

```text
proof factors
-> applicable Dedukti projection
-> external checker/translation
-> validation evidence and target proposals
-> ITIR reconciliation
```

Reuse existing theory encodings and translation paths where available. Persist the
morphism path, computation relation, axiom delta, checker version, and unresolved
boundaries in receipts.

### Zelph

Treat Zelph as an executable graph adapter:

```text
applicable domain-IR projection
-> Zelph graph/rule/query request
-> result proposal and execution receipt
-> assessment and reconciliation
```

Zelph results remain external evidence. They do not become canonical factors
without the normal lifecycle.

## Where agda2lean lives

The agda2lean repository remains a separate toolchain and specialised product,
while exposing an ITIR-compatible proof adapter protocol.

Current components map as follows:

| agda2lean component | Unified-flow role |
| --- | --- |
| Agda backend | source observation adapter implementation |
| elaboration snapshot | Agda source fibre payload |
| typed DAG IR | proof-domain observation/carrier payload |
| `BuiltinId` | protected proof concept identity |
| registry layers | target alignment declarations |
| support classifications | capability and residual declarations |
| checked Lean emitter | Lean target execution/reconstruction adapter |
| diagnostics | obligations and residual evidence |
| conformance corpus | adapter/fibre promotion contract |
| CBOR, hashes, receipts | deterministic interchange and provenance |

Do not move the Agda compiler backend into SensibLaw Python. Define a versioned
boundary and invoke or ingest it as an external source adapter.

## Proposed data contracts

### SourceArtifact

```text
artifact_ref
content_sha256
path or content handle
media_type
explicit_source_kind?
detected_source_kind?
source_kind_evidence
```

### SourceObservationEnvelope

```text
envelope_ref
artifact_ref
source_kind
adapter_declaration_ref
coordinate_system
observations
relations
capabilities
losses
provenance_refs
receipt_ref
```

### DomainSignature

```text
signature_ref
domain_kind
factor_type_declarations
relation_type_declarations
constraint_type_declarations
residual_type_declarations
projection_declarations
```

### ExternalExecutionDeclaration

```text
executor_ref
accepted_projection_kinds
required_capabilities
result_schema
trust/authority effect
version and digest
```

These should be immutable, deterministic, and content addressed.

## Capability gating

Gating belongs at four explicit boundaries:

1. **source admission** — can the selected adapter observe this artifact?
2. **domain reduction** — are the observed constructs covered by declared proof
   factor/relation reductions?
3. **target projection** — can a target fibre realise the required constructs as
   native, derived, encoded, conditional, or unavailable?
4. **external execution** — does a checker/engine accept the projection and what
   authority does its result carry?

A target should never be selected merely from file extension. File type chooses
or suggests the source adapter; target selection is an independent request.

## Implementation tranches

### P0: authority-preserving plan and inventory

- adopt this document as the planning contract;
- inventory all current compiler entry points and source/media adapters;
- identify the callable canonical document compiler target after operational /
  fibred parity work;
- prohibit new proof-specific compiler entry points;
- define expected receipts for adapter selection and source-kind disagreement.

Acceptance:

- no runtime behaviour change;
- no second compiler or CLI path;
- authority documentation points to this plan for proof-language integration.

### P1: source-kind resolver and generic envelope

- add `SourceKind`, `SourceArtifact`, and `SourceObservationEnvelope`;
- wrap the current text/media path as the first adapter;
- implement deterministic extension/MIME resolution with explicit override;
- add `python -m src.cli compile ... --source-kind ...` only through the canonical
  gateway;
- ensure existing text compilation projects into byte-for-byte or semantically
  equivalent downstream artifacts.

Acceptance:

- existing natural-language fixtures retain semantic parity;
- ambiguous source kind fails closed;
- detected/declared source-kind receipts are deterministic;
- no PNF reducer depends directly on a filename extension.

### P2: proof-domain declarations and agda2lean ingestion

- define the proof `DomainSignature`;
- add an adapter for agda2lean canonical CBOR;
- project module, declaration, term, builtin, feature, and dependency observations
  into proof-specific factors and constraints;
- preserve original CBOR hash and agda2lean version context;
- emit residuals for unsupported/unclassified constructs;
- do not yet emit Lean or invoke Dedukti from SensibLaw.

Acceptance:

- the same generic compiler lifecycle processes text and Agda artifacts;
- factor/constraint/demand/lifecycle receipts share schemas;
- proof factors never use natural-language-only semantic assumptions;
- the 19-case agda2lean conformance corpus can be imported deterministically.

### P3: target-fibre applicability and Lean bridge

- represent target capability/alignment declarations as domain-IR applicability
  rules;
- request the existing agda2lean checked Lean emitter through an external
  execution declaration;
- ingest Lean diagnostics and receipts as target-fibre evidence;
- preserve reconstruction boundaries and fail-on-reconstruction policy;
- ensure target output cannot mutate the source carrier.

Acceptance:

- target absence leaves a valid source compilation with residual demands;
- supported Lean projections produce an execution receipt;
- reconstruction and unsupported cases remain explicit;
- native target output is linked to source factors and declarations.

### P4: Dedukti/Lambdapi semantic projection

- add a proof projection declaration for Lambdapi/Dedukti;
- integrate external checking without embedding another kernel;
- compare ITIR projection with Agda2Dedukti on shared fixtures;
- record theory/morphism path, checker identity, axiom delta, and computation
  relation;
- treat Logipedia exports as target proposals/fallbacks rather than canonical
  native reconstructions.

Acceptance:

- checker success and semantic correspondence remain distinct assessments;
- disagreement produces a typed obligation rather than selecting one path;
- external theory translations cannot bypass lifecycle admission.

### P5: Zelph execution adapter and mixed-domain evidence

- reuse the existing external graph bridge and domain-IR execution boundary;
- declare Zelph query/rule capabilities and result schemas;
- allow proof and text factors to request graph evidence through typed demands;
- preserve source/domain scope and prohibit accidental cross-domain identity
  collapse.

Acceptance:

- Zelph execution is optional and revision-pinned;
- result rows remain evidence/proposals;
- no graph result promotes proof validity, legal truth, or entity identity by
  itself.

### P6: consolidation

- collapse operational/fibred/parallel variants into strategies after parity;
- make the source-adapter registry and domain signatures declarative;
- retire proof-of-concept adapters that bypass the generic envelope;
- move durable maintenance scripts under the canonical CLI;
- document one end-to-end flow for every supported source kind.

## Tests and invariants

Required invariants:

- one compiler authority and one public CLI gateway;
- one artifact identity independent of source adapter and target request;
- source observation is immutable after admission;
- file type affects adapter selection only;
- target selection affects only target demands/fibres;
- external execution cannot promote semantic truth;
- all losses and unsupported constructs are explicit;
- identical source, declarations, configuration, and tool versions yield
  identical carrier hashes and receipts;
- text and proof domains share lifecycle contracts without sharing an
  impoverished term algebra;
- mixed-source directories remain deterministic and document scoped;
- failed target realisation does not invalidate a valid source compilation.

## Explicit non-goals

- no universal proof kernel inside SensibLaw;
- no Agda surface parser in Python;
- no second proof-specific PNF implementation;
- no direct Logipedia or Zelph result promotion;
- no filename-to-target coupling;
- no flattening of proof terms into prose predicates;
- no claim that semantic transport automatically yields idiomatic target code;
- no new top-level compiler module before current compiler parity/consolidation.

## Decision

Proceed with proof-language support as a source adapter plus domain signature and
fibres over the one existing semantic lifecycle. Gate source observation by
`SourceKind` and explicit CLI override, and gate target projections by capability
and applicability declarations. Keep agda2lean external but ITIR-compatible;
reuse Dedukti/Logipedia for semantic transport and checking; use Zelph through the
existing external execution boundary.
