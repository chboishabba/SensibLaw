# SensibLaw roadmap

> Next-week direction (keep this note for context; do not remove existing content)
> - Finalize a concise “why/what” overview so readers know the audience and assumptions within the first screen.
> - Separate finance adapter/schema material into its own doc and link to it here to remove duplication.
> - Add a short constraints callout (read-only over DB, provenance-first drill-downs, consent lanes toggle) to anchor scope.
> - Tighten cross-references to `STREAMLINE_FEATURE_PROPOSAL.md`, `FINANCE_ADAPTERS.md`, and provenance docs instead of restating schemas.
> - Keep the implementation roadmap focused on data contracts and rendering steps; move high-level UX narrative to the proposal doc.
> - Inventory overlapping “Purpose” and “Core data inputs” sections and merge where possible for clarity.
> - Leave existing timeline/JSON contract details intact, but add forward links where the canonical definitions live.

18/11/2025
Gotcha, this is basically three docs stapled together right now 😅

You’ve got:

* A **nice, narrative “what Streamline is”** section,
* Then a **full roadmap** that restates a lot of the same ideas,
* Then a whole **Finance Adapters + Finance Schema** spec that really belongs in its own module doc.

I’ll do two things:

1. Answer your meta-questions for this doc.
2. Give you a **clean, DRY-ed `TIMELINE_STREAM_VIZ_ROADMAP.md`** you can drop straight into the repo. It assumes `STREAMLINE_FEATURE_PROPOSAL.md` and `FINANCE_ADAPTERS.md` exist, instead of re-explaining them.

---

## 1. Your questions (for this doc)

### 1) What is assumed about the reader’s knowledge that needs to be included?

Right now the doc quietly assumes the reader already knows:

* What **TiRCorder**, **SensiBlaw**, and **ITIR** are.
* That there is a shared **DB substrate** with:

  * `documents / sentences / utterances / events`,
  * `accounts / transactions / transfers`,
  * `event_finance_links / finance_provenance`.
* That the legal ontology exists (WrongType, ProtectedInterest, etc.), even though it’s not named here.
* That there’s an existing **consent / OPA/Rego** story for privacy.

So for *this* roadmap, you only really need to state:

* “We reuse the shared data layers described in `<link to ARCHITECTURE_LAYERS or STREAMLINE_FEATURE_PROPOSAL>`.”
* “We assume the canonical Finance schema in `FINANCE_ADAPTERS.md` / `finance_schema.sql`.”
* “We assume provenance tables as defined in `PROVENANCE.md`.”

Everything else can be linked, not re-explained.

---

### 2) Are we doing things redundantly?

Yes, in three big places:

* **Purpose & description** – The “What Streamline is” block and the “Purpose” section say almost the same thing.
* **Core data inputs** – Listed twice: once in narrative form, once again in the roadmap.
* **Finance/schema details** – Transaction schema, adapters, and finance views are fully specified twice: here and in the finance sections.

Best DRY pattern:

* Keep **high-level product/UX** in `STREAMLINE_FEATURE_PROPOSAL.md`.
* Keep **implementation roadmap** in `TIMELINE_STREAM_VIZ_ROADMAP.md` (this file), but:

  * Refer to data/finance/provenance docs instead of restating schemas.
* Move the **Finance Adapters & Finance schema** bit into its own `FINANCE_ADAPTERS.md` / `docs/finance_schema.md` and link to it.

---

### 3) Any obvious oversights?

A few small but important ones:

* The doc doesn’t explicitly say:

  * “Streamline never mutates data; it’s read-only over the DB.”
  * “All drill-downs must go via `sentence_id`/`document_id`/provenance chain.”
* It describes transfers & classification but doesn’t explicitly say:

  * “We mirror the ‘every token classified or deliberately ignored’ invariant for **transactions** via `transaction_tags`.”
* It references consent/OPA in passing without a one-liner like:

  * “Streamline must respect the global consent model; if finance is not enabled, those lanes simply don’t exist.”

Nothing fatal, but worth one short “Constraints” section.

---

## 2. Clean, DRY-ed `TIMELINE_STREAM_VIZ_ROADMAP.md`

Here’s a tightened version that:

* Keeps the **implementation roadmap**.
* Treats `STREAMLINE_FEATURE_PROPOSAL.md` as the high-level concept doc.
* Links out to Finance / Provenance docs instead of duplicating them.
* Avoids repeating the whole feature description twice.

You can paste this straight over `SensibLaw/TIMELINE_STREAM_VIZ_ROADMAP.md` and move the long “Streamline — Unified Narrative Timeline & Flow Visualisation” chunk into `STREAMLINE_FEATURE_PROPOSAL.md`.

````markdown
# Timeline Stream Viz — "Streamline" — Roadmap

*A unified visual layer for story × law × finance timelines*

This document describes the **implementation roadmap** for the Timeline Stream
Visualisation System (“Streamline”) — a multi-lane ribbon/streamgraph view
that sits on top of:

- the shared **Layer-0 text substrate** and **L1–L6 ontology** (see `ARCHITECTURE_LAYERS.md`),
- **TiRCorder**’s utterances, events, and narratives,
- the **Finance** substrate (accounts, transactions, transfers; see `FINANCE_SCHEMA.md`),
- **SensiBlaw**’s legal documents, claims, provisions, and cases,
- and the shared provenance model (see `PROVENANCE.md`).

