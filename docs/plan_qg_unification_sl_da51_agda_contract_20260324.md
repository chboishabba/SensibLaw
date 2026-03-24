# QG Unification Proof Boundary: SL ↔ DA51 ↔ Agda Contract

Reference: ChatGPT thread `QG Unification Proofs` (online UUID `69c27a0a-ed74-839c-8a57-3c184c28f88e`, canonical thread ID `f20d9304aae805879a1f934b71443bd2c80ac19b`).

This is a **documentation-only** capture of the resolved thread’s formal boundary proposal.

## 1) Core intent

The proposed contract defines a boundary where SensibLaw (SL) acts as a canonical structure and compression layer, while formal semantics remain in DA51/Agda systems.

- SL does **not** alter canonical proof or trace semantics.
- SL contributes: structured representation, MDL compression, admissibility filtering, dependency graph output.

## 2) Layered contract

```text
DA51 (empirical) → SL (canonical structure) → Agda (formal proof)
```

## 3) DA51 → SL boundary

Input contract (`DA51Trace`)

```json
{
  "da51": "id",
  "exponents": [e1..e15],
  "hot": int,
  "cold": int,
  "mass": int,
  "steps": int,
  "basin": int,
  "j_fixed": bool
}
```

Proposed canonical SL shape

```python
class TraceVector:
    id: str
    exponents: List[int]          # ℤ^15
    normalized: List[float]       # S^14 projection
    mass: int
    sparsity: float
    hot: int
    cold: int
    steps: int
    basin: int
    j_fixed: bool
    mdls: Optional[Dict[str, float]]
    admissible: bool
```

## 4) Proposed minimum implementation direction (non-run yet)

1. Parse `DA51Trace` messages into the canonical `TraceVector` schema.
2. Emit deterministic, reviewable `SL` spans/artifacts from normalized vectors.
3. Keep semantic truth and semantics of trace semantics outside SL in Agda-facing surfaces.
4. Publish dependency-graph metadata in a strict, typed envelope for later proof bridge adapters.

## 6) Follow-up

- No implementation was added in this pull-through to SensibLaw.
- Treat this as a contractual vocabulary for future cross-project integration only.
