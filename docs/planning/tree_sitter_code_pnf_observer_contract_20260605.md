# Tree-sitter Code PNF Observer Contract

Date: 2026-06-05

## Purpose

Define Tree-sitter as a code-structure observer lane that can emit bounded,
provenance-backed code observations and optional `PredicatePNF` candidates.

Tree-sitter is not a truth oracle. Its authority is syntax structure only:
declarations, imports, calls, CLI flags, file IO, schema fields, projection
boundaries, bounded absence scans, test assertion shapes, and similar
parse-backed structure. Runtime truth, task completion, Kanban movement, and
lifecycle promotion still require residual review plus separate test, runtime,
human, or documentation evidence.

## Flow

```text
source file
  -> Tree-sitter parse
  -> code_observation_v1 JSONL row
  -> optional PredicatePNF candidate
  -> residual review against plan/task/context PNF
  -> candidate residual or review receipt
```

The first integration target is read-only residual review. A Tree-sitter agent
may produce evidence rows; it must not create StatiBaker cards, move Kanban
items, mark tasks done, mutate task memory, or promote source-derived structure
into canonical workflow state.

## Authority Boundary

Allowed:

- syntax-backed observations over explicitly scanned files
- source anchors, line spans, byte ranges, language, repo, and commit identity
- bounded `PredicatePNF` candidates with `wrapper.evidence_only = true`
- residual comparisons against supplied plan, task, context, or test carriers
- bounded absence receipts scoped to a declared scan set
- candidate review signals that preserve residual state

Not allowed:

- treating parser output as semantic or runtime truth
- claiming a behavior is implemented only because a call or declaration exists
- claiming global absence from a partial scan
- emitting raw negative predicates such as `code_does_not_call`
- creating, moving, closing, or completing StatiBaker/Kanboard cards
- treating syntax-only matches as sufficient for `done`
- fabricating provenance, commits, tests, runtime evidence, or review receipts

## Allowed Predicates

Tree-sitter-originated PNF candidates are limited to code-structure predicates:

- `code_declares_symbol`
- `code_imports_module`
- `code_calls_symbol`
- `code_defines_cli_flag`
- `code_reads_file`
- `code_writes_file`
- `code_test_asserts_behavior`
- `code_schema_field_observed`
- `code_projection_boundary`

Additional predicates require a new contract revision or a narrower downstream
adapter contract. The predicate name must describe observed structure, not
inferred intent.

## Residual Semantics

Tree-sitter atoms compare through the existing residual lattice:

```text
exact | partial | no_typed_meet | contradiction
```

An `exact` structural meet means only that a requested structural pattern was
observed within the bounded scan. It does not prove runtime behavior, task
completion, user acceptance, documentation coverage, or Kanban lifecycle state.

Absence claims require bounded scan receipts. A scanner may report that a
declared scan scope produced `observed_call_count = 0` for a target pattern. It
must not emit unscoped global claims such as "this repo does not call X."

## JSONL Shape

Each row is a `code_observation_v1` object:

```json
{
  "schema": "code_observation_v1",
  "ts": "2026-06-05T00:00:00Z",
  "repo": "SensibLaw",
  "commit": "abc1234",
  "path": "src/example.py",
  "language": "python",
  "observation_kind": "symbol_declared",
  "symbol": "main",
  "callee": null,
  "module": null,
  "line_start": 12,
  "line_end": 20,
  "byte_range": [240, 612],
  "scan_scope": {
    "scope_id": "repo:SensibLaw:src-python",
    "root": "src",
    "include_globs": ["src/**/*.py"],
    "exclude_globs": ["**/__pycache__/**"],
    "files_scanned": 42,
    "parser": "tree-sitter-python",
    "parser_version": "pinned-or-runtime-reported"
  },
  "pnf_candidates": [],
  "provenance": [
    {
      "kind": "source_span",
      "path": "src/example.py",
      "line_start": 12,
      "line_end": 20,
      "byte_range": [240, 612],
      "commit": "abc1234"
    }
  ],
  "non_authoritative": true
}
```

Required fields:

