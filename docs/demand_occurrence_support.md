# Demand occurrence support

`semantic_pnf_demand.source_object_id` is an optional one-object fast path, not the canonical provenance relation for a demand.

Migration 122 adds `semantic_pnf_demand_occurrence_support`, a many-valued carrier from a demand to structural occurrences already represented by the numeric PNF.

Strong support kinds are:

- `1`: exact object export on the same interface with the same lexical key and grammatical role;
- `2`: exact typed factor slot on the same interface with matching factor type and role.

Support kind `9` records the historical 090a `source_object_id` projection for audit only. H9 entity admission does not consume it.

Migration 125's attempted `source_object_id` reuse is repaired by 126-127: historical `source_object_id` keeps its 090a semantics, while `occurrence_source_object_id` is the optional unique fast path over strong support. The many-valued occurrence carrier remains authoritative.

H9 entity-bearing and label-anchor views begin from `semantic_pnf_demand_strong_occurrence_support_v1`. Missing support is an unresolved provenance state, not negative semantic evidence.

Migration 130 bridges a strong demand occurrence to the exact numeric spaCy entity span containing its parser token and reconstructs the whole entity surface as the candidate provider label. It does not equate the PNF lexical object with a separately promoted entity object.

## Provider entity quality

Raw spaCy `doc.ents` are parser observations, not provider authority. Live GWB validation found exact parser spans such as `GEORGE BUSH BELIEVED` and `JFK May Drop Johnson` labelled as named entities. The occurrence bridge was correct; those NER spans themselves were unsafe as provider labels.

Migration 133 therefore keeps every raw `semantic_parser_entity_span` but inserts a quality carrier before external admission. `semantic_parser_provider_entity_span_v1` contains only spans that:

- belong to an owned parser sentence;
- contain at least one parser token;
- align exactly to token start/end boundaries;
- cover one contiguous token interval in one sentence;
- contain no parser `VERB` or `AUX` token;
- contain at least one nominal `PROPN` or `NOUN` anchor;
- are bounded to at most 16 tokens and 256 characters;
- use a provider-world-bearing spaCy entity type: `PERSON`, `ORG`, `GPE`, `LOC`, `FAC`, `LAW`, `EVENT`, `WORK_OF_ART`, `PRODUCT`, or `LANGUAGE`.

Measurement/value NER classes such as dates, money, quantities and cardinals are deliberately not provider-world-bearing by default. The late external layer is an entity authority/cache, not a general semantic dictionary.

Quality states are explicit and auditable:

- `1`: provider-admissible;
- `10`: no owned sentence;
- `11`: no covered parser tokens;
- `12`: not token-boundary aligned;
- `13`: non-contiguous sentence-token interval;
- `14`: contains a verbal/clausal token;
- `15`: oversized provider label;
- `16`: non-world-bearing entity type;
- `17`: no nominal anchor.

A rejected span remains raw parser evidence. Rejection is not negative evidence about the world and does not resolve the H9 residual.

The intended funnel is now:

```text
H9 contract match
  -> strong demand occurrence support
  -> exact raw parser entity occurrence
  -> provider entity quality gate
  -> unique canonical entity surface
  -> exact provider label anchor
  -> external need
```

Use `scripts/report_demand_occurrence_support.py` to measure the structural provenance carrier. Then use `scripts/report_h9_outgoing_entity_labels.py` before any Zelph/Wikidata run. The latter performs no provider I/O and reports both the surviving provider labels and rejected raw parser spans with quality reasons.
