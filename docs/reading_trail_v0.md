# Reading Trail v0

`reading_trail` is a framework-neutral projection and interaction boundary for semantic reading surfaces.

It exists so a renderer (initially intended to be an ITIR/Svelte experiment) can draw interactive regions over source text without becoming the owner of canonical SensibLaw/SLR state.

## Data flow

```text
canonical semantic / reducer outputs
            |
            v
     ReadingWorld
       /       \
      v         v
ReadingProjection   admitted structured intent
      |                   |
      v                   v
UI interpreter      ReadingTrailState
```

A `ReadingWorld` is larger than what the current UI chooses to display. `ReadingProjection` is only the visible subset.

## Event contract

The initial interaction vocabulary contains one event:

```json
{
  "kind": "FollowTarget",
  "targetId": "concept:native_title"
}
```

The event is decoded and admitted before reduction. Unknown event kinds, missing/empty target ids, and target ids not present in the world are rejected. Rejection has no mutation authority over the existing state.

This is deliberately similar to a small external JSON/FIFO-style control protocol: serialization is a communication boundary, not the runtime state machine itself.

## Projection contract

A projected target is JSON-compatible and uses the repository's producer-style character-span naming:

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

Overlapping targets are intentional. A renderer must not force the target set into one non-overlapping token partition. In the Mabo fixture, `native title` and its constituent `title` are distinct independently addressable targets with overlapping source spans.

## Mabo fixture

`build_mabo_reading_fixture()` uses the synthetic sentence:

```text
Mabo recognised native title in Australian common law.
```

It is a deterministic interaction specimen, **not a quotation from the judgment**.

The Mabo target reuses the repository's established AU semantic key:

```text
legal_ref:mabo_v_queensland_no_2
```

The fixture also contains a hidden contextual target to demonstrate that omission from a projection does not delete a target from the world bucket.

## Authority firewalls

The following are architectural invariants:

```text
UIIntent != SemanticMutation
FollowTarget != IdentityPromotion
WikiContext != LegalAuthority
RoleOverlay != Comprehension
HiddenFromView != AbsentFromWorld
```

A role overlay such as `subject`, `predicate`, or `object` is presentation metadata pointing toward producer-owned analysis. The reading layer does not duplicate or replace `PredicatePNF`, `PredicateAtom`, `TypedArg`, `RoleState`, or the shared reducer.

A contextual link may aid reading but cannot acquire court/statute authority simply because it appears beside an authoritative legal target.

## Interpreter responsibility

A Svelte, Streamlit, native, canvas, or GPU-backed interpreter may choose different rendering techniques. The v0 semantic contract asks only that it preserve the consumer-relevant interaction:

```text
render target T as an activatable region
activation -> FollowTarget(T.targetId)
```

Exact pixels, layout algorithms, event-loop implementation, and rendering efficiency are outside this contract.

This is the same abstraction used when a sequential loop and a parallel/GPU loop implement the same consumer-observed logical operation through different execution strategies.

## Svelte handoff

A later Svelte interpreter should:

1. consume `project_reading_view(...)` output;
2. render all visible targets, including nested/overlapping ones;
3. emit only structured intents such as `FollowTarget`;
4. receive updated projection/navigation state from the semantic boundary;
5. never rewrite `semanticRef`, `authorityKind`, or canonical world membership on its own.

No Node/Svelte dependency is introduced by v0. That keeps the current Python semantic contract independently testable and prevents an experimental UI stack from becoming a canonical dependency by accident.
