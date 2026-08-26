# Delta-native dream-flow sprint — 2026-08-26

Status: active planning and acceptance contract for PR #485.

Parent runtime authority and style documents:

- [Repository README](../../README.md)
- [ITIR versus SensibLaw invariants](../itir_vs_sl.md)
- [Implementation style guide](../implementation_style_guide.md)
- [Runtime authority surfaces](../authority_surfaces.md)

Architecture view:

- [Delta-native C4 / PlantUML view](../architecture/dream_flow_delta_native_c4.puml)

Formal proof owner:

- `DASHI.Cognition.PNF.DreamFlowExecutionEverything`
- `DASHI.Cognition.PNF.DreamFlowSprintConstitutionExact`

## Sprint outcome

The sprint is successful only if the existing single semantic compiler authority can execute a representative strict-numeric tranche through the delta-native strategy with exact semantic authority, materially lower avoidable work, and an explicit path to near-spaCy post-parser wall time.

This is not a request to add another compiler. The delta-native path is an execution strategy under the existing authority.

## Formal model

The sprint model is intentionally the same in Agda and Python.

| Symbol | Meaning | Sprint value |
| --- | --- | --- |
| O | Organization | ITIR / SensibLaw operating context and accountable authority boundary |
| R | Requirement / RFP | spaCy → packed fibre-local PNF delta flow → fused PostgreSQL authority, preserving the existing semantic compiler contract |
| C | Code | the candidate execution strategy and its exact adapters, not a new compiler authority |
| S | State | current semantic authority plus measured execution/work state for the frozen workload |
| L | Lattice | PNF/fibre hierarchy, residual lattice, natural restriction/projection maps and consumer-indexed authority surfaces |
| P | Proposal | replace a measured PG-synchronous/local reconstruction step with an authority-exact delta-native realization |
| G | Governance | single-authority, provenance, security, privacy, AI-risk, accessibility, release/change and fail-closed controls |
| F | Gap function | weighted count/vector of unclosed acceptance obligations between the current state and the accepted dream-flow state |

F is not wall time alone. A faster result can still have a non-zero formal gap.

## Constraints

The following are hard constraints, not optimization preferences.

1. One semantic compiler authority. Execution/storage changes are strategies, never a second compiler.
2. PostgreSQL remains durable authority until an explicitly proved replacement exists; local buffers and sparse engines are rebuildable execution carriers.
3. spaCy is an observation producer, not semantic authority.
4. No token/span/provenance loss. Canonical text remains referenced rather than duplicated.
5. Ambiguity and residuals remain explicit. Missing information is not negative evidence.
6. No engine receives privilege by name. PostgreSQL, NumPy, packed native code, custom worklists, Zelph and Datalog must preserve authority and win measured work for the kernel geometry they claim.
7. No per-event database round trip is presumed necessary. Global authority access must be batched or indexed unless a measured semantic need proves otherwise.
8. No accumulated-state hierarchy rescan is presumed necessary. Parent progression should consume exact transported deltas/summaries.
9. No broad demand × candidate materialization is presumed necessary. Candidate exposure must factor through the relevant fibre/index whenever exactness can be proved.
10. No production promotion from one historical trace when the semantic relation is nondeterministic or underspecified.
11. Performance instrumentation must not itself become normal compiler work.
12. No external provider or network engine becomes truth or edit authority.

## Invariants

These must hold before and after every accepted proposal.

- Canonical parser/token coordinates are preserved exactly.
- Semantic identity, database authority identity, fibre-local execution address and transient solver-path address remain distinct.
- Dependency heads remain sentence/fibre valid; cross-fibre heads fail closed or produce an explicit boundary obligation.
- Parser observations, PNF alternatives, promoted authority and residuals remain distinct states.
- Delta application preserves the same observable semantic authority as the reference specification.
- Restriction/projection commutes with delta application at every hierarchy level used by the strategy.
- Closed child fibres are not reopened unless the retained summary/residual is insufficient for the active consumer.
- PostgreSQL publication is observationally equivalent to applying the fused semantic delta to authority.
- Provenance and source identity survive packing, caching, batching, replay and publication.
- Security/privacy controls never require semantic weakening to gain performance.
- Human-facing review surfaces remain inspectable and non-inventive.

