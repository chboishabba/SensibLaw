# Document Schema

The `Document` model represents a legal document along with essential metadata. It is
implemented in `src/models/document.py` and includes both a `DocumentMetadata`
structure and the document body text.

## Fields

### DocumentMetadata
- **jurisdiction** (`str`): Geographic or political jurisdiction of the document.
- **citation** (`str`): Formal citation or identifier for the document.
- **date** (`date`): Date the document was issued, in ISO format (`YYYY-MM-DD`).
- **court** (`Optional[str]`): Court or body that issued the document.
- **lpo_tags** (`Optional[List[str]]`): Legal policy objective tags.
- **cco_tags** (`Optional[List[str]]`): Cross-cultural obligation tags.
- **cultural_flags** (`Optional[List[str]]`): Cultural sensitivity flags.
- **jurisdiction_codes** (`List[str]`): Standardised jurisdiction codes.
- **ontology_tags** (`Dict[str, List[str]]`): Tags matched from configured ontologies.

### Document
- **metadata** (`DocumentMetadata`): Metadata associated with the document.
- **body** (`str`): Full body text of the document.
- **provisions** (`List[Provision]`): Extracted provisions within the document.

## JSON Representation

`Document` instances serialize to JSON with the following structure:

```json
{
  "metadata": {
    "jurisdiction": "US",
    "citation": "410 U.S. 113",
    "date": "1973-01-22",
    "court": "Supreme Court",
    "lpo_tags": ["example"],
    "cco_tags": ["demo"],
    "cultural_flags": ["public-domain"],
    "jurisdiction_codes": ["US"],
    "ontology_tags": {"lpo": ["example"], "cco": ["demo"]}
  },
  "body": "Full text of the opinion...",
  "provisions": []
}
```

Both `Document` and `DocumentMetadata` provide `to_dict`, `from_dict`,
`to_json`, and `from_json` helpers to facilitate serialization and ingestion.
