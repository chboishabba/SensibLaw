# Mabo Reading Workbench V0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a framework-neutral Mabo reading interaction that preserves constituent/composite semantic targets as independently addressable overlapping spans, validates structured follow intents, and changes navigation state without mutating canonical semantic identity.

**Architecture:** Add a small projection/interaction carrier under `src/sensiblaw/interfaces/` that references canonical semantic ids and producer-owned source spans rather than duplicating AU semantic or PNF types. A deterministic Mabo specimen exercises nested/overlapping targets. The first tranche ends at the Python semantic boundary; Svelte/ITIR remains a downstream interpreter once this contract is stable.

**Tech Stack:** Python 3.10+, dataclasses, JSON-compatible mappings, pytest; existing SensibLaw AU semantic ids, shared reducer/PNF conventions, and corpus fixtures.

**Spec:** `docs/superpowers/specs/2026-09-15-portable-semantic-reading-trail-design.md`

## Global Constraints

- Canonical SensibLaw/SLR semantic state remains authoritative; the reading layer stores references and projection/navigation metadata only.
- Reuse the canonical Mabo key `legal_ref:mabo_v_queensland_no_2`; do not create a competing Mabo identity.
- Reuse producer-style character-span/source-artifact semantics (`charStart`, `charEnd`, `sourceArtifactId`) at the wire boundary.
- Constituent and composite semantic targets may overlap and remain independently addressable.
- `UIIntent` must not imply semantic mutation; `FollowTarget` must not imply identity promotion.
- Hidden targets remain members of the world bucket.
- Context links never become legal authority merely by being present or followed.
- PNF/role overlays are references/projection metadata; do not duplicate canonical `PredicatePNF`, `PredicateAtom`, `TypedArg`, `RoleState`, or reducer logic.
- Unknown or malformed intents fail admission before reduction and leave reading state unchanged.
- No Svelte/Node/WebGPU dependency is introduced in this tranche.
- Tests are deterministic and offline.

---

### Task 1: RED regression for constituent/composite reading semantics

**Files:**
- Create: `tests/test_reading_trail.py`
- Later implementation: `src/sensiblaw/interfaces/reading_trail.py`

**Interfaces:**
- Consumes: canonical semantic reference strings and character/source spans.
- Produces required public surface: `SemanticTarget`, `ReadingWorld`, `ReadingProjection`, `ReadingTrailState`, `IntentAdmissionError`, `parse_reading_intent`, `reduce_reading_intent`, `build_mabo_reading_fixture`.

- [ ] **Step 1: Write the failing tests**

