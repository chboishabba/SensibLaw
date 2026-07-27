# Runtime Authority Surfaces

Status: documentation freeze before consolidation  
Baseline audited: `f8f6ff5db1bc2b443e03e9f58cb14e1bd1486aa5`

SensibLaw currently contains several cases where execution policy, persistence
policy, lane identity, or compatibility history created a second top-level
implementation. This document records the authority boundary to use while
those implementations are consolidated.

It is normative for new code and documentation. Historical modules may remain
temporarily for compatibility, but they must not be described as independent
authorities or used as templates for new surfaces.

## Governing Rule

A capability has one semantic authority. Variation belongs in explicit
strategies or profiles:

```text
one capability authority
  + execution strategy
  + persistence strategy
  + admission policy
  + progress sink
  + lane/profile configuration
```

Concurrency, storage, admission, UI, and corpus identity do not justify a new
semantic compiler, parser, API, graph, linkage engine, or world model.

## Canonical Entry Point

The single source-tree CLI gateway is:

```bash
python -m src.cli
```

Its callable authority is `src.cli:main`.

The top-level `cli` package contains the current command implementation. It is
internal and may be imported by `src.cli`; users, automation, scripts, and new
documentation must not invoke `python -m cli.__main__` directly.

The project metadata declares an installed `sensiblaw` console command, but the
current package topology can make it resolve differently from a source
checkout. It is compatibility debt, not a supported second entry point.
Packaging should eventually bind that alias through the same gateway once the
package layout is consolidated.

Standalone maintenance scripts are not project entry points. A script that
remains necessary should become a subcommand or explicitly document why it
cannot use the shared CLI lifecycle.

## Current Authority Map

| Capability | Current competing surfaces | Authority decision | Transitional treatment |
| --- | --- | --- | --- |
| Project CLI | `src/cli.py`, `cli/__main__.py`, declared console alias, direct scripts | `src.cli:main` is the gateway; `cli` is internal implementation | Do not add direct `cli.__main__` invocations. Move durable scripts under the gateway. |
| Section parsing | `src/ingestion/section_parser.py`, `src/section_parser.py` | `src.ingestion.section_parser` owns parsing and structural construction | `src.section_parser` is a deprecated compatibility projection. Migrate callers, then remove it. |
| Public parser naming | `sensiblaw.interfaces.parser_adapter.parse_canonical_text`, `src.ingestion.media_adapter.parse_canonical_text` | `sensiblaw.interfaces.parse_canonical_text` owns the public parse operation | Prefer `build_parsed_envelope` for the media-envelope operation; retire its ambiguous alias. |
| Corpus compilation | base, operational, fibred, PostgreSQL, streaming, optimized streaming, parallel, and curated modules | One document/corpus compiler contract must own semantics | Freeze new compiler entry points. Treat executor, persistence, admission, retry, and progress as strategies pending parity work. |
| Package identity | root `sensiblaw/__init__.py`, `src/sensiblaw/__init__.py` | `src/sensiblaw` is the target installed product package | Root package is a temporary checkout compatibility shim; do not add exports to it. |
| Dependency imports | root `fastapi.py` / `pydantic.py`, root `fastapi/` / `pydantic/`, real dependencies | Real third-party packages own these names | Move test doubles into test fixtures and remove repository-root shadows. |
| HTTP API | `src/api/routes.py`, `sensiblaw/api/routes.py` | One router tree under the installed `src/sensiblaw/api` package | Freeze new endpoints in competing routers until routes, stores, and extraction behavior are merged. |
| Legal follow | `src/policy/legal_follow_graph.py`, `src/policy/gwb_legal_follow_graph.py` | Shared follow machinery configured by profiles | AU/GWB labels may remain only as profile defaults and outward labels. |
| Semantic linkage | `src/au_semantic/linkage.py`, `src/gwb_us_law/linkage.py` | Shared persistence, matching, selection, and reporting engine | Lane modules become field mappings and defaults only. |
| World-model construction | generic runtime plus AU, GWB narrative, GWB broader-review, and Brexit builders | `world_model.py`, `world_model_adapters.py`, and `world_model_projections.py` own the shared process | Lane builders are transitional adapters and must collapse to configuration plus mapping. |
| Fetch/progress/serialization utilities | repeated request pacing, `_json`, `_refs`, `_as_text`, hashing, cache, and progress helpers | Shared runtime utility owners | Do not copy helpers into another lane or script. Extract when touched. |
| UI/story ingestion | multiple frontends and incompatible `StoryImporter` contracts | One product UI and one ingestion contract are required | Classify alternates as examples or retire them after caller inventory. |

