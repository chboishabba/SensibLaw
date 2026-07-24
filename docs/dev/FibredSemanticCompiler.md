# Fibred Semantic Compiler

## Status

This document defines the semantic organisation implemented by the SensibLaw
PNF compiler after the streaming fixed-point tranche.

`ITIR-suite` is the suite-level control and handoff surface. `SensibLaw` owns the
substantive deterministic semantic compiler, proposal contract, PNF reduction,
and immutable build evidence. The fibred algebra therefore lives here rather
than in a second suite-level implementation.

## Consolidation rule

The compiler has:

```text
one broad integrated semantic producer
+ one immutable proposal contract
+ one deterministic fibrewise PNF reduction boundary
```

This does **not** mean one process, model, or algorithm. Parser pools, closure
workers, linking indexes, ontology lookups, and learned scorers may execute in
parallel. They implement one versioned semantic producer family and cannot
publish competing authoritative graphs.

Ordinary core proposals identify:

```text
producer_contract = integrated-semantic-producer:v0_1
operation_contract = the typing/linking/composition/closure contract used
execution_metadata.sub_executor_ref = Python, Zelph, parser, index, or model
```

Executor telemetry is deliberately excluded from proposal identity. Two
backends that derive the same semantic proposal therefore receive the same
proposal reference. Their different runtimes and receipts remain auditable.

External learners, LLM suggestions, imported assertions, and third-party
repair systems remain distinguishable with `producer_scope=external`. They use
the same proposal shape and reducer but retain their own producer authority.

## Base coordinates

Let \(\mathcal C\) be the base category of semantic coordinates. An implemented
coordinate records:

```text
document
scope
source spans
statement role
factor family
coordinate kind
```

Coordinate kinds are:

```text
object       a semantic object or question
morphism     a candidate relation such as scope or attachment
obligation   a validation, coverage, or ontology-axis demand
external     a coordinate in an external knowledge base
```

Statement role is part of the coordinate. A property in a main statement and
the same property in a qualifier do not occupy the same fibre merely because
they share a surface predicate and span neighbourhood.

## Fibres

The total semantic evidence space projects to the base:

\[
\pi : \mathcal E \to \mathcal C.
\]

For a coordinate \(c\), its fibre is:

\[
\mathcal E_c = \pi^{-1}(c).
\]

A fibre may contain:

```text
observations
hypotheses
composed candidates
constraint findings
logical consequences
enrichment evidence
residuals
review evidence
```

Every element is immutable and content-addressed. It retains its producer,
operation, sources, dependencies, transports, ontology axes, assumptions,
coverage requirements, support state, optional score, and candidate payload.

The fibre ledger joins by set union over content identities. Its merge is
associative, commutative, and idempotent.

## Observation sections

spaCy is an observation adapter rather than a semantic authority. It emits
source-grounded token, lemma, part-of-speech, morphology, dependency, and
sentence-boundary records.

Each parser observation names an observation coordinate and populates its
observation fibre. Different parser implementations can provide different
sections over the same canonical text coordinate without changing the semantic
base.

Parser output remains fallible evidence:

```text
parser observation != semantic assertion
```

## Typing as lifting

Semantic typing lifts observation elements into hypothesis fibres:

\[
\operatorname{Lift}_{type}(o) \subseteq \mathcal H_c.
\]

One observation may support several type candidates. The multiplicity is
preserved rather than collapsed before constraints or wider context can act.

Typing operations use the integrated proposal contract with
`fibre_kind=hypothesis` and retain their own operation declaration.

## Linking as controlled transport

Entity and concept linking relate local text coordinates to external knowledge
coordinates. A link is represented as a `SemanticTransport`, not as an
unqualified rewrite.

A transport declares:

```text
source and target coordinates
transport type
strength
evidence
ontology axes
allowed operations
residuals
```

Transport strengths include discoverable, candidate, close, exact, and
identity. A discoverable relation such as `rdfs:seeAlso` may permit inspection
or enrichment but is forbidden from permitting unrestricted substitution.
Every transport record keeps `identity_closed=false` and
`semantic_state_promoted=false`.

This allows selected external evidence to be reindexed into a local fibre
without collapsing the local and external coordinates.

## Scope and attachment as base morphisms

Scope and attachment proposals are candidate morphisms in the base. The edge
itself has a fibre containing syntax, containment, typing compatibility,
competing hosts, learned scores, rule support, and coverage evidence.

A semantic edge is therefore not merely present or absent. It is a coordinate
with a provenance-bearing fibre of candidate derivations.

## Composition as compatible fibre product

Operator composition constructs higher-order coordinates from diagrams of
compatible lower-order elements. For a modal, eventuality, negation, and their
scope candidates, the composed fibre is drawn from a compatible subset of the
corresponding product:

\[
\mathcal E_k \subseteq
\mathcal E_m \times \mathcal E_e \times \mathcal E_n
\times \mathcal E_{m\to e} \times \mathcal E_{n\to e}.
\]

This makes the optimisation rule precise:

```text
reduce cheap duplicates and impossible candidates inside input fibres
before taking expensive compositional fibre products
```

The streaming operator adapter now emits composition fibre proposals at an
explicit sentence coordinate and records coverage requirements and assumptions.