- `schema`
- `ts`
- `repo`
- `commit`
- `path`
- `language`
- `observation_kind`
- `line_start`
- `line_end`
- `byte_range`
- `scan_scope`
- `provenance`
- `non_authoritative: true`

Kind-specific fields such as `symbol`, `callee`, and `module` may be null when
they do not apply, but their corresponding PNF candidate must not invent values
that were not observed.

## PNF Candidate Shape

Rows may include zero or more `pnf_candidates`. Each candidate uses the
existing `PredicatePNF` fields:

```json
{
  "predicate": "code_calls_symbol",
  "structural_signature": "python.call:Path.read_text",
  "roles": {
    "caller_file": {"value": "src/example.py", "entity_type": "file_path"},
    "callee": {"value": "Path.read_text", "entity_type": "symbol"},
    "line": {"value": "31", "entity_type": "line_number"}
  },
  "qualifiers": {
    "polarity": "positive"
  },
  "wrapper": {
    "status": "observed_syntax",
    "evidence_only": true
  },
  "provenance": [
    "repo:SensibLaw@abc1234:src/example.py:31"
  ],
  "source_observation_schema": "code_observation_v1",
  "domain": "code_structure"
}
```

The `domain` must be `code_structure`. The candidate must cite
`source_observation_schema = code_observation_v1`. The wrapper must preserve
`evidence_only = true`; downstream residual review may compare the carrier but
must not reinterpret it as proof of behavior.

## Examples

### Declaration

```json
{"schema":"code_observation_v1","ts":"2026-06-05T00:00:00Z","repo":"SensibLaw","commit":"abc1234","path":"src/cli.py","language":"python","observation_kind":"symbol_declared","symbol":"build_parser","line_start":14,"line_end":28,"byte_range":[310,880],"scan_scope":{"scope_id":"cli-file","root":"src/cli.py","include_globs":["src/cli.py"],"files_scanned":1},"pnf_candidates":[{"predicate":"code_declares_symbol","structural_signature":"python.function:build_parser","roles":{"file":{"value":"src/cli.py","entity_type":"file_path"},"symbol":{"value":"build_parser","entity_type":"symbol"}},"qualifiers":{"polarity":"positive"},"wrapper":{"status":"observed_syntax","evidence_only":true},"provenance":["repo:SensibLaw@abc1234:src/cli.py:14-28"],"domain":"code_structure"}],"provenance":[{"kind":"source_span","path":"src/cli.py","line_start":14,"line_end":28,"byte_range":[310,880],"commit":"abc1234"}],"non_authoritative":true}
```

### Call

```json
{"schema":"code_observation_v1","ts":"2026-06-05T00:00:01Z","repo":"SensibLaw","commit":"abc1234","path":"src/cli.py","language":"python","observation_kind":"call_observed","callee":"parse_args","line_start":42,"line_end":42,"byte_range":[1320,1348],"scan_scope":{"scope_id":"cli-file","root":"src/cli.py","include_globs":["src/cli.py"],"files_scanned":1},"pnf_candidates":[{"predicate":"code_calls_symbol","structural_signature":"python.call:parse_args","roles":{"file":{"value":"src/cli.py","entity_type":"file_path"},"callee":{"value":"parse_args","entity_type":"symbol"},"line":{"value":"42","entity_type":"line_number"}},"qualifiers":{"polarity":"positive"},"wrapper":{"status":"observed_syntax","evidence_only":true},"provenance":["repo:SensibLaw@abc1234:src/cli.py:42"],"domain":"code_structure"}],"provenance":[{"kind":"source_span","path":"src/cli.py","line_start":42,"line_end":42,"byte_range":[1320,1348],"commit":"abc1234"}],"non_authoritative":true}
```

### CLI Flag

