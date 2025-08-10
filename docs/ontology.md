# Ontology Tagging

The project includes a lightweight tagging utility that assigns legal
principles and commercial customs to provisions extracted from documents.

## Ontology Definitions

Two simple ontologies are bundled as JSON files under `data/ontology`:

- **lpo.json** – Legal Principles Ontology (LPO)
- **cco.json** – Commercial Customs Ontology (CCO)

Each ontology maps tag names to a list of keywords used for rule-based
matching.

## Tagging Provisions

The function `ontology.tagger.tag_text` creates a :class:`~models.provision.Provision`
from raw text and populates `principles` and `customs` lists based on the
ontology keyword matches.  Existing `Provision` instances can be tagged with
`ontology.tagger.tag_provision`.

```python
from ontology.tagger import tag_text

prov = tag_text("Fair business practices protect the environment.")
print(prov.principles)  # ['fairness', 'environmental_protection']
print(prov.customs)     # ['business_practice']
```

## Ingestion Pipeline Integration

During ingestion, `src.ingestion.parser.emit_document` applies the tagger to
produce `Document` objects whose `provisions` field contains the tagged
content.  Each document currently generates a single provision from its body
text, but the approach can be extended to finer-grained parsing.
