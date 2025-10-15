# Negotiation Tree Core Structure

The negotiation tree captures each disputed item in a family law matter and the
preferences that each party has about the possible outcomes. It is intended to
be a light-weight structure that can be serialised to JSON for downstream
reasoning tools or rendered as a diagram inside the product UI.

## Nodes

* **Issue node** – Represents a single contested issue such as the house,
  superannuation split, or parenting schedule.
* **Outcome node** – Enumerates the stance a party can take on that issue.
* **Preference weight** – Each outcome node stores a numeric weight that
  expresses how strongly the party prefers the outcome (e.g. a normalised value
  from 0.0–1.0 or an ordinal score like 1–5).

The tree is bipartite at each depth: issue nodes only connect to outcome nodes,
and outcome nodes connect back to issue nodes that depend on the chosen stance
(e.g. branching to alternative holiday calendars after selecting a shared care
model).

## Example

The following example illustrates two parties negotiating four issues. Party A
and Party B each have preference weights for the outcomes attached to every
issue. Higher weights indicate a stronger preference.

```text
Matter Root
├── House (issue)
│   ├── Party A: Keep House [0.90]
│   └── Party B: Sell & Split Equity [0.65]
├── Car (issue)
│   ├── Party A: Retain Car [0.40]
│   └── Party B: Transfer Car [0.75]
├── Parenting Time (issue)
│   ├── Party A: 60/40 Schedule [0.80]
│   ├── Party B: 50/50 Schedule [0.85]
│   └── Dependent Issue → Holiday Calendar
│       ├── Party A: Alternate Weeks [0.70]
│       └── Party B: School Term Split [0.55]
└── Superannuation (issue)
    ├── Party A: 55/45 Split [0.35]
    └── Party B: Equal Split [0.90]
```

This representation keeps contested issues explicit while recording each party's
stance and the relative strength of that stance. It also makes it easy to
compute trade-offs (e.g. by summing weights when parties agree) or surface
opportunities for compromise (where the weights are close together). Downstream
services can traverse the tree to suggest packages or highlight issues where the
parties are far apart.