## Constraints and validation fibres

Constraints inspect elements and transports associated with one or more
coordinates. They can reject impossible combinations, preserve alternatives,
introduce residuals, or create new validation and ontology-axis obligations.

Validation is five-way:

```text
satisfied
violated
both
undetermined
inapplicable
```

The outcome is computed from supporting, contradicting, and unresolved fibre
elements plus applicability and coverage. Absence of a contradiction does not
become satisfaction, and incomplete ontology traversal does not become a
violation.

## Ontology subfibrations and domain-specific pressure

Wikidata is not treated as one complete universal type lattice. Named ontology
axes are first-class versioned subfibrations. Examples may include
bibliographic, legal, biological, event, media, or BFO continuant/occurrent
axes.

A coordinate can have a rich fibre on one axis and an empty or unresolved fibre
on another. A domain constraint can create an `AxisObligation` requesting
classification evidence along the required axis.

An axis result records its current state and frontier. Resource exhaustion is
not closure, and every axis obligation keeps `truth_closed=false`.

## Closure

Logical closure monotonically extends fibres:

\[
\mathcal E_c^{n+1} = \mathcal E_c^n \sqcup \Delta\mathcal E_c.
\]

Python and Zelph implement the same internal `ClosureExecutor` boundary. They
receive immutable revision-bound jobs and return proposal receipts. Neither
backend owns semantic state or materialises a graph.

For ordinary closure rules, decoded results are normalised under the integrated
producer family. Backend identity remains in sub-executor and solver receipts,
not in proposal identity. Exact proposal and reduction parity is therefore a
meaningful backend comparison.

Structural document closure and ontological closure remain separate operation
contracts, rule revisions, provenance, cost centres, and authority contexts,
even though both populate the same fibred state.

## Learned and LLM components

A learned model contributes candidate elements or an ordering within a fibre.
For example, a country predictor can contribute scored link hypotheses, and an
attachment model can contribute scored morphisms.

A constrained lattice model may guarantee monotone or shape-constrained scoring
behaviour. It still does not materialise the canonical factor. An LLM likewise
may contribute external candidate derivations but cannot bypass the reducer.

If a learned capability becomes stable, broad, and core, it can be absorbed as
an internal capability of the integrated producer while retaining its model
revision and execution receipt.

## Residuals and boundary data

Residuals are not discarded failures. They identify incomplete, conflicted, or
externally dependent fibres. Examples include unresolved typing, competing
attachments, unopened ontology axes, incomplete coverage, or unresolved
identity candidates.

A `FibreBoundaryObligation` exports the unresolved frontier from a local region.
Regional and document coordinators route only these boundaries rather than
recomputing every local fibre.

A document fixed point requires no runnable local boundary obligation. External
residuals may remain explicit.

## Deterministic fibrewise reduction

For each coordinate \(c\), the reducer computes a canonical summary:

\[
\rho_c(\mathcal E_c) = (F_c, A_c, R_c, D_c),
\]

where:

```text
F_c compatible factor representatives
A_c retained alternatives
R_c residual obligations
D_c derivation and provenance evidence
```

The implementation groups by:

```text
semantic coordinate
fibre kind
factor type
structural signature
```

Only proposals within the same fibre compete. Similar proposals at different
statement roles or semantic coordinates remain separate. Incompatible contents
inside one fibre remain explicit alternatives with a conflict residual.

The global PNF graph is a deterministic materialised view over these fibrewise
summaries. No parser, Python rule, Zelph rule, learner, ontology linker, or LLM
publishes an independent authoritative graph.

## Active execution flow

```text
canonical text
→ parser observation fibres
→ atomic typing/linking/role hypotheses
→ early fibre reduction
→ scope and attachment morphisms
→ compatible composition fibres
→ compositional reduction
→ affected constraints and axis obligations
→ Python/Zelph consequence extensions
→ demand-driven external enrichment
→ affected fibre reductions
→ residual boundary routing
→ document-local fixed point
→ refined PNF
→ Legal IR / PostgreSQL / SPARQL / MCP / LLM projections
```

This is iterative and delta-driven. A changed coordinate schedules only its
dependent fibres and constraints.

## Persistence

Migration `021_semantic_fibres.sql` extends proposal persistence and adds:

```text
semantic_coordinate
semantic_fibre_element
semantic_fibre_derivation
semantic_transport
semantic_ontology_axis
semantic_axis_obligation
semantic_fibre_boundary_obligation
semantic_fibre_summary
integrated_semantic_producer_receipt
```

The persistence layer derives the fibred view from the ordinary streaming
ledger and stores it in the same document transaction. Database checks prohibit
identity promotion, legal-truth closure, or transport-driven semantic promotion.

## Compatibility and migration

Existing proposal constructors remain valid. Core proposals that formerly
identified independent Python, operator, or linking producers are automatically
normalised to the integrated producer family, while the former producer value
becomes `operation_contract`.

Existing executors and keyed owners remain the operational substrate. This
tranche does not introduce a second fibre engine or reducer. It makes the
already-streamed semantic state explicit as fibres and changes deterministic
reduction identity accordingly.

The suite-level integration surface may expose these receipts later through
MCP, but substantive semantic logic remains in SensibLaw.