```python
from __future__ import annotations

import pytest

from src.sensiblaw.interfaces.reading_trail import (
    FollowTarget,
    IntentAdmissionError,
    build_mabo_reading_fixture,
    parse_reading_intent,
    reduce_reading_intent,
)


def test_mabo_fixture_preserves_constituent_and_composite_overlapping_spans():
    state, projection = build_mabo_reading_fixture()
    native_title = state.world.targets["concept:native_title"]
    title = state.world.targets["lexeme:title"]

    assert native_title.char_start < title.char_start
    assert title.char_end == native_title.char_end
    assert native_title.target_id in projection.visible_target_ids
    assert title.target_id in projection.visible_target_ids
    assert native_title.semantic_ref != title.semantic_ref


def test_follow_target_changes_navigation_not_world_or_identity():
    state, _ = build_mabo_reading_fixture()
    world_before = state.world

    next_state = reduce_reading_intent(
        state,
        FollowTarget(target_id="concept:native_title"),
    )

    assert next_state.world is world_before
    assert next_state.active_target_id == "concept:native_title"
    assert next_state.trail == ("concept:native_title",)
    assert next_state.world.targets["concept:native_title"].semantic_ref == "concept:native_title"
    assert next_state.world.targets["lexeme:title"].semantic_ref == "lexeme:title"


def test_hidden_target_remains_in_world_bucket():
    state, projection = build_mabo_reading_fixture()

    assert "context:wikipedia_mabo" in state.world.targets
    assert "context:wikipedia_mabo" not in projection.visible_target_ids


def test_context_target_does_not_acquire_legal_authority():
    state, _ = build_mabo_reading_fixture()
    context = state.world.targets["context:wikipedia_mabo"]
    mabo = state.world.targets["legal_ref:mabo_v_queensland_no_2"]

    assert context.authority_kind == "context"
    assert mabo.authority_kind == "legal_authority_reference"


def test_malformed_or_unknown_intent_is_rejected_before_reduction():
    state, _ = build_mabo_reading_fixture()

    with pytest.raises(IntentAdmissionError):
        parse_reading_intent({"kind": "FollowTarget"})

    with pytest.raises(IntentAdmissionError):
        parse_reading_intent({"kind": "RewriteCanonicalEntity", "targetId": "x"})

    unknown = parse_reading_intent({"kind": "FollowTarget", "targetId": "missing"})
    with pytest.raises(IntentAdmissionError):
        reduce_reading_intent(state, unknown)

    assert state.trail == ()
    assert state.active_target_id is None


def test_following_composite_does_not_follow_constituent():
    state, _ = build_mabo_reading_fixture()
    next_state = reduce_reading_intent(
        state,
        parse_reading_intent(
            {"kind": "FollowTarget", "targetId": "concept:native_title"}
        ),
    )

    assert next_state.trail == ("concept:native_title",)
    assert "lexeme:title" not in next_state.trail
```

- [ ] **Step 2: Run the focused regression and confirm RED**

Run:

```bash
pytest -q tests/test_reading_trail.py
```

Expected: collection/import failure because `src.sensiblaw.interfaces.reading_trail` does not yet exist.

- [ ] **Step 3: Commit the RED contract**

```bash
git add tests/test_reading_trail.py
git commit -m "test: define Mabo reading trail semantic contract"
```

---

### Task 2: Add the framework-neutral reading projection carrier

**Files:**
- Create: `src/sensiblaw/interfaces/reading_trail.py`
- Test: `tests/test_reading_trail.py`

**Interfaces:**
- Produces:
  - `SemanticTarget`
  - `ReadingWorld`
  - `ReadingProjection`
  - `ReadingTrailState`
  - `FollowTarget`
  - `IntentAdmissionError`
  - `parse_reading_intent(payload: Mapping[str, object]) -> FollowTarget`
  - `reduce_reading_intent(state: ReadingTrailState, intent: FollowTarget) -> ReadingTrailState`

- [ ] **Step 1: Implement immutable projection/navigation types**

```python
from __future__ import annotations

from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True, slots=True)
class SemanticTarget:
    target_id: str
    source_artifact_id: str
    char_start: int
    char_end: int
    display_text: str
    semantic_ref: str
    target_kind: str
    authority_kind: str = "projection"
    role_overlays: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.target_id:
            raise ValueError("target_id must be non-empty")
        if not self.source_artifact_id:
            raise ValueError("source_artifact_id must be non-empty")
        if self.char_start < 0 or self.char_end <= self.char_start:
            raise ValueError("invalid target character span")


@dataclass(frozen=True, slots=True)
class ReadingWorld:
    source_text: str
    targets: Mapping[str, SemanticTarget]

    @classmethod
    def from_targets(
        cls,
        source_text: str,
        targets: tuple[SemanticTarget, ...],
    ) -> "ReadingWorld":
        by_id = {target.target_id: target for target in targets}
        if len(by_id) != len(targets):
            raise ValueError("duplicate target_id in reading world")
        for target in targets:
            if target.char_end > len(source_text):
                raise ValueError(f"target span outside source text: {target.target_id}")
        return cls(source_text=source_text, targets=MappingProxyType(by_id))


@dataclass(frozen=True, slots=True)
class ReadingProjection:
    visible_target_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReadingTrailState:
    world: ReadingWorld
    trail: tuple[str, ...] = ()
    active_target_id: str | None = None


@dataclass(frozen=True, slots=True)
class FollowTarget:
    target_id: str


class IntentAdmissionError(ValueError):
    pass
```

