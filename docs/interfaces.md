# SensibLaw Interface Contract (Intended)

## Intersections
- Upstream evidence and transcripts from `tircorder-JOBBIE/` and `WhisperX-WebUI/`.
- Read-only core payload source for `SL-reasoner/`.
- Graph/legal artifacts consumed by `itir-ribbon/`, `StatiBaker/`, and ITIR tools.

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

### Channel D: Operations Ingress
- Input: CLI/UI/API commands for ingest, validation, and inspection.
- Constraint: commands must preserve deterministic substrate guarantees.
