# Corpus Setup

This document outlines how to expand the legal corpus using the `Document` schema.

## Adding new documents
1. Obtain authoritative text from official repositories.
2. Create metadata and body using the `Document` model:

```python
from datetime import date
from src.models.document import Document, DocumentMetadata

metadata = DocumentMetadata(
    jurisdiction="Example State",
    citation="Example Act 2024 (Ex)",
    date=date(2024, 1, 1),
    lpo_tags=["example"],
    cco_tags=["demo"],
    cultural_flags=["test"]
)
doc = Document(metadata=metadata, body="Full text here")
with open("data/corpus/example_act.json", "w") as f:
    f.write(doc.to_json())
```

3. Store the resulting JSON file under `data/corpus/` using a descriptive name.
4. Ensure minimal LPO/CCO tags and cultural flags are included for cultural context.
5. Run `pytest` to verify integrity.

### Sample generation script

A helper script is provided to create example Act and judgment files. Run:

```bash
python scripts/generate_sample_corpus.py
```

This writes `sample_act.json` and `sample_judgment.json` into `data/corpus/`,
demonstrating the required metadata fields.

## Directory structure
- `data/corpus/` – JSON documents in the schema.

## Future expansion
For bulk additions, consider writing helper scripts that pull texts from official APIs,
convert them using the model above, and save them into the corpus directory.
