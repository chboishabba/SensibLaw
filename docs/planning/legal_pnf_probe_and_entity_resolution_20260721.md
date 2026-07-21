# Legal PNF probe and entity-resolution policy

## Parser doctrine

The probe preserves the repository-wide semantic boundary:

```text
one media adapter
→ one canonical text substrate
→ one parser spine
→ PNF
```

There is no legal parser, legal extraction profile, source-family parser, or
verb-to-law map.  Legal IR is projected from legal PNF revisions.

## Probe purpose

The probe answers an empirical question before further semantic work is added:

> What does the ordinary PNF compiler actually construct when given legislation,
> judgments, pleadings, submissions, and administrative decisions?

The executable entry point is:

```bash
python scripts/run_legal_pnf_probe.py \
  --input-directory tests/fixtures/legal_pnf_probe \
  --output-dir /tmp/legal-pnf-probe \
  --compare-legacy
```

It emits, for every canonical document:

```text
compilation.json
parser_observations.json
pnf_graph.json
refined_pnf_graph.json
legal_ir.json
legacy_obligations.json
comparison_ledger.json
entity_resolution_decisions.json
wikidata_plan.json
```

and a corpus-level `coverage_scorecard.json`.

## Differential status

The legacy `RuleAtom` and `ObligationAtom` lanes are diagnostic oracles only.
They may expose coverage gaps, but they do not overwrite or promote PNF.

For each structural coordinate the ledger records:

```text
PNF present?
Legal IR present?
legacy observation present?
coverage state
open residuals
```

A legacy-only observation creates an explicit residual such as:

```text
legacy_modality_candidate_not_reconstructed_in_pnf
legacy_exception_candidate_not_reconstructed_in_pnf
```

No automatic conversion from the legacy result into legal PNF is performed.

## Wikidata: when and why

Wikidata is a candidate identity and context provider.  It is not a legal source,
legal authority, or applicability engine.

The system should not call Wikidata merely because a proper noun or named entity
appears.  A lookup is warranted only where all of the following hold:

1. the factor is entity-shaped;
2. identity remains open (`external_identity_unresolved` or a legal identity
   residual);
3. the factor fills or blocks a legal coordinate, for example:
   - bearer/actor;
   - court or tribunal;
   - party;
   - institution or decision-maker;
   - jurisdiction;
   - legal authority;
4. a stable source surface is available;
5. no reusable fresh candidate snapshot already satisfies the same lookup key;
6. provider budget remains available.

This is represented by:

```text
PNF factor
× Legal IR role use
× unresolved identity pressure
→ LegalEntityResolutionDecision
→ candidate-only ExternalLookupDemand
```

The decision states one of:

```text
candidate_lookup_warranted
not_warranted
blocked_missing_surface
```

A location or person mentioned in a legal document but unused by a legal PNF role
does not trigger the legal-resolution pass.  It may still be handled by the
ordinary external-enrichment planner if its independent world-model identity is
material.

## Two registry passes

The intended tranche architecture has two bounded registry opportunities:

### Ordinary world/PNF pass

Runs after local PNF and provisional world construction.  It handles ordinary
entity and lexical pressure, including aliases, offices, organizations, places,
and lexical senses.

### Legal-materiality pass

Runs only after legal-corpus PNF and Legal IR exist.  It handles identities whose
resolution became material to legal comparison, such as the precise court,
statutory office, institution, party, or jurisdiction filling a legal role.

The second pass must deduplicate against the first pass by semantic lookup key and
reuse existing provider snapshots.  It must not refetch or create a second local
entity solely because the demand arose later.

## Authority boundaries

The following implications are forbidden:

```text
Wikidata candidate → local identity closure
Wikidata entity type → legal actor-class closure
Wikidata office/jurisdiction claim → legal applicability
Legal IR observation → promoted rule
Legacy obligation observation → PNF legal fact
Empty lookup → no legal entity or no applicable law
```

Every provider result remains candidate-only and revision-pinned.  Review or a
separate governed promotion gate is required for identity closure.

## Probe fixture genres

The initial fixture covers:

- obligation, prohibition, permission and exclusion;
- power and entitlement;
- defence, exception and burden language;
- holdings, distinguishing, orders and disposition;
- commencement, repeal and amendment.

The fixture is intentionally small and hand-auditable.  Its purpose is to expose
which structures already emerge from generic PNF and which require improvements
to generic PNF composition.

## Next semantic work after measurement

Probe results should determine the implementation order.  Expected areas include:

```text
modal scope
normative versus epistemic modality
negation composition
condition and exception attachment
holding-content wrappers
burden bearer and standard
commencement/amendment/repeal transitions
legal time and rule-version intervals
```

These improvements belong in generic PNF construction.  Legal IR should continue
to normalize and project those structures, not rediscover them.
