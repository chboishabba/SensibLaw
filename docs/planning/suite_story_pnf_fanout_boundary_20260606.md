# Suite Story PNF Fanout Boundary

Date: 2026-06-06

This note records how the suite-wide story PNF fanout work should relate to the
current SensibLaw authority contract, regex boundary, observer lanes, and
utterance latent-fibre layer.

The planned public helper is:

```python
collect_canonical_story_pnf_receipts(
    source,
    *,
    source_profile,
    source_id=None,
    context=None,
)
```

It should emit `sl.story_pnf_receipts.v0_1` payloads with:

- `emission_receipts`
- `residual_receipts`
- `residual_summary`
- `diagnostics`
- `authority_boundary`

The helper is a suite-wide evidence adapter. It is not a promotion API, routing
API, task mutator, fact mutator, legal conclusion engine, or observer truth
surface.

## Current Foundation

The existing lower layer now provides the foundation the story fanout should
reuse:

- regex-derived surfaces are limited to `lexical_hint_v1`
- utterance parser/reducer paths emit evidence-only `PredicatePNF` carriers
- utterance latent fibres can add pinned, corpus-backed evidence metadata
- Tree-sitter code observers can emit bounded `code_observation_v1` evidence
- OpenRecall/browser/vision rows remain observer-only and non-authoritative
- `src/text/residual_lattice.py` remains the shared residual algebra

The practical stack is:

```text
raw source
  -> lexical_hint_v1 / parser observation / observer row
  -> structured receipt or pinned latent-fibre evidence
  -> PredicatePNF
  -> residual comparison
  -> review/support summary
  -> lane-specific promotion only when a separate authority gate allows it
```

## Meaning For The Story Fanout Worker

The story fanout should sit above existing reducers and observers. It should
normalize suite stories into comparable PNF receipts, then call the existing
residual lattice for comparison. It should not duplicate residual semantics or
introduce a parallel authority ladder.

Recommended profile ownership:

- `conversation_text`: use the shared utterance reducer and optional
  utterance latent-fibre enrichment
- `story_event`: map TiRCorder-style event rows to sequence/event and
  epistemic/status carriers
- `observer_capture`: consume OpenRecall/browser-assist rows as observer-only
  evidence with device/session provenance
- `execution_envelope`: map StatiBaker build/test/script/model/tool run
  envelopes to sequence, commitment, absence, and lifecycle carriers
- `fact_review_item`: map SensibLaw source/excerpt/statement/observation rows
  to claim/assertion and evidence-status carriers
- `handoff_entry`: emit minimized handoff/scope/export carriers without
  replaying sensitive protected-disclosure text unnecessarily

Mirror remains one consumer. It should consume residual summaries as
support-envelope metadata while preserving its own local route authority.
StatiBaker, TiRCorder, OpenRecall, chat/history, SensibLaw, and `itir-svelte`
are also first-class producers or consumers.

## Authority Boundaries

The fanout helper must keep `authority_boundary` explicit:

```json
{
  "non_authoritative": true,
  "receipt_backed": true,
  "promotion_authority": false,
  "mutation_authority": false
}
```

Consumer-facing residual summaries may guide inspection:

- inspect contradiction
- fill missing support
- review handoff
- follow authority
- abstain

Those summaries must not directly mutate:

- StatiBaker tasks or lifecycle state
- Mirror routes
- SensibLaw facts, observations, or promoted records
- Wikidata edits or migration authority
- OpenRecall observer rows
- handoff/export scope

## Predicate Families

The v1 family set should remain deterministic and receipt-backed:

- `context/frame`: time, medium, audience, role, source class, device/session
- `epistemic/status`: hypothesis, projection, candidate, commitment,
  accepted/promoted, abstained, unknown
- `claim/assertion`: claimed, denied, alleged, observed, ordered, ruled,
  sourced
- `sequence/event`: actor, action, object, time, session boundary,
  interruption, execution run
- `commitment/lifecycle`: promise, follow-needed, blocker, done, undone,
  superseded
- `absence/gap`: missing date, actor, source, test, log, feed, or coverage
- `scope/boundary`: home/work, private/professional, public/private,
  recipient scope, do-not-sync/local-only
- `handoff/export`: recipient profile, redaction marker, exclusion,
  professional note boundary
- `observer/evidence`: OpenRecall OCR/window/browser rows and TiRCorder
  captures as observer-only evidence

The residual vocabulary remains the existing lattice:

```text
exact < partial < no_typed_meet < contradiction
```

## Review Questions For The Incoming Patch

Review should focus on authority creep and schema reuse:

- Does `observer_capture` stay observer-only with no promotion or mutation
  authority?
- Does `conversation_text` use parser/latent-fibre-backed carriers rather than
  regex semantics?
- Does `handoff_entry` minimize sensitive fields and avoid unnecessary
  verbatim replay?
- Do residuals use `src/text/residual_lattice.py` unchanged?
- Are `emission_receipts` and `residual_receipts` provenance-bearing?
- Are consumer summaries inspect/fill/review/follow/abstain signals only?
- Are source profiles deterministic and fixture-backed in v1?
- Is Mirror treated as one consumer rather than the owner of the PNF layer?

## Deferred Implementation Work

The implementation worker owns:

- adding `src/sensiblaw/interfaces/story_pnf_receipts.py` or updating it if it
  already exists
- publishing `collect_canonical_story_pnf_receipts(...)`
- adding fixtures across the six v1 source profiles
- pinning emission, residual, minimization, and non-mutation tests
- adding exporter/read-model tests only after the core receipt contract is
  stable

This note is documentation only. It does not claim that the suite-wide helper
already exists or that any consumer currently honors `sl.story_pnf_receipts.v0_1`.
