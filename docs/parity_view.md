# Tit-for-Tat / Parity View

The parity view is a negotiation aid that mirrors each party's stated and implied
interests side-by-side. It is designed for matters such as consent orders or
property settlements where each concession by one party can become leverage for
another claim. By capturing both explicit pleadings and the metadata that hints
at hidden priorities, the view highlights when issues are strictly zero-sum,
where asymmetrical valuations create opportunities for trade, and how a change
in one dimension shifts bargaining power elsewhere.

## Purpose

- Surface **direct conflicts** where the same item has opposing outcomes.
- Detect **hidden asymmetries** by comparing narrative importance with
  objective metrics such as market value or precedent ranges.
- Suggest **potential trade-offs** so that a concession on one axis can purchase
  movement on another.
- Provide an auditable artefact for mediators that records which inputs drove a
  proposed compromise.

## Data Inputs

The view unifies structured pleadings, narrative statements, and historical
signals. Each axis is normalised so that parties can be compared without losing
context from their original materials.

| Source | Description |
| --- | --- |
| Party A claims | Extracted from affidavits, position statements, and mediation briefs. |
| Party B claims | Same extraction pipeline as Party A to keep the feature space aligned. |
| Metadata | Asset type, emotional significance score, market value ranges, child-related weightings, temporal urgency, etc. |
| System learning | Historical settlement data, typical concession ratios, jurisdictional norms, and optional reinforcement feedback from past mediations. |

## Data Model

| Object | Key fields | Notes |
| --- | --- | --- |
| `NegotiationAxis` | `identifier`, `category`, `description`, `is_zero_sum` | Groups the asset, liability, or parenting topic being negotiated. |
| `PartyPosition` | `party_id`, `demand`, `priority_score`, `precedent_range`, `narrative_weight` | Represents one side's ask together with their stated importance and typical outcomes. |
| `AxisSignal` | `source`, `value`, `confidence`, `timestamp` | Encapsulates metadata such as valuations or psychological flags that modulate parity scoring. |
| `TradeRecommendation` | `give_axis`, `receive_axis`, `rationale`, `confidence` | Output object that describes a proposed concession swap. |

Existing storage layers (e.g. the versioned document store) can persist the
axis model so mediators can revisit earlier drafts of the negotiation matrix.

## Derived Metrics

1. **Conflict intensity** – compares the numerical distance between parties and
   scales it by `priority_score`. The metric is flagged as red when both parties
   consider the axis high priority and the feasible overlap is empty.
2. **Asymmetry index** – contrasts `narrative_weight` with external valuations.
   When a party is over-indexing on sentiment relative to market value, the
   interface recommends non-monetary concessions.
3. **Trade potential** – scans axes with complementary asymmetry indices (e.g.
   high importance for Party A vs. low for Party B) to generate candidate swaps.
4. **Parity delta** – shows how much leverage shifts if one party moves to the
   midpoint of the precedent range. This helps calibrate tit-for-tat offers.

## Workflow

1. **Ingest claims** using the existing ingestion helpers (PDF parsing, text
   normalisation, concept tagging).
2. **Enrich metadata** via valuation lookups, emotional tone scoring, and child
   welfare weighting models where relevant.
3. **Score axes** by populating the derived metrics and classify each as
   `conflict`, `latent_trade`, or `resolved`.
4. **Render parity view** in the UI by stacking Party A and Party B columns for
   each axis, with badges for conflicts and suggested trades.
5. **Log feedback** from mediators (accepted/rejected swaps) to update the
   system learning layer.

## Example Use Case

Consider a property settlement with three axes: the family home, superannuation,
and parenting time. The parity view might highlight that:

- The family home is a high conflict axis (both parties assign top priority and
  there is no overlap in proposed equity splits).
- Superannuation shows a hidden asymmetry because Party A overvalues the cash
  component relative to market benchmarks; a partial pension offset becomes a
  suggested concession.
- Parenting time reveals a potential trade: Party B is willing to concede an
  extra overnight stay in exchange for retaining a sentimental heirloom valued
  low by Party A.

Mediators can iterate offers while watching parity delta gauges update in real
time, making it easier to frame tit-for-tat exchanges that feel proportionate
on both sides.
