# Timeline Stream Viz — "streamline" — Roadmap

Right, this is the juicy bit: **money + conversations** as *first-class* things that sit alongside “law” in the ontology, not bolted on afterwards.

I’ll treat it as:

1. How finances become true first-class citizens in the 6-layer stack
2. How social / chat streams + sentiment plug into the same stack
3. How we actually *see* patterns like “user more distressed + partner behaviour changes + money siphons” across views

---

## 1. Making finances truly first-class

You already have the low-level finance schema (accounts, transactions, transfers) and linkage into Events + Sentences. To make them **ontologically first-class**, we plug them into the *same axes* as everything else:

### a) Events & Actors (Layer 1)

Treat each transaction as a *specialised event*, not a separate universe.

* `Event.event_kind` gains:

  * `FINANCIAL_TRANSACTION`
  * `FINANCIAL_AGREEMENT` (e.g. “we agreed I’d pay all rent”)
  * `FINANCIAL_SHOCK` (unexpected charge, garnishee, cut-off)
  * `FINANCIAL_WITHHOLDING` (bill not paid, money not given)

* Roles on those events:

  * `PAYER`, `PAYEE`, `ACCOUNT_HOLDER`, `BENEFICIARY`, `INSTITUTION`

* Link to transactions (from earlier):

  ```sql
  event_finance_links(event_id, transaction_id, link_kind='caused'|'evidence'|'context')
  ```

So “paid bond”, “partner drained savings”, “Centrelink stopped” are all *Events* that just happen to be evidenced by `transactions`.

### b) Protected Interests & Harms (Layer 5)

Make financial security explicit, not implicit:

* `protected_interest_types` includes things like:

  * `FINANCIAL_SECURITY`
  * `HOUSING_STABILITY`
  * `BASIC_NEEDS` (food, utilities)
  * `ABILITY_TO_WORK` (e.g. car payments, tools, childcare)

* `harm_classes` includes:

  * `HARM_FINANCIAL`
  * `HARM_HOUSING` (eviction/instability)
  * `HARM_DEPENDENCY` (forced financial dependence)

* `HarmInstance` for money:

  ```text
  event_id            → the financial event (“rent not paid” / “card maxed”)
  protected_interest  → FINANCIAL_SECURITY / HOUSING_STABILITY
  harm_class          → HARM_FINANCIAL / HARM_HOUSING
  concept_id          → ECONOMIC_STRAIN / LOSS_OF_INCOME (semantic atom)
  sentence_id         → where the user explains “he stopped paying rent”
  ```

Now finances show up in *exactly the same way* as bodily harms: as **harm instances** to protected interests, not “just numbers”.

### c) Wrong Types & Duties (Layer 4)

Introduce explicit wrongs around economic control:

* `wrong_types` (per legal system / perspective):

  * `ECONOMIC_ABUSE`
  * `FINANCIAL_COERCION`
  * `FINANCIAL_NEGLECT` (e.g. refusing to contribute to joint necessities)
  * `CONTROL_OF_EARNINGS`
  * `UNCONSENTED_DEBT` (taking loans in victim’s name)
  * `WITHHOLDING_CHILD_SUPPORT`

Each gets **elements** that bind to the finance layer:

```text
WrongType: ECONOMIC_ABUSE (AU.FAMILY.Violence)

Elements:
- CONDUCT: concept = UNFAIR_CONTROL_OF_MONEY
- RELATIONSHIP: pattern = INTIMATE_PARTNER / CAREGIVER
- RESULT: harm_class = HARM_FINANCIAL, HARM_DEPENDENCY
- CONTEXT: condition = PATTERN_OVER_TIME (not one-off)
```

*How this hits finance:*

* Patterns like:

  * user income ↑, partner discretionary spending ↑, user cash reserves ↓
  * repeated unpaid bills while partner has plenty of personal spending
  * joint account emptied right before separation

…become **evidence for those wrong types**, not just “interesting graphs”.

### d) Value Frames (Layer 6)

Finance is deeply moralised:

* `value_frames` that touch money:

  * `EQUITABLE_SHARING_IN_RELATIONSHIP`
  * `CARING_FOR_DEPENDANTS`
  * `AUTONOMY_OVER_ONE’S_EARNINGS`
  * `HUMAN_RIGHTS_DECENT_STANDARD_OF_LIVING`
  * `TIKANGA_WHAKAPAPA_DUTIES` (if e.g. money being withheld from whānau obligations)

* `wrongtype_valueframes` + `protectedinterest_valueframes` say:

  * economic abuse violates `AUTONOMY` + `CARING_FOR_DEPENDANTS`
  * withholding school fees violates `CHILD_INTERESTS` + HR frames

So money isn’t just “data”; it is tied to **what is considered just or unjust** in multiple systems.

---

## 2. Integrating social / chat streams + sentiment

You already treat recordings / transcripts as Layer-0 Documents with Utterances. Social feeds are structurally the same.

### a) Social feeds as Documents & Utterances

For each platform / channel:

* `documents`:

  * `doc_type = 'SOCIAL_FEED' | 'DM_THREAD' | 'SMS_EXPORT' | 'EMAIL_THREAD'`
  * text lives in `TextBlock`, then `sentences`.

* Each message:

  * `utterances` row with `start_time`, `sender_actor_id`, maybe `platform`.

* Link utterances ↔ sentences via `utterance_sentences`.

So a Twitter thread, WhatsApp chat, Facebook DM – all just become **streams of utterances** on the *same substrate* your court transcripts use.

### b) Sentiment / concern / pattern features

Per **sentence** or **utterance** you attach features like:

