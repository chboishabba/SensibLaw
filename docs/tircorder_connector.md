# TiRCorder connector contract

This document defines how TiRCorder connectors hand data to SensiBlaw. It covers
transport options, the ingestion hooks SensiBlaw will call, the normalized
payload shape, validation expectations, and examples for both file-based drops
and HTTP APIs.



* ❗ SensiBlaw handles *all* NLP, semantic extraction, concept mapping, rule atoms, ontology linking, contradiction detection, etc.
* ✔ TiRCorder handles *only* capture, diarisation, transcription, segmentation, provenance, and emitting structured utterance/events.
* ❗ The draft you pasted was actually the *legal-graph ingestion* contract — not the TiRCorder one.
* ✔ Below is the **correct** contract specifically for TiRCorder’s role in ITIR → SL ingestion.

---

# ✅ **TiRCorder → SensiBlaw Connector Contract**

This contract defines precisely what **TiRCorder must emit**, how it does so, and how **SensiBlaw consumes** these packets.
It is intentionally scoped to match the ITIR/SensiBlaw architecture:

* TiRCorder = **recording + diarisation + transcription + provenance**
* SensiBlaw = **text substrate + NLP + ontology + actors + events + legal logic**

Everything below keeps that separation strict.

---

# 1. Overview

A TiRCorder connector hands structured recordings into SensiBlaw using a **NormalizedTiRCEventPacket**.
This packet:

* contains *zero* semantics
* contains *zero* NLP preprocessing
* contains *zero* ontology logic
* carries only **utterances**, **timestamps**, **speaker labels**, **provenance**, **audio hashes**, and optional **audio analytics**

SensiBlaw then:

* creates documents, sentences, tokens
* resolves actors
* attaches sentences to events
* performs NLP, semantic triggers, concept detection
* integrates into Streamline/Timeline
* performs rule extraction, harm/wrong detection, etc.

---

# 2. Transport Options

TiRCorder connectors may deliver packets via either:

## **A. Local file drops (preferred for backfills)**

* Write to: `data/tircorder/<connector_name>/`
* Format: `*.ndjson` or single JSON file
* Each line/file = one `NormalizedTiRCEventPacket`

SensiBlaw calls:

```python
load_from_path(path: Path) -> NormalizedTiRCEventPacket
```

Atomic write requirement:

* Write to `tmpfile`
* Then rename to final name

Prevents partial reads.

---

## **B. HTTP ingestion (for live/streaming feeds)**

POST to:

```
POST /api/ingestion/tircorder
```

GET healthcheck:

```
GET /api/ingestion/tircorder/health
```

Cursor-based pagination for streamers:

```python
fetch_since(cursor: Optional[str]) -> NormalizedTiRCEventPacket
```

Auth: Bearer token.

---

# 3. The **Normalized TiRC Event Packet** (Final Schema)

This is the canonical payload **TiRCorder MUST emit**.

⚠️ **No NLP tokens, no semantic labels, no concepts, no edges, no nodes.**
These belong to SensiBlaw.

---

# ✅ **TiRCorder Payload Schema (final)**

```json
{
  "connector": "tircorder",
  "batch_id": "2025-02-15T12:33:44Z",
  "ingested_at": "2025-02-15T12:33:44Z",

  "source": {
    "origin": "tircorder-device-id",
    "contact": "device-owner-or-operator"
  },

  "cursor": null,
  "next_cursor": null,

  "sessions": [
    {
      "session_id": "sess-4412",
      "device_id": "ABC-123",
      "started_at": "ISO-8601",
      "ended_at":   "ISO-8601",
      "audio_sha256": "hash-of-raw-audio-file",

      "utterances": [
        {
          "utterance_id": "utt-1",
          "start": "ISO-8601",
          "end":   "ISO-8601",

          "speaker_label": "SPEAKER_1",
          "speaker_confidence": 0.94,

          "text": "full utterance text",

          "words": [
            { "w": "hello", "start": 1.23, "end": 1.44, "conf": 0.98 }
          ],

          "silence_before": 0.8,
          "silence_after": 0.3,
          "energy": 0.62,

          "sentence_splits": [
            { "char_start": 0, "char_end": 22 },
            { "char_start": 23, "char_end": 32 }
          ]
        }
      ],

      "segments": [
        { "start": 0.0, "end": 2.1, "type": "speech" },
        { "start": 2.1, "end": 4.5, "type": "silence" }
      ],

      "analytics": {
        "emotion": "neutral",
        "sentiment": 0.1,
        "pitch_contour": [],
        "vad_energy": []
      }
    }
  ],

  "raw_payload": {}
}
```

