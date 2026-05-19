# Semantic Memory Bridge Future Lane

Date: 2026-05-06

## Purpose

Pin a future lane that generalizes the current Wikidata grounding work into a
private semantic-memory bridge:

```text
raw note/transcript
  -> ITIR atoms / PredicatePNF
  -> Wikidata / Wikipedia / local grounding candidates
  -> ontology closure
  -> semantic memory index
  -> natural-language retrieval with explanation paths
```

This is a planning boundary only. It does not change runtime behavior, schemas,
CLI commands, or the current Wikidata review-packet gates.

## Relationship To Current Surfaces

This lane should reuse the current documented spine instead of creating a new
source-family parser:

- ordinary notes, transcripts, wiki text, and document excerpts first adapt
  into canonical text
- `parse_canonical_text(...)` remains the shared parser-spine entry point
- extraction profiles may emit ITIR atoms or `PredicatePNF` carriers above the
  parse
- Wikidata grounding remains downstream of PNF, not an input parser identity
- `ChangeReviewPacket`-style candidate comparison remains review-only and
  residual-bearing

The immediate conceptual dependency is the existing
`PredicatePNF_to_Wikidata` posture: grounding candidates are supplied or
derived under bounded policy, then reviewed with explicit residuals. This note
widens the destination from "public Wikidata review support" to "private
memory retrieval support," but keeps the same honesty constraints.

## Boundary

The semantic-memory bridge is not public Wikidata truth.

Allowed:

- private-memory retrieval over a user's notes, transcripts, reviewed local
  artifacts, and pinned public evidence
- local entities that do not have Wikidata QIDs
- Wikidata/Wikipedia candidates as grounding aids when provenance is pinned
- local ontology closure over a recorded ontology snapshot
- residual-bearing matches such as exact, partial, broader, narrower,
  contradiction, unresolved, and ungrounded
- explanation paths that show which atoms, grounding candidates, ontology
  edges, and residuals supported a retrieval result

Not allowed:

- fabricated QIDs or PIDs
- label-by-inspection promotion into Wikidata identity
- treating a memory hit as a public Wikidata correction
- treating ontology closure as truth without snapshot provenance
- collapsing wrapper text, browser chrome, speaker labels, citations, or
  transcript furniture into semantic evidence
- hidden writes to public Wikidata, local canonical truth stores, or downstream
  decision systems

## Grounding Model

Grounding must preserve uncertainty rather than erase it.

Candidate records should carry at least:

- source atom or `PredicatePNF` id
- candidate kind:
  - `wikidata_qid`
  - `wikidata_pid`
  - `wikipedia_page`
  - `local_entity`
  - `local_relation`
  - `ungrounded`
- candidate id or local stable id
- provenance:
  - source document / transcript id
  - source span or anchor
  - Wikidata dump or revision id when applicable
  - Wikipedia page revision id when applicable
  - ontology snapshot id
- residual:
  exact, partial, broader, narrower, contradiction, unresolved, or ungrounded
- explanation path:
  a bounded chain from source atom through grounding candidate, ontology edge,
  and retrieval result

No candidate record may invent a public identifier. If a note contains a real
private entity, the correct carrier is a local stable id with provenance and an
explicit residual against any public candidate.

## Wrapper-Aware Retrieval

Retrieval should be wrapper-aware because raw memory surfaces often contain
non-content structure:

- transcript speaker turns
- meeting/tool wrappers
- chat UI or browser chrome
- source cards and citation panels
- OCR debris
- section headings and quoted material

The bridge should retrieve against body-qualified atoms where possible and keep
wrapper metadata available as context. Wrapper metadata may explain why a
result is relevant, but it must not silently become the semantic claim being
retrieved.

## StatiBaker Todo/Kanban Candidate Receipts

The same bridge now supports a first Level-0 StatiBaker helper for free-text to
todo/Kanban review, but only as a receipt-producing read model. Its taskhood
gate is `TaskLike(Γ, TaskPNF)`: a structural action-frame judgment over a
normalized task PNF carrier plus Γ as `ProjectContextPNFIndex`, not a list
predicate, keyword predicate, or raw text classifier. Γ is a PNF-indexed project
context normalized from canonical text and structured project systems; it is not
a hand-maintained text blob. A `TaskLike` candidate must carry a residual/meet
comparison between `TaskPNF` and the Γ-PNF indexes, with unresolved residuals
preserved in the emitted receipt instead of silently promoting the candidate.

Allowed:

- input from runtime-supplied typed atoms or `PredicatePNF` carriers
- Γ supplied as `ProjectContextPNFIndex` normalized from text and structured
  systems
