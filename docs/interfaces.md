# SensibLaw Public Interfaces

This document defines the public downstream import boundary for SensibLaw.

It is intentionally narrower than the full repository surface. Downstreams such
as Mirror should import from `sensiblaw.interfaces` and should treat the values
returned there as deterministic parsing and extraction evidence, not as routing
or policy authority.

## Public Now

The following surfaces are public and implemented now.

### Canonical text adapter

- `build_canonical_conversation_text(...)`

Purpose:
- adapt conversation-style inputs into canonical text before parsing

### Parser adapter

Public module:
- `sensiblaw.interfaces.parser_adapter`

Public helpers:
- `parse_canonical_text(...)`
- `collect_canonical_operational_structure_occurrences(...)`
- `parse_canonical_message_header(...)`
- `parse_canonical_time_range_header(...)`
- `split_presemantic_text_segments(...)`
- `split_presemantic_text_clauses(...)`
- `split_presemantic_semicolon_clauses(...)`
- `strip_presemantic_enumeration_prefix(...)`
- `tokenize_presemantic_text(...)`

Purpose:
- parse canonical text and expose bounded structural observations
- expose transcript/header helpers and presemantic segmentation/tokenization

### Shared reducer

Public module:
- `sensiblaw.interfaces.shared_reducer`

Public helpers and types:
- `LexemeToken`
- `LexemeOccurrence`
- `LexemeTokenizerProfile`
- `RelationalAtom`
- `StructureOccurrence`
- `get_canonical_tokenizer_profile(...)`
- `tokenize_canonical_detailed(...)`
- `tokenize_canonical_with_spans(...)`
- `collect_canonical_lexeme_occurrences(...)`
- `collect_canonical_lexeme_occurrences_with_profile(...)`
- `collect_canonical_structure_occurrences(...)`
- `collect_canonical_relational_bundle(...)`

Purpose:
- provide reusable canonical token/span/relational extraction primitives

### Story importer

- `StoryImporter`

Purpose:
- import and normalize supported story/data surfaces through the published
  interface boundary

## Public Now For Parser, IR, and Signals

The following parser-first surfaces are implemented in this checkout and are
part of the public contract when imported through `sensiblaw.interfaces`.

### IR types

Public module:
- `sensiblaw.interfaces.ir_types`

Public types:
- `InteractionMode`
- `InteractionProjectionReceipt`
- `QueryNode`
- `QueryEdge`
- `QueryTree`

### IR adapter

Public module:
- `sensiblaw.interfaces.ir_adapter`

Public helpers:
- `build_query_tree(...)`
- `project_interaction_mode(...)`

### Signals

Public module:
- `sensiblaw.interfaces.signals`

Public helpers and types:
- `SIGNAL_STATE_VERSION`
- `SignalSpan`
- `SignalAtom`
- `SignalState`
- `extract_interaction_signals(...)`
- `collect_signal_state(...)`
- `summarize_signal_state(...)`

Purpose:
- expose parser-grounded IR and descriptive signal derivation above canonical
  parser output

## Public But Release-Sensitive

The parser/IR/signals surface exists in this checkout, but downstreams that may
span older commits or partially promoted environments should still treat it as
release-sensitive until all intended consumers pin a revision that includes
these exports.

Public end-to-end flow:

```text
canonical text -> parse -> IR -> signals
```

This is the bounded descriptive parser contract. It does not grant route
authority, renderer authority, or application policy authority to SensibLaw.

## Downstream Import Rule

Downstreams should:
- import public helpers from `sensiblaw.interfaces`
- treat parser / IR / signals as evidence and extraction support
- keep application-specific admissibility, routing, execution, and delivery
  policy local

Downstreams should not:
- import private `src.*` parser internals as if they were stable public API
- treat SensibLaw parser outputs as product route decisions
- push Telegram, Discord, or other channel policy into the SensibLaw interface
  contract

## Internal Or Private

The following surfaces must remain internal unless explicitly promoted later:

- parser implementation internals under private `src.*` modules
- experimental or lane-local adapters that are not re-exported from
  `sensiblaw.interfaces`
- channel-specific policy such as Telegram targeting, admissibility, ambient
  join behavior, or answer routing
- downstream renderer or route functions

## Implemented Versus Staged

Current state:
- parser adapter and shared reducer surfaces are implemented and public now
- canonical conversation text adaptation is implemented and public now
- IR types, IR adapter, and signals surfaces are implemented in this checkout
- downstreams that cross revision boundaries should still feature-detect the
  newer IR/signals imports until they can rely on a release or pinned SHA that
  guarantees them

That means downstream docs may refer to the parser-to-IR-to-signals pipeline as
the public contract, but code that spans mixed revisions should still
feature-detect or gate imports of the newer IR/signals surfaces.

## QG Unification Boundary Notes

- In 2026-03-24 the thread `QG Unification Proofs` (canonical ID
  `f20d9304aae805879a1f934b71443bd2c80ac19b`) introduced a proposed
  cross-project formalization boundary:
  `DA51 (empirical) -> SL (canonical structure) -> Agda (formal proof)`.
- That proposal states:
  - SL should not alter canonical proof or trace semantics.
  - SL provides structured representation, MDL compression, admissibility
    filtering, and dependency graph output.
  - A typed canonical boundary contract is preferred over ad hoc pipeline glue.
  - For legal-follow pressure specifically, SL owns only the emitted metadata
    surface, not the reusable pressure algebra itself.
- Runtime bridge stubs exist in `src/qg_unification.py` as a staged prototype.
- Fixture-backed replay exists for the same boundary:
  - `SensibLaw/tests/fixtures/qg_unification/da51_valid_demo.json`
  - `SensibLaw/tests/fixtures/qg_unification/da51_invalid_short_exponents.json`
  - `SensibLaw/scripts/qg_unification_smoke.py --json-file ...`
- Stage-2 bridge execution now writes deterministic staged JSON artifacts and may
  also persist each run to SQLite with `--db-path` (`qg_unification_runs`
  table), giving adapters a durable first-class record key before consuming
  payload artifacts.
- The stage-2 SL record is a typed transport boundary, not the formal proof
  authority: SL emits canonical `TraceVector` + dependency-envelope payloads,
  while Agda remains the source of proof semantics outside the SL runtime.
- The later `CLOCK` / `DASHI` phase reading now captured in the wider ITIR docs
  is relevant here only as an optional downstream formalization target:
  - if this lane is ever formalized in Agda, model `CLOCK` as the cyclic
    `Z/6` lift of `DASHI`'s `Z/3` phase, not as a dihedral construction
  - treat the extra `CLOCK` bit as microphase / half-step refinement, not as a
    reversal or symmetry involution
  - keep phase kinematics separate from admissibility; cone, contraction, and
    MDL remain the bounded gate on what can be promoted or proven
  - legal-follow pressure, when surfaced, must remain additive deterministic
    metadata on derived graph/review products and must not replace existing
    decision/reason fields
  - do not read this as granting proposal layers (`ZOS`-style retrieval or
    ranking) any proof or truth authority
- Stage-3 and Stage-3b adapters support `--dry-run` and persistence modes:
  - `SensibLaw/scripts/qg_unification_to_itir_db.py`
  - `SensibLaw/scripts/qg_unification_to_tirc_capture_db.py`
- `SensibLaw/scripts/run_qg_unification_to_tirc_capture.sh` runs stage-2
  bridging, both adapter dry-runs, and both adapter persistence steps in one
  command.
- Stage-3b adapter path adds transcript/capture projection:
  `SensibLaw/scripts/qg_unification_to_tirc_capture_db.py` creates
  `qg_tirc_capture_runs`, `qg_tirc_capture_sessions`, and
  `qg_tirc_capture_utterances` rows in the destination DB.
- The cross-project lane remains non-authoritative and remains private pending
  explicit JMD confirmation of the remaining mapping context.