---

# 4. What TiRCorder MUST Emit

### Required:

| Field                                | Why                                             |
| ------------------------------------ | ----------------------------------------------- |
| **audio hash**                       | provenance & tamper-evidence                    |
| **timestamps (segment & utterance)** | timeline anchoring                              |
| **utterance text**                   | SL creates sentences/tokens                     |
| **speaker_label**                    | actor alias resolution                          |
| **device/session metadata**          | identity + chain-of-custody                     |
| **sentence_splits**                  | sentence table seeding                          |
| **word timings**                     | improves timeline overlay, FTS snippet accuracy |
| **segments (speech/silence)**        | Streamline ribbon overlays                      |

---

# 5. What TiRCorder MAY Emit

Optional enhancements:

* VAD energy time series
* Pitch/emotion
* Word-level confidence
* Noise events
* Structured markers (cough, bang, door slam)
* Overlapping speakers (if diariser supports it)

---

# 6. What TiRCorder MUST NOT Emit

❌ NLP tokens
❌ lemmas
❌ POS tags
❌ dependency labels
❌ concept triggers
❌ legal edges or nodes
❌ rule atoms
❌ harm/wrong classifications
❌ actor canonical IDs
❌ event types beyond basic “utterance”

These belong **exclusively** to SensiBlaw.

---

# 7. How SensiBlaw Consumes This Payload

SensiBlaw converts the above into:

| SensiBlaw Table    | Data from TiRCorder             |
| ------------------ | ------------------------------- |
| `documents`        | session transcript text         |
| `sentences`        | from `sentence_splits`          |
| `tokens`           | SensiBlaw NLP                   |
| `utterances`       | from `utterances[*]`            |
| `events`           | event_kind=SPEECH               |
| `event_provenance` | timestamps + audio hash         |
| `actor_aliases`    | using speaker_label             |
| `audio_features`   | from analytics                  |
| `timeline_events`  | mapped from utterance start/end |

This locks perfectly into:

* Streamline ribbons
* Event overlays
* Cross-linking with finance
* Graph nodes (event nodes)
* Claims/case analysis
* Harm/wrong inference
* ReceiptPack generation

---

# 8. Validation Rules (Final)

SensiBlaw enforces:

1. **connector**, **batch_id**, **ingested_at**, **sessions** required
2. utterances require at minimum:

   * `utterance_id`, `start`, `end`, `text`, `speaker_label`
3. all timestamps ISO-8601
4. audio hashes must be hex SHA-256
5. word timings must be monotonic
6. sentence_splits must map to character offsets inside `text`

All validation happens before any DB write.

---

# 9. Idempotency

* Same `{connector,batch_id}` + same content → **no-op**
* Same batch_id + *different* content → **409** error
* SensiBlaw merges speaker labels across batches
* SensiBlaw deduplicates event anchors by `(session_id, utterance_id)`

---

# 10. Sample `.ndjson`

```jsonl
{"connector":"tircorder","batch_id":"2025-02-10T11:12:33Z","ingested_at":"2025-02-10T11:12:33Z","source":{"origin":"android-device","contact":"user@example"},"sessions":[{"session_id":"sess-99","device_id":"XYZ","started_at":"2025-02-10T10:00:00Z","ended_at":"2025-02-10T11:00:00Z","audio_sha256":"abc123...","utterances":[{"utterance_id":"utt-1","start":"2025-02-10T10:10:11Z","end":"2025-02-10T10:10:13Z","speaker_label":"S1","text":"I can't keep doing this.","words":[{"w":"I","start":11.1,"end":11.2},{"w":"can't","start":11.2,"end":11.5}],"sentence_splits":[{"char_start":0,"char_end":20}]}]}]}
```