## Preconditions for a replacement proposal

A kernel replacement may enter implementation only when all of the following are true.

1. The kernel is measured on the same frozen workload/configuration as its reference.
2. The semantic authority/consumer observation to preserve is named before timing is considered.
3. The kernel geometry is classified as local bounded fibre, global indexed exposure, or sparse delta closure.
4. The relevant formal theorem surface exists or the missing theorem is the explicit first deliverable.
5. Input/output carriers are exact and bounded enough to implement without hidden corpus rescans.
6. Rollback is trivial because the candidate is an execution strategy, not an irreversible authority rewrite.
7. Data-access scope, sensitive-data handling and external I/O are declared before execution.

## Postconditions for a completed proposal

A completed proposal must provide all of the following.

- Exact semantic/consumer authority equivalence or an explicit fail-closed unresolved result.
- The same invariants after execution as before execution.
- No new public compiler/API authority.
- A measured work receipt with at least wall time, CPU time, boundary crossings, bytes read/written and kernel-specific work units.
- A gap score no larger than before the proposal.
- A regression that fails if the replacement silently reintroduces global IDs into a local fibre, a per-event DB crossing, accumulated-state rescan, or semantic trace-for-specification substitution.
- A short rollback/change record suitable for normal change enablement.

## Gap function

The operational F should be retained as a vector and optionally scalarized for prioritization. The vector is authoritative because different defects are not interchangeable.

The current dimensions are:

| Gap axis | Zero condition |
| --- | --- |
| semantic | candidate authority equals the declared semantic/consumer authority on the frozen workload |
| delta-native | first parser observation enters the same delta algebra as every later observation; no privileged bootstrap state build |
| local-address | hot token/head/branch navigation uses fibre-local coordinates where global identity is unnecessary |
| hierarchy | parent advancement consumes transported deltas/summaries without ordinary child-state reconstruction |
| database-boundary | local deterministic algebra executes without microscopic PostgreSQL RPC; durable/global work crosses in fused batches |
| sparse-closure | global sparse closure work is proportional to activated/relevant incidences rather than the whole candidate universe |
| storage | packed/local representation round-trips exactly and measured storage/cache behavior is no worse for the target workload |
| engine-placement | every non-default engine has an authority-exact tournament receipt and measured reason to exist |
| learning | reusable same-domain compiled structures reduce or preserve work per token without weakening semantics |
| observability | all claimed work/timing measures are explicit and normal production does not pay unrequested observatory scans |
| governance | authority, provenance, privacy, security, AI-risk, accessibility and change controls are satisfied |
| runtime | post-parser wall time reaches the sprint performance gate |

A proposal that lowers one axis while worsening another is progress only if the governance-approved gap order permits it. Acceptance requires every mandatory axis to be zero.

## Highest-alpha lanes

### Lane A — packed fibre-local parser → PNF delta seam — ACTIVE / P0

Goal: make the first production computation after spaCy the packed fibre-local numeric carrier and local PNF delta emission, before any sentence-close database round trip.

Deliverables:

- exact adapter from spaCy numeric observation to sentence-fibre packed carrier;
- exact local dependency/head addressing;
- direct emission of the first useful PNF semantic delta/residual from that carrier;
- exact comparison against current authority for a representative sentence/document set;
- measured local work and database-boundary crossings.

Acceptance:

- zero semantic mismatch;
- zero cross-fibre-head guessing;
- no rich document semantic graph reconstructed;
- no PostgreSQL round trip required merely to solve a sentence-local deterministic operation;
- candidate local work is no worse than the reference and boundary crossings are strictly lower on at least one representative workload.

### Lane B — hierarchy delta transport and fusion — ACTIVE / P0

Goal: remove sentence → paragraph → message/conversation state reconstruction where existing naturality/summary theorems permit transport of change.

Deliverables:

