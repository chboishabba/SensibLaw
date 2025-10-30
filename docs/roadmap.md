# SensibLaw roadmap

This roadmap captures the focus areas we are driving in parallel with the
near-term deliverables outlined in the README. The objective is to ship a
deterministic, provenance-aware pipeline that plugs directly into Gremlin while
providing a streamlined viewer for legal reasoning outputs.

## 1. Provenance-first extraction stack (DX-101, DX-102)

- Publish `extract-stack/docker-compose.yml` that orchestrates Apache Tika,
  OCRUSREX, and a provenance sidecar under a non-root, no-egress posture.
- Implement `provenance/sidecar.py` + `provenance/schema.json` to coordinate
  text extraction, compute input/output hashes, and emit receipt JSON with tool
  versions, page maps, and container digests.
- Expose a `bin/extract_text` CLI wrapping the sidecar so upstream systems can
  request text with or without OCR and receive deterministic provenance bundles.
- Back the stack with integration tests (`tests/extract/test_extract_text.py`)
  that cover native and image-only PDFs and assert identical receipts across
  reruns.

## 2. Gremlin-aligned pipeline orchestration (ORCH-201 to ORCH-203)

- Document the Gremlin node contract in `docs/gremlin_node_contract.md`,
  clarifying inputs, outputs, `previous_results`, and provenance expectations for
  each stage.
- Provide `pipelines/sensiblaw_logic_graph.json` that Gremlin can import without
  code edits, defining the DAG from extraction through graph ingestion and
  result export.
- Build containerised nodes under `nodes/` with Make targets for
  `build-nodes`, `run-pipeline`, and `conformance`, ensuring the same artefacts
  run locally and inside Gremlin.
- Ship `adapters/gremlin_runner.py` capable of executing the pipeline against
  local Docker nodes, streaming receipts, and resuming from persisted
  `previous_results` payloads.

## 3. Standardised node execution contract (NODE-301)

- Introduce `sdk/node_base.py` that handles stdin/stdout JSON processing,
  structured logging, exit codes, and metrics for every node.
- Define shared schemas (`schemas/inputs.schema.json`,
  `schemas/outputs.schema.json`, `schemas/error.schema.json`) so nodes validate
  their contracts automatically.
- Update reference nodes (`normalise`, `token_classify`, `logic_tree`,
  `graph_ingest`) to consume the SDK, emit provenance metadata, and honour the
  shared schemas.
- Add `tests/nodes/test_contracts.py` with fixtures that confirm schema
  compliance, deterministic outputs, and consistent error handling across all
  nodes.

## 4. Reasoning viewer and embedding (UI-401, UI-402)

- Deliver `ui/streamlit_app.py` as a read-only viewer that loads pipeline result
  bundles, renders proof trees, highlights source text spans, and inspects
  knowledge graph neighbourhoods.
- Document embed mode via `ui/embed.md` and `ui/config.toml`, ensuring the
  Streamlit app runs headless and is iframe-safe for Gremlin panels.
- Describe the result bundle contract in `docs/result_bundle.md`, detailing
  `result.json`, per-node receipts, and highlight payloads to guarantee
  round-trippable job archives.
- Provide `gremlin/iframe.html` as a minimal wrapper that Gremlin can host to
  launch the Streamlit viewer with `?job_id=` routing.

## Cross-cutting principles

- Every node and service emits version metadata (`tool_name`, `semver`,
  `git_sha`, `image_digest`) so receipts can be traced and audited.
- Receipts for each pipeline step are stored under `run/receipts/` with
  timestamped filenames to support resumability and compliance reviews.
- Containers run as non-root with outbound network disabled by default (except
  where OCR models require downloads), aligning with the security posture agreed
  with Gremlin.
- Success metrics: <90s time-to-result on a 10-page PDF, deterministic reruns
  for identical inputs, and a one-click "Open Reasoning Viewer" experience for
  Gremlin operators.

