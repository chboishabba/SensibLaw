# Automation & Intelligence

SensibLaw's automation layer enriches negotiation and policy workflows with
lightweight intelligence that builds on the rules extractor, ontology tagger, and
historical case repository. The platform stitches these primitives into
workflows that help teams surface trading ranges and rehearse negotiation moves
without leaving the console.

## Natural-language extraction

* **Passive signal harvesting.** Statements gathered from intake interviews,
  emails, or form submissions (for example, "we'd consider selling if…") are
  piped through the `rules.extractor` module and ontology tagger to identify the
  actor, action, and qualifying conditions. The resulting structured rule
  objects automatically seed concession points and weightings.
* **Auto-suggested concessions.** Extracted intents feed into checklist
  components like `ProvisionAtomChecklist`, ensuring that negotiators see the
  concessions that counterparties have implicitly floated alongside the ones
  they have committed to explicitly.

## Scenario simulation

* **Interactive adjustments.** Each concession from the checklist is bound to a
  slider or toggle within the Streamlit console. Adjusting a slider recomputes a
  "fairness index" by combining the concession weights, rule modality, and any
  cultural flags applied during ingestion.
* **Real-time ratios.** The same adjustment updates a projected win/loss ratio
  for both parties, helping teams visualise how a new concession shifts the
  perceived balance of the deal before it is tabled.

## Historical learning

* **Similarity lookups.** Concession bundles are embedded using the existing
  concept cloud pipeline and compared against past matters stored in the
  `VersionedStore`. The nearest matches highlight compromise corridors that have
  previously worked for similar parties or fact patterns.
* **Playbook prompts.** When a match is found, the console surfaces the
  historical resolution, extracted rules, and ontology tags so negotiators can
  decide whether to mirror the precedent or consciously diverge from it.
