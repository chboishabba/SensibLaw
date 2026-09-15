# Wikimedia World Bucket Walk — 2026-09-15

## Purpose

Turn the existing Wikidata/Wikipedia/source-follow/PNF machinery into a bounded local inquiry-world recurrence whose selected projection can later be packaged through the existing Kant/eRDFa/IPFS publication lane.

This is not a new crawler and not a global truth graph.

## Core recurrence

```text
seed
  -> typed candidate expansion
  -> bounded deterministic selection
  -> append-only WorldGrowthReceipt
  -> local bucket
  -> selected publication projection
  -> logical Kant/eRDFa shard envelope
  -> later reviewed publication adapter
```

The runtime owner is:

- `src/ontology/wikimedia_world_walk.py`

Schemas:

- `sl.wikimedia_world_walk.v0_1`
- `sl.wikimedia_world_bucket.v0_1`

## Edge families

The first runtime is intentionally producer-neutral. Existing producers may supply candidate edges from:

- Wikidata ontology/property traversal;
- Wikipedia navigation/revision links;
- cited/reference source follow;
- PNF semantic candidate relations;
- source/provenance relations;
- residual-driven inquiry.

The world walk does not decide that any candidate is true or authoritative.

## First executable contract

`WorldWalkPolicy` defaults to a 100-hop budget and one selected extension per expansion locus. The policy is deterministic and records cycles rather than silently erasing them.

Each selected extension produces a typed receipt containing:

- hop index;
- source;
- target;
- edge family;
- relation;
- priority;
- cycle marker.

The runtime does not fetch or crawl. It consumes already-produced candidate edges so existing Wikidata, Wikipedia, source-follow and PNF machinery remain authoritative for acquisition/parsing semantics.

## Publication boundary

`build_publishable_bucket_manifest(...)` projects only explicitly selected nodes/edges into a candidate manifest.

The manifest is deliberately:

- `candidate_only = true`;
- `semantic_promotion = false`;
- `live_ipfs_publication_performed = false`;
- `publication_projection_is_browsing_history = false`.

The logical packaging block currently declares:

- target: `kant-erdfa-shardset`;
- envelope: `cbor-compatible-logical-envelope`;
- addressing state: `sha256-now-cid-later`;
- deterministic logical shard id;
- empty sink refs.

This is a compatibility target, not a claim that actual Kant CBOR/eRDFa serialization or IPFS publication occurred.

## Privacy / anti-panopticon boundary

A local inquiry bucket and a Reading Trail are not the same object.

Publishing a selected world must not implicitly publish:

- click/navigation history;
- private side trails;
- inferred beliefs;
- inferred comprehension;
- unselected local candidate fibres.

The selected graph may be publishable while the local navigation history remains non-factorable through that projection.

## Relation to existing machinery

Reuse, do not replace:

- `src/ontology/wikidata.py` for Wikibase statement/property/qualifier/reference structure;
- revision-locked Wiki review packet machinery for Wikipedia/Wikidata source context;
- `wikidata_review_packet_follow_depth.py` and source-follow receipts for bounded reference evidence;
- SLR/PNF producers for semantic candidate relations;
- ITIR Reading Trail for human exploration;
- Kant/eRDFa for later immutable shard packaging;
- IPFS/HF sinks for later content-addressed publication;
- Zelph for query-shaped global retrieval.

## Current status

Implemented and focused-test GREEN:

- bounded deterministic world walk;
- append-only typed growth receipts;
- cycle preservation;
- 100-hop default budget;
- candidate-only selected publication projection;
- browsing-history exclusion;
- deterministic SHA-256 content digest;
- Kant/eRDFa-shaped logical packaging metadata.

Not yet paid:

- live adapter from real Wikidata statement candidates into `EdgeCandidate`;
- live adapter from revision-locked Wikipedia navigation/reference candidates;
- PNF branching-pressure adapter;
- executed 100-hop Mabo world-growth receipt;
- empirical cross-policy comparison (`ontology`, `wiki`, `source`, `semantic`, `hybrid`);
- real CBOR/eRDFa shard serialization;
- CID derivation / IPFS publication;
- Zelph ingestion/query of published world buckets;
- global semantic promotion/review.

## Roadmap consequence

The architecture is now split into three distinct planes:

1. **Acquire / grow locally** — WikimediaWorldWalk and existing source/PNF producers.
2. **Select / package** — candidate-only bucket projection with immutable logical identity.
3. **Review / publish / query globally** — later Kant/eRDFa/IPFS publication and Zelph retrieval.

This moves the roadmap beyond UI-only Reading Trail work. The Reading Trail can now sit over a much larger precomputed local bucket without rendering or publishing the whole bucket.

### P0 next

Run the first real Mabo `hybrid` world walk with a 100-hop budget from already-retained/revision-pinned inputs. Produce:

- world-growth receipts;
- edge-family counts;
- QID/PID/revision/source/PNF counts;
- cycles/revisits/dead ends;
- unresolved residuals;
- selected candidate publication manifest.

### P1

Run the same seed through separate traversal policies and compare typed overlap/world-growth fingerprints.

### P2

Bind the candidate manifest to the existing Kant/eRDFa shard emitter and produce a local immutable artifact without yet pushing it to a public sink.

### P3

Only after local artifact parity: publish an explicitly selected bucket to IPFS/HF, ingest/query through Zelph, and keep semantic promotion as a separate review action.
