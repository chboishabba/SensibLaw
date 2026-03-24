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
- For now this lane is a **documentation-only cross-project reference**.
  It is not implemented as runtime code in SensibLaw, but the contract terms are
  now the intended vocabulary if/when external formalization integration is
  planned.
