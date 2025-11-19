# ITIR Product-Combinatorial Roadmap

Gotcha — so: “yes, we’re refactoring, but don’t throw away the good bits.”

Let me pull the main lessons from **tircorder-JOBBIE + docs** and show how they inform the **new finance / Streamline design**.

---

## 1. Lessons from `transaction_analysis.py` itself

### ✅ Good things to carry forward

1. **Graph-first mental model is right**

```python
graph = build_transaction_graph(transactions)
cycles = find_transaction_cycles(graph)
communities = detect_transaction_communities(graph)
```

* Treating money as a **graph of accounts and flows** is exactly what we want.
* Aggregating edges by `(source_account, destination_account)` with:

  * `transactions`: list of underlying objects
  * `weight`: total amount

…is *perfect* for both:

* **investigative graph views** (cycles, clusters), and
* **Streamline** (those same edges become curved branches).

👉 Lesson: keep **NetworkX-style analysis** as a separate layer that consumes *canonical* finance data, instead of baking analytics into storage.

2. **Cycles + communities as first-class outputs**

`find_suspicious_cycles` returning `{"graph", "cycles", "communities"}` is a nice, small surface:

* Cycles → potential money-go-round / layering.
* Communities → “who’s financially entangled with whom?”.

👉 Lesson: in the new world, we still want **one call** that returns:

* a graph,
* cycle sets,
* community partitions,

but now also:

* references to **Events**, **Sentences**, and **Receipt Packs** for provenance.

3. **Minimal, implementation-agnostic API**

Everything is typed in terms of `Transaction` objects and networkx, not a specific DB. That makes it:

* testable in isolation,
* reusable in ITIR / SensiBlaw,
* easy to point at a mock dataset.

👉 Lesson: keep an **analysis-service layer** that is ignorant of storage; just give it a list of domain `Transaction` objects.

---

### 😬 Where the old approach hits limits

1. **Account identity is too ad-hoc**

Right now `source_account` / `destination_account` are basically opaque labels. There is no:

* linking to `Actor` / person,
* multi-tenant support,
* notion of “this is *my* account vs external party”.

👉 New schema fixes that with explicit `accounts` plus optional `accounts.owner_actor_id` / `account_actors` join.

2. **No time windowing / segmentation**

All transactions go into **one big graph**:

* Great for small sets,
* Not good when you want:

  * “last 90 days”,
  * “only flows that touch Case X”,
  * “just the months around this life event”.

👉 New design: views / queries that slice by time, case, actor, and then pass that subset to the graph layer.

3. **No provenance links**

The graph knows nothing about:

* the **sentences** describing a transfer,
* the **events** it relates to,
* whether it’s in a **signed Receipt Pack**.

👉 New design adds:

* `finance_provenance(transaction_id, sentence_id)`
* `event_finance_links(event_id, transaction_id, link_kind, confidence)`
* `receipt_packs` / `receipt_pack_items`

…so those same `Transaction` objects can carry `sentence_id` / `event_id` / `pack_id` along for Streamline + legal use.

4. **Scalability / ergonomics**

For a real bank export:

* Graph with thousands of nodes/edges → heavy.
* You probably want:

  * thresholds (`min_amount`, `min_edge_weight`),
  * time-sliced graphs,
  * account-subset graphs.

👉 Lesson: bake in **filtering knobs** at the loader / view level, *not* into the algorithms.

---

## 2. Lessons from TiRCorder’s roadmap & connectors

From the ITIR / TiRCorder roadmap:

* Mid-term aim: **“Unified Timeline Visualizer”** merging 3D, ribbon, and financial timelines into a cohesive dashboard. 
* Also: **Live Data Fusion** and multi-source integration (social, calendars, etc.). 

From the social / health connectors:

* `twitter_backup.md` and `facebook_backup.md` describe the pattern:

  * each connector has **clear expectations of file layout**,
  * does its own normalization into a common event shape.
* `google_fit.md` shows the same pattern for APIs (scopes, token, then clean metrics). 

👉 Lessons to carry forward for finance:

1. **Finance connectors should look like the others**

