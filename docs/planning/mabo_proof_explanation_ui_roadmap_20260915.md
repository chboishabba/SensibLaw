# SensibLaw roadmap: Mabo proof specimen and progressive explanation UI

Date: 2026-09-15

## Goal

Use Mabo as the first end-to-end legal specimen where the same typed object supports:

```text
literal argument
-> legal proposition/issue
-> authority/application
-> support + defeater + comparator
-> residual/acquisition
-> review/payment
-> human-readable explanation
-> exact-source/proof audit
```

The objective is not ceremonial reverence for a famous case and not a global theorem that "proves Mabo". The objective is to make one concrete chain understandable, challengeable, and reopenable.

## Ownership boundary

SensibLaw owns legal meaning:

```text
proposition identity
applicable authority
application/precondition semantics
support / defeater / comparator roles
same-object/source-role distinctions
admissibility and review/payment
legal explanation
```

SLR owns the generic research recurrence:

```text
cheap parse
-> consumer residual
-> typed producer choice
-> bounded acquisition
-> next parse
-> typed evidence/provenance delta
```

ITIR/Svelte owns presentation/projection over the canonical proof specimen.

StatiBaker may expose retrieval/materialisation/history receipts but does not own legal meaning or proof validity.

## User classes

The proof specimen should work for multiple consumers without separate truth models.

### Lay / self-represented / CLC intake

Goal: make a concern or argument more complete and interpretable before advice or filing.

The user should be able to see:

```text
what I am literally saying
what issue the system thinks I am raising
which facts/events matter
which legal rule/authority is potentially relevant
what supports it
what limits/contradicts it
what still needs checking
```

The visible formulation and inferred intended issue remain distinct. A lawyer/CLC can therefore advise on the literal submission, the reconstructed issue, or ask for clarification without silently replacing one with the other.

### Public-interest / activist / political-accountability

Goal: turn a concern into a source-anchored, inspectable argument rather than a link dump or assertion bundle.

This supports workflows such as:

```text
claim by institution/politician
-> exact source
-> predicate events
-> relevant statutory/policy coordinates
-> supporting and contrary material
-> unresolved residuals
-> questions suitable for CLC, representative, journalist, regulator, or court pathway
```

This does not create standing, legal advice, or factual truth automatically. It makes the argument and its missing dependencies explicit.

### Lawyer / court / expert

Goal: reopen every explanation into its exact source/proof coordinates, see alternative readings, inspect authority/application, and distinguish support, defeaters, comparators, contradictions, and live residuals.

## One canonical proof specimen

Do not create a public simplified graph separate from the expert graph.

Use one canonical Mabo specimen and expose projections:

```text
MaboProofSpecimen
-> pi_explain
-> pi_inspect
-> pi_source
-> pi_graph
```

Projection changes visibility, not semantic state.

## Progressive disclosure

Default policy:

```text
argument-first
-> graph-second
-> provenance-on-demand
```

A lay user should not begin with QIDs, paragraph IDs, hashes, residual classes, source-role tags, or every edge.

### V0: Explain

Answer a human question such as:

```text
Why was Mabo such a big deal?
```

Show one bounded chain:

```text
before
-> proposition challenged
-> what the Court did
-> why that changed the available legal argument space
```

Also show a plain-language boundary such as `What this does not establish` / `What still needs checking`.

### V1: Why / contingent arguments

Expand only the selected proposition:

```text
claim
-> authority
-> applicability
-> support
-> qualifier/defeater/comparator
-> live residual
```

A `Show contingent arguments` action should reveal how the proposition depends on facts, jurisdiction, time, authority, exceptions, or competing lines in the selected corpus.

### V2: Source

Open the exact passage in context:

```text
document identity
court/instrument/source role
paragraph/section/span
version/revision
exact text in surrounding context
full-source action
```

Primary-authority payment requires this verified source/span layer; snippets and encyclopedia summaries cannot substitute for it.

### V3: Research/context

Wiki/Wikidata/public ontologies are a navigation lens:

```text
entity identity
related people/cases/statutes/concepts
cited references
outbound/follow candidates
acquired-source trail
```

The UI should be able to say plainly:

> Wikipedia helped us find this source. It is not the authority for this proposition.

### V4: Proof graph

Expose full typed graph, conflicts, ancestry, source roles, residual/payment history, alternative readings, and review state.

This is a power view, not the mandatory entry point.

## Legal term drill-in

A term such as `estoppel` should not have one overloaded tooltip pretending to be the whole legal doctrine.

Progressive drill-in:

```text
Estoppel
-> short lexical definition / pronunciation / ordinary-language orientation
-> encyclopedia lead/image when useful
-> resolved concept/entity identity
-> Australian authority/legislation/case construction in the selected corpus
-> this matter's predicates/applicability
-> contingent arguments / exceptions / competing lines
```

Important firewall:

```text
Wiktionary definition != Australian legal rule
Wikipedia article != authority
ontology identity != applicability
```

The first hover/card can remain light. The legal construction appears only when requested or when necessary to understand the selected argument.

## Query-indexed disclosure adequacy

Reuse existing `FactorsThrough` machinery.

Expected results:

```text
Q_layExplanation
  may FactorsThrough V0

Q_exactSourceAudit
  does not FactorsThrough V0

Q_primaryAuthorityAudit
  does not FactorsThrough V0

Q_contextNavigation
  may FactorsThrough V3

Q_fullArgumentChallenge
  requires the richer proof/source projection
```

Progressive disclosure is therefore not epistemic compression.

```text
hidden now
!= discarded
!= unavailable
!= unsupported
```

Every explanation-bearing claim needs a reversible path to proof/source coordinates.

## Wiki/Wikidata/source trail

Keep distinct:

```text
QID identity
source identity
same-object evidence
semantic equivalence
authority
```

Follow trail:

```text
wiki/wikidata navigation
-> cited reference/follow candidate
-> acquired source
-> source-role review
-> possible legal/evidentiary payment
```

Do not inherit authority from the discovery surface.

## Mabo flagship acceptance slice

Select one proposition chain already represented by existing Mabo algebra/parsing work.

The slice is complete when one UI specimen can show:

```text
literal statement
-> reconstructed legal issue
-> authority candidate
-> applicability predicates
-> at least one support edge
-> at least one explicit limiter/defeater or comparator where genuinely present
-> live residual or zero-residual state
-> exact source spans
-> bounded plain-language explanation
```

The user must be able to move from the explanation to the exact source and back without changing proof state.

## Implementation order

High alpha now:

1. formal progressive-disclosure / source-reopen parity owner in DASHI;
2. canonical Mabo proof-specimen DTO/interface in SensibLaw;
3. thin Mabo SLR profile adapter using existing SLRC/SLRE recurrence;
4. source inspector projection with exact spans/version/source role;
5. Wiki/Wikidata context projection with explicit discovery-vs-authority wording;
6. `Explain <-> Inspect` UI in `itir-svelte` over the same specimen;
7. one end-to-end Mabo proposition specimen.

Defer until the flagship works:

- graph visualisation polish for its own sake;
- broad legal corpus ingestion just to increase node count;
- custom Mabo-only source model;
- Streamlit as destination UI;
- generic legal-term ontology expansion not demanded by an active argument;
- UI exposure of internal IDs/hashes by default.

## Acceptance language

A lay user should be able to leave with an answer to:

```text
What was the legal assumption/problem?
What did the Court change or reject?
Why was it legally possible to do that?
Which primary sources support that account?
What qualifications or competing arguments matter?
What is still unresolved?
```

A lawyer/researcher should be able to audit the exact same object rather than receiving a separately generated summary.