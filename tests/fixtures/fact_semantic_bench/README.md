# Fact Semantic Benchmark Corpora

These corpora are the canonical bounded benchmark inputs for the normalized
`fact_intake` semantic layer.

Each corpus file is JSON with:

- `corpus_id`
- `description`
- `entries`

Each entry must include:

- `id`
- `source_type`
- `text`
- `length_bucket`
- `expected_classes`
- `expected_policies`
- optional `expected_relations`
- optional `provenance`

Design rules:

- keep entries revision-locked and deterministic
- include short / medium / long text
- include at least one adversarial-noise entry
- include prompt-injection / override phrasing (e.g., “ignore previous”)
- preserve source type and provenance needed for lexical pack selection

Primary corpus families:

- `wiki_revision_seed.json`
- `chat_archive_seed.json`
- `transcript_handoff_seed.json`
- `au_legal_seed.json`

Runner examples:

```bash
../.venv/bin/python scripts/benchmark_fact_semantics.py \
  --corpus-file tests/fixtures/fact_semantic_bench/wiki_revision_seed.json \
  --count 100

../.venv/bin/python scripts/benchmark_fact_semantics.py \
  --corpus-file tests/fixtures/fact_semantic_bench/chat_archive_seed.json \
  --count 1000

../.venv/bin/python scripts/run_fact_semantic_benchmark_matrix.py \
  --manifest tests/fixtures/fact_semantic_bench/corpus_manifest.json \
  --output-dir .cache_local/fact_semantic_bench \
  --baseline-dir tests/fixtures/fact_semantic_bench/results/2026-03-19 \
  --max-tier 1000
```

Suggested tier schedule:

- wiki_revision: `100`, `1000`, `10000`
- chat_archive: `100`, `1000`, `10000`
- transcript_handoff: `100`, `1000`, `5000`
- au_legal: `100`, `1000`, `5000`

Recent adversarial coverage additions (2026-03-20):
- wiki_revision: link-spam + HTML-comment “ignore previous” injections
- chat_archive: “system override / ignore doubts” and code-switch handoff noise
- transcript_handoff: redaction/run-on overrides that blur timeline ownership
- au_legal: misleading press-release authority transfer and docket noise

Latest benchmark runs (2026-03-20):
- Tiers 100 and 1000 for all corpora completed with `refresh_status=ok`; reports under `tests/fixtures/fact_semantic_bench/results/`.
- Drift vs 2026-03-19:
  - wiki_revision: assertions -8% (100) / -5% (1000); relations -18% / -18%; policies flat; facts +7% / +3%.
  - chat_archive: assertions -14% / -5%; policies -3% / -3%; facts +15% / -2%.
  - transcript_handoff: assertions -2% / -2%; policies flat; facts +10% / +10%.
  - au_legal: assertions +2% / +2%; relations +3% (100) / +13% (1000); policies +3% / +3%; facts +2% / +2%.
- Runtimes: ~10–24s for 1k tiers; no execution failures.

Diagnostic output:
- `entry_diagnostics` groups repeated benchmark samples back to their seed `entry_id`.
- Each diagnostic row includes expected vs realized classes/policies, per-entry assertion/relation/policy counts, and sample facts for inspection.
- `expectation_summary` reports corpus-level recall for expected classes and policies.

Matrix drift output:
- `baseline_report_path` identifies the matched prior report for the same corpus/tier.
- `drift` reports relative deltas for assertions, relations, policies, facts, and elapsed time.
- `guardrail_status` warns when absolute drift exceeds the default bands:
  - assertions / policies / facts: `15%`
  - relations: `25%` when the baseline relation count is non-zero
- expectation recall below `1.0` is flagged for review but does not fail the run.