- [ ] **Step 2: Implement structured intent admission**

```python
def parse_reading_intent(payload: Mapping[str, object]) -> FollowTarget:
    if payload.get("kind") != "FollowTarget":
        raise IntentAdmissionError("unsupported reading intent kind")
    target_id = payload.get("targetId")
    if not isinstance(target_id, str) or not target_id.strip():
        raise IntentAdmissionError("FollowTarget requires a non-empty targetId")
    return FollowTarget(target_id=target_id)
```

- [ ] **Step 3: Implement navigation-only reduction**

```python
def reduce_reading_intent(
    state: ReadingTrailState,
    intent: FollowTarget,
) -> ReadingTrailState:
    if intent.target_id not in state.world.targets:
        raise IntentAdmissionError(f"unknown reading target: {intent.target_id}")
    return replace(
        state,
        trail=state.trail + (intent.target_id,),
        active_target_id=intent.target_id,
    )
```

- [ ] **Step 4: Run the focused regression**

Run:

```bash
pytest -q tests/test_reading_trail.py
```

Expected at this point: only fixture-dependent tests fail because `build_mabo_reading_fixture` is not yet implemented; carrier/admission tests import successfully.

- [ ] **Step 5: Commit**

```bash
git add src/sensiblaw/interfaces/reading_trail.py tests/test_reading_trail.py
git commit -m "feat: add reading trail projection and intent boundary"
```

---

### Task 3: Add the deterministic Mabo constituent/composite fixture

**Files:**
- Modify: `src/sensiblaw/interfaces/reading_trail.py`
- Modify: `tests/test_reading_trail.py`

**Interfaces:**
- Consumes canonical Mabo reference string `legal_ref:mabo_v_queensland_no_2`.
- Produces `build_mabo_reading_fixture() -> tuple[ReadingTrailState, ReadingProjection]`.

- [ ] **Step 1: Implement helper for deterministic span construction**

```python
def _target_for_surface(
    *,
    target_id: str,
    source_artifact_id: str,
    source_text: str,
    surface: str,
    semantic_ref: str,
    target_kind: str,
    authority_kind: str = "projection",
    role_overlays: tuple[str, ...] = (),
    occurrence: int = 0,
) -> SemanticTarget:
    cursor = -1
    start = 0
    for _ in range(occurrence + 1):
        cursor = source_text.index(surface, start)
        start = cursor + len(surface)
    return SemanticTarget(
        target_id=target_id,
        source_artifact_id=source_artifact_id,
        char_start=cursor,
        char_end=cursor + len(surface),
        display_text=surface,
        semantic_ref=semantic_ref,
        target_kind=target_kind,
        authority_kind=authority_kind,
        role_overlays=role_overlays,
    )
```

- [ ] **Step 2: Implement the Mabo fixture**

Use a clearly synthetic reading sentence rather than representing it as an authoritative quotation:

```python
def build_mabo_reading_fixture() -> tuple[ReadingTrailState, ReadingProjection]:
    source_text = "Mabo recognised native title in Australian common law."
    source_artifact_id = "fixture:mabo_reading_v0"

    targets = (
        _target_for_surface(
            target_id="legal_ref:mabo_v_queensland_no_2",
            source_artifact_id=source_artifact_id,
            source_text=source_text,
            surface="Mabo",
            semantic_ref="legal_ref:mabo_v_queensland_no_2",
            target_kind="legal_ref",
            authority_kind="legal_authority_reference",
            role_overlays=("subject",),
        ),
        _target_for_surface(
            target_id="action:recognised",
            source_artifact_id=source_artifact_id,
            source_text=source_text,
            surface="recognised",
            semantic_ref="action:recognised",
            target_kind="action",
            role_overlays=("predicate",),
        ),
        _target_for_surface(
            target_id="concept:native_title",
            source_artifact_id=source_artifact_id,
            source_text=source_text,
            surface="native title",
            semantic_ref="concept:native_title",
            target_kind="composite_concept",
            role_overlays=("object",),
        ),
        _target_for_surface(
            target_id="lexeme:title",
            source_artifact_id=source_artifact_id,
            source_text=source_text,
            surface="title",
            semantic_ref="lexeme:title",
            target_kind="constituent",
        ),
        SemanticTarget(
            target_id="context:wikipedia_mabo",
            source_artifact_id=source_artifact_id,
            char_start=0,
            char_end=4,
            display_text="Mabo context",
            semantic_ref="context:wikipedia_mabo",
            target_kind="context_link",
            authority_kind="context",
        ),
    )

    world = ReadingWorld.from_targets(source_text, targets)
    projection = ReadingProjection(
        visible_target_ids=(
            "legal_ref:mabo_v_queensland_no_2",
            "action:recognised",
            "concept:native_title",
            "lexeme:title",
        )
    )
    return ReadingTrailState(world=world), projection
```

- [ ] **Step 3: Run all reading-trail tests**

Run:

```bash
pytest -q tests/test_reading_trail.py
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add src/sensiblaw/interfaces/reading_trail.py tests/test_reading_trail.py
git commit -m "feat: add Mabo overlapping reading target fixture"
```

---

### Task 4: Add wire-format projection and explicit authority/role firewalls

**Files:**
- Modify: `src/sensiblaw/interfaces/reading_trail.py`
- Modify: `tests/test_reading_trail.py`

**Interfaces:**
- Produces `project_reading_view(state, projection) -> dict[str, object]`.
- Wire target keys use existing source-span naming: `charStart`, `charEnd`, `sourceArtifactId`.

- [ ] **Step 1: Add RED assertions for the wire projection**

```python
def test_wire_projection_preserves_overlapping_targets_and_span_contract():
    state, projection = build_mabo_reading_fixture()
    view = project_reading_view(state, projection)
    by_id = {target["targetId"]: target for target in view["targets"]}

    assert by_id["concept:native_title"]["charEnd"] == by_id["lexeme:title"]["charEnd"]
    assert by_id["concept:native_title"]["charStart"] < by_id["lexeme:title"]["charStart"]
    assert all(target["sourceArtifactId"] for target in view["targets"])
    assert by_id["legal_ref:mabo_v_queensland_no_2"]["roleOverlays"] == ["subject"]
    assert view["activeTargetId"] is None


def test_projection_hides_context_without_deleting_it_from_world():
    state, projection = build_mabo_reading_fixture()
    view = project_reading_view(state, projection)

    assert all(target["targetId"] != "context:wikipedia_mabo" for target in view["targets"])
    assert "context:wikipedia_mabo" in state.world.targets
```

- [ ] **Step 2: Implement wire projection without semantic mutation**

```python
def project_reading_view(
    state: ReadingTrailState,
    projection: ReadingProjection,
) -> dict[str, object]:
    targets: list[dict[str, object]] = []
    for target_id in projection.visible_target_ids:
        target = state.world.targets[target_id]
        targets.append(
            {
                "targetId": target.target_id,
                "sourceArtifactId": target.source_artifact_id,
                "charStart": target.char_start,
                "charEnd": target.char_end,
                "displayText": target.display_text,
                "semanticRef": target.semantic_ref,
                "targetKind": target.target_kind,
                "authorityKind": target.authority_kind,
                "roleOverlays": list(target.role_overlays),
            }
        )
    return {
        "sourceText": state.world.source_text,
        "targets": targets,
        "trail": list(state.trail),
        "activeTargetId": state.active_target_id,
    }
```

- [ ] **Step 3: Run focused tests**