- residual/meet comparison against Γ-PNF indexes as the project-context check
- `Actionable` and `ProjectRelevant` action frames with source support
- `PromotableWrapper` only when the wrapper has receipt support, or
  `HasLifecycleTransition` when an explicit lifecycle transition is present
- candidate task receipts with source anchors, provenance, and residual state
- SB-facing todo/Kanban suggestions that remain review candidates
- explicit promotion or completion receipts supplied by the runtime or
  downstream governance layer
- spaCy and dependency frames as PNF/action-frame evidence only

Not allowed:

- raw keyword tasking from unparsed free text
- keyword lists, checklist shape, or category labels as taskhood authority
- hand-maintained project-context blobs as Γ authority
- treating speaker labels, wrapper text, headings, or UI furniture as tasks
- promoting `ClosedOrNegated` or `PurelyPhatic` frames into tasks
- treating spaCy/dependency parses as taskhood authority
- live mutation of StatiBaker state
- marking SB tasks promoted, accepted, completed, or closed without receipts
- fabricating promotion, completion, grounding, or lifecycle receipts
- treating a task candidate as semantic truth or workflow authority

The current Level-0 output is therefore `sl.statibaker_task_memory.v0_1`
candidate task receipts plus a `sl.statibaker_kanban_projection.v0_1` read-only
board projection, not a direct SB command. If the source text only supports
"possible follow-up," the receipt should preserve that residual instead of
fabricating an actionable todo.

The current deterministic corpus probe for this lane is
`tests/fixtures/statibaker_kanban/archive_freetext_probe_v0_1.json`. It pins a
small local chat-archive query excerpt selected through `robust-context-fetch`,
then carries the explicit `TaskPNF`, grounding catalog, and Γ fixture required
for the helper to create one review-only candidate card. This is intentionally
not raw free-text tasking; it is a corpus fixture for the boundary where
canonical text has already been normalized into typed task/context carriers.

A second deterministic corpus probe is
`tests/fixtures/statibaker_kanban/archive_thread_timeline_probe_v0_1.json`. It
pins 10 archive-derived seeds and proves bidirectional task timeline
reconciliation: prior thread events can reinterpret the seed task, later events
can update or close the lifecycle, and task-timeline receipts can trace back to
their canonical archive events. The proof requires source anchors, normalized
`TaskPNF`, Γ residual state, explicit lifecycle receipts, successor/blocker
state, and missing expected slots for unresolved one-sided matches. It remains a
read-only receipt surface, not live StatiBaker mutation, promotion, completion,
or archive-derived truth.

Related fact-intake probe:
`tests/fixtures/fact_intake/fact_extraction_probe_v0_1.json` belongs to the
text-grounded observation lane, not the private semantic-memory retrieval lane.
It may supply typed observations as future bridge input, but it is not itself a
memory hit, belief inference, public grounding authority, or downstream
workflow command.

## Ontology Snapshot Provenance

Ontology closure is only meaningful against a named snapshot.

Every closure-backed retrieval result should record:

- ontology snapshot id
- snapshot source:
  - local ontology file set
  - Wikidata dump or bounded slice
  - imported external ontology
  - mixed snapshot manifest
- closure ruleset id
- edge/path ids used in the explanation path
- residual or severity state after closure

If the ontology snapshot changes, the semantic-memory index must be treated as
stale until rebuilt or explicitly marked as using the older snapshot.

## Promotion Gates

Future implementation should proceed in this order:

1. Docs-only packet shape over existing canonical text / PNF language.
2. Fixture-only JSON examples with local entities, public candidates, and
   residual-bearing explanation paths.
3. Read-only local index over pinned fixture packets.
4. Natural-language retrieval against that local index with explanation paths.
5. Optional bridge to broader Wikidata review surfaces, still without public
   edit authority.

The first executable slice should prove abstention and residual preservation
before it proves broad recall. A useful bridge is one that can say "this looks
like `Q...`, but the local note only supports a partial private-memory match"
without promoting that candidate to public truth.

## Acceptance Criteria For A Later Slice

A later implementation proposal is reviewable only when it demonstrates:

- one raw note or transcript adapted through canonical text
- one extracted atom or `PredicatePNF` carrier
- at least one public grounding candidate and one local-entity candidate
- no fabricated QIDs/PIDs
- ontology snapshot provenance on every closure-backed result
- wrapper-aware span handling
- residual-bearing retrieval results
- natural-language answers that include explanation paths and abstain when the
  grounding is unresolved
