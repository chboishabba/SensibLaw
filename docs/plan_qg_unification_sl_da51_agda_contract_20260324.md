# QG Unification Proof Boundary: SL ↔ DA51 ↔ Agda Contract

Reference: ChatGPT thread `QG Unification Proofs` (online UUID `69c27a0a-ed74-839c-8a57-3c184c28f88e`, canonical thread ID `f20d9304aae805879a1f934b71443bd2c80ac19b`).

This is the boundary contract capture from the resolved thread, with an initial
prototype scaffold implemented in SensibLaw:
`src/qg_unification.py`.

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

## 4) Implemented prototype direction

1. Parse `DA51Trace` messages into the canonical `TraceVector` schema.
2. Emit deterministic, reviewable `SL` envelope payloads from normalized vectors.
3. Keep semantic truth and semantics of trace semantics outside SL in Agda-facing surfaces.
4. Publish dependency-graph metadata in a strict, typed envelope for later proof bridge adapters.

Current status in this PR:
1. Added `DA51Trace` parsing/validation and canonical `TraceVector` projection in
   `src/qg_unification.py`.
2. Added deterministic dependency-envelope emission helper for downstream adapters.
3. Kept the boundary semantics-only until explicit adapter contracts are confirmed
   with JMD.
4. Treated any JMD-specific ZKP mapping references as private until confirmation;
   they are only summarized as implementation intent in docs.
5. Added a smoke script:
   - `SensibLaw/scripts/qg_unification_smoke.py`
   - includes `--invalid` mode for contract validation failure checks.
6. Added one-command runner:
  - `PYTHONPATH=. bash SensibLaw/scripts/run_qg_unification_smoke.sh`
7. Added stage-2 bridge artifact writer:
   - `python SensibLaw/scripts/qg_unification_stage2_bridge.py`
8. Added deterministic replay fixtures for the boundary payload shape:
   - `SensibLaw/tests/fixtures/qg_unification/da51_valid_demo.json`
   - `SensibLaw/tests/fixtures/qg_unification/da51_invalid_short_exponents.json`
9. Added fixture-backed stage-2 runner:
   - `PYTHONPATH=. bash SensibLaw/scripts/run_qg_unification_stage2_fixture.sh`
10. Verified stage-2 fixture replay writes both artifact JSON and optional
    SQLite `qg_unification_runs` state from the same typed payload.

Suggested Stage 2 command:
- `PYTHONPATH=. python SensibLaw/scripts/qg_unification_stage2_bridge.py --run-id demo-1 --out-dir /tmp/qg-unification-stage2`
- `PYTHONPATH=. python SensibLaw/scripts/qg_unification_stage2_bridge.py --json-file /path/to/payload.json --out-dir /tmp/qg-unification-stage2`

Suggested Stage 3 bridge command:
- `PYTHONPATH=. python SensibLaw/scripts/qg_unification_stage2_bridge.py --run-id demo-1 --out-dir /tmp/qg-unification-stage2 --db-path /tmp/qg-unification-stage2/qg_unification.sqlite`
Suggested Stage 4 adapter command:
- `PYTHONPATH=. python SensibLaw/scripts/qg_unification_to_itir_db.py --run-id demo-1 --bridge-db /tmp/qg-unification-stage2/qg_unification.sqlite --itir-db /tmp/qg-unification-stage2/itir.sqlite`
Suggested Stage 4a TiRC/capture adapter command:
- `PYTHONPATH=. python SensibLaw/scripts/qg_unification_to_tirc_capture_db.py --run-id demo-1 --bridge-db /tmp/qg-unification-stage2/qg_unification.sqlite --itir-db /tmp/qg-unification-stage2/itir.sqlite`
- Suggested one-command demo run (dry-run then persist):
  - `PYTHONPATH=. bash SensibLaw/scripts/run_qg_unification_to_tirc_capture.sh --run-id demo-1 --out-dir /tmp/qg-unification-stage2`

Planned follow-up:
- Persist canonical stage-2 outputs in SQLite (`qg_unification_runs`) whenever a run is built with `--db-path`, so cross-product adapters can resolve a stable, queryable record first and then consume artifact payloads.
- Then consume those records via `qg_unification_to_itir_db.py` using `qg_unification_runs` rows to populate an ITIR read-model table with deterministic upsert.
- Current follow-up now also includes deterministic TiRC/capture sink projection via
  `qg_unification_to_tirc_capture_db.py`, writing to dedicated `qg_tirc_capture_*` tables.

## 6) Follow-up

- Implementation is now staged at the boundary-bridge surface.
- Keep this contract as cross-project intent until external adapter approvals and
  JMD confirmation are explicit.
