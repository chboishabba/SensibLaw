# SensibLaw Interface Contract (Intended)

## Intersections
- Upstream evidence and transcripts from `tircorder-JOBBIE/` and `WhisperX-WebUI/`.
- Read-only core payload source for `SL-reasoner/`.
- Graph/legal artifacts consumed by `itir-ribbon/`, `StatiBaker/`, and ITIR tools.
- Owns the bounded Wikipedia revision monitor and history-aware pair-report lane
  used for live source-ingest evaluation and reviewer-support artifacts.

## Interaction Model
1. Ingest legal sources and evidence artifacts.
2. Produce deterministic spans, rules, and graph-ready structures.
3. Expose CLI/API/UI views without mutating provenance.
4. Publish structured outputs for downstream interpretation layers.

## Exchange Channels
### Channel A: Source Ingress
- Input: PDFs, structured legal text, and evidence-linked records.
- Output: normalized document/provision structures with stable identifiers.

### Channel B: Structural Egress
- Output: span-anchored text, logic trees, and extraction artifacts.
- Consumer: deterministic downstream processing and verification.

### Channel C: Graph/API Egress
- Output: graph entities/edges and route responses for external consumers.
- Consumer: `SL-reasoner/`, `itir-ribbon/`, and suite tooling.

### Channel E: Revision Monitor Egress
- Output: bounded Wikipedia revision run summaries, candidate-pair scores,
  section-delta summaries, pair reports, contested-region graph artifacts, and
  issue-packet refs.
- Consumer:
  - `SL-reasoner/` as read-only hypothesis input
  - `StatiBaker/` as observer-class external signal only
  - future suite tooling such as `fuzzymodo/` or `casey-git-clone/` by
    reference only
- Constraint:
  - no authority-write path out of this lane
  - no ontology mutation or Wikipedia/Wikidata edit automation

### Channel D: Operations Ingress
- Input: CLI/UI/API commands for ingest, validation, and inspection.
- Constraint: commands must preserve deterministic substrate guarantees.

## External Formalization Boundary Notes

- In 2026-03-24 the thread `QG Unification Proofs` (canonical ID
  `f20d9304aae805879a1f934b71443bd2c80ac19b`) introduced a proposed
  cross-project formalization boundary:
  `DA51 (empirical) -> SL (canonical structure) -> Agda (formal proof)`.
- That proposal states:
  - SL should not alter canonical proof or trace semantics.
  - SL provides structured representation, MDL compression, admissibility
    filtering, and dependency graph output.
  - A typed canonical boundary contract is preferred over ad hoc pipeline glue.
- Runtime bridge stubs exist in `src/qg_unification.py` as a staged prototype.
- Fixture-backed replay exists for the same boundary:
  - `SensibLaw/tests/fixtures/qg_unification/da51_valid_demo.json`
  - `SensibLaw/tests/fixtures/qg_unification/da51_invalid_short_exponents.json`
  - `SensibLaw/scripts/qg_unification_smoke.py --json-file ...`
- Stage-2 bridge execution now writes deterministic staged JSON artifacts and may also persist
  each run to SQLite with `--db-path` (`qg_unification_runs` table), giving
  adapters a durable first-class record key before consuming payload artifacts.
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
  - do not read this as granting proposal layers (`ZOS`-style retrieval or
    ranking) any proof or truth authority
- Stage-3 and Stage-3b adapters support `--dry-run` and persistence modes:
  - `SensibLaw/scripts/qg_unification_to_itir_db.py`
  - `SensibLaw/scripts/qg_unification_to_tirc_capture_db.py`
- `SensibLaw/scripts/run_qg_unification_to_tirc_capture.sh` runs stage-2 bridging, both
  adapter dry-runs, and both adapter persistence steps in one command.
- Stage-3b adapter path adds transcript/capture projection:
  `SensibLaw/scripts/qg_unification_to_tirc_capture_db.py` creates
  `qg_tirc_capture_runs`, `qg_tirc_capture_sessions`, and
  `qg_tirc_capture_utterances` rows in the destination DB.
- The cross-project lane remains non-authoritative and remains private pending
  explicit JMD confirmation of the remaining mapping context.
