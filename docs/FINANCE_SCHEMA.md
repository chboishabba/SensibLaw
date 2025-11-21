# Finance Schema

This schema captures accounts, transactions, and transfers as first-class structures that align with the ontology layers.

- **Accounts**: identifiers, ownership, account kinds (personal, joint, institution), and linkage to actors/relationships.
- **Transactions**: amounts, currencies, timestamps, counterparty accounts, and categorisation for inflows/outflows.
- **Transfers**: explicit source/destination joins for money movement across accounts.
- **Event links**: `event_finance_links(event_id, transaction_id, link_kind)` to evidence harms, duties, and pattern shifts.
- **Harm/interest hooks**: protected interests such as `FINANCIAL_SECURITY` or `HOUSING_STABILITY` tied to transaction events.

The schema enables Streamline to render financial streams alongside chat, legal, and narrative signals.
