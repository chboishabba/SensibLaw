# Timeline Stream Viz — "streamline" — Roadmap

*A unified visual layer for story × law × finance timelines*

This document describes the roadmap for building the **Timeline Stream Visualisation System** — a multi-lane ribbon/streamgraph view that merges:

* **TiRCorder** (recordings, utterances, events)
* **Finance layer** (accounts, transactions, transfers)
* **SensiBlaw** (legal documents, claims, provisions, cases)
* **Life events + narrative anchors**

This is the main UX layer of ITIR:
A **single, coherent timeline** where the user can see *what happened*, *what was said*, *how money moved*, and *what legal/structural frames apply* — all with provenance.

---

## 1. Purpose

The system should let a user:

* Visually track **flows of time, speech, money, influence, and consequence**.
* See **ribbons** whose width corresponds to quantity/importance:

  * Audio intensity, speaker share, financial inflows/outflows, case load, etc.
* See **threads/siphons** peeling off the main flow:

  * Savings transfers, business expenses, legal escalations, branching events.
* Pin **events**, **sentences**, **transactions**, **provisions**, and **claims** directly onto the stream.
* Click anything to open linked:

  * Transcripts (Layer 0)
  * Documents (SensiBlaw)
  * Evidence Packs
  * Financial transactions
  * Transfer ribbons
  * Case law or statutory references

All while preserving **valid-time provenance**.

---

## 2. Core Data Inputs

### 2.1 From TiRCorder

* `utterances`
* `speakers`
* `sentences`
* `utterance_sentences`
* Energy/intensity per time slice (optional)
* Events derived from speech (“I paid rent”, “My knee collapsed last night”)

### 2.2 From Finance adapters

* `accounts`
* `transactions`
* `transfers`
* `event_finance_links`
* `finance_provenance`

### 2.3 From SensiBlaw

* `documents` (legal)
* `provisions` / `norm sources` / `cases`
* `claims`
* `events` / `harm instances`
* Anchoring via document + sentence IDs

### 2.4 User timeline events

* Life events (moves, breakups, school, injuries)
* Work events
* Medical events
* Receipts packs

---

## 3. JSON Contract for the Viz Engine

Renderer will receive a **flattened, pre-fused view**.

```json
{
  "lanes": [
    {
      "id": "main_income",
      "label": "Cheque Account",
      "z": 0,
      "color": "#6C5CE7"
    },
    {
      "id": "savings",
      "label": "Savings",
      "z": -1,
      "color": "#00CEC9"
    },
    {
      "id": "business",
      "label": "Business Account",
      "z": -2,
      "color": "#0984E3"
    },
    {
      "id": "speech",
      "label": "Speech Stream",
      "z": 2,
      "color": "#E84393"
    }
  ],
  "segments": [
    {
      "t": "2025-05-03T10:21:00",
      "lane": "savings",
      "amount": -250000,
      "transfer_id": 42,
      "event": { "id": 311, "label": "Paid Bond" },
      "anchors": { "sentence_id": 9912 }
    }
  ]
}
```

The renderer does **no inference** — it only draws.

---

## 4. Visual Grammar

### 4.1 Ribbons (Flows)

A ribbon is a continuous band whose thickness reflects:

* Financial volume (cents)
* Speech feature (energy, cadence)
* Case pressure (claims/harm entities over time)

### 4.2 Threads (Siphons)

When a transaction is part of a `transfer` pair:

* A thin stream peels off the parent lane
* Curves smoothly into the destination lane
* Width proportional to amount
* Transparency proportional to inference certainty

### 4.3 Event Markers

Pinned to exact `t` coordinate:

* Life events: circle markers
* Utterance clusters: speech bubbles
* Legal nodes: scales-of-justice markers
* Financial triggers: pill-shaped markers

Hover → FTS5 snippet preview.
Click → open full document/recording transaction.

### 4.4 Stacking / Z-depth

Lanes have **z-index** so the viz never becomes spaghetti:

* Speech above timeline
* Financial accounts below
* Legal overlays floating or collapsible
* Hover enlarges only that stream

---

## 5. Pipeline Architecture

### Step 1 — Data Collection

* TiRCorder recordings → transcript + diarization → L0 embedding
* Finance adapters → `transactions`
* SensiBlaw → documents → `sentences`/`concepts`

### Step 2 — Normalisation

* Merge timestamps into a unified timeline axis
* Deduplicate/align events ±2 min
* Apply valid-time slices