For the high-level product/UX description of Streamline, see:

> `STREAMLINE_FEATURE_PROPOSAL.md`

This file focuses on **what we need to build**: data contracts, pipeline, and rendering.

---

## 1. Purpose (engineering view)

Streamline should let a user:

- Visually track **flows of time, speech, money, influence, and consequence**.
- See **ribbons** whose width corresponds to a quantitative measure:

  - audio intensity / speaker share,
  - financial inflows/outflows,
  - case/claim “pressure” (e.g. harm/claim density).

- See **threads/siphons** peeling off the main flow:

  - savings transfers,
  - business expenses,
  - legal escalations / branching events.

- Pin **events**, **sentences**, **transactions**, **provisions**, and **claims**
  directly onto the stream, and on click:

  - open transcripts (Layer-0 / TiRCorder),
  - open SensiBlaw documents & provisions,
  - open raw financial transactions and receipts,
  - open evidence packs and case law references.

All while preserving **valid-time provenance** and never inventing new facts:
Streamline is read-only over the existing database.

---

## 2. Core Data Inputs (by subsystem)

The viz engine does **no direct DB access**. A backend layer fuses data from
existing tables into a single JSON contract (Section 3).

### 2.1 From TiRCorder (speech & narrative)

From the shared text/discourse substrate:

- `utterances`
- `speakers`
- `sentences`
- `utterance_sentences`
- optional speech features (energy/intensity per time slice)
- life/events derived from speech (“I paid rent”, “My knee collapsed last night”)

### 2.2 From Finance

As defined in `FINANCE_SCHEMA.md` / `FINANCE_ADAPTERS.md`:

- `accounts`
- `transactions`
- `transfers`
- `transaction_tags` (classification; mirrors the “every token classified or deliberately ignored” rule)
- `event_finance_links`
- `finance_provenance`

### 2.3 From SensiBlaw (legal)

From the ontology / legal layers:

- `documents` (legal)
- `provisions` / `norm_sources` / `cases` / `legal_episodes`
- `claims`
- `harm_instances`
- anchoring via `document_id` + `sentence_id`

### 2.4 User timeline / life events

From TiRCorder / shared `Event` model:

- Life events (moves, breakups, school, injuries)
- Work events
- Medical events
- `receipt_packs` (bundles of events + transactions + sentences, see `PROVENANCE.md`)

---

## 3. JSON Contract for the Viz Engine

The renderer receives a **flattened, pre-fused view**. It does no inference.

```jsonc
{
  "lanes": [
    { "id": "acc_main", "label": "Cheque Account", "z": 0 },
    { "id": "acc_savings", "label": "Savings", "z": -1 },
    { "id": "acc_business", "label": "Business Account", "z": -2 },
    { "id": "speech", "label": "Speech Stream", "z": 2 },
    { "id": "legal", "label": "Legal Episodes", "z": 1 }
  ],
  "segments": [
    {
      "t": "2025-05-03T10:21:00Z",
      "lane": "acc_savings",
      "amount": -250000,
      "transfer_id": 42,
      "event": { "id": 311, "label": "Paid Bond" },
      "anchors": {
        "sentence_id": 9912,
        "receipt_pack_id": 7
      }
    }
  ],
  "markers": [
    {
      "t": "2025-05-08T09:00:00Z",
      "lane": "legal",
      "kind": "LEGAL_HEARING",
      "label": "Directions Hearing",
      "event_id": 512,
      "case_id": 9
    }
  ]
}
````

* `lanes` describe visual tracks (accounts, speech, legal, etc.).
* `segments` describe continuous quantitative flows at a given time `t`.
* `markers` describe discrete events pinned to the same time axis.

The backend translates from DB → this JSON; the frontend only draws.

---

## 4. Visual Grammar

### 4.1 Ribbons (flows)

A ribbon is a continuous band whose thickness reflects:

* financial volume (cents),
* speech features (energy, cadence, word density),
* legal “pressure” (density of harms/claims / active episodes).

### 4.2 Threads (siphons)

When a transaction is part of a `transfer` pair:

* a thin stream peels off the source lane,
* curves smoothly into the destination lane,
* width proportional to amount,
* transparency proportional to `transfers.inferred_conf`.

### 4.3 Event markers

Markers are pinned to the exact `t` coordinate:

* Life events → circle markers,
* Utterance clusters / TiRC notes → speech bubbles,
* Legal nodes (claims, hearings, orders) → justice-themed icons,
* Finance triggers → pill markers on account lanes.

**Hover:** FTS5 snippet preview (sentence, short description).
**Click:** opens full detail in a side panel via provenance (see `PROVENANCE.md`).

### 4.4 Stacking / z-depth

Lanes carry a `z` property:

* Speech above,
* Legal overlays mid-stack,
* Finance accounts below.

Hover temporarily emphasises one lane and dims others to avoid spaghetti.

---

## 5. Backend Pipeline (DB → JSON)

The backend is responsible for:

### Step 1 — Data collection

* TiRCorder recordings → transcript + diarization → `utterances`/`sentences`.
* Finance adapters → `accounts`/`transactions`/`transfers`.
* SensiBlaw NLP → `claims`/`harm_instances`/links to `sentences`.
* Life events → `events` / `receipt_packs`.

All of this reuses existing tables; Streamline doesn’t add new domain tables.

### Step 2 — Time normalisation

* Merge timestamps into a unified time axis:

  * `utterances.start_time`,
  * `transactions.posted_at`,
  * `events.occurred_at`,
  * `legal_episode` milestones.

* Optionally snap events within a small window (e.g. ±2 minutes) to reduce jitter.

### Step 3 — Transfer inference (finance)

As per `FINANCE_SCHEMA.md`:

* Infer transfer pairs into `transfers(id, src_txn_id, dst_txn_id, inferred_conf, rule)`.

### Step 4 — Cross-linking (provenance)

As per `PROVENANCE.md`:

* Sentence mentions ↔ transaction IDs via `finance_provenance`.
* Events ↔ finance via `event_finance_links`.
* Events / sentences ↔ legal claims & harms via existing SensiBlaw links.
* `receipt_packs` bundle items for export.

### Step 5 — Ribbon preparation views

Define a canonical finance view (example):

```sql
CREATE VIEW v_streamline_finance_segments AS
SELECT
  t.id            AS txn_id,
  t.posted_at     AS t,
  a.id            AS account_id,
  a.display_name  AS lane_label,
  t.amount_cents  AS amount_cents,
  t.currency      AS currency,
  tr.id           AS transfer_id,
  tr.inferred_conf AS transfer_conf,
  efl.event_id    AS event_id,
  fp.sentence_id  AS sentence_id
