# Human Tools Integration (Logseq / Obsidian)

## Purpose
Clarify how human thinking tools interact with ITIR/SensibLaw without
contaminating authority. The goal is epistemic hygiene, not automation.

## First principle
Exploration is allowed. Authority is gated.

ITIR may host hypotheses and exploratory reasoning, but must always make their
status explicit and non-authoritative unless promoted by rule.

## Division of labor

### Human tools (Logseq / Obsidian)
- hypotheses, planning, interpretation
- TODOs, priorities, narrative
- disagreement and speculation

### ITIR / SensibLaw
- span-anchored facts
- provenance and diffs
- deterministic references
- explicit epistemic status

## Interaction model (asymmetric)
- Human tools query or reference ITIR/SensibLaw.
- ITIR/SensibLaw emits read-only facts and provenance blocks.
- No two-way mutation. No copy-paste as authority.

## Integration patterns

### A. Stable reference embeds
Use IDs and spans, not copied text.

Example:
```
- Obligation reference: sb://obligation/OBL-2025-031
  (rev: 2025-01-14 → 2025-02-02)
```

### B. Provenance blocks (machine-written)
```
> SL CHECK
> Source: Crimes Act 1914 (Cth), s 233BAB
> Span: chars 812–1044
> Status: unchanged since 2021-07-01
> Signals: none
```
These blocks are generated and refreshable. Humans comment around them.

### C. Query-backed tasking
```
TODO Review changes to obligations affecting "employer"
:sl-query: actor=employer AND changed_since=2025-01-01
```
Human tools handle scheduling. SL returns deterministic result sets.

### D. Interpretation quarantine
Keep human interpretation separate from SL facts.

```
## Interpretation (human)
I think this implies contractors are excluded unless…

## SL facts
- Obligation OBL-981 applies to "employer"
- No exception spans referencing "contractor"
- No cross-version change detected
```

## Scheduling and deadlines
SL emits temporal facts (e.g., effective dates). Human tools decide deadlines
and urgency. SL must never assert "due" or "required by".

## Identity boundaries
- Note titles, tags, and backlinks never become SL identifiers.
- SL IDs remain machine-issued and stable.

## Refresh semantics
- SL outputs are refreshable, diffable, and replaceable.
- Avoid copy-paste permanence; prefer references.

## Doctrine sentence
SL provides authoritative, read-only facts with provenance; human tools
organise, interpret, and act on them.