---

# 11. Summary (TL;DR)

**TiRCorder emits only:**

* audio metadata
* timestamps
* utterances
* sentence boundaries
* diarisation labels
* audio analytics

**SensiBlaw handles everything semantic**, including:

* NLP
* actor mapping
* event creation
* claims
* harms
* wrongs
* rule atoms
* graphs
* timeline visualisation

This ensures **clean separation**, high auditability, and full reproducibility.



## Transport options

Two transport mechanisms are supported. Connectors should choose the one that
best matches their source, but both yield the same normalized payload shape.

1. **Local files (preferred for bulk backfills)**
   - **Location**: staged under `data/tircorder/<connector_name>/` by default.
   - **Format**: newline-delimited JSON (`.ndjson`) or plain JSON files carrying
     a single `NormalizedTircorderPayload` object (schema below).
   - **Entry point SensiBlaw calls**: `sensiblaw.connectors.tircorder.load_from_path(path: Path) -> NormalizedTircorderPayload`.
   - **Polling cadence**: SensiBlaw can be configured to scan the staging
     directory on a schedule; connectors should emit atomic files (write to a
     temp name then rename) to avoid partial reads.

2. **HTTP API (for streaming or frequently updated feeds)**
   - **Endpoint shape**: `POST /api/ingestion/tircorder` accepts the normalized
     payload; `GET /api/ingestion/tircorder/health` is used for liveness checks.
   - **Entry point SensiBlaw calls**: `sensiblaw.connectors.tircorder.fetch_since(cursor: Optional[str]) -> NormalizedTircorderPayload`.
   - **Auth**: Bearer tokens supplied via `Authorization: Bearer <token>`.
   - **Pagination**: API connectors must honour `cursor` values returned by
     SensiBlaw and return `next_cursor` when more data remains.

## Ingestion entry points

SensiBlaw expects the following callable surfaces; connector authors should
provide thin adapters that fulfil them:

- `load_from_path(path: Path) -> NormalizedTircorderPayload`
  - Invoked for file drops. Should parse and validate a single payload from
    disk and raise `ValueError` when validation fails.
- `fetch_since(cursor: Optional[str]) -> NormalizedTircorderPayload`
  - Invoked for API connectors. Should return the next page of data starting at
    the supplied cursor (or the first page when `cursor` is `None`).
- `iter_batches(source: str | Path) -> Iterable[NormalizedTircorderPayload]`
  - Optional helper letting SensiBlaw stream multiple batches from a large file
    or paginated API; each yielded batch must independently satisfy validation
    rules and idempotency contracts.

Downstream, SensiBlaw will call `src.graph.tircorder.build_tircorder_edges`
with the normalized edges, so connectors must keep edge `type`, `source`, and
`target` aligned with `NodeType` and `EdgeType` values defined in
`src/graph/models.py`.

## Normalized payload (Schema)

Every connector emits a `NormalizedTircorderPayload` with the fields below. All
fields are required unless marked optional.