## Compiler Freeze

The existing compiler modules do not differ only by throughput:

- `compile_directory_postgres` uses `compile_document_operational` and the
  `postgres-semantic-compiler:v0_11` contract. Oversized inputs are parser
  execution fibres over one document structural carrier; chunk outputs do not
  become independent semantic graphs or document identities.

  The active large-document contract is:

  - exact, disjoint ownership intervals over canonical document coordinates;
  - bounded bilateral context overlap selected below the parser safety limit;
  - parallel physical parsing with deterministic global token/span coordinates;
  - atomic per-fibre checkpoints keyed by source, policy, and interval identity;
  - explicit cross-fibre demand and fixed-point receipts;
  - one document-level mention, PNF, constraint, and demand computation;
  - one PostgreSQL savepoint commit after document reconciliation.
- parallel and curated paths use `compile_document_fibred_operational` and the
  `postgres-fibred-semantic-compiler:v0_2` contract.
- persistence, retry, admission-receipt, and progress behavior also differ.

Therefore changing a caller from the sequential function to the parallel or
curated function is not presumed behavior-preserving.

Until output parity and one canonical contract are established:

- do not create another compiler module or directory-level compiler;
- do not call an execution variant a canonical compiler;
- record the exact compiler contract in receipts and operator output;
- add concurrency only after semantic and persistence parity is demonstrated;
- model concurrency, persistence, admission, retry, and progress as strategies
  of the eventual single compiler.

## Parser Compatibility Freeze

`src.section_parser` creates ambiguity even though it delegates parsing. It
retains historical `Provision` and simple-section output shapes and is
therefore a projection, not a parser authority.

Rules:

- new code imports `src.ingestion.section_parser` or the public
  `sensiblaw.interfaces` parser surface;
- no new import of `src.section_parser` is permitted;
- compatibility callers should be inventoried and migrated;
- the shim is removed after its last caller moves;
- two operations with different input/output contracts must not share the
  public name `parse_canonical_text`.

## Persistence and Migration Tracks

| Location | Status | Permitted use |
| --- | --- | --- |
| `database/postgres_migrations/` | Active | Sole active semantic persistence and schema migration track |
| `database/migrations/` | Deprecated | Bounded historical SQLite ontology import/replay and tests only |
| `migrations/` | Superseded reference | Read-only historical reference; never execute |
| `schemas/migrations/` | Superseded reference | Read-only historical reference; never execute |

The active PostgreSQL directory currently contains duplicate numeric prefixes
(`006_*` and `007_*`). The deprecated SQLite directory also contains duplicate
`002_*` prefixes. Lexical ordering happens to be deterministic, but the
identifier convention is ambiguous for humans, tooling, and backports.

Until a renumbering plan preserves already-applied filename/checksum receipts:

- do not add a new migration with an existing prefix;
- do not rename an already-applied migration in place;
- do not execute either superseded reference directory;
- require a unique next prefix for every new PostgreSQL migration;
- treat SQLite migration work as retirement/import maintenance, not active
  semantic development.

## Consolidation Order

1. Freeze new compiler and authority entry points.
2. Establish one document compiler contract and parity-test operational and
   fibred products.
3. Express sequential, process-parallel, curated, streaming, and progress
   behavior as strategies.
4. Remove dependency shadows and converge the two `sensiblaw` initializers.
5. Merge the HTTP routers.
6. Extract shared follow and linkage engines.
7. Collapse lane world-model builders into declarative adapters.
8. Extract shared fetch, progress, serialization, cache, hash, and
   normalization utilities.
9. Retire or explicitly classify alternate UI and story-ingestion surfaces.
10. Remove the section-parser compatibility projection after its callers move.

## Review Checklist

Before adding a module, command, store, router, or lane implementation, answer:

1. Which existing capability authority owns this behavior?
2. Is the requested difference semantic, or only execution/storage/profile
   policy?
3. Can it be an injected strategy, declaration, or profile?
4. Does it create a second public invocation or import path?
5. Which compatibility surface can be retired as part of the change?

If the change would create a second authority, stop and extend the existing
authority instead.
