# Timeline Stream Viz — "Streamline" Roadmap

A single roadmap for building the Streamline timeline visualisation that fuses finance, speech, and legal context. This plan removes prior narrative drafts and keeps one authoritative flow covering scope, sequencing, and responsibilities.

---

## 1. Goals and Scope
* Show a unified time axis with aligned ribbons for finance, speech sentiment, and legal risk/coverage.
* Preserve provenance: every visual element links back to Layer 0 (documents, utterances, transactions).
* Support consent-first handling of sensitive data, with clear boundaries on interpretation (patterns, not verdicts).

---

## 2. Core Inputs and Owners
| Source | Key Fields | Owner |
| --- | --- | --- |
| TiRCorder (speech & narrative) | Documents → Utterances → Sentences; speaker IDs; embeddings; sentiment/concern scores | AI/ML |
| Finance adapters | Accounts; transactions; inferred transfers; account external IDs; raw payloads | Data Eng |
| SensiBlaw (legal) | HarmInstances; WrongTypes; ValueFrames; obligations/remedies; evidence links | Legal Eng |
| User timeline | User-entered milestones (moves, relationships, jobs) | Product |

Dependencies: adapters emit canonical transaction rows; TiRCorder provides sentence-level features; legal layer emits harms/wrongs linked to evidence.

---

## 3. Visual Grammar
* **Ribbons (continuous flows)**: finance net flow/balance, sentiment/concern averages, legal risk/obligation intensity. Width/height encodes magnitude; color encodes source.
* **Threads (siphons/flows)**: directional arrows or bezier threads between accounts/actors to show transfers.
* **Event markers**: discrete events (transactions, harms, orders, user milestones) with icons and tooltips linking to provenance.
* **Stacking**: lanes per actor/relationship; z-depth reserved for drill-down overlays.

---

## 4. Data Pipeline (Sequenced Steps)
1. **Collect** inputs from TiRCorder, finance adapters, legal outputs, and user-entered events. Owners: AI/ML (TiRCorder), Data Eng (finance), Legal Eng (harm/wrong export), Product (user events).
2. **Normalise** into canonical shapes: accounts/transactions; utterances with sentiment; legal harms/wrongs; timeline events. Owner: Data Eng.
3. **Transfer inference** to reconcile intra/inter-account flows. Owner: Data Eng.
4. **Cross-link** evidence: map transactions ↔ events, sentences ↔ harms, actors/relationships across systems. Owner: Platform Eng.
5. **Compute ribbons**: windowed aggregates (net flow, concern/ control scores, legal risk counts) per relationship/account lane. Owner: AI/ML + Data Eng.
6. **Emit viz contract**: JSON payload with streams, events, lanes, and provenance pointers. Owner: Platform Eng.
7. **Render** via chosen stack (see Section 6). Owner: Frontend.

---

## 5. JSON Contract (Viz Engine Input)
```jsonc
{
  "time_range": { "start": "2024-01-01T00:00:00Z", "end": "2024-12-31T23:59:59Z" },
  "lanes": [
    {
      "lane_id": "relationship:partner",
      "kind": "relationship",
      "label": "User ↔ Partner",
      "ribbons": [
        {"id": "finance_net", "type": "finance", "points": [{"t": "2024-03-01T00:00:00Z", "value": -250.0, "src": {"account_id": "acct-1"}}]},
        {"id": "sentiment", "type": "speech", "points": [{"t": "2024-03-01T00:00:00Z", "value": -0.2, "src": {"sentence_id": "s-123"}}]},
        {"id": "legal_risk", "type": "legal", "points": [{"t": "2024-03-01T00:00:00Z", "value": 1, "src": {"harm_id": "h-9"}}]}
      ],
      "events": [
        {"id": "txn-123", "kind": "transaction", "t": "2024-03-02T10:21:00Z", "amount": -250.0, "provenance": {"transaction_id": "txn-123"}},
        {"id": "harm-9", "kind": "legal", "t": "2024-03-05T00:00:00Z", "label": "Economic abuse (candidate)", "provenance": {"harm_id": "h-9", "evidence": ["txn-123", "s-123"]}}
      ]
    }
  ],
  "meta": { "version": "1.0", "generated_at": "2024-03-06T12:00:00Z" }
}
```
Requirements:
* Every point/event includes provenance IDs.
* Time is ISO 8601 UTC.
* Ribbons use consistent cadence (e.g., 1d/1h) decided per stream.

---

## 6. Rendering Stack Options
* **Option A — Svelte + D3**: fast iteration, good for SVG interactions; watch for performance on long timelines.
* **Option B — Canvas 2D + Regl/WebGL (preferred)**: performant ribbon drawing and threads; use WebGL for large datasets and hover picking.
* **Option C — Three.js hybrid**: if 3D layering/drama is required; reserve until after MVP.

Decision: Start with Option B for scalability; expose a thin adapter so lanes/ribbons are declarative.

---

## 7. Interaction Model
* Hover: show tooltip with values and provenance links; highlight correlated ribbons.
* Click: pin details, open evidence drawer with Layer 0 links.
* Zoom/Pan: continuous scroll/drag; snap to events; mini-map for long ranges.
* Mode toggles: finance-only, speech-only, legal-only, or mixed; consent/visibility toggles per lane.

---

## 8. Privacy, Consent, and Interpretive Stance
* Default to opt-in per stream; respect redaction/visibility flags.
* Display patterns as “things to review,” not judgments; always show raw evidence links.
* Support multiple frames (legal, human-rights, user-defined) when labeling harms/wrongs.

---

## 9. Milestones and Responsibilities
1. **Milestone 1 — Data plumbing (2 weeks)**
   * Finish finance adapters + tests; wire TiRCorder outputs; legal harm export with evidence links. Owners: Data Eng (adapters), AI/ML (scores), Legal Eng (harm feed).
   * Deliver JSON contract sample covering all streams.
2. **Milestone 2 — WebGL pipeline (2–3 weeks)**
   * Implement canvas/WebGL renderer for ribbons/threads; ingest JSON contract. Owner: Frontend.
3. **Milestone 3 — Interactions & provenance (2 weeks)**
   * Hover/click, evidence drawer, mini-map; ensure provenance IDs resolve back. Owners: Frontend + Platform.
4. **Milestone 4 — Legal overlays (2–3 weeks)**
   * Render harms/wrongs, obligations/remedies bands, consent toggles. Owner: Legal Eng + Frontend.
5. **Milestone 5 — Polish & exports (2 weeks)**
   * Animations, accessibility, export (PNG/JSON pack), performance hardening. Owner: Frontend + QA.

---

## 10. Deliverables Checklist
* Canonical finance adapters with golden tests; transfer inference documented.
* TiRCorder sentence-level scores accessible via API.
* Legal harm/wrong export with ValueFrames and evidence references.
* JSON contract specification and sample payloads.
* Frontend renderer (Option B) with interactions and consent controls.
* Documentation on provenance resolution and privacy guarantees.

---

## 11. Contact Points
* Data Engineering: finance ingestion, transfer inference, ribbon aggregation.
* AI/ML: TiRCorder features, sentiment/concern scoring, windowed aggregates.
* Legal Engineering: harms/wrongs/value frames, obligations/remedies overlays.
* Platform: cross-linking, APIs, JSON contract emission.
* Frontend: rendering, interaction model, exports.

