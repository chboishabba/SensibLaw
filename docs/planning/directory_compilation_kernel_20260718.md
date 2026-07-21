# Directory compilation kernel

Date: 2026-07-18
Status: local-only corpus orchestration contract

## Purpose

The directory kernel turns a bounded filesystem corpus into deterministic,
inspectable per-document compiler artifacts. It scales orchestration only:
the semantic compiler remains the shared `compile_document(document_input,
compiler_context)` operation.

It is deliberately not a corpus-specific parser, profile selector, resolver,
or authority surface.

## Contract

```text
input directory
-> CorpusManifest
-> independent DocumentCompilation values
-> immutable content-addressed artifact projections
-> corpus unresolved-demand groups
```

The initial implementation is local-only. It may derive canonical text,
annotations, mention/form/type artifacts, document-local evidence, typed
local meets, factor-local refinement receipts, and unresolved demand inventory.
It may not call a registry, select an external identity, close a
cross-document identity, promote a claim, or infer truth from repeated forms.

## Context and media

`CompilerContext` is explicit and declarative. It records the compiler and
media-normalisation versions plus supported capability declarations. It is not
a named semantic profile. Plain UTF-8 text is the first supported capability;
unsupported media remains visible in the manifest rather than falling through
to a guessed text parser.

## Safety and reproducibility

- recursion is bounded and does not follow symlinks by default;
- archives are recognised but not expanded;
- output and cache paths are excluded from input inventory;
- lexical relative-path ordering controls inventory order;
- content plus media-normalisation declaration determines document identity;
- paths are occurrence/provenance records, not document identity;
- a malformed or unsupported file yields a deterministic receipt and does not
  abort the corpus;
- existing content-addressed objects are reused only if byte-identical;
- phase results are separate visible artifacts, so local compile, demand
  planning, external acquisition, refinement, and projections can be invoked
  independently.

## Phase boundary

```text
inventory -> local compilation -> corpus demand planning
```

is the first release. Evidence acquisition, external snapshots, cross-document
candidate generation, reconciliation, and readiness projections remain later
explicit phases. GWB and AU are fixture directories for proof only; they do
not change the kernel's media or semantic behaviour.
