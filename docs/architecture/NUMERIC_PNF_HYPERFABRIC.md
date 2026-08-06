# Numeric multiscale PNF hyperfabric

## Authority flow

```text
immutable source text
→ bounded spaCy Doc workspace
→ corpus-wide numeric symbol interning
→ numeric sentence/token/dependency observations
→ sentence-local PNF closure
→ staged regional quotient and promotion
→ closed document interface
→ residual demand frontier
→ tranche/world integration
```

The source is parsed once for one parser contract. Ordinary semantic work never
reopens raw text or reconstructs the document-wide parser mapping. Targeted
boundary repair and a changed parser contract are the only parser re-entry
surfaces.

## Identity strata

Three identities must not be conflated:

1. **Corpus symbol identity** — one `BIGINT` for a normalized lexical or
   grammatical symbol inside the PostgreSQL authority database.
2. **Source occurrence identity** — one numeric sentence/token/span row tied to
   source coordinates.
3. **Semantic object identity** — one numeric object/factor/demand in the PNF
   hyperfabric.

Stable `BYTEA` digests accompany database-local dense IDs where identity must
survive rebuilding or transfer. Hexadecimal text is permitted only as a
human-facing publication label; joins, scheduling, lookup and graph identity use
integers or binary digests.

## Numeric boundary

After parser projection, hot-path PNF operations consume:

```text
run_id            BIGINT
document_id       BIGINT
sentence_id       BIGINT
token_id          BIGINT
head_token_id     BIGINT
orth_symbol_id    BIGINT
lemma_symbol_id   BIGINT
pos_symbol_id     BIGINT
dependency_id     BIGINT
morph_set_id      BIGINT
region_kind       SMALLINT
edge_kind         SMALLINT
factor_type_id    BIGINT
role_id           BIGINT
residual_type_id  BIGINT
```

Text remains only in symbol catalogs, source/provenance storage, compatibility
labels and explicit export boundaries.

## Cardinality funnel

Let `X_k` be the active interface at scale `k`. The evidence ledger is monotone,
but the active view is reductive:

\[
E_{k+1}=E_k\sqcup\Delta_k,
\qquad
X_{k+1}=\operatorname{QuotientAndPromote}(X_k).
\]

The intended tendency is:

\[
|X_{k+1}|\le |X_k|,
\]

with strict reduction whenever local observations can be represented by fewer,
richer objects. Lower-level evidence remains reachable through numeric support
edges; it is not carried in the active parent interface.

## Regional algebra

For a region `R`, local closure produces `G_R`. Its outward interface is:

\[
\Sigma(R)=\operatorname{Interface}(G_R)
         =(O_R,F_R,D_R,S_R,K_R),
\]

where:

- `O_R` — promoted objects;
- `F_R` — promoted factors;
- `D_R` — unresolved outward demands;
- `S_R` — exported definitions, scopes and temporal/modal state;
- `K_R` — coverage and closure evidence.

A parent consumes child interfaces, not descendant token populations:

\[
G_R=\operatorname{Close}_R\!\left(
       \bigsqcup_{C\prec R}\Sigma(C)
     \right).
\]

Authored paragraphs, lists, headings, provisions, sections and chapters provide
structural priors. Execution windows may use physical page/page-range boundaries
without making those boundaries semantic authority.

## Promotion law

A candidate `m` is promoted only when its value outside the current region
exceeds carrying and ambiguity cost:

\[
\operatorname{score}(m)=
I(m;\text{outer context})
+P(m)+2D(m)+2K(m)+\tfrac12R(m)
-\alpha L(m)-\beta A(m),
\]

where `P`, `D`, `K` and `R` measure factor participation, outward demand,
definition participation and recurrence. Promotion requires:

\[
\operatorname{score}(m)>\tau_k.
\]

Parent interfaces additionally admit repeated child exports, factor
participants and outward-demand carriers. Unsupported local noun candidates
remain in their closed child graph.

## MDL hierarchy planning

For a candidate region:

\[
C(R)=C_{\mathrm{internal}}(R)
    +\lambda C_{\mathrm{boundary}}(R)
    +\mu C_{\mathrm{execution}}(R).
\]

Operational description length includes graph nodes/edges, alternatives,
unresolved demands, boundary pressure, typed-row bytes, rule count, closure
rounds, query cost, promoted object count and interface cardinality.

Adjacent interface sketches are segmented with bounded beam dynamic
programming:

\[
DP[j]=\min_{j-W\le i<j}\left(DP[i]+C(G_{i+1:j})\right).
\]

Candidate aggregates are extended incrementally and path states use
constant-size backpointers. Therefore:

\[
T(N)=O(NWB),\qquad M(N)=O(NB),
\]

which is linear in book length for fixed semantic window `W` and beam width
`B`.

## Region DAG and skip indexes

Containment alone is a tree, but the compiled structure is a DAG with numeric
edges for containment, adjacency, export, resolution, support and continuation.
Binary-lifting rows store ancestors at distances:

\[
1,2,4,8,\ldots
\]

Typed ancestor rows also point directly to the nearest paragraph, provision,
section, chapter, execution window and document interface.

## Direct demand lookup

Every exported key contributes one row to a linear global interface index. It
is not copied into every descendant.

A demand performs:

\[
\text{numeric demand key}
\rightarrow
\text{B-tree candidate probe}
\rightarrow
\text{bounded candidate set}
\rightarrow
\text{nearest-common-interface DAG validation}.
\]

The expected cost is:

\[
O(\log N+k+h),
\]

where `k` is the bounded candidate count and `h` the small validated DAG path.
No all-pairs mention clustering or descendant-by-document-interface expansion is
permitted.

## Mention decomposition

1. Sentence closure emits local numeric span candidates and pronoun demands.
2. Adjacent/paragraph closure resolves immediate continuity and groups
   recurrence by symbol key in linear time.
3. Regional closure promotes factor participants, definitions, recurrent
   discourse objects and outward demands.
4. Document closure performs bounded indexed reconciliation.
5. Only unresolved promoted demands proceed to tranche/world resolution.

Negative, unique and exhaustive claims require the relevant coverage barrier.

## External-resolution barrier

World lookup never runs over tokens, arbitrary noun phrases or an open document.
It receives only the residual frontier of a closed document or tranche:

\[
\operatorname{WorldInput}=R(D^*)\ll T.
\]

## Prohibitions

Strict execution forbids:

- JSON/JSONB state, identity, checkpointing or replay;
- JSON-derived hashes;
- reparsing already committed observations under the same parser contract;
- document-wide token renumbering;
- duplicate dependency projection;
- reconstruction of a document-sized parser/mention mapping;
- all-pairs mention clustering;
- materializing every ancestor lookup in every descendant;
- world-model queries before local document/tranche closure.

Compatibility and export code may expose textual views from typed authority, but
those views cannot be read back as execution authority.
