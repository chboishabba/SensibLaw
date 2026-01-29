# CLI Usage Examples

## Obligations (Sprint 7 read-only surfaces)

Extract obligations from text and emit projections or explanations without adding semantics:

```bash
sensiblaw obligations --text-file examples/sample.txt \
  --emit-projections actor action timeline \
  --emit-explanation
```

Outputs JSON with:
- `obligations` (deterministic list)
- `projections` keyed by view (`actor|action|clause|timeline`)
- `explanations` (`obligation.explanation.v1`)
- optional `obligation_activation` when simulating activation

Diff/align two versions while keeping identities stable:

```bash
sensiblaw obligations --text-file old.txt \
  --diff-text-file new.txt \
  --emit-obligation-alignment
```

Simulate activation using a FactEnvelope:

```bash
sensiblaw obligations --text-file doc.txt \
  --simulate-activation --facts facts.json
```

`facts.json`:
```json
{"version": "fact.envelope.v1", "facts": [{"key": "upon commencement", "value": true}]}
```

## Fetch sections from AustLII

Download specific sections from an Act hosted on AustLII and store them in the
local database:

```bash
sensiblaw austlii-fetch --act https://example.org/act --sections s5,s223
```

## View a stored section

Display the text, extracted rules, provenance and ontology tags for a stored
section identified by its canonical ID:

```bash
sensiblaw view --id s5
```

Both commands use `data/store.db` by default. Provide `--db` to specify a
custom database path.
