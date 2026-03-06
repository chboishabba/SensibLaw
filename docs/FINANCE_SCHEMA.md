# Finance Schema

This schema captures accounts, transactions, and transfers as first-class structures that align with the ontology layers.

- **Accounts**: identifiers, ownership, account kinds (personal, joint, institution), and linkage to actors/relationships.
- **Transactions**: amounts, currencies, timestamps, counterparty accounts, and categorisation for inflows/outflows.
- **Transfers**: explicit source/destination joins for money movement across accounts.
- **Event links**: `event_finance_links(event_id, transaction_id, link_kind)` to evidence harms, duties, and pattern shifts.
- **Harm/interest hooks**: protected interests such as `FINANCIAL_SECURITY` or `HOUSING_STABILITY` tied to transaction events.

The schema enables Streamline to render financial streams alongside chat, legal, and narrative signals.

## Derived Series (Transformations)
Time-series derivations (diffs, aggregates, currency conversions) are modeled
as explicit transformations over canonical observations.

Examples:
- Monthly flow from cumulative totals: `B(t) = A(t) - A(t-1)`
- Currency conversion: `C(t) = B(t) * exchange_rate(t)`

Transformation contracts live in:
- `../../docs/planning/time_series_transformations.md`

This keeps finance observations canonical and derived series auditable.