```json
{
  "connector": "<machine-readable connector name>",
  "batch_id": "<stable id for this drop>",
  "ingested_at": "<ISO-8601 timestamp>",
  "source": { "origin": "<human source name>", "contact": "<email|url>" },
  "cursor": "<opaque pointer used for paging>",
  "next_cursor": "<opaque pointer; omit when no more data>",
  "nodes": [
    {
      "identifier": "<stable id>",
      "type": "case|concept|provision|document|extrinsic|judge_opinion|principle|test_element|statute_section|issue|order",
      "title": "<display label>",
      "date": "<YYYY-MM-DD>",
      "metadata": { "court": "<court>", "jurisdiction": "<ISO code>", "citation": "<neutral citation>", "summary": "<optional string>" },
      "cultural_flags": ["<flag>"],
      "consent_required": false,
      "court_rank": 3,
      "panel_size": 5,
      "role": "<extrinsic role>",
      "stage": "<extrinsic stage>"
    }
  ],
  "edges": [
    {
      "type": "articulates|has_element|applies_to|interprets|controls|cites|applies|distinguishes|follows|overrules",
      "source": "<node identifier>",
      "target": "<node identifier>",
      "metadata": { "evidence": "<headnote|manual tagging>" },
      "date": "<YYYY-MM-DD>",
      "weight": 1.0,
      "event_link": { "event_id": "<timeline event uuid>", "sentence_id": "<nlp span id>", "pack_id": "<upstream packet id>" }
    }
  ],
  "events": [
    {
      "event_id": "<timeline event uuid>",
      "label": "<short description>",
      "occurred_at": "<ISO-8601 timestamp>",
      "summary": "<longer narrative>",
      "references": ["<source url or citation>"]
    }
  ],
  "attachments": {
    "documents": [
      {
        "identifier": "<doc id matching a node>",
        "body": "<full text>",
        "metadata": {
          "jurisdiction": "<ISO code>",
          "citation": "<citation>",
          "date": "<YYYY-MM-DD>",
          "court": "<court>",
          "jurisdiction_codes": ["<code>"]
        }
      }
    ]
  }
}
```

### Field notes

- `connector`, `batch_id`, and `ingested_at` let SensiBlaw deduplicate and
  track provenance.
- `nodes.type` must match a `NodeType` enum value; extra fields such as
  `court_rank`/`panel_size` (for cases) or `role`/`stage` (for extrinsic entries)
  are honoured when the node type supports them.
- `edges.type` must match an `EdgeType` enum value. `event_link` is how
  TiRCorder objects connect to Streamline timeline events and NLP sentence
  anchors.
- `attachments.documents[*]` mirrors the `Document`/`DocumentMetadata` schema
  described in `docs/schema.md` and is the place to ship full text alongside
  graph nodes.

## Sample payloads

### Local file drop (`.ndjson`)

Each line is a complete payload. Example for a single case/concept pair linked
by TiRCorder predicates:

```json
{"connector": "nsw_reports_csv", "batch_id": "2024-05-15T00:00:00Z", "ingested_at": "2024-05-15T00:00:00Z", "source": {"origin": "NSW Reports export", "contact": "data@reports.example"}, "cursor": null, "next_cursor": null, "nodes": [{"identifier": "Case#Smith2020", "type": "case", "title": "Smith v Jones", "date": "2020-02-14", "metadata": {"court": "NSWCA", "jurisdiction": "AU-NSW", "citation": "[2020] NSWCA 12"}, "court_rank": 2, "panel_size": 3}, {"identifier": "Concept#DutyOfCare", "type": "concept", "title": "Duty of care", "date": null, "metadata": {"summary": "Caparo duty of care test"}}], "edges": [{"type": "articulates", "source": "Case#Smith2020", "target": "Concept#DutyOfCare", "metadata": {"evidence": "majority reasons"}, "weight": 1.0, "event_link": {"event_id": "evt-1", "sentence_id": "s-104", "pack_id": "bundle-22"}}], "events": [{"event_id": "evt-1", "label": "Appeal decided", "occurred_at": "2020-02-14T12:00:00Z", "summary": "Court of Appeal articulates duty of care"}], "attachments": {"documents": [{"identifier": "Case#Smith2020", "body": "<full text here>", "metadata": {"jurisdiction": "AU-NSW", "citation": "[2020] NSWCA 12", "date": "2020-02-14", "court": "NSWCA", "jurisdiction_codes": ["AU-NSW"]}}]}}
```

### API request/response

Request to `POST /api/ingestion/tircorder` with bearer auth:

```http
POST /api/ingestion/tircorder HTTP/1.1
Authorization: Bearer <token>
Content-Type: application/json

{
  "connector": "uk_supreme_api",
  "batch_id": "batch-4481",
  "ingested_at": "2024-05-20T00:00:00Z",
  "source": {"origin": "UKSC feed", "contact": "ops@uksc.example"},
  "cursor": "page-3",
  "next_cursor": "page-4",
  "nodes": [
    {"identifier": "Case#UKSC-2024-12", "type": "case", "title": "R v Brown", "date": "2024-04-12", "metadata": {"court": "UKSC", "jurisdiction": "GB", "citation": "[2024] UKSC 12"}, "court_rank": 5},
    {"identifier": "Provision#OAPA-s47", "type": "provision", "title": "Offences Against the Person Act 1861 s47", "metadata": {"jurisdiction": "GB"}},
    {"identifier": "Concept#MensRea", "type": "concept", "title": "Mens rea", "metadata": {"summary": "mental element"}}
  ],
  "edges": [
    {"type": "interprets", "source": "Case#UKSC-2024-12", "target": "Provision#OAPA-s47", "metadata": {"evidence": "syllabus"}, "weight": 0.8, "event_link": {"event_id": "evt-99", "sentence_id": "s-22", "pack_id": "api-page-3"}},
    {"type": "applies_to", "source": "Concept#MensRea", "target": "Provision#OAPA-s47", "metadata": {"source": "majority"}}
  ],
  "events": [{"event_id": "evt-99", "label": "Judgment released", "occurred_at": "2024-04-12T09:00:00Z", "summary": "UKSC clarifies mental element"}]
}
```

Success response from SensiBlaw:

```json
{
  "status": "accepted",
  "batch_id": "batch-4481",
  "ingested_nodes": 3,
  "ingested_edges": 2,
  "next_cursor": "page-4",
  "duplicates_skipped": ["Case#UKSC-2024-12"],
  "errors": []
}
```

## Validation rules

SensiBlaw enforces the following before persisting a payload:

1. **Required fields**: `connector`, `batch_id`, `ingested_at`, `source`, `nodes`, and `edges` must be present. `events` and `attachments` are optional but, when provided, must be arrays/objects (not `null`).
2. **Enum conformance**: `nodes[*].type` must be one of `NodeType` values and
   `edges[*].type` must be one of `EdgeType` values in `src/graph/models.py`.
3. **Referential integrity**: every edge `source` and `target` must resolve to an
   existing node in the same payload or a prior batch from the same connector.
4. **Dates**: `date` and `ingested_at` must be ISO-8601; omit or use `null` if
   unknown rather than placeholder strings.
5. **Weights**: `weight` defaults to `1.0` and must be positive.
6. **Document body alignment**: any entry in `attachments.documents` must refer
   to a `nodes.identifier` and include the `metadata` fields mandated by
   `DocumentMetadata` (`jurisdiction`, `citation`, `date`, `court`, and
   `jurisdiction_codes`).
7. **Event links**: when `event_link` is supplied on an edge, the referenced
   `event_id` must appear in the `events` array.

Validation failures surface as `400` responses for API calls or raised
`ValueError` for file loads; no partial writes occur.

## Idempotency and batching

- **Stable identifiers**: `nodes.identifier` and `edges` (via the
  `source`+`target`+`type` triple plus optional `event_link`) must be stable
  across retries. SensiBlaw treats these as upserts per `connector` and
  `batch_id`.
- **Batch scope**: a payload is the minimal batch unit. SensiBlaw will ingest or
  reject an entire payload atomically.
- **Idempotent replays**: re-sending the same `batch_id` with identical content
  is a no-op; differing content under the same `batch_id` triggers a `409` for
  APIs or a validation failure for file loads.
- **Pagination**: connectors using `fetch_since` should include `next_cursor`
  until exhausted. SensiBlaw will pass the last confirmed `next_cursor` on
  subsequent calls to avoid duplicate ingestion.
- **Dedup hints**: include `metadata.checksum` at the payload level when
  available so the platform can short-circuit duplicate batches early.

Connector authors who adhere to these contracts can expect predictable ingestion
behaviour, clear validation feedback, and aligned TiRCorder outputs that map
directly onto SensiBlaw’s graph and document schemas.
