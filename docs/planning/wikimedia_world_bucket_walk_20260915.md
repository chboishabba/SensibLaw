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
  -> append-only Postgres materialisation
  -> selected publication projection
  -> later logical Kant/eRDFa shard envelope
  -> later reviewed publication adapter
```

The runtime owners are:

- `src/ontology/wikimedia_world_walk.py`
- `src/storage/postgres/world_bucket_store.py`

Schemas:

- `sl.wikimedia_world_walk.v0_1`
- `sl.wikimedia_world_bucket.v0_1`
- Postgres migration `182_world_bucket_append_only_materialisation.sql`

## Edge families

The first runtime is producer-neutral above explicit adapters. Candidate edges may come from:

- Wikidata ontology/property traversal;
- Wikipedia navigation/revision links;
- cited/reference source follow;
- PNF semantic candidate relations;
- source/provenance relations;
- residual-driven inquiry.

The world walk does not decide that any candidate is true or authoritative.

### First real producer adapter

`edge_candidates_from_wikidata_bundles(...)` consumes the existing retained `StatementBundle` shape from `src/ontology/wikidata.py`; it does not parse Wikidata again.

Default admitted properties are the existing structural profile:

- `P31`;
- `P279`;
- `P361`;
- `P527`.

Only entity-valued/QID-resolvable statements are admitted. Non-entity values are ignored rather than guessed. Additional properties require an explicit property filter and are typed as `wikidata_property` rather than silently conflated with the structural ontology family.

The current production-shaped world-walk module no longer depends on JSON canonicalisation or regex QID parsing. QID admission is structural and projection identity is hashed from typed length-prefixed fields.

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

## Postgres materialisation boundary

The immediate physical implementation target is Postgres, not live eRDFa/IPFS publication.

Migration `182_world_bucket_append_only_materialisation.sql` normalises the bucket into seven append-only families:

1. bucket identity;
2. bucket node membership;
3. typed world-growth receipts;
4. selected projection identity;
5. selected projection members;
6. projection parent/lineage refs;
7. materialisation receipts.

The materialisation states are:

- `skeleton`;
- `reference_only`;
- `full_local`;
- `cold_local`;
- `federated_only`.

These are possession/materialisation coordinates, not epistemic statuses.

The database rejects `UPDATE`/`DELETE` on the world-bucket families. Runtime replay uses deterministic identities with `INSERT ... ON CONFLICT DO NOTHING`, so replay is idempotent without rewriting prior evidence.

A materialisation transition is another append-only observation. For example:

```text
full_local -> skeleton
```

does not erase the earlier full-local receipt. A later consumer may derive current possession state while the historical transition remains available.

Core firewall:

```text
materialised bytes != semantic authority != evidence payment
```

and query-indexed adequacy remains decisive:

```text
navigation may factor through skeleton/reference-only state
exact quotation and strict primary-authority review do not
```

## Publication boundary

`build_publishable_bucket_manifest(...)` now returns a typed `WorldBucketProjection` rather than a generic mapping. It projects only explicitly selected nodes/edges into a candidate logical package.

The projection is deliberately:

- `candidate_only = true`;
- `semantic_promotion = false`;
- `live_ipfs_publication_performed = false`;
- `publication_projection_is_browsing_history = false`.

The logical packaging coordinates remain:

- target: `kant-erdfa-shardset`;
- envelope: `cbor-compatible-logical-envelope`;
- addressing state: `sha256-now-cid-later`;
- deterministic logical shard id;
- empty sink refs.

Parent bucket CIDs/refs are retained explicitly in Postgres projection lineage rather than existing only inside a digest.

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
- Postgres world-bucket storage for durable local/skeletal state;
- ITIR Reading Trail for human exploration;
- Kant/eRDFa for later immutable shard packaging;
- IPFS/HF sinks for later content-addressed publication;
- Zelph for query-shaped global retrieval.

## Current status

Previously observed focused world-walk contract:

- bounded deterministic world walk;
- append-only typed growth receipts;
- cycle preservation;
- 100-hop default budget;
- real adapter from existing Wikidata `StatementBundle` rows;
- candidate-only selected publication projection;
- browsing-history exclusion.

New Postgres tranche is source-written and awaiting local verification:

- JSON/regex removed from the world-walk projection path;
- typed `WorldBucketProjection`;
- typed-field SHA-256 identity rather than JSON canonicalisation;
- normalized append-only Postgres schema;
- explicit projection lineage refs;
- five materialisation states;
- database UPDATE/DELETE rejection;
- idempotent insert-only persistence adapter;
- matching DASHI owner `SensibLawWorldBucketPostgresMaterialisationExact`.

Not yet claimed:

- focused Python tests for the new Postgres tranche on exact head;
- migration execution against a live Postgres instance;
- focused Agda type-check of the new materialisation owner;
- live adapter from revision-locked Wikipedia navigation/reference candidates;
- PNF branching-pressure adapter;
- executed 100-hop Mabo world-growth receipt;
- empirical cross-policy comparison (`ontology`, `wiki`, `source`, `semantic`, `hybrid`);
- real CBOR/eRDFa shard serialization;
- CID derivation / IPFS publication;
- Zelph ingestion/query of published world buckets;
- global semantic promotion/review.

## Roadmap consequence

The architecture is now four distinct planes:

1. **Acquire / grow locally** — WikimediaWorldWalk and existing source/PNF producers.
2. **Materialise adequately** — Postgres full/skeletal/reference-only/federated possession state.
3. **Select / package** — candidate-only bucket projection with immutable logical identity.
4. **Review / publish / query globally** — later Kant/eRDFa/IPFS publication and Zelph retrieval.

The key deployment law is:

```text
self-populating != self-hoarding
```

A large world may be representable/reopenable without every node storing every source byte locally.

### P0 next — verify Postgres materialisation

Run focused tests and apply migration 182 to a disposable/live development database. Persist a small Mabo bucket twice and verify:

- second replay inserts no conflicting replacement state;
- historical growth receipts remain unchanged;
- a skeleton materialisation receipt can coexist with a prior/full-local receipt;
- selected projection and parent refs reopen exactly;
- no persistence event creates semantic promotion or evidence payment.

### P1 — first bounded Mabo world specimen

Run the first real Mabo `hybrid` world walk from already-retained/revision-pinned inputs. Start small enough to inspect manually, then raise the budget toward 100 only after PG receipts are stable. Produce:

- world-growth receipts;
- edge-family counts;
- QID/PID/revision/source/PNF counts;
- cycles/revisits/dead ends;
- unresolved residuals;
- selected candidate projection;
- materialisation/storage metrics.

The missing non-Wikidata colours remain revision-locked Wikipedia navigation/reference candidates and PNF/source/residual candidate projections.

### P2 — Reading/Review Workbench projection

Expose a bounded Mabo proof/reading trail over the persisted bucket. The displayed world remains much smaller than the available world; source/provenance and graph detail reopen on demand.

### P3 — policy comparison

Run the same seed through separate traversal policies and compare typed overlap/world-growth fingerprints plus residual-contraction-per-byte/request.

### P4 — immutable publication artifact

Bind an explicitly selected projection to the existing Kant/eRDFa shard emitter and produce a local immutable artifact without yet pushing it to a public sink.

### P5 — optional federation/publication

Only after local artifact parity: publish explicitly selected public buckets to IPFS/HF, ingest/query through Zelph, and keep semantic promotion as a separate review action.