### Step 3 — Transfer Inference

* Pair transaction inflow/outflow
* Emit `transfers(id, src_txn_id, dst_txn_id, inferred_conf)`

### Step 4 — Cross-linking

* Sentence mentions ↔ transaction IDs
* Events ↔ finance via `event_finance_links`
* Utterances ↔ legal claims via concept triggers

### Step 5 — Ribbon Preparation

Create `v_ribbon_segments` materialised view:

```sql
SELECT
  t.posted_at AS t,
  a.account_type AS lane,
  t.amount_cents AS amount,
  tr.id AS transfer_id,
  efl.event_id AS event_id,
  fp.sentence_id AS sentence_id
FROM transactions t
JOIN accounts a ON t.account_id=a.id
LEFT JOIN transfers tr ON (tr.src_txn_id=t.id OR tr.dst_txn_id=t.id)
LEFT JOIN event_finance_links efl ON efl.transaction_id=t.id
LEFT JOIN finance_provenance fp ON fp.transaction_id=t.id;
```

### Step 6 — Emit JSON contract

A small FastAPI endpoint returns the fully fused view.

### Step 7 — Render

Frontend (Svelte/D3/Canvas/WebGL) draws lanes + ribbons.

---

## 6. Rendering Technologies (choose 1 or hybrid)

### Option A — Svelte + D3

Pros: flexible, good for curved streams, moderate performance
Cons: heavy CPU for very large timelines

### Option B — Canvas 2D + Regl/WebGL

Pros: extremely fast, ideal for thousands of segments
Cons: requires shader-ish thinking for smoothing

### Option C — Three.js (full 3D)

Pros: true z-depth, animated parallax, cinematic
Cons: heavier and more complex, but uber sexy

**Recommended:**
**Canvas/WebGL for the ribbons + Svelte for UI**.

---

## 7. UI Interaction Model

* **Hover:** show snippet (`snippet(sentence.text)`)
* **Click:** open Right Pane with:

  * Transcript range
  * Transaction note + raw bank data
  * Provision excerpt from SensiBlaw
  * Receipts pack
* **Drag:** pan timeline
* **Wheel:** zoom
* **Toggle lanes:** show/hide accounts, speech, legal overlays
* **Scrubber:** video-editor style timeline controller

---

## 8. Privacy & Consent Integration

Before any linked data becomes visible:

* Run OPA/Rego “consent gates”:

  * e.g. “financial data cannot be shown unless user has attested consent”
* Redact account numbers to `****5678`
* Only show legal text with appropriate visibility flags

Receipts packs are signed with **ed25519/minisign** and can be exported.

---

## 9. Milestones

### Milestone 1 — MVP (2 weeks)

* CSV/OFX → transactions
* Simple transfer inference
* Basic D3 ribbon prototype
* Speech lane + events
* Hover previews

### Milestone 2 — Cross-linking (2–4 weeks)

* Link events ↔ finance
* Provenance tooltips (sentences → FTS5)
* Multi-lane layout
* Legal lane for claims/harm instances

### Milestone 3 — Beautiful Viz (4–8 weeks)

* Curved Bezier ribbon engine
* Smooth siphons
* Z-depth
* Parallax
* Animated transitions

### Milestone 4 — Exports & Packs

* Evidence pack export
* Signed JSON receipts
* Printable timeline PDF
* Offline bundle for clinicians/case workers

---

## 10. Future Directions (optional)

* Emotion/sentiment stream above speech lane
* Physiological data (sleep, HRV) as another ribbon
* Comparative view (two people’s lanes with consent)
* Legal “heatmap” of obligations/duties over time
* “Explainer mode” that shows narrative → money → law causal chains

---

## Summary

This visual system becomes the **front window** of ITIR:
A single interactive view where the user can **see their life**, **their finances**, and **the legal frames around them**, all tied back to provenance in Layer 0.

If you want, I can generate:

* A full **mockup** (PNG/SVG) in your aesthetic
* A **component breakdown** for the frontend
* A **backend API spec** for `/timeline/stream`

Just tell me which one you want next.


# Finance Adapters

This module provides **thin, deterministic adapters** that turn bank exports into a common `transactions` table TiRCorder/ITIR can reason about and visualise (e.g. ribbon timelines).

The goal:

> *“Parse everything, interpret nothing”*

Adapters **only** normalise raw data → a canonical transaction schema.
All higher-level logic (transfer inference, consent, story linking, viz) lives elsewhere.