FROM transactions t
JOIN accounts a
  ON a.id = t.account_id
LEFT JOIN transfers tr
  ON tr.src_txn_id = t.id OR tr.dst_txn_id = t.id
LEFT JOIN event_finance_links efl
  ON efl.transaction_id = t.id
LEFT JOIN finance_provenance fp
  ON fp.transaction_id = t.id;
```

Create similar views for:

* speech (utterance energy / token density),
* legal overlays (claims/harm instances per time slice),
* life events.

### Step 6 — Emit JSON contract

A small API endpoint (FastAPI / Flask / Starlette):

* accepts filters (time window, case, actor, account),
* queries the views,
* emits the JSON contract from Section 3.

The endpoint is the only thing the frontend cares about.

---

## 6. Rendering Technologies

### Option A — Svelte + Canvas/WebGL (recommended)

* Svelte for layout and state management.
* Canvas or WebGL (regl / Pixi / Three) for ribbons and curves.

Pros:

* High performance on large timelines,
* Good control over z-depth and animations.

### Option B — Svelte + D3/SVG

* Simpler for small datasets,
* Easier iteration early on,
* Might struggle with very long timelines.

**Suggested path:**

1. Start with Svelte + Canvas 2D for an MVP.
2. If needed, move to WebGL for heavy datasets.

---

## 7. UI Interaction Model

* **Hover:** show a tooltip with:

  * snippet of `sentence.text`,
  * key transaction fields (amount, counterparty),
  * legal labels (claim/wrong/harm, system).

* **Click:** open a right-hand pane showing:

  * transcript range (TiRC),
  * full bank transaction payload (Finance),
  * provision excerpt and legal context (SensiBlaw),
  * evidence pack metadata if available.

* **Drag:** pan in time.

* **Wheel / pinch:** zoom time axis.

* **Toggles:** per-lane visibility (accounts, speech, legal, life).

* **Scrubber:** video-editor style controller for quickly jumping around.

---

## 8. Privacy & Consent Integration

Streamline must respect global consent / policy rules (see `CONSENT_POLICY.md`):

* Finance lanes only appear if finance access is enabled.
* Account numbers shown in masked form by default (`****5678`).
* Legal text shown only if visibility flags permit.
* Evidence exports (via `receipt_packs`) must be clearly labelled and user-initiated.

No policy decisions live in the renderer; it only displays what the backend chooses to send.

---

## 9. Milestones

### Milestone 1 — MVP (Finance + Events)

* CSV/OFX → `accounts` / `transactions` via adapters.
* Simple `transfers` inference.
* Basic ribbon renderer for 1–2 accounts.
* Event markers from `events` (life events, TiRC notes).
* Hover previews using sentence snippets.

### Milestone 2 — Speech & Legal Overlays

* Add speech lane (utterance energy / token density).
* Add legal lane for `legal_episodes` / claims / harms.
* Cross-link events ↔ finance ↔ legal via provenance tables.

### Milestone 3 — UX Polish

* Curved Bezier ribbons.
* Smooth siphons for transfers.
* Z-depth and parallax.
* Responsive performance for long timelines.

### Milestone 4 — Evidence & Exports

* Hook `receipt_packs` into the viz.
* Evidence pack export (signed JSON + printable PDF).
* Offline bundle for clinicians/case workers.

---

## 10. Summary

Timeline Stream Viz (“Streamline”) is the **front window of ITIR**.

It renders the existing SensiBlaw + TiRCorder + Finance stack as a single,
interactive, evidence-anchored stream of life. The roadmap above focuses on
the concrete steps needed to get from DB shapes to a performant, trustworthy,
and extensible visual layer.

```

