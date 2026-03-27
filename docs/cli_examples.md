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

## Search AustLII for a known case and fetch one hit

Use the bounded SINO search seam to select one authority page, then save the
fetched artifact for local review:

```bash
sensiblaw austlii-search \
  --query '"Marvel & Marvel"' \
  --method phrase \
  --pick by_mnc \
  --mnc "[2021] FamCA 83" \
  --paragraph 120 \
  --paragraph-window 1 \
  --db-path .cache_local/itir.sqlite \
  --out /tmp/marvel_2021_famca_83.html
```

This command is for selection + fetch only. Once the HTML/PDF is fetched,
paragraph isolation happens locally on the fetched HTML. The saved artifact can
then be reviewed or reprocessed without repeated live queries. When `--db-path`
is supplied, the command also persists a bounded authority-ingest receipt in
sqlite with whole-fetch provenance plus the selected paragraph window.

## Fetch a known AustLII authority by citation or URL and inspect local paragraphs

Use the direct AustLII authority seam when you already know the neutral
citation or explicit AustLII case URL:

```bash
sensiblaw austlii-case-fetch \
  --citation "[2010] FamCAFC 13" \
  --paragraph 100 \
  --paragraph-window 1 \
  --db-path .cache_local/itir.sqlite \
  --out /tmp/ss_ah_2010_famcafc_13.html
```

This command deterministically resolves a neutral citation to the canonical
AustLII case URL before fetching. It does not use SINO. Paragraph isolation
happens locally after fetch, and `--db-path` persists the bounded receipt.

## Fetch a known JADE authority and inspect local paragraphs

Use the repo-owned JADE seam for a known neutral citation or explicit JADE URL:

```bash
sensiblaw jade-fetch \
  --citation "[2021] FamCA 83" \
  --paragraph 120 \
  --paragraph-window 1 \
  --db-path .cache_local/itir.sqlite \
  --out /tmp/marvel_2021_famca_83_jade.txt
```

This command fetches once and then performs paragraph inspection locally on the
returned artifact. It does not perform a second live lookup pass. When
`--db-path` is supplied, the selected paragraph window is also persisted as a
bounded authority-ingest receipt.

## Search JADE best-effort, then fetch one hit and inspect locally

Use the secondary JADE search seam when you start from free text or want the
operator path to synthesize an exact-MNC `/mnc/...` hit locally:

```bash
sensiblaw jade-search \
  --query "[2021] FamCA 83" \
  --pick by_mnc \
  --mnc "[2021] FamCA 83" \
  --paragraph 120 \
  --paragraph-window 1 \
  --db-path .cache_local/itir.sqlite \
  --out /tmp/marvel_2021_famca_83_jade_search.html
```

This command performs one bounded JADE search request, parses any server-side
hits it can see, appends an exact-MNC fallback hit when the query contains a
neutral citation, then fetches once and performs paragraph inspection locally.
Use `scripts/query_fact_review.py authority-summary` to export a clean JSON
receipt from sqlite when `--db-path` is supplied.

## View a stored section

Display the text, extracted rules, provenance and ontology tags for a stored
section identified by its canonical ID:

```bash
sensiblaw view --id s5
```

Both commands use `data/store.db` by default. Provide `--db` to specify a
custom database path.
