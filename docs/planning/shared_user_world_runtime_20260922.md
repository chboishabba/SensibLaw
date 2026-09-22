# Shared User/World Runtime and Consumer Architecture

Date: 2026-09-22
Status: product/user-story convergence document

## Product framing

SensibLaw is a major semantic/review component in a broader ITIR smart-journal
stack.  The product should therefore support both:

1. provenance-preserving personal/public/professional world construction; and
2. specialised consumers such as legal reasoning, chronology, handoff,
   advocacy, mission/accounting, research and comparison.

The legal proof engine must not become a second world store, and the personal
world must not become an unreviewed evidence oracle.

## End-to-end user path

```text
capture difficult reality
  -> source/revision/span/context
  -> observation/event/claim/hypothesis
  -> review/promote/hold
  -> shared world
  -> consumer dependency slice
  -> reuse reviewed coordinates where scope allows
  -> emit exact residuals only for genuinely missing distinctions
  -> acquire/review new material
  -> update shared world
  -> recompute affected consumers
```

## Personal/private first-class use

Supported user-world inputs include:

- personal journal fragments and notes;
- chats/messages;
- audio/transcripts;
- OpenRecall/browser/app captures;
- schedules/tasks;
- personal documents;
- professional/support notes;
- public materials selected by the user.

Personal records may remain uncertain, contradictory, fragmentary or private.

Required boundaries:

- private hypothesis != fact;
- personal note != professional evidence;
- observer capture != canonical truth;
- approximate chronology != fabricated exact date;
- selected handoff != whole-archive disclosure.

## Consumer families

### Personal
- journal reconstruction;
- timeline reconstruction;
- provenance/receipt inspection;
- obligations/reference support.

### Professional handoff
- lawyer/advocate;
- doctor/psychologist/care team;
- regulator/ombuds;
- journalist/watchdog;
- community/disability support.

### Legal
- matter/fact intake;
- legal atom decomposition;
- authority/source follow;
- support/defeat/counter-defeat proof graph;
- WrongType;
- comparative party routes.

### Operational
- mission actual-vs-should;
- task/commitment continuity;
- reviewed activity mapping.

### Research/public knowledge
- historical/colonisation consumer;
- investigative/public-source consumer;
- comparative narratives/worlds.

## Shared-world reuse

A consumer must first ask whether a required coordinate is already present,
reviewed to the required level and in scope.

```text
required x
  -> shared-world lookup
  -> [reusable] consume
  -> [missing] producer/research
  -> [scope blocked] abstain/exclude
  -> [WrongType] emit corrected residual
```

This prevents repeated research and prevents inappropriate reuse.

## Affected-consumer propagation

A reviewed world delta may affect several consumers:

```text
reviewed Delta W
     |
     v
affected-consumer index
 /       |        \
journal legal    mission
  |      |         |
rerun   rerun     rerun
```

Only declared dependencies trigger recomputation.

Revision/staleness uses the same propagation mechanism and is maintenance, not
the primary discovery loop.

## Adversarial legal proof search

Legal consumers specialise the generic recurrence:

```text
party proposition
 -> legal atoms
 -> support routes
 -> defeaters/exceptions
 -> counter-defeaters/distinctions
 -> WrongType/missing atoms
 -> proof-directed source search
 -> reviewed delta
 -> rerun
```

The existing Pabai regression is the canonical shape:
reachable route -> reviewed defeater -> route defeated -> repair search.

A reachable route means only reachable under the admitted graph.  It does not
predict the court's result.

## Mary-parity relationship

Mary-parity remains the operator-facing fact substrate:

```text
source/excerpt
 -> observation
 -> event/fact
 -> chronology
 -> contestation
 -> review
```

SensibLaw extends that substrate with:

```text
claim
 -> norm/rule
 -> legal atom
 -> support/defeat graph
```

ITIR may carry explicit competing hypotheses/interpretations over the same
source-backed substrate.

## Case and consumer battery

Use a heterogeneous battery rather than one Mabo-specific campaign:

- Pabai: support -> defeat -> repair;
- Yindjibarndi/Yunupingu/Mabo: reviewed shared-doctrine reuse;
- Munkara/Tipakalippa: shared context/authority without legal-issue collapse;
- Murujuga: open discovery control; no forced Mabo join;
- colonisation consumer: historical + statutory + modern legal world;
- personal-world -> lawyer handoff: selected factual coordinates reused while
  private hypotheses stay excluded;
- personal-world -> doctor/advocate handoff: same shared world, different scope
  and dependency slice;
- mission consumer: observer activity reused without becoming mission truth.

## Roadmap

### S19 Shared User/World Runtime
Primary substrate.

### S20 Adversarial Legal Proof Search
Primary legal reasoning specialization.

### S21 Real Legal Case Battery
Empirical legal validation.

### S22 Personal World / Smart Journal
First-class personal-world construction.

### S23 Role-Safe Handoff
Scoped professional projections.

### S24 Mission / Activity
Actual-vs-should over reviewed observer mappings.

### S25 Workbench
Journal/Timeline/Matter/Claim/Proof/Mission/Research/Handoff/Source/Comparative.

### S26 Comparative / Multi-world
Party/account/jurisdiction/time/world comparisons.

### S27 Publication / Federation
Replayable, bounded, provenance-bearing exports.

## Acceptance invariants

- no silent truth promotion;
- no silent legal-authority promotion;
- no scope bypass;
- no forced narrative coherence;
- no graph adjacency -> dependency promotion;
- no shared coordinate -> merged consumer ontology;
- no reachable legal route -> predicted judicial outcome;
- no revision event required for ordinary discovery;
- already-paid coordinates quotient out before new research;
- all consequential outputs expand back to sources/revisions/spans/review receipts.