---

## 1. Canonical transaction schema

All adapters emit rows that map 1:1 to this logical shape (matching the DB schema):

```jsonc
{
  "account_external_id": "1234-5678",    // bank/account identifier
  "posted_at": "2025-05-03T10:21:00Z",   // ISO 8601
  "amount_cents": -250000,               // signed; cents/minor units
  "currency": "AUD",
  "counterparty": "ACME PTY LTD",
  "description": "CARD PURCHASE 123456 ACME PTY LTD BRISBANE AU",
  "ext_ref": "N1234567890",              // bank’s own transaction ID, if any
  "raw_payload": { ... }                 // original fields, unmodified
}
```

At DB time, this becomes:

* `accounts` row (`provider`, `account_type`, `display_name`, `owner_actor_id?`)
* `transactions` row (`account_id`, `posted_at`, `amount_cents`, `currency`, `counterparty`, `description`, `ext_ref`, `raw_payload`)

> **Important:** adapters must never “guess” categories or events. They should **preserve** bank text in `description` and `raw_payload` so later passes can re-interpret safely.

---

## 2. Adapter contract

Each adapter lives in `adapters/` and implements a consistent interface:

```python
# adapters/base.py

from typing import Iterable, Protocol, BinaryIO, Mapping, Any

class TransactionRow(Mapping[str, Any]):
    """
    Dict-like structure with at least:
    - account_external_id
    - posted_at
    - amount_cents
    - currency
    - counterparty
    - description
    - ext_ref
    - raw_payload
    """
    ...

class TxnAdapter(Protocol):
    @staticmethod
    def sniff(source: BinaryIO) -> bool:
        """Return True if this adapter recognises the file/stream."""

    @staticmethod
    def parse(source: BinaryIO) -> Iterable[TransactionRow]:
        """
        Yield normalised transaction rows.
        Must not throw on minor format quirks; log + skip instead.
        """
```

Dispatcher:

```python
# adapters/__init__.py

from .csv_bank import CsvBankAdapter
from .ofx_qfx import OfxQfxAdapter
from .mt940 import Mt940Adapter
from .iso20022_camt import Iso20022CamtAdapter
from .json_api import JsonApiAdapter

ADAPTERS = [
    CsvBankAdapter,
    OfxQfxAdapter,
    Mt940Adapter,
    Iso20022CamtAdapter,
    JsonApiAdapter,
]

def detect_and_parse(source: BinaryIO):
    for adapter in ADAPTERS:
        source.seek(0)
        if adapter.sniff(source):
            source.seek(0)
            yield from adapter.parse(source)
            return
    raise ValueError("No matching finance adapter for input")
```

---

## 3. Supported formats

### 3.1 CSV bank exports

**Typical sources:** AU retail banks, neo-banks, credit cards.
**File characteristics:** comma-separated, headers like:

```text
Date,Amount,Description,Balance,Account Number,Transaction ID
2025-05-03,-250.00,CARD PURCHASE 123456 ACME PTY LTD BRISBANE AU,840.23,12345678,987654321
```

**Adapter:** `adapters/csv_bank.py`

Responsibilities:

* Robust date parsing (`YYYY-MM-DD`, `DD/MM/YYYY`, etc.).
* Locale amount parsing (`-250.00`, `"1,234.56"`).
* Map bank-specific column names onto canonical fields.
* Preserve **entire row** as `raw_payload`.

```python
# pseudo-core of CsvBankAdapter.parse
{
  "account_external_id": row["Account Number"],
  "posted_at": iso8601_from(row["Date"]),
  "amount_cents": to_cents(row["Amount"]),
  "currency": "AUD",
  "counterparty": infer_counterparty(row["Description"]),
  "description": row["Description"],
  "ext_ref": row.get("Transaction ID", ""),
  "raw_payload": dict(row),
}
```

> `infer_counterparty` here should be conservative: usually just the first merchant name segment, not a classifier.

---

### 3.2 OFX / QFX

**Typical sources:** Quicken/QuickBooks exports, some bank downloads.

**Adapter:** `adapters/ofx_qfx.py`

* Use an OFX parser (e.g. `ofxparse`) to extract `<BANKTRANLIST><STMTTRN>` blocks.
* Map `DTPOSTED`, `TRNAMT`, `FITID`, `NAME`, `MEMO` into canonical fields.
* Use account info from `<BANKACCTFROM>` as `account_external_id`.