```text
sentiment_score   (e.g. -1..+1)
emotion_primary   (JOY, ANGER, FEAR, SADNESS, SHAME, NUMB…)
subjectivity      (0..1)
concern_score     (0..1) – specialised “worry/concern” detector
control_language  (0..1) – partner’s controlling / threatening language
```

Implementation-wise this can be a `utterance_features` table:

```sql
CREATE TABLE utterance_features (
    utterance_id   INTEGER PRIMARY KEY REFERENCES utterances(id),
    sentiment      REAL,         -- -1..1
    arousal        REAL,         -- 0..1
    concern_score  REAL,
    anger_score    REAL,
    fear_score     REAL,
    shame_score    REAL,
    control_score  REAL,         -- language about control / threats
    blame_score    REAL          -- “this is your fault”, “you always…”
);
```

Then you can **aggregate over time**, per relationship:

```sql
CREATE TABLE relationship_metrics (
    id                INTEGER PRIMARY KEY,
    relationship_id   INTEGER NOT NULL,   -- A↔B link
    window_start      TIMESTAMP NOT NULL,
    window_end        TIMESTAMP NOT NULL,
    speaker_actor_id  INTEGER,            -- who is speaking
    mean_sentiment    REAL,
    mean_concern      REAL,
    mean_control      REAL,
    msg_count         INTEGER
);
```

This is how you get “from date X onward, user’s concern ↑, partner’s control ↑”.

### c) Relationship as shared container

You can model:

```sql
relationships(id, actor_a_id, actor_b_id, relationship_kind)
```

Then:

* finance:

  * accounts tagged to either/both actors
  * transactions tagged to relationship (“household spend” vs “personal spend”)

* social:

  * utterances tagged by which relationship they belong to (DM thread or chat with that partner)

* events:

  * `Event.relationship_id` for key incidents (arguments, moves, breakups)

All your time-series aggregates become **per-relationship streams**.

---

## 3. Putting it together: streams & pattern detection

Conceptually, you want **multiple streams** per relationship:

* `Stream: CHAT_SENTIMENT` (per direction)
* `Stream: FINANCIAL_BALANCE` (per account)
* `Stream: FINANCIAL_DEPENDENCY` (how reliant A is on B’s money)
* `Stream: LEGAL_PRESSURE` (count/weight of claims, orders, deadlines)

### a) Define abstract “streams” on top of the DB

You don’t have to create a new table, but it often helps:

```sql
CREATE TABLE streams (
    id              INTEGER PRIMARY KEY,
    relationship_id INTEGER,
    stream_type     TEXT NOT NULL,   -- 'CHAT_SENTIMENT', 'FINANCE_NET', 'LEGAL_HARMS'
    direction       TEXT,            -- 'A_TO_B','B_TO_A','JOINT'
    label           TEXT NOT NULL
);

CREATE TABLE stream_points (
    stream_id       INTEGER NOT NULL REFERENCES streams(id),
    t               TIMESTAMP NOT NULL,
    value           REAL NOT NULL,
    payload         JSON,            -- optional: extra detail
    PRIMARY KEY (stream_id, t)
);
```

Then:

* A chat sentiment stream for “User → Partner” has time points with `value = mean_concern_score` or `mean_sentiment`.
* A finance stream has `value = net_outflow_from_user` or `balance`.
* A legal stream has `value = # of active orders / severity score`.

Your **Timeline Ribbon viz** just stitches these stream_points into ribbons.

### b) Cross-stream alignment (the pattern you described)

Example you gave:

> starting date X – we notice that xyz pattern from partner also starts around then

Concretely:

* For relationship R (User ↔ Partner):

  * Stream S1: `User concern_score over time` (chat/diary).
  * Stream S2: `Partner control_score over time` (chat).
  * Stream S3: `Net financial dependence of User on Partner` (ratio of User personal income vs Partner contributions + joint spending).

We can:

* Compute **rolling windows** (e.g. weekly):

  * `mean_concern_user(t)`
  * `mean_control_partner(t)`
  * `dependency_ratio(t)`

* Detect change points:

  * “concern_user” jumps +2 SD after some date.
  * “control_partner” jumps around the same period.
  * “dependency_ratio” crosses a threshold (e.g. user now 80–90% dependent on partner’s income).

Then we **annotate**:

* A “pattern event”:

  ```text
  Event.event_kind = RELATIONAL_PATTERN_SHIFT
  Event.context    = INTIMATE_RELATIONSHIP
  Event.relationship_id = R
  Event.occurred_at = approx change-point date
  ```

* And attach HarmInstances & candidate WrongTypes:

  * `HarmInstance` with `protected_interest = FINANCIAL_SECURITY` / `PSYCHOLOGICAL_INTEGRITY`
  * Candidate `WrongType = ECONOMIC_ABUSE` / `COERCIVE_CONTROL` (depending on jurisdiction)

You display this in the viz as:

> “Around June 2024:
> – User’s concern in messages increased
> – Partner’s controlling language increased
> – User’s financial dependence also increased”

but you are very clear that this is **pattern detection, not a verdict**.

---

## 4. Safety + interpretive stance

Because this is sensitive as hell, the system should:

* Treat all analytic flags as:

  * **“Something to look at”**, not “your partner is definitely abusive”.

* Always surface:

  * The **raw evidence snippets** (messages, transactions) via sentence/doc links.
  * The **ValueFrames** used (e.g. “this would worry family-violence services because it affects autonomy and financial security”).

