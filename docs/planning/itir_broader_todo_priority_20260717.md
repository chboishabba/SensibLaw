# Broader TODO Priority Checkpoint

Date: 2026-07-17
Status: suite-wide sequencing decision

## Read

The shared architecture is now ahead of the lane-specific operational
surfaces. AU and GWB already emit the small `compiler_contract`, and
Wikidata/Nat has the strongest deterministic replay and coverage machinery.
The remaining risk is not another lane carrier rewrite. The shared spine must
now begin one layer earlier than targeting: exhaustive recoverable mention
discovery, typed entity-candidate sets, and a PNF-driven resolution loop must
survive real lane ambiguity before targeting and promotion can be trusted.

Canonical P0 architecture and implementation notes:
`pnf_driven_entity_resolution_spine_20260717.md`.

## Priority order

### P0a — Canonical parser/span substrate

Converge the two section-parser implementations, retain one canonical text and
stable character-coordinate system, derive token/annotation views once per
versioned profile, and make internal structural/entity/PNF records refer to
spans. Preserve existing verbose JSON as a compatibility projection.

Implementation checkpoint: canonical parsing, rule extraction, and structural
node construction now live in `src.ingestion.section_parser`. The historical
`src.section_parser` surface is a compatibility projection that returns
`Provision` trees and simple JSON over those canonical nodes. Remaining P0a
work is shared text/blob span storage, one-pass token/annotation views, and
profile-versioned cache keys.

### P0b — Shared mention and entity-candidate layer

Define the complete recoverable span lattice while instantiating candidates
lazily. Add generic `MentionSpan`, `EntityCandidateSet`, and
`CoreferenceCluster` carriers. Ordinary nouns and labelled phrases may produce
typed candidates; stopwords remain structural evidence unless they participate
in a larger meaningful span.

The coverage lane must also type meaningful relations, quantities, roles, and
linguistic eventualities from the shared annotation/reducer substrate. PNF
residuals prioritize evaluation depth; they do not define candidate-world
admission.

Implementation checkpoint: `src.policy.entity_resolution` now provides the
candidate-only, deterministic carrier for those three records. It rejects
cross-document coreference and non-candidate authority. P0b.1 additionally
implements a backend-free baseline licensing receipt over public
parser/reducer output: non-structural lexical spans, numeric spans, maximal
name-shaped phrases, and adapter-annotated eventualities are materialized;
the full token-span lattice and structural suppression remain explicit.
Alias/grammar expansion, generated-mention clustering, and candidate retrieval
remain pending.

### P0c — PNF-driven resolution loop

`PartialPNF`, independent closure pressure, and backend-neutral
`ResolutionDemand` are now implemented. Before the scheduler, add typed
resolution subjects for entity, event type, event occurrence, event artifact,
document-local cluster, and property/relation targets. Event artifacts must
preserve occurrence, observation, cluster, forecast, report, alert, and
rolling-state roles. Then derive semantic demand-equivalence keys from subject
kind/role, local types, PNF slot role, typed constraints, evidence facets, and
document scope—not surface text.

After those contracts, add the registry-neutral broker that serves local/cache
evidence first and schedules remaining work through deduplicated, rate-limited
microbatches while local compilation continues. Then add
`ResolutionAssessment` and incremental `PNFRefinement`.

Implementation checkpoint: typed resolution-subject declarations and semantic
demand-equivalence receipts are now implemented in the shared carrier. Event
occurrence and event-artifact roles are validated separately; equivalent
demands retain every member and are only marked coalescible. No scheduler,
backend, cache mutation, evidence retrieval, or identity decision exists yet.

Add shared eventuality/observation/external-identity carriers and typed event
meets. Preserve event occurrence, observation, cluster, forecast, report,
alert, and rolling-state roles. Wikidata and WorldMonitor remain optional
snapshot backends; neither owns event typing or authority.

### P0d — Targeting and promotion

Finish the bounded evidence-bundle -> promoted-outcome contract and make the
shared targeting kernel consume resolved or explicitly ambiguous PNF/entity
alternatives above `review_text` and `review_candidate`. Keep
`review_alignment` held until the readiness oracle can promote it without
lane-specific caveats.

Acceptance requires at least two tranches to consume the same mention,
resolution, PNF, and weak-targeting surfaces while preserving
`promote | abstain | audit | hold`, recoverable ambiguity, and explicit
authority boundaries.

### P0 — GWB/affidavit convergence proving lane

GWB is the first ambiguity-heavy adopter because widened targeting now exposes
real multiplicity:

- public review: 28 singleton seed linkages / 42 multi-candidate unresolved;
- broader review: 14 singleton seed linkages / 13 multi-candidate unresolved.

First separate mention/entity ambiguity from claim/target ambiguity. Repeated
names, roles, event aliases, and local pronouns should enter document-bounded
coreference clusters and PNF demands before target interpretation. Then tighten
basis vocabulary and source semantics. Keep shared emitted alignment held until
the oracle reaches `promote`. Prioritize books/memoir and official-record
text-source surfaces before forcing affidavit-shaped artifacts.

### P1 — AU normalization and operator workflow

AU is the next shared resolver/targeting adopter, not the first
shared-alignment proof. Reuse the generic mention, PNF-demand, candidate, and
resolution carriers for courts, statutes, parties, roles, dates, and procedural
events. Keep AU fact-review/legal-follow outputs on the shared compiler
contract, then normalize the review-queue -> event-target subset into the weak
targeting surface. After that, move to the first operator-grade review
workflow.

### P1 — Nat/Wikidata bounded diagnostics

Continue the climate policy-resolution dry run and Nat contract discovery as
bounded, revision-pinned diagnostics. Reuse its entity snapshots, hierarchy
evidence, and receipts as an optional backend for the generic resolver. Measure
full-backlog rule coverage and reviewed near misses before proposing any
migration rule. The climate tranche and the broader Nat/Wikidata lane remain
non-authoritative and must not become the shared semantic owner.

### P2 — External graph expansion and hard ontology remainder

The generic external-graph bridge is mostly complete. Finish the narrow
Apoteket isolation/reproducibility handoff and one mature cross-lane replay
before investing in asynchronous joins, route indexes, shard optimization,
spectral pressure, or broad ontology repair. Keep climate scope-ambiguous
holds, GWB OCR blockers, and other hard remainders behind the above gates.

## Explicit non-priorities

- no shared emitted alignment primitive yet;
- no eager all-span/all-candidate materialization or mandatory live Wikidata
  lookup during parsing;
- no backend calls from parser code, one-request-per-mention fetching, or
  corpus-wide blocking registry batch;
- no event identity closure from one scalar similarity score;
- no silent or default cross-context identity merge;
- no live Wikidata write or migration executor;
- no broad ontology merge/split automation;
- no OCR expansion unless it is the actual blocker for a promoted source
  family;
- no graph layer as an organizing truth surface.

## Sequencing rule

Do not start another lane-specific semantic expansion while the shared
parser/span substrate, PNF-driven resolver, targeting kernel, GWB ambiguity
oracle, and AU/Nat adopter boundaries remain unmeasured. Prefer one bounded
generic implementation plus receipts and operator-facing review evidence per
tranche.

Immediate order:

```text
typed resolution subjects and event roles
-> semantic demand equivalence/deduplication receipts
-> append-only evidence cache and microbatch scheduler
-> Wikidata and WorldMonitor snapshot adapters
-> typed entity/event meet assessment
-> incremental PNF refinement
-> small GWB end-to-end proof
-> generic readiness/targeting
-> AU second-lane proof
```