- concrete runtime delta type(s) corresponding to the formal transport law;
- exact sentence-to-parent transport for the first hierarchy edge;
- fused publication batch over several commuting child deltas;
- instrumentation proving no ordinary child rescan.

Acceptance:

- transported result equals reference parent authority;
- no closed-child rescan in the accepted path unless an explicit insufficiency/reopen receipt exists;
- work scales with emitted/transported deltas rather than accumulated child state.

### Lane C — whole-tranche work attribution and near-spaCy benchmark — ACTIVE / P0

Goal: make the real bottleneck mechanically visible on a representative GPT tranche.

Deliverables:

- explicit spaCy wall/CPU time;
- post-parser wall/CPU time;
- N/E/R/D/U/G/B/H work vector;
- database boundary count and bytes;
- top kernel contribution table;
- cold and warm/same-domain measurements using comparable token-normalized workloads.

Acceptance:

- no inferred parser timing by subtraction;
- every dominant post-parser kernel accounts for a named formal work class;
- no unclassified bucket exceeds 5% of post-parser wall time;
- repeatability sufficient that the median result, not a best run, drives promotion.

Performance gates for this sprint are staged: less than 2.0× spaCy is the first architectural gate; less than 1.5× is a strong sprint result; less than or equal to 1.2× is target acceptance for the optimized post-parser path. The final programme target remains near wall-clock parity rather than an arbitrary microbenchmark win.

### Lane D — engine tournament for sparse/global kernels — ACTIVE, AFTER C IDENTIFIES A KERNEL / P1

Goal: let PostgreSQL, a custom worklist, packed/native code, NumPy where appropriate, Zelph or a Datalog engine compete on an actual measured kernel.

Deliverables:

- reference authority function;
- same frozen workloads for all candidates;
- semantic-equivalence predicate appropriate to deterministic or relational semantics;
- wall/CPU/boundary/bytes receipt;
- operational complexity notes.

Acceptance:

- authority exact on every supplied workload;
- median CPU and boundary work no worse than the reference;
- strict median wall-time win on at least one representative workload;
- engine introduction does not create a second durable authority or synchronization protocol.

Zelph is not a lane by itself. It is a candidate inside this tournament.

### Lane E — storage codec / PG physical layout — ACTIVE MEASUREMENT ONLY / P1

Goal: determine whether fibre-local low-entropy coordinates buy enough storage/cache/read efficiency to justify a physical persistence change.

Deliverables:

- representative distributions for token count, local start offset, token length, head delta, branch count/ordinal, POS/dependency codes and residual state;
- packed payload size, exact codec size and compressed size;
- PostgreSQL table/index size measurements when/if a concrete schema candidate is tested;
- random-access/decode cost.

Acceptance:

- exact round trip;
- no claim based solely on integer magnitude or repetition;
- a persistence migration is proposed only after measured end-to-end storage/read/write benefit outweighs decode and operational complexity.

### Lane F — cross-document compiled-template reuse — ACTIVE FORMAL/MEASUREMENT / P1

Goal: ensure the 5,000th same-domain conversation does less semantic work per token than the first where certified structure is reusable.

Deliverables:

- admissibility predicate for reusable templates;
- authority-exact reuse path;
- hit/miss receipt;
- comparable cold vs warm work-per-token measurements.

Acceptance:

- authority exact;
- no speculative cross-document identity merge;
- reuse work per token no worse than cold compile for comparable workloads;
- at least one recurrent structure demonstrates a strict work reduction before promotion.

## Held lanes

No worker should be assigned to these without a specific new cause.

- Migration-062 wildcard policy changes: HELD. Its nondeterministic/underspecified semantics are isolated and must not drive the whole-tranche architecture.
- New PostgreSQL schema/migration for packed parser tape: HELD until Lane E produces evidence.
- Zelph integration: HELD until Lane C/D identifies a sparse closure kernel and Zelph wins or is required for a concrete experiment.
- Rust/C++/Cython rewrite: HELD until Lane A/C shows Python/local-buffer execution itself is a dominant cost after architectural DB crossings are removed.
- New compiler entrypoint: PROHIBITED by the current authority freeze.
- Broad UI work: HELD; no current performance/authority gap requires it.