* Allow multiple perspectives:

  * State legal frame (e.g. family-violence legislation).
  * Human-rights child/women’s rights frame.
  * Indigenous or religious frame if the user wants that lens.
  * User’s own felt frame (“this feels unjust to me”).

Morality is handled by **ValueFrames and perspectives**, not by hard-coding labels like “BAD_PARTNER” into the schema.

---

## 5. Short version

* **Finances as first-class**:

  * Transactions are Events.
  * They produce HarmInstances on protected interests like `FINANCIAL_SECURITY`.
  * WrongTypes like `ECONOMIC_ABUSE` and `FINANCIAL_NEGLECT` are defined in terms of patterns over those events.
  * Remedies are things like maintenance orders, property splits, debt releases, etc.

* **Social streams as first-class**:

  * All messages are Utterances → Sentences → Tokens → Concepts.
  * Sentiment / concern / control features are attached per utterance, aggregated per relationship/time window.

* **Cross-view grouping**:

  * Define relationship-scoped Streams (`CHAT_SENTIMENT`, `FINANCE_NET`, `LEGAL_HARMS`).
  * Compute rolling metrics and change points.
  * Represent major shifts as Events with candidate harms/wrongs.
  * Visualise them together in the ribbon/timeline view with provenance and value-frame overlays.

If you like, next I can sketch a **concrete worked example** end-to-end:

> “From March to July, User’s messages get more worried, Partner’s language gets sharper, money starts being siphoned out of joint account, and the system surfaces this as a potential economic-abuse pattern with links to relevant law and value frames.”



# Most up to date 
18/11/2025 - dry'd

# Timeline Stream Viz — "Streamline" — Roadmap

*A unified visual layer for story × law × finance timelines*

This document describes the **implementation roadmap** for the Timeline Stream
Visualisation System (“Streamline”) — a multi-lane ribbon/streamgraph view
that sits on top of:

- the shared **Layer-0 text substrate** and **L1–L6 ontology** (see [`ARCHITECTURE_LAYERS.md`](docs/ARCHITECTURE_LAYERS.md)),
- **TiRCorder**’s utterances, events, and narratives,
- the **Finance** substrate (accounts, transactions, transfers; see [`FINANCE_SCHEMA.md`](docs/FINANCE_SCHEMA.md)),
- **SensiBlaw**’s legal documents, claims, provisions, and cases,
- and the shared provenance model (see [`PROVENANCE.md`](docs/PROVENANCE.md)).

For the high-level product/UX description of Streamline, see [`STREAMLINE_FEATURE_PROPOSAL.md`](docs/STREAMLINE_FEATURE_PROPOSAL.md).

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




*A unified visual layer for story × law × finance timelines*

This document describes the roadmap for building the **Timeline Stream Visualisation System** — a multi-lane ribbon/streamgraph view that merges:

* **TiRCorder** (recordings, utterances, events)
* **Finance layer** (accounts, transactions, transfers)
* **SensiBlaw** (legal documents, claims, provisions, cases)
* **Life events + narrative anchors**

This is the main UX layer of ITIR:
A **single, coherent timeline** where the user can see *what happened*, *what was said*, *how money moved*, and *what legal/structural frames apply* — all with provenance.



Absolutely — now that the **full shape of the SensiBlaw + TiRCorder + Finance substrate** is clear (Layer-0 text substrate, L1–L6 ontology, the TiRCorder utterance/event stack, the finance adapters + transfers + provenance), we can re-describe the feature as a unified, technically clear proposal.

Here is the **refined, architecturally accurate feature description**, now called **Streamline**.

You can drop this into your README, ROADMAP, or as its own proposal file:
**`STREAMLINE_FEATURE_PROPOSAL.md`**

---

# Streamline — Unified Narrative Timeline & Flow Visualisation

*A cross-modal, provenance-anchored stream-timeline integrating speech, money, law, and life events.*

Streamline is the visual heart of the ITIR ecosystem, fusing **TiRCorder**’s real-world recordings, **SensiBlaw**’s structured legal knowledge, and the new **Finance** substrate into one coherent, interactive timeline.

Streamline does **not** invent new data structures — it **renders exactly what the database already describes**, via:

* Layer-0 Text Substrate
* Layer-1 to Layer-6 Legal Ontology
* TiRCorder utterances & events
* Finance accounts, transactions, transfers
* Evidence packs, provenance links, concepts, protected interests, harms

Everything flows back to **sentences**, **documents**, and **valid-time**.

---

# 1. What Streamline *is*

Streamline is a **multi-lane, curved “flow of life” visualiser** where:

* Time runs **downward** (Y-axis).
* Each **lane** represents a system:

  * Speech / Voice
  * Personal Accounts (Cheque, Savings, Business, Credit)
  * Legal Processes (Claims, Cases, Provisions, Wrong Types)
  * Life Events / Personal history
* **Ribbons** represent quantities changing over time:

  * Financial amounts
  * Speaker dominance / utterance energy
  * Legal burden / case intensity
* **Threads** (siphons) peel off the main flows:

  * Money leaving the main account
  * Sub-events branching from main life events
  * Legal escalations from a base claim

All elements are anchored to real evidence:

* Click a ribbon → see the **transaction** and raw bank payload
* Click an event → see the **utterance** or **sentence** where it was mentioned
* Click a legal tag → see the **provision** text or **claim** narrative segment
* Hover anything → FTS5 snippet + provenance snippet

Streamline is **cinematic**, not just informational.

---

# 2. Functional Overview

### **2.1 Unified Time Axis**

All events, utterances, sentences, transactions, transfers, and legal references collapse into one timeline.

We use:

* `utterances.start_time`
* `transactions.posted_at`
* `documents.created_at`
* `events.valid_time`
* `provisions.as_at`

Streamline aligns these into a clean, scrollable stack.

---

### **2.2 Ribbons (Continuous Flows)**

#### Finance

* Main account (e.g., Cheque) as a wide vertical ribbon.
* Fluctuations reflect net inflow/outflow.
* Transfers create thin peeling threads curving into other account lanes.

#### Speech

* Speech energy/utterance density plotted as a ribbon in the “speech lane”.
* Diarization → color-coded mini-streams per speaker.

#### Legal

* Claims & wrong types appear as **horizontal overlays** or vertical stacked layers.
* Duties, protected interests, harm classes appear as **thin metadata streams** aligned to sentences and events.

---

### **2.3 Events & Narrative Markers**

Events from TiRCorder, SensiBlaw, and Finance all pin to their exact moment:

* “Paid rent” (transaction)
* “Lost job” (life event)
* “Referred to s223 NTA” (legal system)
* “Doctor said → xyz” (utterance linked to a concept)

Event types can expand or collapse.

---

### **2.4 Provenance Everywhere**

Every visible object carries:

* `sentence_id`
* `document_id`
* `transaction_id`
* `transfer_id`
* `event_id`

Streamline never creates synthetic data — it visualises *only what the database knows*.

This makes it:

* Auditable
* Legally defensible
* Explainable
* Trustworthy

---

# 3. How Streamline Uses Your Existing DB Shapes

### **3.1 Layer 0 → Streamline**

Every ribbon segment can map back to:

* Sentences (via `finance_provenance` or utterance links)
* Lexeme & phrase concepts (to highlight important mentions)

This gives you snippets and narrative context.

---

### **3.2 TiRCorder → Streamline**

* `utterances` define the speech lane
* `utterance_sentences` anchor narrative
* diarization defines stream “sub-channels”
* `Event` table ties speech to life events

You get a chronological “pulse” of the voice.

---

### **3.3 Finance Layer → Streamline**

* `accounts` = separate lanes
* `transactions` = segments in those lanes
* `transfers` = curved siphons connecting lanes
* `event_finance_links` = life events attached to flows
* `finance_provenance` = which sentences explain which money moves

This enables the ribbon-stream visual structure.

---

### **3.4 SensiBlaw → Streamline**

Layer 1–6 objects tie in as light overlays:

| Ontology Layer              | Visual Form in Streamline   | Source                |
| --------------------------- | --------------------------- | --------------------- |
| Events & Actors             | timeline markers            | TiRCorder + SensiBlaw |
| Claims & Cases              | wide-band overlays          | SensiBlaw             |
| Norm Sources / Provisions   | collapsible annotation lane | SensiBlaw             |
| Wrong Types / Duties        | thin metadata ribbons       | SensiBlaw             |
| Protected Interests / Harms | coloured sidebands          | SensiBlaw             |
| Value Frames / Remedies     | justification tags          | SensiBlaw             |

Streamline shows **how the law sees the same timeline**.

---

# 4. Interaction Model

### Hover

* Snippet from relevant `sentence.text`
* Preview transaction summary
* Show legal justification (“This relates to WrongType: defamation / duty breached: reckless misrepresentation”)

### Click

Opens a right-hand panel with:

* Transcript range
* Raw bank transaction payload
* Provision text (Akoma Ntoso)
* Extracted concepts
* Evidence pack (signed)

### Zoom/Pan

* Infinite scroll
* Smooth WebGL transitions

### Mode Toggles

* Show/hide:

  * Speech streams
  * Financial lanes
  * Legal overlays
  * Life events
  * Transfers (siphons)

---

# 5. Why Streamline Matters

Streamline is the first system that:

* Combines **speech**, **money**, **documents**, **legal analysis**, **emotions**, and **narrative**
* Anchors everything to evidence
* Computes nothing opaque
* Allows a user to review their life as **connected flows**, not disconnected artifacts
* Gives clinicians, caseworkers, lawyers, and the user themselves a shared, comprehensible timeline

It’s a **visual narrative audit trail**.

---

# 6. Implementation Roadmap (Short)

### Phase 1 — Data Plumbing

* Materialize `v_ribbon_segments`
* Build `/streamline/data` endpoint
* Expose lanes and segments

### Phase 2 — WebGL Pipeline

* Bezier stream band renderer
* Transfer curves
* Z-depth stacking

### Phase 3 — Interactions

* Provenance hovers
* Right-panel detail views
* Snippet linking

### Phase 4 — Legal overlays

* Claim/wrong/harm strip renderers
* Protected-interest mapping

### Phase 5 — High polish

* Animations
* Parallax
* Export to PDF
* Evidence pack stamping

---

# 7. Summary

**Streamline** is the unifying visual language of ITIR.

It converts your **text substrate**, **legal ontology**, **utterances**, and **financial flows** into one honest, elegant, evidence-driven stream of life.










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


Nice, this is a good place to line things up properly.

I’ll treat this as: **“Given the existing SensiBlaw + TiRCorder DB shape, what exactly do the finance tables look like and how do they plug in cleanly?”**

I’ll keep it concrete and schema-ish, but in a way that drops straight into your mental model.

---

## 0. Anchors we already have

From your current design (Layer 0 + L1–L6 + TiRCorder):

* **Layer 0 (Text substrate)**

  * `documents(id, doc_type, text_block_id, created_at, …)`
  * `sentences(id, document_id, sentence_index, start_char, end_char, text)`
  * `tokens/lexemes/concepts/phrases` etc.