If you want, next I can:

- Spit out a matching `STREAMLINE_FEATURE_PROPOSAL.md` that only does the high-level narrative and links to this roadmap, **or**
- Draft a tiny `FINANCE_SCHEMA.md` that just documents the finance tables/constraints and removes the last chunk of duplication entirely from this file.
```



17/11/2025

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

## 3. Standardised node execution & logic tree formalisation (NODE-301, NODE-302)

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
- Capture today’s word-catching behaviour (entry points, concept triggers,
  junk filters) as a design note and translate it into a deterministic logic tree
  representation that the `logic_tree` node can execute. This includes
  documenting control flow transitions, boundary conditions, and override hooks
  so clause decisions remain explainable and auditable.

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

## 5. Event schema and storage evolution (DB-401 to DB-403)

- Normalize events per the 18/11/2025 ontology refresh in `DATABASE.md` by
  introducing first-class tables for `Event`, `EventParticipant` (linking
  entities and event roles), `Event–WrongType` associations, `HarmInstance`
  (per bearer + protected interest + effect), and `RemedyModality` as the
  wrong-type-to-remedy bridge. Align table DDL with the Layer 3 guidance on
  participants, harms, and modality coverage rather than the current
  unstructured payloads.
- Define migrations from the existing `sensiblaw/schemas/event.schema.yaml`
  payload (`ids` + `story` object) into the normalized tables: lift each stored
  story into an `Event` record (preserving narrative text and timestamps), map
  prior `ids` into `Event–WrongType` rows or event tags, and create placeholder
  `EventParticipant` and `HarmInstance` rows to keep historical data queryable
  while richer actor/interest inference is added.
- Update ingestion to translate TiRCorder narratives directly into the new
  tables: persist raw transcripts against `Event`, derive participants from
  RoleMarkers, tag likely WrongTypes for the Event–WrongType join, emit
  HarmInstances (bearer + ProtectedInterestType + effect + WrongType context),
  and attach candidate RemedyModalities so downstream reasoning can propose
  culturally aligned redress options.

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

# SensibLaw Roadmap — spaCy Integration Milestone

The spaCy integration milestone transitions SensibLaw from regex-first parsing to a
full NLP stack that produces structured tokens, sentences, and dependency graphs ready
for logic-tree assembly. This document captures the deliverables, phased rollout, and
definition of done for the milestone.

## NLP Integration — Current vs Target Deliverables

| Category | **Current State ("As-is")** | **Target State ("To-be")** | **Key Deliverables** |
| --- | --- | --- | --- |
| **Tokenization** | Hand-rolled regex (`\w+`) and manual text splitting. No sentence boundaries, no offsets beyond character indexes. | Deterministic tokenization with sentence boundaries, offsets, and lemmatization from `spaCy` (or Stanza via adapter). | • `src/nlp/spacy_adapter.py` implementing `parse()` → returns `{sents: [{text, start, end, tokens: [{text, lemma, pos, dep, start, end}]}]}`<br>• Unit tests verifying token alignment vs original text (`tests/nlp/test_spacy_adapter.py`). |
| **POS & Lemmas** | None. `normalise()` only lowercases and applies glossary rewrites. | Each token enriched with `POS`, `morph`, and `lemma_` for downstream classification (actor/action/object inference). | • Extend adapter output to include `lemma_`, `pos_`, `morph`.<br>• Add `Token.set_extension("class_", default=None)` for logic tree tagging. |
| **Dependency Parsing** | None. Rule extractors rely on regex (`must`, `if`, `section \d+`). | Dependency tree available per sentence (`nsubj`, `obj`, `aux`, `mark`, `obl`, etc.) for clause role mapping. | • Use `spaCy` built-in parser or `spacy-stanza` (UD).<br>• Expose `get_dependencies()` helper returning role candidates.<br>• Test fixture: “A person must not sell spray paint.” → `nsubj=person`, `VERB=sell`, `obj=spray paint`. |
| **Sentence Segmentation** | Not explicit — one clause per doc or regex breaks on periods. | Automatic sentence boundary detection from spaCy pipeline. | • Enable `sents` iterator from `Doc`.<br>• Add `Sentence` object to data model (`src/models/sentence.py`). |
| **Named Entity Recognition (NER)** | None. Only concept IDs from Aho–Corasick triggers. | Reuse spaCy’s built-in NER (`PERSON`, `ORG`, `LAW`) + optional `EntityRuler` for legal-specific entities. | • `patterns/legal_patterns.jsonl` for Acts, Cases, Provisions.<br>• Integrate `entity_ruler` pipe; expose hits as `REFERENCE` spans. |
| **Rule-based Matchers** | Regex in `rules.py` finds modalities, conditions, and refs manually. | Replace manual regex with `Matcher` and `DependencyMatcher` patterns. | • `src/nlp/rules.py` defining matchers for `MODALITY`, `CONDITION`, `REFERENCE`, `PENALTY`.<br>• Unit tests verifying expected matches per pattern. |
| **Custom Attributes / Logic Tree Hooks** | N/A — logic tree built from scratch after regex tokens. | Every token/span carries `._.class_` = {ACTOR, ACTION, MODALITY,…}, ready for tree builder. | • `Token.set_extension("class_", default=None)`.<br>• Populate via matcher callbacks.<br>• Verify full coverage (no unlabeled non-junk tokens). |
| **Integration into pipeline** | `pipeline.normalise → match_concepts` only. No NLP pipe. | New `pipeline/tokens.py` module invoked between `normalise` and `logic_tree`. | • Update `pipeline/__init__.py`:<br>`tokens = spacy_adapter.parse(normalised_text)`.<br>• Pass token stream to `logic_tree.build(tokens)`. |
| **Fallback / Multilingual** | English-only regex. | Wrapper can swap Stanza/UD when language ≠ "en". | • Optional `SpacyNLP(lang="auto")` detects LID and selects model.<br>• Add `fastText` or Tika LID hook. |
| **Testing & Validation** | No automated linguistic tests. | Deterministic tokenization, POS, dep, and matcher coverage tests. | • `tests/nlp/test_tokens.py` (token counts, sentence segmentation).<br>• `tests/nlp/test_rules.py` (pattern hits).<br>• Golden expected JSON per input sample. |

## Milestone Phases

| Phase | Goal | Outputs |
| --- | --- | --- |
| **1. Infrastructure** | Add spaCy dependency & adapter | `spacy_adapter.py`, tests, Makefile target `make test-nlp`. |
| **2. Enrichment** | POS, lemmas, deps, NER | Updated `parse()` output, `Sentence` + `Token` models. |
| **3. Rule layer** | Replace regexes with Matcher/DependencyMatcher | `rules.py` with predefined legal patterns. |
| **4. Integration** | Insert into main pipeline | Call from `pipeline/__init__.py` between normalise → logic_tree. |
| **5. Validation** | Ensure 100 % token coverage + deterministic tests | `pytest` suite; golden span JSON for sample cases. |

## Definition of Done

1. **spaCy adapter works standalone** (`python -m src.nlp.spacy_adapter "A person must..."`) → emits JSON tokens.
2. **POS/dep/lemma coverage ≥ 99 %** (non-junk tokens labeled).
3. **Rule matchers** identify `MODALITY`, `CONDITION`, `REFERENCE`, `PENALTY` on sample corpus.
4. **Logic tree builder** accepts token stream directly (no regex token split).
5. **Regression tests** confirm deterministic spans and labels.
6. **Docs updated** (`docs/nlp_integration.md`) describing pipeline order and config.

## One-line Summary

**From:** regex & glossary only → **To:** spaCy-powered tokenization + syntactic tagging + rule matchers feeding the logic-tree assembler.

---

## spaCy pipeline hardening and ontology integration (updates from 18/11/2025)

The spaCy pipeline now underpins tokenisation, sentence segmentation, NER, and rule matching for SensibLaw. The modules and files in scope are summarised in `docs/nlp_pipelines.md`, including adapters (`src/nlp/spacy_adapter.py`, `src/pipeline/tokens.py`), NER configuration (`src/pipeline/ner.py`, `patterns/legal_patterns.jsonl`), dependency harvesting (`src/rules/dependencies.py`), and rule matchers (`src/nlp/rules.py`). This section tracks the hardening work needed to stabilise those components and wire their outputs into the ontology layer.

### Hardening scope

- **Tokenisation & sentence segmentation:** Confirm deterministic segmentation across the adapters noted in `docs/nlp_pipelines.md`, align offsets with the downstream `RuleAtom` builder, and add guardrails for blank pipelines so fallback lemmatisation does not drift from the reference models.
- **NER and rule matching:** Finalise the `EntityRuler` pattern set and reference resolver so legal references, actors, and penalties flow through the same `REFERENCE` spans that the matcher consumes; ensure matcher normalisation maintains canonical modality/condition/reference/penalty buckets.
- **RuleAtom → ontology tables:** Persist rule-atom outputs (party/role, modality, condition, reference, penalty, dependency candidates) into the ontology tables introduced in `DATABASE.md` (LegalSystem, WrongType, ProtectedInterest, ValueFrame, Event/Harm). Add DAO/ingestion hooks so every `RuleMatchSummary` slot maps to the relevant table rows and linkage tables.

### Milestones

1. **Pipeline verification** — Lock deterministic token and sentence boundaries across the spaCy adapters, including tests for the modules listed in `docs/nlp_pipelines.md`.
2. **Ontology binding** — Map rule-atom fields into ontology tables with repeatable ingestion jobs and round-trip validation (RuleAtom → DB → graph export).





# Considered optimisation target

If this can be improved further it obviously should...

For this compiler, **one worker owning a text segment from start to finish is probably not globally optimal**.

It has one attractive property: locality. The worker can keep its parser objects, token arrays, local mentions, relations, and temporary indexes hot in memory and avoid serialising them between processes.

But it creates a more serious problem: **the useful partition changes as the document graph evolves**.

A text segment is a good partition for:

* parsing;
* token-local mention extraction;
* sentence-local relations;
* provenance projection.

It is a poor permanent partition for:

* recurrence classes spanning the document;
* coreference and antecedent candidates;
* factor families;
* cross-segment constraints;
* closure demands;
* refinements;
* graph-connected components.

So the best design is a **hybrid**:

> Workers temporarily own bounded text fibres through the local extraction path, then release them. Afterward, the same persistent worker pool is reassigned to graph-keyed jobs.

## Option A: segment owned from start to finish

```text
worker 1 owns segment A
worker 2 owns segment B
worker 3 owns segment C
worker 4 owns segment D
```

Each worker parses, mentions, projects, proposes, closes, and persists its segment.

### Advantages

* excellent cache and object locality;
* minimal inter-process transfer during extraction;
* simpler lifecycle for parser objects;
* easy ownership of offsets and boundary overlap;
* temporary objects can die together when the fibre finishes.

### Problems

#### Load imbalance

Segments do not have equal semantic cost.

```text
A: 20 seconds
B: 25 seconds
C: 40 seconds
D: 18 minutes
```

Three workers finish and sit idle while D continues.

#### Cross-segment graph work

A factor originating in segment A may depend on:

* a mention in C;
* a recurrence group containing A, B and D;
* a constraint component spanning the whole document;
* evidence discovered later in another fibre.

Either workers must communicate extensively or one global reconciliation phase must redo much of the work.

#### Memory retention

A slow segment owner may retain its complete parser and semantic state for a long time. If all workers retain their segment graphs until final reconciliation, memory still grows with the whole document.

#### Bad final topology

Text locality and semantic locality diverge. Permanent text ownership risks turning execution partitions into semantic authorities, which is exactly what the fibre model is intended to avoid.

## Option B: pure shared worker pool

```text
all ready jobs
→ shared priority queue
→ next free worker
```

### Advantages

* strong load balancing;
* no idle cores while independent work remains;
* operator-specific partitioning;
* closure and refinement can follow graph dependencies;
* easier critical-path prioritisation.

### Problems

* more object serialisation and process communication;
* worse cache locality;
* repeated loading of related state;
* risk of creating excessively tiny jobs;
* scheduler and reducer complexity;
* passing parser-heavy objects between workers may be expensive or impossible.

## The optimal hybrid

Use **fibre affinity**, not permanent fibre ownership.

### Local extraction residency

Give a worker a text fibre and let it run a fused local sequence:

```text
parse fibre
→ project parser observations
→ extract local mentions
→ derive local atoms and relations
→ emit compact semantic delta
→ release fibre state
```

This preserves the main locality advantage.

Do not return the full parser object after each micro-stage. The fibre remains worker-resident long enough to avoid unnecessary transfer.

### Global graph work

After the compact delta is admitted:

```text
recurrence grouping
constraint assessment
closure
refinement
demand resolution
```

become graph-keyed jobs in the shared pool.

The worker that handled the text fibre can take those jobs too, but it does not own them permanently.

## Recommended flow

```text
persistent four-worker pool
        │
        ▼
