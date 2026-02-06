# Timeline Ribbon (Conserved Allocation Spine)

The ribbon is a continuous spine that accounts for 100% of a conserved quantity
under the active lens. It is an accounting surface, not a narrative device.

## Core invariant

Segment width represents allocation of a conserved quantity under the active
lens. The conserved quantity must be named and inspectable (time, evidence
density, procedural weight, attention, exposure, environmental load, etc).

## Definitions

Let the spine domain be a time interval T = [t0, t1]. A lens L induces a
nonnegative measure mu_L over T. In density form, mu_L(A) = ∫_A rho_L(t) dt.

Width of a segment I is:
  width(I) = mu_L(I) / mu_L(T)

Conservation:
  sum(width(I_i)) = 1 for any partition of T.

## Segmentation rule

A segment represents a contiguous interval over which the rate of allocation
is approximately coherent. Segments are ordered, touch without gaps, and do not
overlap. Segmentation changes when the allocation regime changes, not when a
story changes.

## Threads (callouts)

Threads attach to segments but carry no mass. They explain why a segment looks
the way it does without changing the allocation. Threads may contain evidence,
citations, sub-events, or competing interpretations, but they never alter
segment widths.

## Lens switching

Switching lenses re-allocates widths but preserves ordering and anchors.
The UI must explicitly name the conserved quantity and show total mass.

## UI affordances (non-negotiable)

- Conservation badge: shows lens name, total mass, and normalization basis.
- Lens inspector: shows rho_L definition, contributors, units, and provenance.
- Segment tooltip: shows interval, width %, mass, and top contributors.
- Compare overlay: optional ghost widths when switching lenses.
- Split/merge UI: must show conservation check (A = B + C).

## Invariants (testable)

- Coverage: segments partition T with no gaps/overlaps.
- Additivity: split/merge preserves mu_L.
- Non-negativity: rho_L, mu_L, width are >= 0.
- Zero-mass handling: if mu_L(T) = 0, fallback or explicit undefined state.
- Threads do not affect widths unless explicitly declared by lens.

## JSON schema (draft-07)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://itir.dev/schema/timeline-ribbon.json",
  "title": "Timeline Ribbon Model",
  "type": "object",
  "required": ["spine", "lens", "segments"],
  "properties": {
    "spine": {
      "type": "object",
      "required": ["domain"],
      "properties": {
        "domain": {
          "type": "object",
          "required": ["type", "start", "end"],
          "properties": {
            "type": { "enum": ["continuous", "discrete"] },
            "start": { "type": "number" },
            "end": { "type": "number" }
          }
        }
      }
    },
    "lens": {
      "type": "object",
      "required": ["id", "name", "units", "total_mass"],
      "properties": {
        "id": { "type": "string" },
        "name": { "type": "string" },
        "units": { "type": "string" },
        "definition": { "type": "string" },
        "blend": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["lens_id", "weight"],
            "properties": {
              "lens_id": { "type": "string" },
              "weight": { "type": "number", "minimum": 0, "maximum": 1 }
            }
          }
        },
        "total_mass": { "type": "number", "minimum": 0 },
        "version_hash": { "type": "string" }
      }
    },
    "segments": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "required": ["id", "t_start", "t_end", "mass", "width_norm"],
        "properties": {
          "id": { "type": "string" },
          "t_start": { "type": "number" },
          "t_end": { "type": "number" },
          "mass": { "type": "number", "minimum": 0 },
          "width_norm": { "type": "number", "minimum": 0, "maximum": 1 },
          "parent_id": { "type": "string" },
          "children_ids": { "type": "array", "items": { "type": "string" } }
        }
      }
    },
    "threads": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "anchor_t", "segment_id", "kind"],
        "properties": {
          "id": { "type": "string" },
          "anchor_t": { "type": "number" },
          "segment_id": { "type": "string" },
          "kind": {
            "enum": ["evidence", "annotation", "citation", "note", "counterpoint"]
          },
          "visibility_scope": { "enum": ["public", "restricted", "private"] }
        }
      }
    }
  }
}
```

## Property tests (Hypothesis-style)

```python
from hypothesis import given, strategies as st
from math import isclose

EPS = 1e-6

@st.composite
def segments(draw):
    cuts = sorted(draw(st.lists(st.floats(0, 1), min_size=1, max_size=6)))
    points = [0.0] + cuts + [1.0]
    segs = []
    remaining_mass = 1.0
    for i in range(len(points) - 1):
        t0, t1 = points[i], points[i + 1]
        mass = draw(st.floats(0, remaining_mass))
        remaining_mass -= mass
        segs.append({"t_start": t0, "t_end": t1, "mass": mass})
    total_mass = sum(s["mass"] for s in segs)
    for s in segs:
        s["width_norm"] = 0 if total_mass == 0 else s["mass"] / total_mass
    return segs, total_mass

@given(segments())
def test_conservation_of_width(segments_and_mass):
    segs, _ = segments_and_mass
    total = sum(s["width_norm"] for s in segs)
    assert isclose(total, 1.0, abs_tol=EPS) or total == 0

@given(segments())
def test_split_additivity(segments_and_mass):
    segs, _ = segments_and_mass
    s = segs[0]
    m1 = s["mass"] * 0.4
    m2 = s["mass"] * 0.6
    assert isclose(m1 + m2, s["mass"], abs_tol=EPS)

@given(segments())
def test_merge_additivity(segments_and_mass):
    segs, _ = segments_and_mass
    if len(segs) < 2:
        return
    s1, s2 = segs[0], segs[1]
    merged_mass = s1["mass"] + s2["mass"]
    assert merged_mass >= s1["mass"]
    assert merged_mass >= s2["mass"]

@given(segments())
def test_non_negativity(segments_and_mass):
    segs, total_mass = segments_and_mass
    assert total_mass >= 0
    for s in segs:
        assert s["mass"] >= 0
        assert s["width_norm"] >= 0

@given(segments())
def test_order_preservation(segments_and_mass):
    segs, _ = segments_and_mass
    for i in range(len(segs) - 1):
        assert segs[i]["t_end"] <= segs[i + 1]["t_start"]
```

## UI component tree (responsibilities)

```
RibbonRoot
├── RibbonHeader
│   ├── ConservationBadge
│   ├── LensName
│   ├── TotalMassDisplay
│   └── InspectButton
├── LensInspector
│   ├── LensDefinition
│   ├── UnitsAndSemantics
│   ├── BlendBreakdown
│   ├── Provenance
│   └── SanityChecks
├── RibbonViewport
│   ├── Heatline (rho(t))
│   ├── SegmentLayer
│   │   └── Segment (xN)
│   │       ├── SegmentBody
│   │       ├── SplitHandle
│   │       └── SegmentTooltip (mass ledger)
│   ├── MergePreviewOverlay
│   └── CompareOverlay (ghost widths from previous lens)
└── ThreadLayer
    ├── ThreadAnchor (xM)
    └── ThreadCard
```

## Why this matters for ITIR/SensibLaw

The ribbon preserves structure before story. It supports multi-truth overlays
without privileging one interpretation. It keeps context visible and avoids
narrative coercion while remaining inspectable and auditable.

## UI selector contract

See `itir-ribbon/ui_contract.md` for the required `data-testid`/`data-*` attributes
used by conservation tests.
