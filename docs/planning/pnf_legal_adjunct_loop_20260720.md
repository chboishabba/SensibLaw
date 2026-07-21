# PNF-driven legal adjunct and Legal IR loop

Date: 2026-07-20

## Parser doctrine

The repository doctrine is exact:

```text
one media adapter
  -> one canonical text substrate
  -> one parser spine
  -> PNF
```

There is no legal parser, source-family parser, normative extraction profile, or
verb-to-law router. Source provenance is retained as evidence metadata but does
not select semantic interpretation.

All semantic structures—including obligation, prohibition, permission, power,
liability, entitlement, condition, exception, burden, judicial holding,
distinguishing treatment, commencement, amendment, and repeal—must arise from
PNF construction and refinement.

Legal IR is downstream:

```text
legal source bytes
  -> same media adapter
  -> same canonical text substrate
  -> same parser spine
  -> legal-corpus PNF
  -> Legal IR projection
```

Legal IR is an operational ABI over PNF state. It does not own an independent
semantic interpretation.

## Two acquisition classes

Seed acquisition and adjunct acquisition are distinct.

### Seed acquisition

Seed acquisition supplies the initial tranche from explicit files, URLs,
declared source-family manifests, or an explicit broad jurisdiction follow.
The complete runner no longer broad-crawls legal profiles for GWB or AU merely
because a legal profile exists. Broad legal follow occurs only when requested
with `--seed-legal-follow`, or when a tranche such as Brexit has no local seed
corpus and requires a bounded seed.

### PNF-demanded legal adjunct acquisition

After deterministic local compilation and provisional world construction:

```text
ordinary PNF
  -> explicit legal residual/facet
  -> NormativeInteractionDemand
  -> LegalSourcePlan
  -> exact endpoint selection
  -> bounded legal source acquisition
  -> same adapter/parser/PNF path
  -> Legal IR projection
  -> typed reconciliation and pressure
```

A predicate lemma does not create legal work. In particular:

```text
predicate = drive
requested facets = {local_type_unresolved}
```

produces no legal demand.

A legal demand requires an explicit trigger such as:

```text
legal.relevance_unresolved
legal.authority_absent
legal.applicability_unresolved
legal.interpretation_unresolved
```

and a structural signature supplied by PNF:

```text
legal.interaction_signature:<signature-ref>
```

Acquisition readiness additionally requires:

```text
legal.jurisdiction:<jurisdiction>
legal.source_role:<role>
legal.authority_level:<level>
```

Optional facets include:

```text
legal.time:<time-or-version-envelope>
legal.provider_profile:<declared-endpoint-ref>
legal.request:<requested-authority-facet>
```

Missing jurisdiction, source role, authority level, or structural signature
blocks acquisition. The planner does not broaden a blocked demand.

## Algebra

Let:

- `N_W` be world/factual PNF;
- `D_L` be normative interaction demands;
- `P_L` be legal source plans;
- `B_L` be acquired legal source artifacts;
- `N_L` be legal-corpus PNF;
- `IR_L` be Legal IR projected from `N_L`.

Then:

```text
N_W -> D_L -> P_L -> B_L -> N_L -> IR_L
```

and reconciliation is:

```text
N_W x IR_L -> LegalTypedMeet
```

A typed meet has separate coordinates for:

```text
structural fibre
jurisdiction
time
actor
conduct
object
circumstance
exception
burden
```

Cross-fibre comparison returns `NO_TYPED_MEET`. Same-fibre comparison remains a
candidate assessment. It does not close applicability, violation, wrong,
liability, burden, or remedy.

## Authority laws

The implementation enforces these non-collapse laws:

```text
legal relevance candidate != applicability
applicability != violation
candidate WrongType != liability
court-held proposition != universal truth
provider candidate != identity
empty legal retrieval != unregulated conduct
Legal IR projection != promoted legal conclusion
```

## Endpoint selection

`follow_legal_source_plan(...)` is deliberately narrow. It accepts a ready
`LegalSourcePlan`, selects only endpoints whose declared jurisdiction,
`source_role`, `authority_level`, and optional endpoint ref match the plan, and
limits following to those endpoint hosts.

For example, an AU request for:

```text
source_role = primary_legislation
authority_level = official
provider_profile = au:federal-register
```

cannot expand into AustLII merely because AustLII is present in the broader AU
profile.

The original `follow_legal_sources(...)` remains available for explicit seed
corpus construction. It is not the PNF relevance mechanism.

## Complete tranche order v0.2

```text
1. source inventory
2. explicit/required seed acquisition
3. canonical projection
4. deterministic local PNF compilation
5. provisional local world/braid
6. registry demand planning
7. legal adjunct demand planning
8. bounded registry acquisition
9. bounded typed legal acquisition
10. adjunct compilation through the same parser spine
11. Legal IR projection from legal PNF
12. typed reconciliation and pressure
13. review packets
14. immutable checkpoint
```

The legal loop may later repeat under explicit iteration, budget, freshness,
new-information, and no-repeat build-key bounds. The current runner performs one
bounded adjunct pass.

## Current implementation boundary

Implemented:

- `src/pnf/legal_adjunct.py`
  - PNF-derived normative demands;
  - legal source plans;
  - Legal IR projection;
  - fibre-safe legal typed meets.
- `src/storage/postgres/legal_adjunct_planner.py`
  - persisted demand-facet planning;
  - legal-PNF row loading for Legal IR projection.
- `src/sources/legal_follow.py`
  - exact typed endpoint selection;
  - bounded plan execution without profile broadening.
- `scripts/run_complete_tranche.py`
  - seed/acquisition separation;
  - post-PNF legal planning;
  - adjunct re-entry through the same compiler;
  - Legal IR and review checkpoints.

Still open:

- richer PNF composition that constructs all normative, exception, burden,
  authority, and legal-transition factors from parser observations;
- persisted normalized tables for legal plans, Legal IR observations, typed
  applicability coordinates, and legal pressure receipts;
- declaration-driven structural signature indexes over the reusable legal
  corpus;
- WrongType, Hohfeldian norm, protected-interest, remedy, and value-frame
  candidate projections;
- bounded iterative acquisition/refinement beyond one pass;
- operator promotion/rejection UI.