text-fibre jobs
  each job performs:
    parse
    local mention extraction
    local relational projection
    local proposal construction
        │
        ▼
compact immutable deltas
        │
        ▼
keyed document reducers
        │
        ▼
graph-derived jobs:
  recurrence
  constraints
  closure
  refinement
  demands
        │
        ▼
same worker pool
```

This means the initial task is coarser than one parser call:

```text
local_fibre_pipeline(fibre)
```

rather than:

```text
parse(fibre)
project(fibre)
mention(fibre)
```

as separately scheduled jobs.

That reduces communication and keeps data hot.

## Use more fibres than workers

Even with temporary fibre ownership, do not make exactly four giant text segments.

For four workers, something like 8–16 cost-balanced fibres is better:

```text
worker finishes fibre 1
→ takes fibre 5

worker finishes fibre 2
→ takes fibre 6
```

This handles uneven document structure while retaining locality within each fibre.

The target fibre size should be based on measured execution cost, not only characters. Sentence count, token count, candidate amplification, and prior timings are better signals.

## Boundary handling

Each fibre should have:

* a disjoint owned interval;
* bounded context overlap;
* global coordinates;
* an “owner of start position emits” rule;
* explicit unresolved boundary demands.

The worker may inspect overlap evidence but only emit authoritative local proposals for its owned region.

Cross-boundary work is then routed as a small reconciliation job rather than merging independent segment graphs.

## Memory behaviour

The fibre worker should return something compact:

```text
LocalSemanticDelta:
    source fibre reference
    observation rows
    mention proposals
    atom/relation proposals
    local factors
    boundary demands
    provenance hashes