* **TiRCorder-ish / discourse**

  * `speakers(id, label, actor_id?)`
  * `utterances(id, document_id, speaker_id, start_time, end_time, …)`
  * `utterance_sentences(utterance_id, sentence_id, seq_index)`

* **Ontology-ish (coarse)**

  * `Actor` (person/org)
  * `Event` (things happening in time)
  * `Claim`, `Case` / LegalEpisode
  * `EvidenceItem` / `HarmInstance`
  * `WrongType`, `ProtectedInterest`, etc.

Streamline wants to show **money flows as just another set of events/flows** in that same universe.

---

## 1. Core finance tables (canonical layer)

Minimal, normalised, and “boring”:

```sql
CREATE TABLE accounts (
    id              INTEGER PRIMARY KEY,
    owner_actor_id  INTEGER,          -- FK → Actor(id), nullable for now
    provider        TEXT,             -- 'CBA','NAB','ING','Wise'
    account_type    TEXT NOT NULL,    -- 'cheque','savings','business','credit','loan','wallet'
    currency        TEXT NOT NULL DEFAULT 'AUD',
    external_id     TEXT,             -- bank acct no / IBAN / masked id
    display_name    TEXT NOT NULL,    -- "Everyday", "Biz OpEx", etc.
    is_primary      INTEGER NOT NULL DEFAULT 0,   -- 0/1
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

```sql
CREATE TABLE transactions (
    id             INTEGER PRIMARY KEY,
    account_id     INTEGER NOT NULL REFERENCES accounts(id),
    posted_at      TIMESTAMP NOT NULL,        -- booking date (valid-time candidate)
    effective_at   TIMESTAMP,                 -- value date if distinct
    amount_cents   INTEGER NOT NULL,          -- signed minor units
    currency       TEXT NOT NULL,             -- keep even if same as account
    counterparty   TEXT,                      -- free label
    description    TEXT,                      -- bank memo / narrative
    ext_ref        TEXT,                      -- FITID / MT940 ref / JSON ID
    raw_payload    BLOB,                      -- original row/XML/JSON
    source_format  TEXT NOT NULL,             -- 'csv','ofx','mt940','camt053','json'
    imported_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_transactions_account_time
    ON transactions(account_id, posted_at);
```

```sql
-- Transfer pairs (inferred or explicit)
CREATE TABLE transfers (
    id            INTEGER PRIMARY KEY,
    src_txn_id    INTEGER NOT NULL REFERENCES transactions(id),
    dst_txn_id    INTEGER NOT NULL REFERENCES transactions(id),
    inferred_conf REAL NOT NULL DEFAULT 0.9,  -- 0..1
    rule          TEXT                        -- 'same_amount_window','mt940_ref','user_tag'
);

CREATE UNIQUE INDEX idx_transfers_pair
    ON transfers(src_txn_id, dst_txn_id);
```

This is the **canonical finance substrate**. Nothing here “knows” about events, cases, sentences, etc. It’s just “what the bank believes”.

---

## 2. Plugging into the existing ontology

### 2.1 Linking to actors

We already have `Actor` in L1. Accounts should be **actor-scoped**, but we don’t need that to be perfect on day one.

* `accounts.owner_actor_id → Actor.id`
* For shared accounts, you can later add a join table:

```sql
CREATE TABLE account_actors (
    account_id  INTEGER NOT NULL REFERENCES accounts(id),
    actor_id    INTEGER NOT NULL, -- FK → Actor
    role        TEXT NOT NULL,    -- 'holder','signatory','beneficiary'
    PRIMARY KEY (account_id, actor_id)
);
```

Streamline can then colour flows per actor if/when you get that metadata.

---

### 2.2 Transactions as events (L1)

You already have `Event` as “something happened in time, involving actors”.

You can either:

* Treat `transactions` as a **specialised event table**, or
* Add a thin link so each transaction *may* have a corresponding `Event` row.

I’d keep it additive:

```sql
CREATE TABLE event_finance_links (
    id             INTEGER PRIMARY KEY,
    event_id       INTEGER NOT NULL,                 -- FK → Event(id)
    transaction_id INTEGER NOT NULL REFERENCES transactions(id),
    link_kind      TEXT NOT NULL,                    -- 'caused','evidence','context'
    confidence     REAL NOT NULL DEFAULT 1.0
);

CREATE INDEX idx_event_finance_links_event
    ON event_finance_links(event_id);
```

This way:

* “Paid bond” can be a **life event** that links to one or more transactions.
* “Centrelink backpay” can link to inflows.
* “Garnishee for debt” can link to outflows etc.

In the **Streamline** viz, we can then:

* Draw event markers where `event_id` exists.
* Pull labels from the `Event` table (which already fits your ontology).

---

## 3. Plugging into Layer 0 (text) for provenance

You already decided that “everything important should be anchorable to sentences”.

So we add:

```sql
CREATE TABLE finance_provenance (
    transaction_id  INTEGER NOT NULL REFERENCES transactions(id),
    sentence_id     INTEGER NOT NULL REFERENCES sentences(id),
    note            TEXT,
    PRIMARY KEY (transaction_id, sentence_id)
);
```

This gives you:

* For any ribbon segment (transaction) we can:

  * Hover → show `snippet(sentence.text)` (FTS5-backed).
  * Click → open the `document` in context.

It mirrors SensiBlaw’s pattern:

* `EvidenceItem` linked to `Document` / `Sentence`
* Provisions linked to `Document`
* Now: `Transaction` linked to `Sentence`

Everything uses the **exact same substrate**.

---

## 4. Evidence packs & legal side

You already planned signed **Receipts Packs** for legal/evidence use. Finance fits very naturally there.

```sql
CREATE TABLE receipt_packs (
    id             INTEGER PRIMARY KEY,
    pack_hash      TEXT NOT NULL UNIQUE,     -- hash of canonical JSON
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    signer_key_id  TEXT NOT NULL,
    signature      BLOB NOT NULL
);

CREATE TABLE receipt_pack_items (
    pack_id        INTEGER NOT NULL REFERENCES receipt_packs(id),
    item_kind      TEXT NOT NULL,            -- 'transaction','sentence','event','document'
    item_id        INTEGER NOT NULL,         -- interpreted by kind
    PRIMARY KEY (pack_id, item_kind, item_id)
);
```

This lets you create a pack like:

* A set of `transactions`
* The `sentences` where they were described
* The `Event` summarising them
* Optionally a `Claim` or `HarmInstance` from SensiBlaw

Then sign the entire pack. Streamline just needs the `pack_id` to show “this section is exportable evidence”.

---

## 5. Views for Streamline

Streamline wants a clean “just draw me” view. DB-wise, that means **pre-joining** the core things.

### 5.1 A canonical finance ribbon view

```sql
CREATE VIEW v_streamline_finance_segments AS
SELECT
    t.id               AS txn_id,
    t.account_id       AS account_id,
    a.account_type     AS lane,             -- maps to viz lane id
    a.display_name     AS lane_label,
    t.posted_at        AS t,
    t.amount_cents     AS amount_cents,
    t.currency         AS currency,
    tr.id              AS transfer_id,
    tr.inferred_conf   AS transfer_conf,
    efl.event_id       AS event_id,
    efl.confidence     AS event_conf,
    fp.sentence_id     AS sentence_id
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

The **Streamline backend** can then:

* Filter by `account_id`, time window, actor, case, etc.
* Emit JSON shaped exactly as your `segments` contract.

You can create **similar views** for:

* Speech (utterance energy, sentence density)
* Legal overlays (claims, wrong types, harms against the same time axis)

and then unify them at the API layer.

---

## 6. “Every transaction classified or deliberately unclassified”

You had this nice goal on the language side:

> Every token is either categorised or deliberately ignorable.

You can mirror that pattern for money.

Add a **classification table**:

```sql
CREATE TABLE transaction_tags (
    transaction_id INTEGER NOT NULL REFERENCES transactions(id),
    tag_code       TEXT NOT NULL,     -- 'RENT','GROCERIES','CAR_REGO','UNKNOWN_REVIEW'
    source         TEXT NOT NULL,     -- 'user','rule','ml_suggestion'
    confidence     REAL NOT NULL DEFAULT 1.0,
    PRIMARY KEY (transaction_id, tag_code, source)
);
```

And optionally a `STOP_TAG` / `IGNORE` concept:

* If a transaction is tagged as `tag_code = 'NOISE'` or `'UNCLASSIFIED_OK'`, you can say:

  * “We looked at this; it’s explicitly not part of the narrative”.

This is the **financial analogue** of:

* `tokens.flags` + `lexeme_concepts` + `STOPWORDS`

and gives you a tidy completeness story across both **words** and **money**.

---

## 7. How this plugs in conceptually

* **Schema-wise**:

  * Finance is just another **segment of your ontology** that:

    * Points down to Layer 0 (`sentences`)
    * Talks to L1 (`Events`, `Actors`)
    * Can be pulled into SensiBlaw’s `EvidenceItem`/`Claim` graphs via `receipt_packs`.

* **Streamline-wise**:

  * It reads from views (`v_streamline_finance_segments`, etc.), not raw tables.
  * It doesn’t care whether finance came from CSV or ISO20022, or whether an event is “TiRCorder” or “SensiBlaw” — just that they share the same time axis and IDs.

* **Extensibility-wise**:

  * You can bolt on:

    * more adapter formats without schema change,
    * more classifiers without changing Streamline,
    * more legal structures without touching finance tables.

---

If you like, next I can:

* Draft a **short SQL migration file** that adds these finance tables on top of your existing schema, or
* Write a **Mermaid ER diagram** for “how finance entities sit next to Events / Actors / Sentences” to drop into `docs/streamline_schema.md`.


Right, this is the juicy bit: **money + conversations** as *first-class* things that sit alongside “law” in the ontology, not bolted on afterwards.

I’ll treat it as:

1. How finances become true first-class citizens in the 6-layer stack
2. How social / chat streams + sentiment plug into the same stack
3. How we actually *see* patterns like “user more distressed + partner behaviour changes + money siphons” across views

---

## 1. Making finances truly first-class

You already have the low-level finance schema (accounts, transactions, transfers) and linkage into Events + Sentences. To make them **ontologically first-class**, we plug them into the *same axes* as everything else:

### a) Events & Actors (Layer 1)

Treat each transaction as a *specialised event*, not a separate universe.

* `Event.event_kind` gains:

  * `FINANCIAL_TRANSACTION`
  * `FINANCIAL_AGREEMENT` (e.g. “we agreed I’d pay all rent”)
  * `FINANCIAL_SHOCK` (unexpected charge, garnishee, cut-off)
  * `FINANCIAL_WITHHOLDING` (bill not paid, money not given)

* Roles on those events:

  * `PAYER`, `PAYEE`, `ACCOUNT_HOLDER`, `BENEFICIARY`, `INSTITUTION`

* Link to transactions (from earlier):

  ```sql
  event_finance_links(event_id, transaction_id, link_kind='caused'|'evidence'|'context')
  ```

So “paid bond”, “partner drained savings”, “Centrelink stopped” are all *Events* that just happen to be evidenced by `transactions`.

### b) Protected Interests & Harms (Layer 5)

Make financial security explicit, not implicit:

* `protected_interest_types` includes things like:

  * `FINANCIAL_SECURITY`
  * `HOUSING_STABILITY`
  * `BASIC_NEEDS` (food, utilities)
  * `ABILITY_TO_WORK` (e.g. car payments, tools, childcare)

* `harm_classes` includes:

  * `HARM_FINANCIAL`
  * `HARM_HOUSING` (eviction/instability)
  * `HARM_DEPENDENCY` (forced financial dependence)

* `HarmInstance` for money:

  ```text
  event_id            → the financial event (“rent not paid” / “card maxed”)
  protected_interest  → FINANCIAL_SECURITY / HOUSING_STABILITY
  harm_class          → HARM_FINANCIAL / HARM_HOUSING
  concept_id          → ECONOMIC_STRAIN / LOSS_OF_INCOME (semantic atom)
  sentence_id         → where the user explains “he stopped paying rent”
  ```

Now finances show up in *exactly the same way* as bodily harms: as **harm instances** to protected interests, not “just numbers”.

### c) Wrong Types & Duties (Layer 4)

Introduce explicit wrongs around economic control:

* `wrong_types` (per legal system / perspective):

  * `ECONOMIC_ABUSE`
  * `FINANCIAL_COERCION`
  * `FINANCIAL_NEGLECT` (e.g. refusing to contribute to joint necessities)
  * `CONTROL_OF_EARNINGS`
  * `UNCONSENTED_DEBT` (taking loans in victim’s name)
  * `WITHHOLDING_CHILD_SUPPORT`

Each gets **elements** that bind to the finance layer:

```text
WrongType: ECONOMIC_ABUSE (AU.FAMILY.Violence)

Elements:
- CONDUCT: concept = UNFAIR_CONTROL_OF_MONEY
- RELATIONSHIP: pattern = INTIMATE_PARTNER / CAREGIVER
- RESULT: harm_class = HARM_FINANCIAL, HARM_DEPENDENCY
- CONTEXT: condition = PATTERN_OVER_TIME (not one-off)
```

*How this hits finance:*

* Patterns like:

  * user income ↑, partner discretionary spending ↑, user cash reserves ↓
  * repeated unpaid bills while partner has plenty of personal spending
  * joint account emptied right before separation

…become **evidence for those wrong types**, not just “interesting graphs”.

### d) Value Frames (Layer 6)

Finance is deeply moralised:

* `value_frames` that touch money:

  * `EQUITABLE_SHARING_IN_RELATIONSHIP`
  * `CARING_FOR_DEPENDANTS`
  * `AUTONOMY_OVER_ONE’S_EARNINGS`
  * `HUMAN_RIGHTS_DECENT_STANDARD_OF_LIVING`
  * `TIKANGA_WHAKAPAPA_DUTIES` (if e.g. money being withheld from whānau obligations)

* `wrongtype_valueframes` + `protectedinterest_valueframes` say:

  * economic abuse violates `AUTONOMY` + `CARING_FOR_DEPENDANTS`
  * withholding school fees violates `CHILD_INTERESTS` + HR frames

So money isn’t just “data”; it is tied to **what is considered just or unjust** in multiple systems.

---

## 2. Integrating social / chat streams + sentiment

You already treat recordings / transcripts as Layer-0 Documents with Utterances. Social feeds are structurally the same.

### a) Social feeds as Documents & Utterances

For each platform / channel:

* `documents`:

  * `doc_type = 'SOCIAL_FEED' | 'DM_THREAD' | 'SMS_EXPORT' | 'EMAIL_THREAD'`
  * text lives in `TextBlock`, then `sentences`.

* Each message:

  * `utterances` row with `start_time`, `sender_actor_id`, maybe `platform`.

* Link utterances ↔ sentences via `utterance_sentences`.

So a Twitter thread, WhatsApp chat, Facebook DM – all just become **streams of utterances** on the *same substrate* your court transcripts use.

### b) Sentiment / concern / pattern features

Per **sentence** or **utterance** you attach features like:

```text
sentiment_score   (e.g. -1..+1)
emotion_primary   (JOY, ANGER, FEAR, SADNESS, SHAME, NUMB…)
subjectivity      (0..1)
concern_score     (0..1) – specialised “worry/concern” detector
control_language  (0..1) – partner’s controlling / threatening language
```

Implementation-wise this can be a `utterance_features` table:

```sql
CREATE TABLE utterance_features (
    utterance_id   INTEGER PRIMARY KEY REFERENCES utterances(id),
    sentiment      REAL,         -- -1..1
    arousal        REAL,         -- 0..1
    concern_score  REAL,
    anger_score    REAL,
    fear_score     REAL,
    shame_score    REAL,
    control_score  REAL,         -- language about control / threats
    blame_score    REAL          -- “this is your fault”, “you always…”
);
```

Then you can **aggregate over time**, per relationship:

```sql
CREATE TABLE relationship_metrics (
    id                INTEGER PRIMARY KEY,
    relationship_id   INTEGER NOT NULL,   -- A↔B link
    window_start      TIMESTAMP NOT NULL,
    window_end        TIMESTAMP NOT NULL,
    speaker_actor_id  INTEGER,            -- who is speaking
    mean_sentiment    REAL,
    mean_concern      REAL,
    mean_control      REAL,
    msg_count         INTEGER
);
```

This is how you get “from date X onward, user’s concern ↑, partner’s control ↑”.

### c) Relationship as shared container

You can model:

```sql
relationships(id, actor_a_id, actor_b_id, relationship_kind)
```

Then:

* finance:

  * accounts tagged to either/both actors
  * transactions tagged to relationship (“household spend” vs “personal spend”)

* social:

  * utterances tagged by which relationship they belong to (DM thread or chat with that partner)

* events:

  * `Event.relationship_id` for key incidents (arguments, moves, breakups)

All your time-series aggregates become **per-relationship streams**.

---

## 3. Putting it together: streams & pattern detection

Conceptually, you want **multiple streams** per relationship:

* `Stream: CHAT_SENTIMENT` (per direction)
* `Stream: FINANCIAL_BALANCE` (per account)
* `Stream: FINANCIAL_DEPENDENCY` (how reliant A is on B’s money)
* `Stream: LEGAL_PRESSURE` (count/weight of claims, orders, deadlines)

### a) Define abstract “streams” on top of the DB

You don’t have to create a new table, but it often helps:

```sql
CREATE TABLE streams (
    id              INTEGER PRIMARY KEY,
    relationship_id INTEGER,
    stream_type     TEXT NOT NULL,   -- 'CHAT_SENTIMENT', 'FINANCE_NET', 'LEGAL_HARMS'
    direction       TEXT,            -- 'A_TO_B','B_TO_A','JOINT'
    label           TEXT NOT NULL
);

CREATE TABLE stream_points (
    stream_id       INTEGER NOT NULL REFERENCES streams(id),
    t               TIMESTAMP NOT NULL,
    value           REAL NOT NULL,
    payload         JSON,            -- optional: extra detail
    PRIMARY KEY (stream_id, t)
);
```

Then:

* A chat sentiment stream for “User → Partner” has time points with `value = mean_concern_score` or `mean_sentiment`.
* A finance stream has `value = net_outflow_from_user` or `balance`.
* A legal stream has `value = # of active orders / severity score`.

Your **Timeline Ribbon viz** just stitches these stream_points into ribbons.

### b) Cross-stream alignment (the pattern you described)

Example you gave:

> starting date X – we notice that xyz pattern from partner also starts around then

Concretely:

* For relationship R (User ↔ Partner):

  * Stream S1: `User concern_score over time` (chat/diary).
  * Stream S2: `Partner control_score over time` (chat).
  * Stream S3: `Net financial dependence of User on Partner` (ratio of User personal income vs Partner contributions + joint spending).

We can:

* Compute **rolling windows** (e.g. weekly):

  * `mean_concern_user(t)`
  * `mean_control_partner(t)`
  * `dependency_ratio(t)`

* Detect change points:

  * “concern_user” jumps +2 SD after some date.
  * “control_partner” jumps around the same period.
  * “dependency_ratio” crosses a threshold (e.g. user now 80–90% dependent on partner’s income).

Then we **annotate**:

* A “pattern event”:

  ```text
  Event.event_kind = RELATIONAL_PATTERN_SHIFT
  Event.context    = INTIMATE_RELATIONSHIP
  Event.relationship_id = R
  Event.occurred_at = approx change-point date
  ```

* And attach HarmInstances & candidate WrongTypes:

  * `HarmInstance` with `protected_interest = FINANCIAL_SECURITY` / `PSYCHOLOGICAL_INTEGRITY`
  * Candidate `WrongType = ECONOMIC_ABUSE` / `COERCIVE_CONTROL` (depending on jurisdiction)

You display this in the viz as:

> “Around June 2024:
> – User’s concern in messages increased
> – Partner’s controlling language increased
> – User’s financial dependence also increased”

but you are very clear that this is **pattern detection, not a verdict**.

---

## 4. Safety + interpretive stance

Because this is sensitive as hell, the system should:

* Treat all analytic flags as:

  * **“Something to look at”**, not “your partner is definitely abusive”.

* Always surface:

  * The **raw evidence snippets** (messages, transactions) via sentence/doc links.
  * The **ValueFrames** used (e.g. “this would worry family-violence services because it affects autonomy and financial security”).

* Allow multiple perspectives:

  * State legal frame (e.g. family-violence legislation).
  * Human-rights child/women’s rights frame.
  * Indigenous or religious frame if the user wants that lens.
  * User’s own felt frame (“this feels unjust to me”).

Morality is handled by **ValueFrames and perspectives**, not by hard-coding labels like “BAD_PARTNER” into the schema.

---

## 5. Short version

* **Finances as first-class**:

  * Transactions are Events.
  * They produce HarmInstances on protected interests like `FINANCIAL_SECURITY`.
  * WrongTypes like `ECONOMIC_ABUSE` and `FINANCIAL_NEGLECT` are defined in terms of patterns over those events.
  * Remedies are things like maintenance orders, property splits, debt releases, etc.

* **Social streams as first-class**:

  * All messages are Utterances → Sentences → Tokens → Concepts.
  * Sentiment / concern / control features are attached per utterance, aggregated per relationship/time window.

* **Cross-view grouping**:

  * Define relationship-scoped Streams (`CHAT_SENTIMENT`, `FINANCE_NET`, `LEGAL_HARMS`).
  * Compute rolling metrics and change points.
  * Represent major shifts as Events with candidate harms/wrongs.
  * Visualise them together in the ribbon/timeline view with provenance and value-frame overlays.

If you like, next I can sketch a **concrete worked example** end-to-end:

> “From March to July, User’s messages get more worried, Partner’s language gets sharper, money starts being siphoned out of joint account, and the system surfaces this as a potential economic-abuse pattern with links to relevant law and value frames.”
