# Portable Semantic Reading Trail Design

## Status

Recovered approved architectural design for the Mabo reading-workbench tranche. The earlier handoff named a branch/commit that is not present on the current remote, so this file preserves the approved design on the successor branch without changing scope.

## Goal

Build a portable semantic reading interaction in which canonical SensibLaw/SLR state remains authoritative while a UI interpreter can expose nested and overlapping semantic targets, follow one target into a reading trail, and replay structured interaction intents without promoting UI state into semantic truth.

The first concrete specimen is Mabo. The first interpreter may later be ITIR/Svelte, but this tranche makes the semantic projection and interaction contract independent of any UI framework.

## Architectural rule

The core distinction is:

```text
constituent target != composite target
```

A phrase can simultaneously expose a whole semantic target and independently navigable constituent targets. Overlap is valid data, not a tokenisation error.

For example, a UI may expose all of:

```text
silk
golden spider
golden spider silk
panel
```

from one sentence. The whole phrase does not absorb the identity, ontology, provenance, or authority of its constituents, and constituents do not automatically inherit the relations of the composite.

The Mabo fixture uses the same rule on legal reading targets, for example `Mabo`, `native title`, and a constituent target within that phrase. The fixture is a deterministic interaction specimen; it does not replace the repository's canonical AU semantic entity and corpus data.

## Existing authority and reuse

The implementation must reuse the repository architecture rather than introduce a second semantic model:

- `src/au_semantic/semantic.py` remains an authority surface for canonical AU semantic entity identity, including the Mabo legal reference.
- `data/corpus/mabo_v_queensland_no2.json` remains the Mabo corpus fixture.
- `src/sensiblaw/interfaces/shared_reducer.py` remains the shared lexer/reducer/PNF access surface.
- producer-owned `text_debug` anchors (`charStart`, `charEnd`, `sourceArtifactId`) are the shared source-span convention when producer spans are available.
- the reading-workbench layer stores references, source spans, role overlays, and navigation state; it does not manufacture canonical semantic identity.

## Layers

### 1. Canonical world

The world bucket is the larger set of target references known to the current reading context. A target has a stable local target id, source-artifact id, character span, display text, semantic-reference string, target kind, and optional role overlays.

These fields are projection metadata. `semantic_ref` points toward a canonical or provisional semantic object; it is not itself evidence that the referenced identity has been promoted or verified.

The world may contain targets that are not currently visible.

```text
HiddenFromView != AbsentFromWorld
```

### 2. Reading projection

A projection chooses which target ids are shown in the current view and preserves their source spans. It may display overlapping/nested targets independently.

No requirement is imposed that displayed spans partition source text. The following are all valid simultaneously:

```text
[        native title        ]
[               title        ]
```

or a larger composite target overlapping both.

### 3. Structured interaction boundary (JCUI-shaped)

UI interactions cross the boundary as structured intents rather than direct mutations of canonical semantic state.

The initial intent vocabulary is deliberately small:

```text
FollowTarget(target_id)
```

The external wire form is JSON-compatible and must be validated before reduction. Unknown intent kinds, absent target ids, malformed payloads, or references to targets not present in the world are rejected at the boundary.

A rejected intent has no state-transition authority.

```text
Fails(here) != Fails(everywhere)
```

### 4. Reading trail reducer

A valid `FollowTarget` changes navigation/trail state only. It may append the selected target to the reading trail and make it the active reading target.

It must not mutate the world bucket, rewrite canonical identities, or promote a provisional reference into an authoritative one.

```text
UIIntent != SemanticMutation
FollowEntity != IdentityPromotion
```

### 5. Interpreter boundary

ITIR/Svelte is intended as the first rich interpreter, but the semantic contract is independent of Svelte, Streamlit, egui, DOM layout, CSS, WebGPU, or retained/immediate rendering.

The consumer-relevant contract is closer to:

```text
render this semantic target as an activatable region;
activation emits FollowTarget(target_id)
```

than to pixel equality across frontends.

A later interpreter may choose DOM elements, canvas regions, GPU surfaces, or native widgets while preserving the same high-level event contract.

## PNF and role overlays

PNF/role information is an overlay on a target or source span. A role overlay may help a reader see that a phrase is currently being treated as a subject, predicate, object, qualifier, or other producer-owned role.

It is not a comprehension certificate and it does not acquire semantic authority merely by being rendered.

```text
RoleOverlay != Comprehension
```

The reading layer should consume producer-owned PNF/reducer output where available. It should not duplicate `PredicatePNF`, `PredicateAtom`, `TypedArg`, `RoleState`, or related canonical reducer types.

## Context and authority

A reading target may link to contextual material such as an encyclopedia entry, dictionary page, case summary, or other reading aid. Such context remains source-bounded.

```text
WikiContext != LegalAuthority
```

A context link does not alter the court/statute/source authority carried by canonical SensibLaw/SLR state.

## Mabo v0 specimen

The deterministic fixture should expose a small source sentence associated with the Mabo reading context and at least these independent target classes:

- a Mabo case target pointing to `legal_ref:mabo_v_queensland_no_2`;
- a composite `native title` target;
- a constituent target overlapping the composite span;
- an action/role overlay sufficient to demonstrate that display roles are separate from semantic identity.

The fixture is deliberately small. It is not a new legal proposition about Mabo and should not claim that a synthetic sentence is an authoritative quotation from the judgment.

## Required behavioural invariants

1. Constituent and composite spans can coexist and overlap.
2. Each target remains independently addressable by target id.
3. Following the composite does not automatically follow or identity-promote its constituents.
4. Following a constituent does not inherit every relation of the composite.
5. Following a valid target changes trail/navigation state while preserving the world bucket.
6. A hidden target can remain present in the world bucket.
7. An unknown/malformed intent is rejected before reduction and leaves canonical reading state unchanged.
8. Context/source-kind metadata does not promote contextual material to legal authority.
9. Role overlays remain projection metadata and do not certify comprehension.
10. Rendering implementation details are outside the semantic contract unless a consumer explicitly asks for them.

## Non-goals for v0

- No new general UI framework.
- No pixel-equivalence proof between Svelte and another renderer.
- No WebGPU capability lattice.
- No replacement for canonical AU semantic identities or PNF types.
- No automatic entity promotion based on clicks.
- No automatic Wikipedia-derived legal claims.
- No full document renderer.
- No requirement that every world target be simultaneously visible.
- No StatiBaker dependency in the first semantic slice; temporal interpretation remains optional and downstream.

## First implementation seam

The first code slice should be framework-neutral Python beside the existing interface layer:

```text
canonical/reducer outputs
        |
        v
ReadingWorld + SemanticTarget references
        |
        +--> ReadingProjection (visible subset)
        |
        +--> admitted FollowTarget intent
                    |
                    v
             ReadingTrailState
```

The UI interpreter consumes this projection and emits structured intents. It never owns semantic authority.

## Test strategy

TDD starts with deterministic Python tests for the semantic boundary before any Svelte surface exists. Tests must prove overlapping-span coexistence, independent target selection, navigation-only reduction, hidden-world retention, authority firewalls, and invalid-intent rejection.

The Svelte/ITIR interpreter is a downstream adapter once the semantic carrier is stable. Because the current repository does not establish Svelte as a canonical runtime, adding a JS toolchain is not part of this v0 semantic tranche unless separately approved.