---

### 3.3 MT940

**Typical sources:** SWIFT statement exports (EU banks, business accounts).

**Adapter:** `adapters/mt940.py`

* Parse fields like `:20:`, `:25:`, `:28C:`, `:61:`, `:86:`.
* Use `:25:` as `account_external_id`.
* Map `:61:` booking/valuta dates + amounts into `posted_at` / `amount_cents`.
* Pack narrative (`:86:`) into `description` & `raw_payload`.

---

### 3.4 ISO 20022 camt.053

**Typical sources:** modern “XML statement” downloads, corporate banking APIs.

**Adapter:** `adapters/iso20022_camt.py`

* Parse `BkToCstmrStmt/Stmt/Ntry` elements.
* Use `Acct/Id/*` as `account_external_id`.
* Map `Amt/@Ccy`, `Amt/text()`, and `BookgDt/…` into canonical fields.
* Squeeze narrative (remittance info, creditor/debtor names) into `counterparty` and `description`.

---

### 3.5 JSON API exports

**Typical sources:** Plaid/TrueLayer/Yodlee-style APIs, or user’s own export from another app.

**Adapter:** `adapters/json_api.py`

* Accepts:

  * **Array** of transaction objects, or
  * `{ "transactions": [ ... ] }` wrappers.
* Expect fields like `amount`, `currency`, `date` + nested `account` / `counterparty` objects.
* Map to canonical shape; stash original JSON under `raw_payload`.

---

## 4. Error handling & logging

Adapters should be **strict about schema, forgiving about rows**:

* If the file is recognised but a row is malformed:

  * Log a warning (e.g. “row 42: invalid date ‘32/13/2025’ – skipped”).
  * **Skip that row**, don’t crash the entire import.
* If the file is not recognised:

  * `sniff()` returns `False`, dispatcher tries the next adapter.
* If no adapter matches:

  * Raise `ValueError("No matching finance adapter for input")` so the UI can show a human explanation.

---

## 5. Consent, privacy, and scope

Finance data is **sensitive**. Adapters must:

* Import **only** files the user explicitly selects or uploads.
* Never phone home or call external APIs.
* Keep raw identifiers in `raw_payload` but **UI layers** should:

  * Mask account numbers by default (`****5678`).
  * Avoid showing full transaction IDs unless explicitly expanded.

Policy/consent (OPA/Rego) lives **outside** adapters; their role is just: *“faithful copy of bank reality into a local, analysable shape.”*

---

## 6. Golden tests (pytest)

Each adapter should ship with **golden files** in `tests/fixtures/finance/`:

```text
tests/fixtures/finance/
  sample_csv_au_1.csv
  sample_ofx_1.ofx
  sample_mt940_1.txt
  sample_camt053_1.xml
  sample_json_api_1.json
```

Example pytest:

```python
# tests/test_csv_bank_adapter.py
from adapters.csv_bank import CsvBankAdapter
from adapters.base import TransactionRow
from pathlib import Path
import io
import json

FIXTURE = Path(__file__).parent / "fixtures" / "finance" / "sample_csv_au_1.csv"
GOLDEN = Path(__file__).parent / "fixtures" / "finance" / "sample_csv_au_1.golden.json"

def test_csv_bank_roundtrip():
    raw = FIXTURE.read_bytes()
    buf = io.BytesIO(raw)

    assert CsvBankAdapter.sniff(buf) is True

    buf.seek(0)
    rows = list(CsvBankAdapter.parse(buf))
    assert rows, "no transactions parsed"

    # Compare against golden JSON (update via explicit script when format changes)
    if GOLDEN.exists():
        golden = json.loads(GOLDEN.read_text())
        assert golden == rows
    else:
        # First-time generation (run manually, not in CI)
        GOLDEN.write_text(json.dumps(rows, indent=2, sort_keys=True))
```

Golden tests give you:

* Stable, reviewable parsing behaviour.
* A safe way to evolve parsing rules (diff the golden JSON).

---

## 7. How this feeds the ribbon timeline

Once adapters populate `accounts` + `transactions`, the rest of the pipeline can:

1. Infer **transfers** (`transfers` table).
2. Link **events** and **recordings** (`event_finance_links`, `finance_provenance`).
3. Expose a clean `v_ribbon_segments` view consumed by the UI.

Adapters are deliberately boring. That’s their superpower:

> If they’re predictable, everything downstream (story, law, viz) can be rich without being brittle.
