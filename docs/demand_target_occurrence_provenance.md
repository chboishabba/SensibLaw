# Demand trigger and target occurrence provenance

A demand's lexical key is not its semantic world-entity target.

The GWB H9 audit exposed demands whose old occurrence support landed on predicate tokens such as `Believed`, `Begins`, `Drop`, and `Seemed`, while a parser entity span happened to cover nearby name tokens. H9 must not repair that by trimming the entity span or selecting a nearby noun.

The producer contract is now:

```text
producer
  -> trigger occurrence: why the demand exists
  -> target occurrence: what exact token/object the unresolved question is about
  -> evidence occurrences: other exact tokens supporting the producer derivation
```

Only the **target occurrence** can authorize H9 world-entity admission.

## Carrier

`semantic_pnf_demand_occurrence_provenance` stores producer-authored occurrence rows:

- role `1`: trigger;
- role `2`: target;
- role `3`: evidence.

`register_numeric_pnf_demand_occurrence(...)` is the generic producer API. It rejects a token unless its parser run/document/span belongs to the demand's source region. If an object is supplied, that object must have exact `semantic_pnf_object_token_support` for the same token in the same region.

No nearest-object, lexical similarity, title case, regex, or NER trimming is part of registration.

## Existing numeric factor producer

For current factor-derived demands, a demand replay can recover its producer trigger from already-authored factor structure only when there is exactly one pair satisfying:

```text
same source region
+ expected factor type
+ factor support token
+ token lemma == demand lexical key
```

The lexical key is therefore allowed to identify the **trigger** within the factor that generated the demand. It is never promoted to target provenance.

Other factor support tokens become evidence occurrences only.

A target is produced only when the residual type explicitly names a semantic target role. The initial finite rules are:

```text
legal_object_identity_unresolved -> legal_object
condition_attachment_unresolved  -> host
exception_attachment_unresolved  -> host
norm_bearer_unresolved            -> bearer
```

The rule must select exactly one factor object carrying exactly one parser-token occurrence. Missing rule, missing slot, or ambiguity leaves the demand without a target.

This means factor-level residuals such as jurisdiction, effective time, modal sense, and generic scope do not receive an entity target merely because a noun exists in the sentence.

## Historical rows and recompilation

Installing migrations 135-136 does **not** backfill historical demand provenance.

Historical rows remain:

```text
trigger unknown
+ target unknown
=> H9 external admission unavailable
```

A genuine compiler replay causes the normal demand `INSERT ... ON CONFLICT UPDATE` path to fire the producer hook against the newly/currently materialized factor graph. Only then can trigger/target/evidence provenance be added.

This distinction is intentional. Re-running a migration over old lexical support would repeat the provenance error instead of correcting it.

## H9 boundary

The old generic occurrence support remains available for compatibility and audits, but H9 parser-entity admission now begins at:

```text
demand
-> producer-authored target occurrence
-> exact target PNF object
-> exact parser token
-> quality-valid parser entity span containing that token
-> consumer world-axis contract
-> external need
```

Trigger and evidence tokens are not visible to the provider-entity occurrence bridge.

Rejected or target-less demands remain unresolved. They are not refuted and do not count as evidence that no world entity exists.

## Live audit

After recompiling the affected corpus, run `scripts/report_demand_target_provenance.py` before any HF/Zelph/Wikidata acquisition.

The report shows:

- contract-matched H9 demands;
- demands with producer triggers;
- demands with producer targets;
- exact H9 target support;
- quality-valid entity targets;
- residual type;
- trigger token;
- target token/object;
- resulting provider label when one exists;
- `provider_io_performed: false`.

A healthy result should demonstrate target provenance such as:

```text
demand -> Bush token/object -> George Bush entity span
```

rather than attempting to recover:

```text
demand -> Believed token -> George Bush Believed span -> trim
```