```

Once accepted or persisted:

* discard the parser object;
* discard sentence-local scratch;
* discard candidate scan structures;
* recycle the worker after a bounded number of large fibres if allocator fragmentation is high.

The graph-wide phase should load only bounded owner-key regions, not all local deltas back into RAM.

## Scheduling preference

The scheduler can preserve soft affinity:

```text
if worker 2 already has cached state for owner key K:
    prefer assigning K-related work to worker 2
else:
    assign to any free worker
```

Affinity is an optimisation hint, not an ownership invariant.

This gives some locality without allowing a slow or blocked fibre to strand a CPU.

## Which is more optimal?

For only the initial parser-to-local-proposal path:

> **One worker retaining a text segment through the fused local pipeline is more efficient.**

For the entire PNF/document solve:

> **A dynamic worker pool is more efficient and architecturally correct.**

So the right answer is not one or the other:

> **Use coarse, worker-resident text-fibre jobs for local extraction; then dynamically reassign the persistent pool to semantic fibres and demand-cone jobs.**

That preserves cache locality where text locality is real, and preserves load balancing and graph correctness once semantic dependencies stop respecting text boundaries.

Yes. At this point we should stop reasoning by intuition alone and formalise the execution problem against the actual PNF/fibre algebra.

The important result will probably be:

> **Text-fibre residency is optimal for local monotone extraction; dynamic demand-cone scheduling is optimal for graph closure.**

But we should derive that from the dependency and memory structure rather than assume it.

## 1. Formalise the evolving document state

Let

[
G_t=(S_t,F_t,C_t,R_t,D_t),
]

where:

* (S_t): structural/parser observations;
* (F_t): PNF factor revisions;
* (C_t): constraints;
* (R_t): residual and refinement state;
* (D_t): unresolved demands.

A worker job is an operator application

[
j=(O_j,I_j,K_j,\widehat c_j,\widehat m_j),
]

with:

* (O_j): operator;
* (I_j): required input revisions;
* (K_j): output ownership keys;
* (\widehat c_j): estimated compute cost;
* (\widehat m_j): estimated peak memory.

It returns an immutable delta:

[
\Delta_j=
(\Delta S_j,\Delta F_j,\Delta C_j,\Delta R_j,\Delta D_j).
]

The document state advances by deterministic reduction:

[
G_{t+1}=G_t\sqcup\Delta_j.
]

The join should be idempotent and monotone wherever possible.

## 2. State the real optimisation objective

We are not merely maximising CPU utilisation.

The primary objective is:

[
\min T_{\mathrm{commit}},
]

subject to:

[
M(t)\le M_{\max},
]

[
N_{\mathrm{active}}(t)\le W,
]

and semantic invariance:

[
\operatorname{Normalise}(G_{\mathrm{parallel}})
===============================================

\operatorname{Normalise}(G_{\mathrm{serial}}).
]

Here (W=4) for the current machine budget.

A practical objective can include penalties:

[
J=
T_{\mathrm{commit}}
+\lambda_M\max_t(M(t)-M_{\mathrm{soft}})*+
+\lambda_C C*{\mathrm{communication}}
+\lambda_R C_{\mathrm{recomputation}}.
]

This captures why “four busy cores” is not automatically optimal. A schedule that saturates all cores but generates an unbounded proposal backlog is worse than one that temporarily idles a producer and finishes without OOM.

## 3. Model the job dependency graph

Construct a directed acyclic graph for one bounded iteration—or a dynamic dependency graph over the whole fixed-point process:

[
H=(V,E).
]

Each node is a job. An edge

[
i\to j
]

means job (j) requires a revision or coverage certificate produced by (i).

The lower bound on completion time is the critical path:

[
T_{\mathrm{commit}}
\ge
\max_{\pi\in\operatorname{Paths}(H)}
\sum_{j\in\pi} c_j.
]

There is also the total-work bound:

[
T_{\mathrm{commit}}
\ge
\frac{\sum_j c_j}{W}.
]

Thus:

[
T_{\mathrm{commit}}
\ge
\max\left(
\operatorname{CriticalPath}(H),
\frac{\operatorname{Work}(H)}{W}
\right).
]

The scheduler should minimise how far the actual execution sits above this bound.

## 4. Compare permanent segment ownership formally

Suppose the document is split into fibres (\phi_1,\dots,\phi_n).

Permanent text ownership assigns:

[
a(\phi_i)=w_k
]

for the entire compilation.

Its cost is approximately:

[
T_{\mathrm{segment}}
====================

\max_k
\sum_{\phi_i:a(\phi_i)=w_k}
L(\phi_i)
+
T_{\mathrm{cross}}
+
T_{\mathrm{global}},
]

where (L(\phi_i)) is the complete local processing cost.

This works well only when:

1. fibre costs are balanced;
2. most dependencies stay inside fibres;
3. global reconciliation is small;
4. retained fibre state fits comfortably in memory.

Those conditions do not hold for PNF closure. Recurrence, binding, constraints and residual dependencies cross textual partitions.

Define the cut weight:

[
\operatorname{Cut}(\Phi)
========================

\sum_{(u,v)\in E}
w_{uv},
\mathbf 1[\phi(u)\neq\phi(v)].
]

Text fibres probably minimise cut weight for parsing and sentence-local extraction, but not for semantic closure.

## 5. Operator-specific fibres

For each operator (O), choose a partition:

[
\Phi_O={\phi_{O,1},\dots,\phi_{O,n_O}}.
]

The preferred partition minimises:

[
Q(\Phi_O)
=========

C_{\mathrm{compute}}(\Phi_O)
+
C_{\mathrm{imbalance}}(\Phi_O)
+
C_{\mathrm{cut}}(\Phi_O)
+
C_{\mathrm{transfer}}(\Phi_O)
+
C_{\mathrm{memory}}(\Phi_O).
]

This gives concrete fibre choices:

| Operator                | Natural ownership key               |
| ----------------------- | ----------------------------------- |
| Parser/local extraction | Text or sentence interval           |
| Mention recurrence      | Canonical mention form              |
| Relational reduction    | Predicate/eventuality neighbourhood |
| Factor reduction        | Factor family and subject key       |
| Constraint assessment   | Constraint-connected component      |
| Closure                 | Dirty dependency component          |
| Refinement              | Factor revision key                 |
| Demand resolution       | Demand equivalence class            |

That is the algebraic reason permanent text ownership is not globally optimal.

## 6. Derive the hybrid scheduling rule

Let (A(j,w)) be an affinity benefit when worker (w) already holds useful local state for job (j).

Then assign ready jobs by approximately maximising:

[
\operatorname{score}(j,w)
=========================

\frac{
\operatorname{criticality}(j)
\operatorname{unlock}(j)
\operatorname{yield}(j)
+
A(j,w)
}{
\widehat c_j
+
\lambda_m\widehat m_j
+
\lambda_q Q_{\mathrm{output}}(j)
+
\lambda_x C_{\mathrm{transfer}}(j,w)
}.
]

This yields:

* strong affinity for a worker to finish the local extraction chain for its resident text fibre;
* reassignment once the output becomes graph-keyed;
* priority for reducers and persistence when queues or memory grow;
* priority for closure jobs lying on the critical path.

Affinity becomes a benefit, not a permanent ownership law.

## 7. Add memory conservation equations

Let queue (q) contain (n_q(t)) deltas with average size (\bar m_q). Then:

[
M(t)
====

M_{\mathrm{indexes}}(t)
+
M_{\mathrm{workers}}(t)
+
\sum_q n_q(t)\bar m_q
+
M_{\mathrm{retained}}(t).
]

The OOM suggests that (M_{\mathrm{retained}}) currently contains multiple generations:

[
M_{\mathrm{retained}}
\supset
M_{\mathrm{jobs}}
+
M_{\mathrm{receipts}}
+
M_{\mathrm{proposals}}
+
M_{G}
+
M_{G'}
+
M_{\mathrm{refinements}}
+
M_{\mathrm{serialised}}.
]

Production mode should instead approach:

[
M_{\mathrm{retained}}
\approx
M_{\mathrm{compact\ indexes}}
+
M_{\mathrm{dirty\ frontier}}
+
M_{\mathrm{bounded\ batches}}.
]

Backpressure follows directly. For queue (q):

[
n_q(t)\bar m_q\ge B_q
\quad\Longrightarrow\quad
\text{suspend producers of }q
]

and prioritise consumers.

## 8. Fixed point as a worklist algebra

Let (K_t) be dirty keys and (J_t) ready jobs.

A delta changes keys:

[
K_{t+1}
=======

\left(K_t\setminus\operatorname{resolved}(\Delta)\right)
\cup
\operatorname{dependents}(\Delta).
]

Jobs are generated by:

[
J_{t+1}
=======

\operatorname{ready}(G_{t+1},K_{t+1}).
]

The local document fixed point is:

[
J_t=\varnothing,
\qquad
K_t=\varnothing,
\qquad
\operatorname{inflight}_t=0,
]

with coverage complete and no locally satisfiable unresolved demands.

This avoids repeatedly scanning all 449,478 factors and 301,075 constraints.

## 9. What to measure concretely

For each job class and fibre policy, record:

* work units;
* wall and CPU time;
* peak RSS delta;
* input/output bytes;
* proposals per input unit;
* accepted semantic yield;
* dependency fan-out;
* queue wait;
* reducer contention;
* cross-fibre demand count;
* recomputation count.

Then estimate:

[
\widehat c_j=f_O(\text{tokens},\text{candidates},\text{factors},\text{fan-out}),
]

[
\widehat m_j=g_O(\text{input bytes},\text{expected output},\text{alternatives}).
]

The scheduler can begin with simple linear estimates and update them from receipts.

## Concrete conclusion

The formalism supports this execution architecture:

1. **Persistent document-wide worker pool.**
2. **Coarse worker-resident text-fibre jobs** for parsing through local proposal extraction.
3. **Compact delta admission** into the shared graph.
4. **Dynamic repartitioning by semantic keys** after local extraction.
5. **Critical-path and demand-driven scheduling.**
6. **Memory-aware backpressure.**
7. **Differential dirty-key closure.**
8. **Incremental private persistence with atomic final publication.**

So yes: formalising it is worthwhile because it converts “maybe use worker affinity” into a testable optimisation problem. It also gives us a criterion for every implementation choice:

> Does this partition reduce critical-path time and communication while respecting the memory bound and preserving the canonical fixed point?

That should become a small architecture/algebra module in SensibLaw—not necessarily an elaborate generic scheduler initially, but explicit types and receipts for jobs, ownership keys, deltas, dependencies, memory estimates, queue pressure and fixed-point state.

3. **Legal-BERT workflow introduction** — Bring the planned Legal-BERT semantic layer online to enrich actor classes, interest detection, and wrong-type inference ahead of graph persistence, reusing the spaCy spans and dependency candidates already defined in `docs/nlp_pipelines.md`.