## Lane scheduling rule

Keep the broad active lanes above available so work can continue without serial dependence. A lane becomes held only when its next action depends on evidence from another lane or when the expected value is lower than the current P0/P1 work.

Do not create work merely to keep a lane busy. Prefer refreshing the existing context and tests for the same authority surface over introducing a new module or benchmark format.

## Acceptance matrix

The sprint is accepted only when all mandatory gates below are green.

| Gate | Mandatory | Acceptance |
| --- | --- | --- |
| formal | yes | O/R/C/S/L/P/G/F model instantiated; constraints, invariants, preconditions and postconditions named; gap closed |
| semantic | yes | zero consumer-visible authority mismatch on the frozen acceptance corpus, with nondeterministic relations compared by the declared relational observation rather than arbitrary historical trace |
| delta-native | yes | first and later observations use one delta algebra; no privileged initial-state compiler path without separate work proof |
| local execution | yes | sentence/fibre-local deterministic work executes without required per-event PG RPC |
| hierarchy | yes | first production hierarchy edge uses exact delta transport/fusion rather than ordinary child reconstruction |
| work | yes | candidate declared work no worse than reference and no hidden whole-corpus/state rescan |
| DB boundary | yes | fused/batched boundary demonstrated; boundary crossings materially lower than the current PG-synchronous reference |
| runtime | yes | post-parser median wall time no more than 1.2× explicit spaCy median on the acceptance workload; interim gates may be used for sprint continuation but not final acceptance |
| storage | yes | exact fibre-local round trip; no regression in required authority/provenance; any compression claim has measured physical evidence |
| engine | conditional | any newly introduced engine earns keep through the tournament |
| learning | yes | same-domain reuse does not increase comparable work per token; strict win demonstrated for at least one certified reusable structure |
| security/privacy | yes | least privilege, data minimization, bounded external I/O, provenance and audit evidence maintained |
| AI risk | yes | parser/model outputs remain observations; uncertainty/residuals remain explicit; no automatic authority promotion from model output |
| usability/accessibility | yes for operator surfaces touched | operator output uses plain labels, visible status/reason, deterministic navigation/order and no color-only or hidden acceptance state |
| change/release | yes | rollback path, affected authority surface, evidence, risk and acceptance decision recorded |

## Quality, service, risk, security, privacy and human-factors controls

The standards named for this programme are used as engineering control lenses, not as a claim of certification.

- ITIL: the candidate remains a change to one service/authority; change enablement, validation, rollback, incident/problem evidence and release decision are explicit.
- ISO 9001 / Six Sigma: requirements and acceptance are measurable; defects are semantic mismatch, hidden work amplification, unauthorized authority creation, provenance loss and uncontrolled boundary crossings; measure before improve, then control against regression.
- ISO/IEC 42001, ISO 23894 and NIST AI RMF: model/parser output is governed evidence, not authority; risks, uncertainty, human review and promotion boundaries remain explicit and measurable.
- ISO/IEC 27001 and ISO/IEC 27701: least privilege, purpose limitation/data minimization, auditability, retention/rollback and controlled provider/network access apply to every candidate engine and benchmark corpus.
- ISO 9241-110, 9241-161, 9241-210, 9241-306, 24552, 16817, 24505 and 22727: touched operator/review surfaces should remain understandable, predictable, inspectable and accessible; avoid status ambiguity, hidden system state, inaccessible diagrams and jargon-only controls.

These controls should be satisfied with existing evidence where possible. Do not add paperwork or telemetry that does not close a real acceptance gap.

## Definition of done

The sprint is done when the accepted production execution strategy has demonstrably crossed the architectural boundary from “spaCy → PostgreSQL staging/closure → reconstruction/reduction” to “spaCy → packed fibre-local solve/delta transport → fused PostgreSQL authority”, while preserving the same declared semantics and meeting the final runtime, work, governance and recovery gates above.
