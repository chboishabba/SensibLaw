# End-to-End Query Flow

This document demonstrates the experimental query pipeline that powers
`python -m src.cli query`. The command accepts different forms of user input and
converts them into a concept cloud.

The high level steps are:

1. **Parse input** – flatten questions, keyword lists or story graphs into
   plain text.
2. **Normalise** – perform simple text normalisation (currently just
   lower‑casing).
3. **Match concepts** – identify concepts in the text. The current
   implementation merely splits the text into tokens.
4. **Build cloud** – aggregate matched concepts into a frequency cloud.
5. **Proof tree** – forthcoming stage that will explain how concepts relate
   to authorities.

## Examples

### Question

```bash
python -m src.cli query --text "Can a native title be extinguished by state law?"
```

### Keyword search

```bash
python -m src.cli query --text "native title extinguishment"
```

### Story graph

Given a minimal story graph JSON file:

```json
{
  "nodes": [
    {"text": "State passes land act"},
    {"text": "Aboriginal group claims native title"}
  ]
}
```

Invoke the command with the path to the file:

```bash
python -m src.cli query --graph story.json
```

Each of the above inputs will produce a simple concept cloud based on the
matched tokens.

### Case treatment

Retrieve how later authorities have treated a given case:

```bash
python -m src.cli query treatment --case case123
```