```json
{"schema":"code_observation_v1","ts":"2026-06-05T00:00:02Z","repo":"SensibLaw","commit":"abc1234","path":"src/cli.py","language":"python","observation_kind":"cli_flag_observed","symbol":"--dry-run","line_start":19,"line_end":19,"byte_range":[520,580],"scan_scope":{"scope_id":"cli-file","root":"src/cli.py","include_globs":["src/cli.py"],"files_scanned":1},"pnf_candidates":[{"predicate":"code_defines_cli_flag","structural_signature":"python.argparse.flag:--dry-run","roles":{"file":{"value":"src/cli.py","entity_type":"file_path"},"flag":{"value":"--dry-run","entity_type":"cli_flag"},"line":{"value":"19","entity_type":"line_number"}},"qualifiers":{"polarity":"positive"},"wrapper":{"status":"observed_syntax","evidence_only":true},"provenance":["repo:SensibLaw@abc1234:src/cli.py:19"],"domain":"code_structure"}],"provenance":[{"kind":"source_span","path":"src/cli.py","line_start":19,"line_end":19,"byte_range":[520,580],"commit":"abc1234"}],"non_authoritative":true}
```

### Bounded Absence Scan

```json
{"schema":"code_observation_v1","ts":"2026-06-05T00:00:03Z","repo":"SensibLaw","commit":"abc1234","path":"src","language":"python","observation_kind":"bounded_absence_scan","symbol":"subprocess.Popen","line_start":0,"line_end":0,"byte_range":[0,0],"scan_scope":{"scope_id":"src-python-no-popen-scan","root":"src","include_globs":["src/**/*.py"],"exclude_globs":["**/__pycache__/**"],"files_scanned":42,"observed_call_count":0,"target_pattern":"subprocess.Popen","parser":"tree-sitter-python"},"pnf_candidates":[],"provenance":[{"kind":"bounded_scan_receipt","scope_id":"src-python-no-popen-scan","root":"src","include_globs":["src/**/*.py"],"files_scanned":42,"commit":"abc1234"}],"non_authoritative":true}
```

This final row says only that the declared scan found zero matching call
surfaces in the declared scope. It is not a global negative fact about the
repository, runtime imports, generated code, shell commands, or dependencies.

## Integration Target

Future MCP observer-evidence seams may add `code_observer_records` beside
browser, OpenRecall, and other observer records. Those records should remain
parallel evidence inputs:

- append-only
- reference-heavy
- bounded by explicit scan scope
- non-authoritative
- excluded from direct task-state mutation

The residual bridge may compare code PNF against plan, task, context, test, and
documentation PNF. It may emit candidate residuals such as:

- structural support observed
- structural support missing in declared scan scope
- structural contradiction
- runtime evidence required
- test evidence required
- documentation evidence required

It must not emit Kanban projection rows or lifecycle movement from Tree-sitter
evidence alone.

## Implementation Status

As of 2026-06-05, the ITIR-suite root `.venv` has usable Python Tree-sitter
bindings for Python, JavaScript, TypeScript, and TSX. The system Tree-sitter CLI
is diagnostic only and is not a runtime dependency for this observer lane.

The current optimisation campaign Stage 5 is to implement the Tree-sitter code
observer as an evidence-only `code_observation_v1` producer. dashiCORE remains a
path-adapter boundary only; it is not part of the observer runtime and must not
be promoted into this lane as a parallel package or authority source.

## Governance Alignment

This contract aligns with the current PNF posture:

- parser output can contribute to `PredicatePNF`
- carriers remain evidence, not authority
- residual comparison preserves exact, partial, no-typed-meet, and
  contradiction outcomes
- task identity and lifecycle residuals require downstream governance
- observer records are append-only and non-authoritative

Tree-sitter observations may support `task_identity_residual` or
`lifecycle_residual` review, but syntax-only evidence cannot close either
residual to `exact` for done-state purposes without separate runtime, test,
documentation, or human review receipts.

## Future Test Plan

Future implementation tests should verify that the observer lane:

- rejects rows without provenance
- rejects rows without bounded `scan_scope`
- preserves `wrapper.evidence_only = true`
- preserves `non_authoritative = true`
- rejects raw negative predicates such as `code_does_not_call`
- classifies syntax-only matches as insufficient for `done`
- requires test or runtime evidence before lifecycle residual can become
  `exact` for completion
- confirms no Kanban projection is emitted from Tree-sitter observer evidence
  alone