```bash
pytest -q tests/test_reading_trail.py
```

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add src/sensiblaw/interfaces/reading_trail.py tests/test_reading_trail.py
git commit -m "feat: project reading trail through producer span contract"
```

---

### Task 5: Cross-check canonical Mabo identity and source boundaries

**Files:**
- Modify: `tests/test_reading_trail.py`
- Read-only dependency: `src/au_semantic/semantic.py`
- Read-only fixture: `data/corpus/mabo_v_queensland_no2.json`

**Interfaces:**
- Verifies the reading fixture points toward, rather than duplicates, canonical Mabo identity.

- [ ] **Step 1: Add a canonical-key regression**

```python
def test_mabo_target_uses_existing_canonical_au_semantic_key():
    state, _ = build_mabo_reading_fixture()
    target = state.world.targets["legal_ref:mabo_v_queensland_no_2"]

    assert target.semantic_ref == "legal_ref:mabo_v_queensland_no_2"
```

Do not import private AU seed tuples solely to make the reading layer depend on their implementation details. The exact canonical string is already a public linkage coordinate used by the existing semantic surface.

- [ ] **Step 2: Run both focused and existing AU semantic regressions**

```bash
pytest -q tests/test_reading_trail.py tests/test_au_semantic.py
```

Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add tests/test_reading_trail.py
git commit -m "test: pin reading target to canonical Mabo semantic key"
```

---

### Task 6: Documentation and bounded interpreter handoff

**Files:**
- Create: `docs/reading_trail_v0.md`
- No Svelte source is created in this tranche.

**Interfaces:**
- Documents the JSON-compatible input/output contract for the later ITIR/Svelte interpreter.

- [ ] **Step 1: Document the event and projection contract**

The document must contain these exact examples:

```json
{
  "kind": "FollowTarget",
  "targetId": "concept:native_title"
}
```

and a projected target shape:

```json
{
  "targetId": "concept:native_title",
  "sourceArtifactId": "fixture:mabo_reading_v0",
  "charStart": 16,
  "charEnd": 28,
  "displayText": "native title",
  "semanticRef": "concept:native_title",
  "targetKind": "composite_concept",
  "authorityKind": "projection",
  "roleOverlays": ["object"]
}
```

The document must state:

```text
UIIntent != SemanticMutation
FollowTarget != IdentityPromotion
WikiContext != LegalAuthority
RoleOverlay != Comprehension
HiddenFromView != AbsentFromWorld
```

and explain that the eventual Svelte interpreter renders targets and emits intents but does not own the reducer or canonical semantic ids.

- [ ] **Step 2: Run formatting/static syntax checks for touched Python**

```bash
python -m compileall -q src/sensiblaw/interfaces/reading_trail.py tests/test_reading_trail.py
ruff check src/sensiblaw/interfaces/reading_trail.py tests/test_reading_trail.py
```

Expected: exit 0.

- [ ] **Step 3: Run final focused validation**

```bash
pytest -q tests/test_reading_trail.py tests/test_au_semantic.py
```

Expected: exit 0 with zero failures.

- [ ] **Step 4: Commit**

```bash
git add docs/reading_trail_v0.md src/sensiblaw/interfaces/reading_trail.py tests/test_reading_trail.py
git commit -m "docs: define reading trail interpreter handoff"
```

## Plan self-review

- Spec coverage: constituent/composite overlap, independent selection, navigation-only mutation, hidden-world retention, context/authority separation, role-overlay separation, structured-intent rejection, and later interpreter boundary are each assigned explicit tests/tasks.
- Scope: one semantic subsystem; Svelte and StatiBaker are intentionally downstream, so this plan remains independently testable.
- Type consistency: `target_id`/`targetId`, `source_artifact_id`/`sourceArtifactId`, and `char_start`/`charStart` are intentionally separated between Python and wire naming.
- Authority consistency: no new canonical entity table or PNF type is introduced.
- Verification caveat: source commits through the GitHub connector are not runtime test receipts. Completion requires the commands above to be executed in a checkout with project dependencies installed.