* One doc per connector: “CBA CSV”, “OFX/MT940”, “Open Banking JSON”.
* “Expected layout” → “how we parse it” → “normalized fields”.
* Consistent emitted model: `RawTransaction` → `transactions` + `transfers`.

2. **Everything lands in one unified substrate**

Exactly like social and calendar land in the timeline, bank data should:

* flow through adapters → canonical tables,
* then feed both:

  * **3D platform/contact timelines**, and
  * **Streamline financial ribbons**.

---

## 3. Lessons from the ribbon / financial timeline docs

You’ve already articulated the “feel” and purpose really well:

* Ribbon timeline goals emphasise:

  * **website-first, responsive**,
  * **storytelling rather than just accounting**,
  * **Z-depth layering for multi-account flows**. 

* Financial timeline vision extends that:

  * Single vertical ribbon for main account,
  * Smooth, proportional branches that peel off,
  * Events as anchors,
  * Light, non-technical analysis,
  * Apple-keynote aesthetic. 

👉 Concrete schema/behaviour lessons:

1. **Model flows as segments, not only as transactions**

Streamline will want something like:

* `v_streamline_finance_segments(account_id, t, amount, lane, transfer_id, event_id, sentence_id)`

We should **materialise or view** these segments instead of composing them ad-hoc in the UI.

2. **You need proportions at the DB or service level**

Branches whose width is “10% of income this period” means:

* queries that summarise:

  * period income,
  * per-destination outflow fractions.

So: design DB views or small analytics jobs that compute:

* “siphon % per destination per period”
* “growth of branch X over time”.

3. **Narrative objects must be first-class**

Since events & story are central, we should:

* always permit linking:

  * `Transaction` → `Event` → `Sentence` / `Utterance`,
* and store short **event cards** as structured data, not only free text.

That way the ribbon timeline doesn’t need to invent its own event store.

---

## 4. Lessons from the 3D timeline docs

The 3D timeline axis doc already fixed a pattern: 

* **X – Platform**
* **Y – Time**
* **Z – Contact**

For Streamline/finance we effectively re-use the template:

* **Y: Time** is still the spine.
* One axis (X or Z) is **account / lane**.
* The remaining dimension is used for **contact / category / legal overlay**.

👉 Lesson:

* Don’t invent new axis semantics; keep **time vertical** and re-use the “lane by category” idea from 3D.
* This keeps cognitive load down when moving between ITIR views.

---

## 5. What that means for the refactor in practice

If we summarise “lessons to carry forward” into actionable design moves:

1. **Split storage vs analysis clearly**

   * Storage: `accounts`, `transactions`, `transfers`, `event_finance_links`, `finance_provenance`, `transaction_tags`.
   * Analysis: NetworkX / graph utilities (`build_transaction_graph`, `find_transaction_cycles`, communities) that consume a pure Python `Transaction` view over that data.

2. **Add provenance everywhere**

   * Keep the old `Transaction` edge mindset, but now attach:

     * `src_txn_id`, `dst_txn_id`,
     * `sentence_id` (or list),
     * optional `event_id` / `pack_id`.
   * That lets Streamline and SensiBlaw jump between **flow**, **story**, and **law** without glue hacks.

3. **Keep the “simple API” surface**

   * Preserve a one-shot `analyse_transactions(...)` style entry point that returns:

     * graph + cycles + communities,
     * plus light summary stats for UI (branch proportions, top hubs, etc).

4. **Treat finance connectors like Twitter/Facebook/GoogleFit**

   * Each has:

     * dedicated doc,
     * clear parsing rules,
     * unified output model.
   * All of them end at the same schema so the ribbon/3D timelines don’t care where data came from.

5. **Design with the ribbon vision explicitly in mind**

   * All new analytics should ask:

     * “Can this be shown as a ribbon width, branch, or event card?”
   * If yes, add it as a **column or view** that Streamline can consume directly.

---

If you want, next step could be:

* I draft a **`finance_schema.sql` + `finance_adapters.py` + `finance_analysis.py` sketch** that:

  * mirrors lessons above,
  * refactors your current `Transaction` class to line up cleanly with the DB,
  * and provides a ready-made bridge for Streamline + SensiBlaw.
