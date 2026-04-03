# SensibLaw TODO

- [P0] Reconsider the moonshot normalization read across AU, GWB, and
  Wikidata:
  the previous judgment-architecture pass was useful but too Nat-centric.
  The stronger cross-lane target is:
  bounded evidence bundle in -> promoted outcomes out -> derived
  review/product/graph surfaces after that.
  - next orchestration order:
    - shared evidence-bundle -> promoted-outcome contract
    - AU product normalization
    - GWB product normalization
    - Nat text-bridge / grounding as one adopter family
    - minimal shared primitive/comparison support only where it directly helps
      those products
  - current promotion order:
    - `Ramanujan`
    - `Erdos`
    - `Lorentz`
    - `Euler`
    - `Ohm`
    - `Huygens`
  - control note:
    - `../docs/planning/moonshot_compiler_normalization_reconsideration_20260402.md`
      controls lane order if a support note differs
  - checkpoint re-read:
    - order unchanged
    - one worker per lane unchanged
    - no further allocation change justified at this checkpoint
    - rechecked again with no change
    - repeated checkpoint confirmation: still no change
    - further docs-only reaffirmation now adds no new governance signal
    - convergence point reached: the next honest move is implementation
      promotion under the same lane ownership and order
    - docs-only orchestration updates are frozen for this checkpoint unless
      new lane evidence materially changes ownership, order, or contract scope
  - keep graph explicitly derived and optional, not the organizing truth layer
  - planning note:
    `../docs/planning/moonshot_compiler_normalization_reconsideration_20260402.md`
  - completion roadmap:
    - land the shared evidence-bundle -> promoted-outcome contract as the
      cross-lane compiler spine
    - normalize AU onto that contract
    - normalize GWB onto that contract
    - land the reusable `promote | abstain | audit` gate above those
      normalized products
    - then shift priority to the first operator-grade workflow layer and the
      remaining high-priority workflow lanes
  - progress read:
    - reusable substrate / canonical-surface program: roughly `90-95%`
    - moonshot compiler-contract reframing: roughly `70-80%`
    - full project overall: roughly `45-50%`
  - completion condition:
    - AU, GWB, and Wikidata/Nat all accept bounded evidence bundles and emit
      promoted outcomes plus derived products under one shared contract
    - reusable promotion gate exists above those products
    - graph stays derived and optional
    - operator workflow no longer lags far behind the architecture
  - first implementation slice:
    - DONE: add one tiny shared `compiler_contract` payload
    - DONE: first adopters:
      - AU public handoff
      - GWB public handoff
      - Wikidata migration pack
    - do not normalize doctrinal or migration semantics at this layer
  - current promoted lane:
    - AU product normalization
    - DONE first bounded cut:
      - emit `semantic_context.compiler_contract` in the AU fact-review bundle
  - current AU read:
    - AU public handoff and AU fact-review bundle now share the compiler
      summary shape
  - next promoted lane:
    - GWB product normalization
    - DONE first bounded cut:
      - emit `compiler_contract` from GWB public review
      - emit `compiler_contract` from GWB broader review
    - current GWB read:
      - GWB public handoff, GWB public review, and GWB broader review now
        share the compiler summary shape
  - current promoted lane:
    - reusable `promote | abstain | audit` gate
    - DONE first bounded cut:
      - add one shared gate record above normalized products
      - adopt it first in AU, GWB, and Wikidata normalized outputs
    - landed adopters:
      - AU public handoff
      - AU fact-review bundle
      - GWB public handoff
      - GWB public review
      - GWB broader review
      - Wikidata migration pack
    - validation:
      - `28 passed`
      - touched modules `py_compile` clean
  - next pinned lane:
    - first operator-grade workflow layer over normalized outputs
    - DONE first bounded cut:
      - emit `semantic_context` and one derived `workflow_summary` from the
        fact-review workbench payload
      - surface one explicit inspect -> decide -> record -> follow-up card in
        the fact-review route
    - validation:
      - backend focused gate: `30 passed`
      - `read_model.py` `py_compile` clean
      - repo-wide `npm run check` still blocked by unrelated pre-existing
        `wiki-timeline-aoo-all` errors
  - next pinned lane:
    - first bounded annotation / QA workbench slice over the existing
      fact-review/read-model/operator-view spine
  - legal moonshot expansion:
    - AU should deepen first through product normalization, not a separate
      speculative doctrine engine
    - next bounded AU cut:
      - emit one derived `legal_follow_graph` from existing authority
        receipts, legal refs, and citation candidates
      - keep the graph derived and reviewable
    - explicit safety boundary:
      - `docs/red_team_anti_panopticon.md`
      - `docs/panopticon_refusal.md`
  - legal moonshot expansion:
    - AU should now widen through normalized legal-follow products, not a
      parallel bespoke graph lane
    - first bounded slice:
      - derive one `legal_follow_graph` from authority receipts, legal refs,
        citations, and follow-needed conjectures inside the AU fact-review
        bundle semantic context
    - keep the graph:
      - derived
      - non-predictive
      - non-authoritative
      - challengeable by source and receipt
    - governing notes:
      - `../docs/planning/legal_surface_expansion_and_graph_union_20260402.md`
      - `../docs/planning/anti_panopticon_red_team_provisions_20260402.md`
  - revised legal-expansion read:
    - AU legal follow is now the next strong legal adopter lane
    - prioritize:
      - case follow
      - authority follow
      - supporting legislation / cited instrument understanding
      - derived legal-follow graph surfaces
      - publish `supporting_legislation_role_counts` for derived graphs
    - keep graph derived, optional, and challengeable
    - do not widen into predictive legal decisionmaking or surveillance logic
  - immediate bounded slice:
    - emit one AU derived legal-follow graph from existing authority receipts,
      legal refs, and citation hints inside the fact-review bundle semantic
      context
    - DONE:
      - `src/policy/legal_follow_graph.py`
      - `semantic_context.legal_follow_graph`
      - `operator_views.legal_follow_graph.summary`
      - AU compiler contract now lists `legal_follow_graph` as a derived
        product
      - AU authority receipts now include structured legal-ref and citation
        detail for downstream graph consumers
      - legal-follow graph now distinguishes case refs, supporting
        legislation, and cited instruments
      - authority-follow operator packets now expose reference-class counts
        plus structured legal-ref and citation detail
    - validation:
      - focused gate: `19 passed`
      - touched modules `py_compile` clean
  - anti-panopticon hardening:
    - keep `panopticon_refusal.md` as a controlling boundary
    - make the red-team posture explicit in:
      `docs/red_team_anti_panopticon.md`
  - next legal-expansion lane:
    - deepen supporting-legislation / cited-instrument attachment surfaces on
      top of the derived legal-follow graph
    - DONE bounded provenance cut:
      - legal-follow graph now merges richer receipt/conjecture metadata into
        shared nodes rather than keeping only the first sparse version
      - supporting-legislation and cited-instrument nodes/edges now retain
        structured ref detail where available
      - citation and authority-receipt nodes now retain structured citation,
        paragraph, and linkage provenance where available
      - attachment-bearing graph nodes now also accumulate bounded
        supporting event and supporting receipt provenance where available
    - validation:
      - focused AU/legal/compiler gate: `21 passed`
  - current bounded AU legal/UI round:
    - deepen supporting-legislation / cited-instrument attachment provenance
      further where it materially improves inspectability
    - surface the derived legal-follow graph in the fact-review workbench as
      a read-only derived inspection surface
    - keep it explicitly non-authoritative and challengeable by source and
      receipt
    - DONE bounded cut:
      - graph summary now exposes supporting receipt counts and supporting
        authority-kind counts for downstream inspection
      - AU authority-follow payloads now also expose bounded
        `jurisdiction_hint_counts` and `instrument_kind_counts`
      - AU authority-follow payloads now also expose bounded
        `ref_kind_counts`
      - AU authority-follow payloads now also expose bounded
        `citation_court_hint_counts` and `citation_year_counts`
      - AU legal-follow graph now preserves those same jurisdiction /
        instrument hints on supporting-legislation and cited-instrument
        nodes and edges, and reports bounded summary counts for them
      - AU legal-follow graph now also reports bounded
        `reference_kind_counts`, `reference_class_counts`, `ref_kind_counts`,
        `edge_kind_counts`, `edge_reference_class_counts`, and
        `edge_ref_kind_counts`
      - AU legal-follow graph now also reports bounded
        `citation_court_hint_counts` and `citation_year_counts`
      - fact-review workbench now surfaces the graph as a read-only derived
        inspection pane with summary, authority/receipt, ref/citation, and
        typed-link views
      - that workbench pane can also render bounded distribution grids when
        the derived graph provides them
    - validation:
      - focused AU/legal/compiler gate: `21 passed`
      - touched Python modules `py_compile` clean
      - `itir-svelte` `npm run check` still fails only on unrelated
        `wiki-timeline-aoo-all` errors
  - next bounded legal parity cut:
    - DONE: added one derived GWB `legal_follow_graph` helper and adopted it
      in:
      - `gwb_public_review`
      - `gwb_broader_review`
    - DONE: existing GWB review summaries now expose that graph via a bounded
      "Derived Legal-Linkage Graph" section
    - DONE: existing GWB review summaries now also expose bounded
      source-kind/source-family/linkage-kind/review-status/support-kind
      distributions from that graph so operators can inspect the linkage
      surface without a separate UI lane
    - DONE: those GWB review summaries now also expose bounded
      `Graph inspection` and `Sample typed links` sections for read-only
      graph inspection without inventing a separate UI lane
    - DONE: the existing fact-review legal-follow pane is typed to render
      those bounded graph distributions when present, keeping the same
      derived-only surface available to AU and GWB
    - DONE: GWB compiler contracts now list `legal_linkage_graph` as an
      explicit derived product for those review outputs
    - DONE: GWB review payloads now also expose one bounded JSON
      `operator_views.legal_follow_graph` surface with summary,
      highlight-node, and sample-edge inspection data
    - DONE: the fact-review workbench now renders that same bounded
      `operator_views.legal_follow_graph` block for GWB workflows
    - DONE: GWB legal-linkage graphs now add bounded followed-source nodes
      when source-review receipts already carry HTTP links
    - keep the surface product-shaped, not doctrinally overclaimed
    - validation:
      - focused AU+GWB/compiler gate: `25 passed`
      - touched modules `py_compile` clean
  - legal moonshot is now normal program state:
    - AU legal-follow and GWB legal-linkage/follow are standard
      compiler-shaped legal lanes now
    - next bounded AU cross-jurisdiction requirement:
      - allow one explicit AU -> UK/British follow hop where current
        authority receipts, refs, or citation detail already point there
      - keep it provenance-backed, derived-only, and review-first
      - do not widen into general common-law ancestry crawl
    - next bounded GWB cohort candidates:
      - previous US presidents with visible executive/litigation follow
      - UK Brexit-era politicians where UK/EU legal interactions are legible
    - named proving-ground rule:
      - treat Brexit as a first-class bounded legal-union proving ground, not
        only as a cohort example
      - use it to test UK domestic law / EU-law interaction surfaces through
        bounded reviewable products
      - keep it anti-panopticon-safe and explicitly non-surveillance
    - DONE bounded cut:
      - AU legal-follow now derives one explicit UK/British follow target when
        current receipt/ref/citation evidence already points there
      - GWB legal-linkage now classifies followed-source legal URLs into
        bounded cite classes and reports Brexit-related follow counts where
        source text/URLs already carry that pressure
      - GWB legal-linkage now also seeds followed-source receipts from the
        canonical foundation-source catalog when a review row already names a
        known UK/EU legal source
    - keep cohort expansion bounded, review-first, and anti-panopticon-safe
    - progress/full-flow checkpoint:
      - recent legal/compiler program: roughly `70-80%`
      - broader legal-moonshot preparation: roughly `35-45%`
      - full end-state moonshot: roughly `15-25%`
      - end-state remains:
        evidence intake -> canonicalization -> typed extraction -> bounded
        follow -> promote/abstain/hold -> derived graph -> cross-system union
        -> commonality/conflict analysis -> operator inspection -> bounded
        products under anti-panopticon governance

## Wikidata
- [x] Implement the bounded `P31` / `P279` Wikidata control-plane prototype described in `docs/planning/wikidata_transition_plan_20260306.md`.
- [x] Add a bounded live-case fixture anchored on the current `alphabet` / `writing system` example.
- [x] Define a reproducible two-window Wikidata slice for EII and SCC diagnostics.
- [x] Add deterministic JSON report schema and CLI surface for Wikidata diagnostics.
- [x] Run the first Niklas/Ege/Peter review pass using `docs/planning/wikidata_working_group_review_template_20260307.md`.
- [x] Define the v0.1 reviewer-facing report contract and severity/ranking rules.
- [x] Add a local entity-export importer (`wikidata build-slice`) so review slices do not require hand-curated JSON.
- [x] Maintain a single working-group status doc at `docs/wikidata_working_group_status.md`.
- [x] Extend phase-1 diagnostics to qualifier drift after the `P31` / `P279` core report is stable.
- [x] Import real qualifier-bearing slices and add an importer-backed phase-2 baseline pack.
- [x] Add a deterministic live qualifier-drift finder that ranks candidates and scans revision pairs programmatically.
- [x] Find a true live revision-pair qualifier-change case with the live finder.
- [x] Promote the primary live materialized drift case (`Q100104196|P166`, `2277985537 -> 2277985693`) into repo-stable fixtures and review docs.
- [x] Promote a second confirmed live drift case (`Q100152461|P54`, `2456615151 -> 2456615274`) into the pinned repo pack.
- [x] Connect the new deterministic lexer/entity bridge outputs to the existing
  external-ref/entity substrate so seeded refs (`UN`, `UNSC`, `ICC`, `ICJ`)
  are persisted as linked entities without polluting canonical lexeme identity.
  Curated batch emission plus CLI upsert roundtrip coverage now exist.
- [x] Expand the DB-backed deterministic bridge substrate only where corpus
  yield justifies it, keeping open-world Wikidata ambiguity resolution outside
  the lexer. Current v1 slice covers seeded global bodies plus the first
  GWB-oriented U.S. court/body set (`U.S. Supreme Court`, `U.S. Senate`,
  `House of Representatives`, `CIA`, `FBI`) and now includes reviewed
  district-court alias variants (`U.S. district courts`, `US district courts`,
  `United States district courts`, `federal district courts`,
  `federal trial court`).
- [x] Consolidate the docs around the extraction/enrichment boundary so the
  contract is explicit everywhere: local tokenizer/parser (`spaCy` dependency
  harvesting included) may provide deterministic structural evidence for
  relation inference, while Wikidata remains downstream enrichment/checking and
  never canonical token identity. See
  `docs/planning/extraction_enrichment_boundary_20260307.md`.
- [x] Add a bounded Wikidata mereology/parthood design note for the current
  Niklas / Ege / Peter lane, focused on typed/disambiguated parthood
  (`class-class`, `instance-instance`, `instance-class`, inverse validity vs
  redundancy) rather than generic ontology repair. See
  `docs/planning/wikidata_mereology_parthood_note_20260307.md`.

- [x] Widen the Nat reviewer-packet attachment lane to a first bounded
  multi-row surface. The attachment coverage index now records `13 / 53`
  packetized held split rows in
  `docs/planning/wikidata_nat_review_packet_attachment_coverage_20260401.md`,
  keeping the lane partial but no longer single-row only. The latest added
  packets are the two sidecar-backed pilot-pack rows `Q10416948` and
  `Q56404383`.
- [x] Decide which parts of the existing DASHI-style epistemic/projection
  formalism are safe to reuse for Wikidata mereology diagnostics without
  collapsing the bounded control-plane work into an ontology-fix proposal.
  Decision captured in
  `docs/planning/wikidata_mereology_parthood_note_20260307.md`.
- [x] Add a bounded Wikidata property/constraint pressure-test note covering:
  financial-flow/timeseries modeling, subset-vs-total quantity representation,
  graph/report surfaces, and practical loaded-property questions (`supports`
  vs `P366`) as deterministic ontology diagnostics rather than ad hoc side
  discussions. See
  `docs/planning/wikidata_property_constraint_pressure_test_20260307.md`.
- [x] Define a review trigger for historical rewind checks on pinned Wikidata packs
  (e.g., confirmed-case disappearance, material severity flips, or focused
  property regressions) to decide when historical slices should be compared
  instead of only using the newest pinned snapshot.
- [x] Add a light diagnostic note on label harmonization signals (`type of XXX`
  vs `XXX subclass` and related variants) so user-facing naming inconsistency
  can be reported without treating labels as ontology truth. Captured in
  `docs/planning/wikidata_property_constraint_pressure_test_20260307.md`.
- [x] Expand the reviewed bridge slice with the next high-yield GWB U.S.
  additions: `Department of Defense` and the `United States Court of Appeals
  for the Sixth Circuit` are now pinned and imported into the shared bridge DB.
- [x] Keep the reviewed bridge slice growing only through pinned, auditable
  entries. The previously queued additions (`United States Department of
  Defense`, `United States Court of Appeals for the Sixth Circuit`, and the
  low-ambiguity district-court alias variants) are now imported.
- [x] Import a reviewed deterministic bridge slice for the remaining GWB U.S.
  bodies/courts not yet present in the live bridge slice after the current sync
  (district-court lane variants now imported; additional executive/judicial
  additions remain review-gated).
- [x] Add checked and dense Wikidata review artifacts above the structural
  handoff so the lane exposes review items, source review rows, unresolved
  clusters, cues, provisional rows, and bundle queues rather than only a
  status/handoff slice.
- [x] Add checked and broader GWB review artifacts above the existing checked
  public handoff and broader corpus checkpoint so the lane exposes the same
  operator-facing review geometry as AU/Wikidata.
- [x] Add a normalized cross-lane summary block for AU, Wikidata, and GWB so
  workload and ranking metrics become directly comparable rather than only
  shape-compatible.
- [x] Reuse normalized Python anchor queueing in
  `scripts/build_gwb_public_review.py` by consuming
  `src/policy/affidavit_extraction_hints.py` for calendar-anchor shaping and
  provisional anchor ranking/bundling while preserving the GWB artifact shape.
- [x] Move Wikidata checked/dense review queueing policy out of
  `scripts/build_wikidata_structural_review.py` into one shared Python
  component that both structural-review builders consume.
- [x] Reuse normalized Python queueing in
  `scripts/build_gwb_broader_review.py` by consuming
  `src/policy/affidavit_extraction_hints.py` for provisional review ranking
  and bundle rollup while preserving the broader-review artifact shape.
- [x] Normalize duplicated transcript and AU fact-review bundle assembly into
  one shared Python component:
  `src/fact_intake/review_bundle.py` now owns chronology assembly,
  abstention rollup, and fact-review bundle envelope shaping, with transcript
  and AU builders reduced to lane-specific semantic context and operator-view
  additions.
- [x] Normalize duplicated transcript and AU fact-intake payload scaffolding
  into one shared Python component:
  `src/fact_intake/payload_builder.py` now owns run/source/excerpt/statement
  /fact-candidate scaffolding and final payload emission, with transcript and
  AU builders reduced to lane-specific observation mapping.
- [x] Normalize duplicated transcript and AU observation row geometry into one
  shared Python component:
  `src/fact_intake/observation_builder.py` now owns observation ID generation
  and common row shaping, with transcript and AU builders reduced to choosing
  which observations to emit.
- [x] Normalize duplicated transcript and AU projection mechanics into one
  shared Python component:
  `src/fact_intake/projection_helpers.py` now owns relation-status policy,
  fact-status policy, and generic role/relation observation emission, with
  transcript and AU builders keeping only lane-specific mapping tables.
- [x] Normalize duplicated fact-intake disclosure/export policy into one
  shared Python component:
  `src/fact_intake/disclosure_policy.py` now owns recipient normalization,
  protected-disclosure settings, share-with normalization, stable hashing, and
  UTC creation stamps, with personal-handoff, protected-disclosure, and chat
  import builders reduced to adopter-specific payload shaping.
- [x] Normalize duplicated fact-intake payload mutation helpers into one
  shared Python component:
  `src/fact_intake/payload_mutations.py` now owns observation, review, and
  contestation append semantics plus deterministic mutation-row IDs, with
  personal-handoff and acceptance-fixture builders reduced to adopter-specific
  inputs and provenance.
- [x] Normalize duplicated fact-intake handoff artifact writing into one
  shared Python component:
  `src/fact_intake/handoff_artifacts.py` now owns mode/version routing,
  summary renderer selection, artifact emission, and common return-payload
  shaping for the chat-json, Messenger, Google Public, message-db, and
  OpenRecall script entrypoints.
- [x] Normalize duplicated loader-side `TextUnit` shaping into one shared
  Python component:
  `src/reporting/text_unit_builders.py` now owns indexed `TextUnit`
  construction, timestamped speaker rendering, and header/body composition for
  Messenger, Google Public, structure-report DB loaders, and OpenRecall.
- [x] Normalize duplicated importer-side source identity and timestamp policy
  into one shared Python component:
  `src/reporting/source_identity.py` now owns hashed source IDs, Google
  public source-id formatting, UTC millisecond timestamp rendering, local
  capture timestamp/date derivation, and OpenRecall capture IDs for Messenger,
  Google Public, and OpenRecall import surfaces.
- [x] Normalize duplicated importer-side source loader policy into one shared
  Python component:
  `src/reporting/source_loaders.py` now owns loader path resolution, Messenger
  export file discovery, HTTP text fetch, and timestamped artifact lookup for
  Messenger, Google Public, and OpenRecall import surfaces.
- [x] Normalize duplicated Wikidata structural IO policy into one shared
  Python component:
  `src/policy/wikidata_structural_io.py` now owns repo-relative path shaping,
  JSON fixture loading, and JSON+markdown artifact emission for the Wikidata
  structural handoff, checked review, and dense review builders.
- [x] Start Wikidata checked/dense review geometry normalization with the
  qualifier-drift overlap:
  `src/policy/wikidata_structural_geometry.py` now owns the shared checked and
  dense qualifier-drift source-row and cue-building geometry, with both review
  builders reduced to orchestration for that first overlap slice.
- [x] Extend Wikidata checked/dense review geometry normalization to the
  hotspot overlap:
  `src/policy/wikidata_structural_geometry.py` now also owns checked hotspot
  summary/question geometry and dense hotspot summary/focus/family geometry,
  with both review builders reduced further toward orchestration shells.
- [x] Extend Wikidata checked/dense review geometry normalization to the
  disjointness overlap:
  `src/policy/wikidata_structural_geometry.py` now also owns checked
  disjointness row/cue geometry and dense disjointness row/cue geometry,
  leaving the builders closer to pure orchestration surfaces.
- [x] Finish the wiki revision monitor writer contraction decision:
  pair-report JSON and contested-graph JSON no longer survive as routine
  report artifacts on the default runner path, and timeline/AOO extraction no
  longer depends on subprocess JSON handoff.
- [x] Finish pair-report demotion in the wiki revision monitor lane so
  `pair_report_path` is no longer an operational state driver.
- [x] Finish current-article state contraction in the wiki revision monitor
  lane so timeline/AOO JSON paths are not persisted as durable continuity, and
  remove the default subprocess JSON handoff by calling the extractors
  in-process.
- [x] Finish the remaining wiki revision monitor contract cleanup:
  remove dead path-centric contract residue, freeze the no-routine-JSON export
  posture explicitly, and confirm the runner/query/docs surfaces all describe
  the lane as SQLite-canonical rather than transitional.
  - DONE:
    default read-model/query payloads now demote export-path fields so
    `report_path`, `pair_report_path`, `contested_graph_path`, and `graph_path`
    do not appear as routine runtime-state fields. Contract note:
    `../docs/planning/wiki_revision_monitor_path_contract_demotion_20260401.md`.
  - DONE:
    the default runner path no longer writes pair-report JSON or
    contested-graph JSON, and the runner summary/triage surface no longer
    advertises those paths as routine report fields. Contract note:
    `../docs/planning/wiki_revision_monitor_no_routine_json_reports_20260401.md`.
  - DONE:
    the dead report/graph path columns are now removed from fresh storage and
    read-model schema, with in-place rebuild coverage for old DBs. Contract
    note: `../docs/planning/wiki_revision_monitor_dead_path_schema_drop_20260401.md`.
  - DONE:
    the provenance boundary is now explicit: local path fields are not truth,
    and any future share/publish posture should resolve through logical
    artifact identity, revision, digest, sink refs, and acknowledgements
    rather than local JSON/path assumptions. Contract note:
    `../docs/planning/wiki_revision_monitor_provenance_path_boundary_20260401.md`.
  - DONE:
    `timeline_path` and `aoo_path` are now removed from
    `wiki_revision_monitor_article_state` and
    `wiki_revision_monitor_article_results`, including old-DB rebuilds.
    Contract note:
    `../docs/planning/wiki_revision_monitor_path_residue_cut_20260402.md`.
  - final posture:
    `snapshot_path` survives only as bounded article-local provenance, and
    `out_dir` survives only as transitional run-level provenance rather than
    truth or semantic identity.
- [x] Land the first bounded manifest-root / manifest-load normalization slice:
  `src/storage/manifest_runtime.py` now owns repo-owned manifest-path
  resolution and top-level JSON-object loading, with first adopters in
  `src/fact_intake/acceptance_fixtures.py` and
  `scripts/source_pack_manifest_pull.py`. Contract note:
  `../docs/planning/manifest_root_normalization_slice_20260402.md`.
- [x] Freeze the first post-substrate user-story alignment read:
  `../docs/planning/user_story_alignment_and_reprioritization_20260402.md`
  now records that the strongest remaining SensibLaw gaps are no longer broad
  substrate normalization, but operator/workflow gaps above the existing
  fact-review/read-model/review-geometry spine:
  - guided next-step workflow clarity through `itir-svelte`
  - a real annotation / QA workbench slice
  - more direct user-feedback evidence beyond proxy/story notes
- [ ] Push the next reusable judgment-architecture split above the now-settled
  substrate layer:
  - use `../docs/planning/judgment_architecture_lane_split_20260402.md` as the
    current lane note
  - current read:
    - the next highest-value work is not more generic infrastructure cleanup
    - it is reusable semantic/judgment scaffolding that can help both the
      Nat moonshot and the broader legal/text-heavy lanes
  - current bounded priority order:
    - first executable text bridge over representative temporal / multi-value
      climate rows
    - first legal doctrinal primitive scaffold over bounded AU
      procedural-meaning cases
    - first common typed primitive/comparison pattern shared across those lanes
    - deeper grounding depth on representative Nat hard packets
    - disciplined competing-interpretation / claim-boundary graph surface
    - stronger promotion / abstain / audit gates
  - worker split:
    - `Ramanujan`: text bridge
    - `Erdos`: legal doctrinal primitives
    - `Euler`: domain-agnostic primitive architecture
    - `Lorentz`: Nat grounding depth
    - `Ohm`: graph discipline
    - `Huygens`: governance gates
  - returned-brief read:
    - `Ramanujan` is ready first on one pinned climate pilot family with
      additive bridge fields only and explicit abstain outside the bounded
      temporal / multi-value pattern
    - `Erdos` should start as a bounded doctrinal projection/review layer over
      AU procedural-meaning cases, not as a semantic-core rewrite
    - `Euler` should keep the common layer tiny: one typed primitive plus one
      bounded comparison surface, with lane-local decisions kept above it
    - `Lorentz` should deepen grounded hard-packet evidence without widening
      packet shape
    - `Ohm` should stay overlay-only and off by default
    - `Huygens` should formalize `promote | abstain | audit` without hardcoding
      Nat-only thresholds into the general abstraction
  - confirmed promotion order:
    - `Ramanujan`
    - `Erdos`
    - `Euler`
    - `Lorentz`
    - `Ohm`
    - `Huygens`
  - immediate execution checkpoint:
    - promote `Ramanujan` next on the pinned additive climate text-bridge
      slice
    - hold the remaining lanes in ranked order unless the first slice exposes
      hidden coupling or a better bounded promotion
    - rechecked orchestration state is unchanged: same lane ownership, same
      promotion order, no new selection round needed before implementation
  - keep explicit:
    - text stays grounded evidence until promoted
    - legal sources remain truth anchors in legal lanes
    - graph work must not silently turn chronology into causality
    - stronger judgment layers must stay fail-closed and auditable
- [x] Land a shared SQLite runtime substrate for repo-relative path resolution
  and connection plumbing; first adopters are the wiki-timeline query runtime
  and fact-review query surface.
- [x] Land a shared provenance / receipt geometry substrate for receipt rows
  and packet headers; first adopters are narrative comparison and handoff
  artifact shaping.
- [x] Land a shared reviewer-packet geometry substrate for queue-item
  normalization; first adopter is the fact-intake control plane.
- [x] Land a shared repo/runtime root helper substrate at
  `src/storage/repo_roots.py` with first adopters in
  `scripts/report_wiki_random_timeline_readiness.py`,
  `scripts/report_wiki_random_article_ingest_coverage.py`, and
  `scripts/run_fact_semantic_benchmark_matrix.py`. Contract note:
  `../docs/planning/repo_runtime_helper_substrate_20260401.md`.
- [x] Collapse the duplicate repo bootstrap helper into the same canonical
  root substrate:
  `src/storage/repo_roots.py` now also owns the remaining script-file-based
  root-resolution helpers, `src/storage/repo_runtime.py` is removed, and the
  remaining adopter scripts now import the canonical root module directly.
  Contract note: `../docs/planning/repo_roots_runtime_collapse_20260402.md`.
- [x] Extend the canonical repo-root substrate through the tested structural
  script family:
  `scripts/build_wikidata_structural_handoff.py`,
  `scripts/build_wikidata_structural_review.py`,
  `scripts/build_wikidata_dense_structural_review.py`, and
  `scripts/build_gwb_broader_corpus_checkpoint.py` now source repo and
  `SensibLaw` roots from `src/storage/repo_roots.py` rather than recomputing
  them locally. Contract note:
  `../docs/planning/repo_roots_structural_script_adoption_20260402.md`.
- [ ] If external Wikimedia funding becomes operationally relevant for the
  Wikidata lane, keep a small maintained funding/watchlist note sourced from
  official online grant pages rather than treating "active Wikidata grants" as
  an implicit stable repo-local list. Current framing/spec note:
  `docs/planning/wikimedia_grant_framing_20260326.md`.

## Semantic / artifact boundary
- [x] Add a canonical persisted receiver for affidavit coverage / contested
  narrative review in `itir.sqlite`, while keeping the JSON/markdown artifact
  as a derived projection/export surface.
- [ ] Update UI/runtime surfaces that still read affidavit review artifacts
  directly so they prefer the persisted contested-review receiver when it is
  available.
- [ ] Add duplicate-root and side-local leaf reconciliation to the affidavit lane
  so contested comparison rows can cluster materially duplicate John-side and
  Johl-side claims under one shared root without flattening side-local wording.
  First target:
  use the live Johl affidavit / response pair to stop same-incident sibling
  leaves cross-swapping into the wrong support or dispute row. Contract notes:
  `../docs/planning/affidavit_claim_reconciliation_contract_20260329.md` and
  `../docs/planning/affidavit_coverage_review_lane_20260325.md`.
- [x] Normalize duplicated affidavit reconciliation-text helpers into a shared
  Python module instead of leaving tokenization / duplicate-heading grouping
  logic inside wrapper scripts such as
  `scripts/build_google_docs_contested_narrative_review.py`.
  First bounded slice:
  extract duplicate-filter tokenization, enumeration stripping, similarity,
  duplicate affidavit-unit detection, and contested-response grouping behind a
  reusable helper with focused regression coverage.
  - DONE:
    `src/policy/affidavit_reconciliation_text.py` now owns that first helper
    seam, and `tests/test_affidavit_reconciliation_text.py` plus
    `tests/test_google_docs_contested_narrative_review.py` pin the behavior.
  - next:
    DONE:
    `src/policy/affidavit_text_normalization.py` now owns token filtering,
    predicate-focus filtering, rebuttal-start detection, clause splitting, and
    affidavit proposition decomposition, with focused coverage in
    `tests/test_affidavit_text_normalization.py`.
  - next:
    DONE:
    `src/policy/affidavit_claim_root.py` now owns duplicate-response excerpt
    detection and claim-root field derivation, with focused coverage in
    `tests/test_affidavit_claim_root.py`.
  - next:
    DONE:
    `src/policy/affidavit_candidate_alignment.py` now owns predicate
    alignment, quote-rebuttal support detection, and family-alignment
    adjustment policy, with focused coverage in
    `tests/test_affidavit_candidate_alignment.py`.
  - next:
    DONE:
    `src/policy/affidavit_candidate_arbitration.py` now owns sibling-leaf
    arbitration, duplicate-root alternate promotion, and final winner and
    tie-break policy, with focused coverage in
    `tests/test_affidavit_candidate_arbitration.py`.
  - next:
    DONE:
    `src/policy/affidavit_response_semantics.py` now owns response packet
    shaping, target-component selection, semantic basis, claim-state,
    missing-dimension, and relation-classification policy, with focused
    coverage in `tests/test_affidavit_response_semantics.py`.
  - next:
    DONE:
    `src/policy/affidavit_structural_sentence.py` now owns parser-facing
    structural sentence analysis and fallback behavior, with focused coverage
    in `tests/test_affidavit_structural_sentence.py`.
  - next:
    DONE:
    `src/policy/affidavit_lexical_heuristics.py` now owns lexical cue
    inventory, grouped heuristic matching, and justification packet shaping,
    with focused coverage in `tests/test_affidavit_lexical_heuristics.py`.
  - next:
    DONE:
    `src/policy/affidavit_extraction_hints.py` now owns extraction-hint
    derivation, candidate-anchor shaping, provisional-anchor ranking and
    bundling, and hint-aware workload recommendations, with focused coverage
    in `tests/test_affidavit_extraction_hints.py`.
  Outcome:
  the planned normalization ladder from reconciliation text through extraction
  hints is now landed; the remaining open affidavit work is parity/outcome
  quality, not this helper-extraction umbrella.
- [x] Extend `src/ingestion/citation_follow.py` so the implemented bounded
  resolver matches the documented authority order (`already-ingested/local ->
  JADE exact MNC -> AustLII explicit/deterministic case URL -> AustLII search
  -> unresolved`). The bounded resolver now uses strict SINO exact-citation
  matching as the final fallback and abstains when no exact match is found.
- [x] Add a direct AustLII authority CLI seam for known case citations/URLs so
  known-authority retrieval does not depend on SINO when discovery is not
  needed.
- [x] Add an explicit persisted bounded-part authority receiver for AU/HCA
  operator-selected authorities. `sensiblaw austlii-search --db-path ...` and
  `sensiblaw jade-fetch --db-path ...` now persist whole-fetch provenance plus
  bounded selected paragraph segments into `itir.sqlite`.
- [x] Add a bounded persisted-authority receipt consumption path into normal AU
  semantic/fact-review runtime. `build_au_semantic_report(...)` and
  `scripts/au_fact_review.py` now reuse persisted `authority_ingest`
  receipts as semantic context by default without performing live authority
  follow, with `--no-authority-receipts` available for minimal runs.
- [x] Make the citation-driven authority follow/ingest expectation explicit as
  a user story in `docs/user_stories.md`, including the current boundary that
  source-pack/HCA/operator lanes can follow/ingest bounded authorities while
  normal AU semantic runtime does not auto-follow cite-like text by itself.
- [x] Bring JADE up to operator-search parity without breaking the bounded
  source contract:
  `sensiblaw jade-search` now provides a secondary best-effort search -> fetch
  -> local paragraph-inspection lane, while exact `jade-fetch` remains the
  stable known-authority path.
- [x] Keep source-agnostic helpers/tests honest:
  paragraph-window selection now lives in a neutral source helper, mixed CLI
  authority coverage no longer sits in an AustLII-named test file, and the
  JADE live canary has its own test module.
- [x] Make persisted authority-receipt reuse the default AU semantic/fact-review
  context path while keeping live authority follow operator-triggered only.
  Current AU semantic runtime now reuses persisted receipts and their
  lightweight substrate summary by default, but still does not auto-invoke
  live authority follow from parser-seen cite-like text.
- [x] Extend the current AU lightweight authority substrate beyond receipt reuse:
  stronger authority-term extraction and clearer conjecture-routing are now
  present, including neutral-citation extraction, authority-term tokens, typed
  follow-needed conjectures, and explicit route targets. AU fact-review now
  exposes this queue in `operator_views.authority_follow`.
- [x] Add a first cross-source follow/review control-plane contract:
  `follow.control.v1` now exists in `src/fact_intake/control_plane.py` and is
  used by AU `authority_follow` plus generic fact-review `intake_triage` and
  `contested_items`, so parity starts at the operator/control-plane layer.
- [ ] Promote the shared follow/review control-plane beyond the current first
  users:
  next targets should be transcript/message follow-needed queues, affidavit
  source-review queues, and other bounded operator surfaces that already carry
  real unresolved work but still require lane-specific UI logic.
- [ ] If external Wikimedia funding becomes active, sample 2-3 funded and 2-3
  rejected Wikimedia proposal pages and compare the final wording against the
  current bounded Rapid Fund surfaces:
  `docs/planning/wikimedia_rapid_fund_draft_20260326.md` and
  `docs/planning/wikimedia_bounded_demo_spec_20260326.md`.
- [ ] If Wikimedia proposal work becomes active, translate
  `docs/planning/wikimedia_rapid_fund_draft_20260326.md` into the actual
  Wikimedia Meta/Fluxx field structure, preserving its documented evaluation
  metrics, acceptance criteria, and reviewer-facing bounded demo scope.
- [ ] If Wikimedia proposal work becomes active, confirm the named people used
  for the already-chosen reviewer route:
  preferred `1-2` Wikidata/ontology-adjacent reviewers, fallback `1-2`
  technically adjacent reviewers.
- [ ] If the attributed entity-kind appendix is kept in the submission pack,
  lock the exact revision-locked article snapshots used for that appendix
  before submission.
- [ ] Before any Wikimedia submission, run one attribution pass over the
  bounded demo pack so each foregrounded case is classified as:
  repo-built surface, attributed example, or method-lineage credit. Current
  matrix:
  `docs/planning/wikimedia_demo_attribution_matrix_20260326.md`.
- [ ] Before any Wikimedia submission, run one final wording pass against
  `docs/planning/wikimedia_prior_work_and_originality_note_20260326.md` so no
  sentence implies reproduction, parity, or first discovery beyond what the
  repo docs actually support.
- [ ] Only after the normalized metric block is stable, extract shared
  ranking/workload primitives and a shared review-core layer from the current
  AU/Wikidata/GWB adapter-local builders.
- [ ] Add one packaging/UX note that distinguishes private-user surfaces from
  institutional reporting surfaces so future Mirror/commercial drafts do not
  silently default to institution-only language or overstate authoritative
  outputs for personal users.
- [ ] Extend the implemented private-user day-to-escalation lane beyond the
  first bounded
  CLI/artifact contract in
  `docs/planning/personal_handoff_bundle_contract_20260326.md`:
  add richer live/export-backed chat/day ingest adapters plus stronger
  selective redaction/scoped export for legal, clinical, advocacy, or
  regulatory handoff beyond the current bounded JSON, repo-local sample-DB,
  direct Messenger-export, anonymous Google public-source, and first
  OpenRecall-backed adapters.
- [ ] Extend the first metadata-only protected-disclosure envelope mode:
  add whistleblower-specific live intake/import adapters and dedicated
  workflow/UI surfaces beyond the current metadata-only contract, which now
  includes recipient allowlisting, disclosure-route gating, and identity-
  minimization controls.
- [ ] Publish an explicit provenance-only integrator contract:
  SDK/API-oriented JSON/export contract docs and at least one fixture-backed
  consumer path, rather than relying on implicit review-artifact stability.
- [ ] Extend the contested-narrative response packet beyond sentence-role heuristics:
  add proposition-component decomposition for actor/action/object/time plus
  scoped response binding for denial, admission, qualification, consent,
  authority, necessity, and characterization dispute on top of
  `docs/planning/contested_narrative_response_packet_contract_20260326.md`.
- [ ] Add a community/disability support intake surface:
  bounded intake schema plus role-scoped export/view contracts above the
  current generic bundle/summary artifacts.
- [ ] Add an annotation/QA workbench layer over the existing review queues:
  abstain/inter-rater handling, disagreement visibility, and deterministic
  export semantics.
- [ ] Add a field inspection/offline-capture lane:
  photo/checklist capture, sync-gap metadata, and regulator/insurer export
  fixtures.
- [ ] Add a research/publication adapter lane:
  lab-note/research import plus publication-safe export with exclusions and
  provenance preserved.

## Medium-Term Targets
- [x] Adopt `sensiblaw.interfaces.shared_reducer` as the explicit supported
  cross-product reducer surface and move SB/TiRC/ITIR consumers onto it
  instead of relying on internal `src.text.*` imports or opaque fixture-only
  boundary assumptions.
- [ ] Track the resolved thread `QG Unification Proofs`
  (`69c27a0a-ed74-839c-8a57-3c184c28f88e` / canonical
  `f20d9304aae805879a1f934b71443bd2c80ac19b`) as a cross-project formalization
  boundary reference:
  - preserve the proposed `DA51 (empirical) → SL (canonical structure) → Agda (formal proof)` contract shape
  - if later phase semantics are formalized on the Agda side, keep the current
    reading explicit: `CLOCK ≅ Z/6`, `DASHI ≅ Z/3`, cyclic lift rather than
    dihedral symmetry, and admissibility still governed by cone / contraction /
    MDL rather than phase labels alone
  - preserve the `DA51Trace` fields (`da51`, `exponents`, `hot`, `cold`, `mass`, `steps`, `basin`, `j_fixed`)
  - note that this remains non-authoritative and private until JMD confirms any
    additional mapping context; do not publish private mapping details.
  - implement minimal prototype and adapter stubs in `src/qg_unification.py`.
- [x] Move to phase-1 adapter wiring once external adapter approvals are explicit:
  first DA51-like staged input -> `TraceVector` -> typed dependency envelope.
  - Added stage-2 staged artifact bridge output in
    `SensibLaw/scripts/qg_unification_stage2_bridge.py` (persisting run-id
    keyed artifacts).
  - Added deterministic fixture payloads for replayable boundary checks:
    - `SensibLaw/tests/fixtures/qg_unification/da51_valid_demo.json`
    - `SensibLaw/tests/fixtures/qg_unification/da51_invalid_short_exponents.json`
  - Added fixture-backed smoke/stage-2 runners so the same payload can be
    replayed through stage-1 and stage-2 paths.
  - Verified fixture-backed stage-2 output end-to-end:
    - artifact JSON emitted in caller-selected `--out-dir`
    - `qg_unification_runs` row persisted when `--db-path` is supplied
- [x] Add cross-product adapter consumers one path at a time:
  - added a first-path read-model adapter to persist staged QG runs into an
    ITIR-facing DB table:
    - `SensibLaw/scripts/qg_unification_to_itir_db.py`
    - `--bridge-db` + `--run-id` + `--itir-db` + `--dry-run`
    - data lands in `qg_unification_runs` using deterministic upsert semantics
  - added TiRC transcript/capture adapter sink:
    - `SensibLaw/scripts/qg_unification_to_tirc_capture_db.py`
    - creates transcript-like session/utterance rows in destination DB
    - deterministic run-id mapped records in `qg_tirc_capture_runs`,
      `qg_tirc_capture_sessions`, and `qg_tirc_capture_utterances`
  - next path: ITIR-facing UI/report producers needing canonical refs.
- [ ] Bridge the new random-page general-text timeline readiness harness into
  the canonical fact-intake observation/event seam. The current harness should
  prove `snapshot -> timeline candidates -> AAO events`; the next step is a
  deterministic sender from that output into Mary-parity observation/event
  storage rather than stopping at readiness scoring.
- [ ] Keep the adapter thin and SL-owned:
  no competing canonical identity store, no semantic authority transfer, and
  no local fallback path silently promoted to canonical.
- [ ] Add jurisdiction-aware GWB action review as a test target: be able to assess George W. Bush timeline actions under pinned U.S. law and Australian law, with U.S. law first.
- [x] Build a reviewed U.S.-law seed set for GWB covering relevant actions,
  proceedings, and court/hearing material so specific events can be pinned to
  authoritative legal sources before broader cross-jurisdiction comparison.
  Current seed is expanded beyond the original starter pack and checked in at
  `SensibLaw/data/ontology/gwb_us_law_linkage_seed_v1.json`.
- [x] Move the reviewed GWB U.S.-law linkage seed into a shared import/query
  path. Shared DB tables, deterministic import/run/report tooling, and receipt
  storage now exist; current plan/status is documented in
  `docs/planning/gwb_us_law_linkage_seed_20260307.md`.
- [x] Tighten the GWB U.S.-law linkage matcher so broad cues like `Congress`,
  `Iraq`, `veto`, and `Supreme Court` need stronger co-signals before low-score
  matches are promoted, while keeping ambiguous candidates visible in receipts.
  This is a promotion-threshold task, not a ban on broad mention extraction.
  Broad-cue-only cases may now remain visible as low-confidence matched/candidate
  output when they win unambiguously, but they no longer inflate medium/high
  confidence without stronger non-broad receipts.
- [x] Add a first deterministic GWB semantic layer on top of the reviewed
  U.S.-law linkage lane: unified entity spine, office-holding rows,
  mention-resolution artifacts, event roles, relation candidates, and promoted
  edge-first semantic relations. Current status is documented in
  `../docs/planning/gwb_semantic_phase_v1_20260307.md`.
- [x] Freeze the GWB semantic storage shape around the unified entity spine,
  actor/office split, mention-resolution artifacts, and edge-first
  `relation_candidate` -> `semantic_relation` progression before widening the
  predicate set further.
- [x] Extend the GWB semantic layer beyond the initial promoted predicates
  (`nominated`, `confirmed_by`, `signed`, `vetoed`) into stronger review and
  litigation relation coverage without collapsing noisy cue-only events into
  canonical relations. Current deterministic coverage now includes
  `ruled_by`, `challenged_in`, and `subject_of_review_by`.
- [ ] Keep the semantic v1.1 spine frozen while pressure-testing it against GWB:
  unified `entity`, first-class `mention_resolution`, `event_role ->
  relation_candidate -> semantic_relation`, and receipt-derived confidence
  should be exercised before adding more special cases.
- [ ] Migrate the current bounded GWB/AU/transcript predicate heuristics toward
  the shared slot/rule/promotion metadata substrate documented in
  `docs/planning/semantic_rule_slots_and_promotion_gates_20260308.md`.
  Shared rule/slot/promotion metadata now exists, promotion is policy-backed,
  and rule-family receipts should now be present on emitted candidates; the
  remaining work is tightening confidence derivation against shared policy
  minima/evidence requirements and only then deciding whether selector
  execution should move beyond profile-local code. Keep any such migration
  incremental and without breaking the event-scoped semantic spine.
- [ ] Revisit the shared selector-interpreter question only after the new
  policy-backed promotion path and rule-family receipts have been pressure-
  tested across GWB/AU/transcript corpora. Current decision is explicit defer:
  selectors remain shared metadata, execution remains profile-local.
- [ ] Keep `Bush administration` and similar discourse/political labels
  non-canonical by default until a reviewed concept/administration entity layer
  exists. Do not silently merge them into person or office actors.
- [ ] Keep title-only ambiguous mentions such as `the President` and `the
  court` abstained until office/forum context is strong enough to resolve them
  deterministically.
- [x] Add the three small deterministic SL -> SB boundary integration tests
  that likely close most current reducer-boundary risk:
  segmentation preservation, canonical ID preservation, and no summary
  injection.
- [ ] Keep SB/TiRC workflow wording explicit: SB only uses/extends SL-owned
  lexer/compression outputs and must not drift into legal-semantic authority.
  Legal-labelled fixtures at the SB boundary should be treated as opaque
  SL-origin canonical payloads only.
- [x] Align SB and SL docs on the same boundary statement: SB is a personal
  state compiler feeding TiRC/ITIR and may use/extend SL-owned
  lexer/compression outputs without acquiring semantic authority.
- [ ] Use the Australian corpus fixtures (`Mabo`, `House v The King`,
  `Plaintiff S157`, `Native Title (NSW) Act 1994`) as the required semantic
  cross-test source for the frozen v1.1 entity/role/relation shape before
  widening it.
- [x] Start a bounded freeform/transcript semantic proving lane after the AU
  legal fixtures to pressure-test the same frozen
  `entity -> mention_resolution -> event_role -> relation_candidate ->
  semantic_relation` shape against noisier text. Keep extraction broad where
  useful, but keep promotion and speaker/actor resolution conservative and
  abstention-friendly. Current v1 persists speaker/mention/event-role artifacts
  plus candidate-only `replied_to` relations; see
  `../docs/planning/transcript_semantic_phase_v1_20260308.md`.
- [x] Extend the transcript/freeform semantic lane beyond the first
  speaker/event-role proving pass so it becomes the profile-neutral SL
  baseline for human text: broad source-local freeform entity extraction now
  exists, explicit non-legal affect/state cues can emit candidate-only
  `felt_state` relations, and legal semantics remain gated to explicit
  AU/GWB/legal entrypoints.
- [x] Tighten the generalized transcript/freeform entity heuristics so obvious
  non-entity titlecase tokens stay abstained without sliding back into
  legal-by-default behavior or shrinking broad human-text coverage. Current
  bounded gates keep contextual single-token person/place surfaces such as
  `Picasso` / `Brisbane`, while dropping obvious titlecase noise such as
  `Thanks`, `Today`, and role/system labels from general entity extraction.
- [ ] Add stronger general non-legal participant/context roles to the
  transcript/freeform lane (beyond `speaker`, `subject`, `mentioned_entity`,
  `theme`) and pressure-test them against journal/transcript corpora before
  promoting any new relation family. Align this with the existing
  actor/event-role contracts already used elsewhere in the repo rather than
  introducing a transcript-only ad hoc role taxonomy. Archive-backed summary:
  `../docs/planning/archive_actor_semantic_threads_20260308.md`.
- [x] Add the first bounded explicit social-relation slice to the
  transcript/freeform lane without widening into open-world social inference.
  Current deterministic v1 covers named explicit kinship/friendship statements
  plus explicit guardian/care surfaces only (`sibling_of`, `parent_of`,
  `child_of`, `spouse_of`, `friend_of`, `guardian_of`, `caregiver_of`), keeps
  them candidate-only, and may attach `related_person` event-role context
  where the paired actor is explicit in the same text span.
- [x] Normalize transcript/freeform care relation naming so canonical
  predicates stay relation-style and tense-neutral. Current choice is
  `caregiver_of`; observed surfaces such as `cared for` / `cares for` remain
  in receipts only.
- [x] Add a compact transcript semantic summary artifact focused on relation
  review. The bounded summary now reports candidate/promoted counts by
  predicate, cue-surface counts, and an explicit note when all social/care
  predicates remain candidate-only.
- [x] Move semantic workbench `text_debug` payload shaping out of
  `itir-svelte` and into Python report producers. Current report builders now
  own tokenization, anchor provenance, relation-family metadata, and
  confidence-derived display opacity for transcript/GWB/AU semantic workbench
  rendering.
- [x] Add a shared producer-owned `review_summary` artifact to GWB/AU/transcript
  semantic reports so predicate counts, cue-surface counts, and `text_debug`
  coverage/exclusion totals are comparable across corpora without inspecting
  raw report JSON.
- [x] Extend producer-owned `text_debug` anchors with `charStart`, `charEnd`,
  and `sourceArtifactId` so the next graph/document linking step has a real
  shared span contract instead of token-only render helpers.
- [x] Use the producer-owned `text_debug` span contract in the semantic report
  workbench for event-local cross-highlighting. Current v1 keeps the separate
  source-document slot explicit about unavailable source text rather than
  inventing a fake full-document surface.
- [x] Extend transcript/freeform reports with grouped source-document payloads
  and source-level event spans so the semantic workbench can cross-highlight
  into a real source-text view without re-deriving offsets in TS.
- [x] Emit grouped timeline-source payloads and source-level event spans for
  GWB/AU from the normalized wiki timeline store so the semantic workbench
  source-document viewer stops being transcript-only.
- [x] Add an append-only semantic review-feedback seam for the workbench.
  Current `/graphs/semantic-report` submissions now persist append-only DB
  review rows keyed by source/run/event/relation/anchor refs instead of
  rewriting semantic tables in place.
- [x] Add a bounded transcript/freeform `mission_observer` artifact for SB-safe
  mission/follow-up overlays. Current v1 is deterministic and local:
  explicit task/follow-up cues, source-local referent backtracking, deadline
  carry-forward when grounded, and abstention on unresolved follow-ups.
- [x] Move semantic review submissions out of local JSONL and into append-only
  `itir.sqlite` tables (`semantic_review_submissions` +
  `semantic_review_evidence_refs`) so the workbench review seam is DB-first.
- [ ] Pressure-test the transcript/freeform `mission_observer` lane against
  more chat/message corpora before widening cue coverage or letting SB derive
  stronger reductions from it.
- [x] Add a bounded public-media narrative corpus fixture for transcript/media
  validation, using FriendlyJordies as the first named public test case. The
  first slice now exists as `SensibLaw/demo/narrative/friendlyjordies_demo.json`
  plus the bounded `narrative_compare.py` producer and comparison workbench.
- [ ] Add a narrative-validation review mode for transcript/media corpora:
  internal consistency checks, source-local proposition extraction, explicit
  external corroboration/support/conflict refs, and abstention when the source
  remains unresolved.
- [x] Add a competing-narratives comparison read model for SensibLaw so two
  source narratives can be compared by shared facts/propositions,
  source-specific propositions, disagreement markers, predicate/flow
  differences, and explicit receipts rather than silent merging. Current first
  slice is a bounded fixture-first producer/workbench pair, not the later
  ingress-backed review mode.
- [x] Persist the transcript/freeform `mission_observer` artifact canonically
  in normalized `itir.sqlite` mission tables before exporting/reviewing it as a
  report payload. Current storage is `mission_runs`, `mission_nodes`,
  `mission_edges`, `mission_evidence_refs`, `mission_observer_overlays`, and
  `mission_overlay_refs`.
- [x] Add the first fused mission-lens substrate on top of the persisted
  mission observer lane: seed ITIR-owned planning nodes/deadlines from mission
  rows, build an actual-vs-should artifact against SB dashboard data, and
  expose bounded planning authoring without changing SB’s core doctrine.
- [x] Add a reviewed actual-to-mission mapping lane on top of the fused mission
  lens so concrete SB activity rows can be linked to planning nodes in
  `itir.sqlite` (`mission_actual_mappings`) instead of relying only on lexical
  fallback when drift/accounting is reviewed.
- [ ] Tighten automatic actual-to-mission mapping beyond the current reviewed +
  lexical bridge before treating mission drift as a stronger accounting
  surface.
- [ ] If mission observer is pushed further into SB-facing accounting, keep it
  operational-state only until there is a separate SL-reducer-backed candidate
  and promotion model for observer/mapping truth. Do not let mission-lens
  `status`/recommendation fields collapse into canonical semantic truth by
  drift.
- [ ] Bring the wiki revision monitor lane up to the same functional standard
  as the stronger suite pipelines before prioritizing GUI integration:
  - [x] Add query-first helpers/read models over latest runs, changed
    articles, severities, and contested-graph selection so consumers stop
    depending on script-local query assembly.
  - [x] Add explicit SQLite run-summary and changed-article read-model tables
    so the query lane can prefer normalized SQLite rows over `summary_json`
    blobs for latest-run and changed-article selection.
  - [x] Add explicit SQLite selected issue-packet rows so selected-article
    packet detail can be queried from SQLite instead of pair-report blobs.
  - [x] Add explicit SQLite selected-pair rows so pair kind, severity, score,
    and section-touch summaries can be queried from SQLite instead of
    pair-report blobs.
  - [x] Add explicit SQLite contested-graph event and epistemic rows, and
    assemble selected contested graphs from SQLite-first graph read models
    instead of `graph_json` blobs.
  - [x] Make blob fallback explicit and observable:
    the query lane now emits `summary_source` and `selected_graph_source` so
    operators can verify SQLite read models win over blob columns and
    artifacts when both exist.
  - [x] Audit the remaining legacy blob columns and freeze a deprecation
    matrix:
    `summary_json` and `graph_json` remain bounded backcompat writes, while
    `packet_counts_json`, article/pair `result_json`, `score_json`, and
    `section_delta_json` are now placeholder-only legacy columns pending a
    later schema drop. See
    `../docs/planning/wiki_revision_monitor_blob_deprecation_matrix_20260331.md`.
  - [x] Freeze the versioned schema contraction plan for the remaining blob
    columns in
    `../docs/planning/wiki_revision_monitor_schema_contraction_plan_20260331.md`:
    placeholder-only legacy columns are the v0.4 drop set, while
    `summary_json` and `graph_json` remain v0.5 candidates pending stricter
    consumer audit.
  - [x] Complete the local workspace consumer audit and promote the v0.4
    placeholder-only schema drop for newly created DBs:
    `../docs/planning/wiki_revision_monitor_v0_4_placeholder_blob_drop_20260331.md`
    and `src/wiki_timeline/revision_pack_runner.py` now remove the dropped
    columns from new-table creation while keeping older DBs writable through
    named-column inserts.
  - [x] Add the in-place v0.4 migration for existing revision-monitor DBs:
    `src/wiki_timeline/revision_pack_runner.py` now rebuilds the legacy
    article-result and candidate-pair tables without the placeholder-only
    columns while preserving surviving row data. Contract note:
    `../docs/planning/wiki_revision_monitor_v0_4_in_place_migration_20260331.md`.
  - [x] Promote the v0.5 backcompat blob drop:
    `summary_json` and `graph_json` are now removed from both fresh schema
    creation and old-DB in-place migration, with query fallback simplified to
    SQLite read models plus artifacts only. Contract note:
    `../docs/planning/wiki_revision_monitor_v0_5_backcompat_blob_drop_20260331.md`.
  - [x] Remove JSON artifact fallback from the query lane:
    `src/wiki_timeline/revision_monitor_query.py` is now SQLite-only for runs,
    summaries, and selected graphs. Contract note:
    `../docs/planning/wiki_revision_monitor_sqlite_only_query_20260331.md`.
  - [x] Remove the first redundant runner-side JSON sidecars:
    the runner no longer emits the run-summary JSON sidecar in `runs/` or the
    duplicate `__latest.json` contested-graph alias, while keeping the
    canonical graph artifact path unchanged. Contract note:
    `../docs/planning/wiki_revision_monitor_sidecar_contraction_slice1_20260331.md`.
  - [x] Remove routine JSON report artifacts from the default runner path and
    call timeline/AOO extraction in-process rather than through file-shaped
    subprocess handoff.
  - [x] Move pack triage and run-summary assembly behind one shared Python
    summary owner so `revision_pack_runner.py` stops owning reporting geometry
    inline.
  - [x] Move artifact naming and JSON IO behind one shared Python storage
    owner so `revision_pack_runner.py` keeps orchestration/state policy rather
    than storage mechanics.
  - keep producer-owned report surfaces explicit so other lanes can consume
    revision artifacts without re-deriving monitor logic
  - preserve the dedicated runner/state-DB posture; this is a standards/
    interoperability task, not a demand to fold the lane into `itir-svelte`
  - next:
    finish the post-contraction contract cleanup so dead path-centric residue
    is removed and the docs/runtime surfaces all describe the lane as
    SQLite-canonical rather than still transitional
- [x] Add an OpenRecall observer integration v1 lane:
  - vendored `openrecall/` SQLite captures now import into `itir.sqlite` via a
    bounded append-only importer and normalized capture tables/read models
  - capture provenance (`captured_at`, app/window title, OCR text, source DB
    path, screenshot refs) is preserved and ingest remains observer-class only
  - imported captures now appear as a mission-lens actual-side source kind and
    as source-local text units for semantic/transcript reuse
  - raw OCR/capture rows remain non-authoritative on ingest
- [ ] Follow up on OpenRecall v1:
  - stabilize or bypass the inconsistent vendored live-capture path before
    relying on OpenRecall as a routine upstream source
  - decide whether capture-derived observer overlays should ever cross into SB,
    and only through ITIR-normalized payloads
  - defer GUI-first OpenRecall browsing until the importer/read-model seam is
    proven stable
- [x] Add the first NotebookLM metadata/review parity slice as a neutral
  producer/query/read-model seam instead of treating `notes_meta` as a fake
  activity ledger. Current v1 now exposes NotebookLM observer date/notebook/
  source/artifact summaries plus recent-event queries and source-summary
  `TextUnit` projection for downstream structure/semantic reuse.
- [ ] Keep NotebookLM metadata-first until a separate interaction-grade capture
  contract exists. Do not upgrade `notes_meta` snapshots into waterfall/
  timeline activity parity or stronger mission actual-side accounting without
  explicit NotebookLM ask/chat/note/artifact/session events.
- [x] Implement the first additive NotebookLM interaction lane without claiming
  activity/session parity:
  - raw capture families: `conversation_observed`, `note_observed`
  - separate normalized signal: `notebooklm_activity`
  - bounded query/read-model helpers and JSON CLI
  - source-local preview `TextUnit` projection
  - keep outputs under `runs/<date>/outputs/notebooklm/`; do not fold them
    into `logs/notes` or dashboard waterfall/timeline accounting yet
  - shared runs-root resolution and dated artifact discovery now live in one
    Python loader so observer/activity reporting stops duplicating local file
    lookup policy
- [ ] Decide how much richer NotebookLM interaction capture should get before
  any dashboard or mission-lens activity/session integration:
  - whether conversation-history observations are sufficient, or whether the
    later lane must capture true ask/request/result and note-edit events
  - whether the interaction lane should stay review/query-only until stronger
    timestamps and dedupe semantics exist
- [ ] Widen the bounded proposition-layer v1 beyond current HCA-first
  `... against ...` reasoning idioms and factual scaffolding:
  - cited-authority subgroup handling (`majority in Lepore`, similar)
  - richer proposition-link families beyond current bounded
    `attributes_to` comparison support
  - broader attribution wrappers beyond current bounded
    `said/argued/submitted/reported/held/showed that`
  - proposition-to-proposition links usable by competing-narratives comparison
  Keep canonical storage on `predicate_key + negation/stance + typed arguments`
  rather than operator syntax.
- [ ] Mine the high-signal local archive threads into first-class repo notes so
  actor/role architecture does not stay trapped in chats. Priority threads:
  `Actor table design` (`21f55daa80206517e38f8c0fa56ee9bb2db8a9a0`),
  `Actor Model Feedback` (`691d79376cb653e7170ea6c200a0a1d0a34bec6b`),
  `Milestone Slice Feedback` (`1802fc3d13a0ad01ad95cef07eeaae9c16c22bed`),
  `Taxonomising legal wrongs` (`74f6d0e08de82556df95c6ab1edb51557fede4fa`),
  `SENSIBLAW` (`4d535d3f33f54b1040ab38ec67f8f550a0f69dce`), plus the currently
  untitled high-hit archive threads `dbcfb20d67213216c7aa02ed8493ae21fd39730d`
  and `dff2e608e358fe5ed5cf1d0376a36ff8a87a6f2d`.
- [ ] Decide which archive-derived actor-model pieces should actually re-enter
  the active semantic schema family after the current comparison pass in
  `../docs/planning/actor_semantic_db_design_from_archive_20260308.md`.
  Current explicit gaps versus the broader archive design are:
  persistent alias registry, merge audit, governed event-role vocabulary, and
  actor detail/annotation extension tables.
- [x] Re-introduce the first archive-backed identity-governance pieces without
  replacing the frozen semantic spine: shared `actors`, `actor_aliases`,
  `actor_merges`, and `event_role_vocab` now exist, and actor-like semantic
  entities map onto the shared actor layer via `semantic_entities.shared_actor_id`.
  This keeps alias persistence / merge audit / role governance shared across
  AU, GWB, and transcript lanes while leaving actor detail/profile extensions
  deferred.
- [ ] Decide how aggressively the new shared `actor_aliases` layer should
  participate in deterministic matching. Current recommendation is
  conservative: keep it primarily as persisted registry/audit support plus
  seed-backed reuse, and only widen alias-driven matching if concrete corpus
  pressure shows lane-local matching is missing high-value recoverable actors.
- [ ] Decide whether any transcript/freeform relation family deserves
  medium/high promotion under the frozen semantic spine. Current `replied_to`
  and `felt_state` relations remain candidate-only, and the new explicit
  social-relation predicates (`sibling_of`, `parent_of`, `child_of`,
  `spouse_of`, `friend_of`, `guardian_of`, `caregiver_of`) also remain
  candidate-only.
- [ ] Keep chat-derived corpora isolated from canonical `itir.sqlite` until an
  explicit retention/redaction policy exists for SB/ITIR/TIRC integration.
  Current bounded test path is `.cache_local/itir_chat_test.sqlite` with hashed
  thread IDs only.
- [ ] Keep personal archive–derived test DBs (`itir_chat_test.sqlite`,
  `itir_messenger_test.sqlite`, similar local experiment stores) local-only and
  never promote them into canonical/shared repo artifacts or checked-in DBs.
- [x] Expand isolated chat test reporting beyond `_ref` counts. The current
  report now includes full kind breakdowns, structural-kind counts, top
  structural atoms, and structural-atom dedupe counts in
  `.cache_local/itir_chat_test.sqlite`.
- [x] Add richer structural reporting so chat/context corpora surface:
  top reused atoms, per-kind atom tables, interlinked/co-occurring atoms, and
  bounded example snippets rather than only aggregate counts.
- [x] Add a second deterministic operational/discourse structure lane for
  chat/dialogue, shell/command, and transcript-style patterns without changing
  the legal lexer.
- [ ] Extend the operational/discourse lane beyond the current regex-level v1:
  reduce false positives further, add better shell/session segmentation, and
  expand transcript/hearing-specific markers against real corpus files.
- [x] Add a repo-wide CI/static enforcement pass for semantic promotion:
  covered truth-bearing lanes now have a static policy guard in
  `tests/policy/test_semantic_gate_enforcement.py` that proves canonical
  promotion fields are sourced from the central gate/claim-state path and that
  mission-observer overlays remain outside the truth-bearing family.
- [ ] Improve parser-backed structural basis in already-covered semantic lanes
  before widening new truth-bearing surfaces: reduce `mixed`/`heuristic`
  candidates where dependency/entity structure can support a stronger
  structural basis.
- [ ] Add a deterministic speaker-inference layer for transcript/message corpora
  only when there is reliable extra evidence (known participant set, coalesced
  disagreement structure, or reviewed entropy/disagreement heuristics). Do not
  infer speakers from subtitle-only timing ranges alone.
- [x] Start the deterministic speaker-inference implementation with explicit
  receipts/abstention behavior over current transcript/message units. Current
  v1 supports explicit message headers, role prefixes, cautious `Q:/A:` mapping
  when known participants are supplied, and explicit abstention on timing-only
  subtitle ranges.
- [ ] Extend speaker inference from per-unit receipts to conservative
  multi-turn coalescence with explicit carry-over receipts and no silent
  speaker invention across conflicting evidence. Current implementation only
  covers single-gap `neighbor_consensus` carry-over when the same explicit
  speaker brackets an `insufficient_evidence` unit.
- [x] Write the deterministic speaker-inference v1 design note before
  implementation. See `docs/planning/speaker_inference_v1_20260307.md`.
- [ ] Decide whether Messenger/Facebook archive ingestion should graduate from
  isolated test DBs into a stable connector; current bounded importer is test
  only and still needs stronger system-row filtering policy.
- [ ] Tighten Messenger sender extraction so platform/system text cannot bleed
  into inferred speaker labels such as `speaker:facebookwe_didn_t_remove_the_ad`
  or similar contaminated forms in the speaker-inference report.
- [x] Tighten bounded Messenger/Facebook importer filtering with deterministic
  keep/drop reason categories and per-run filter stats.
- [x] Add a deterministic Messenger test DB report command instead of relying
  on ad hoc Python summaries. `scripts/report_messenger_test_tokenizer_stats.py`
  now reports structure metrics plus kept/dropped filter counts.
- [x] Import a reviewed deterministic bridge slice for the current high-yield
  GWB U.S. bodies/courts in the seeded bridge substrate, including
  `Department of Defense` (`Q11209`) and the Sixth Circuit (`Q250472`).
- [ ] Extend the reviewed deterministic bridge slice further for remaining
  district-court / executive variants once corpus yield justifies the added
  aliases.
- [ ] Add a side-by-side corpus comparison summary artifact for
  chat/context/transcript runs so `--by-source` output is easier to review than
  the raw JSON dump. Initial compact summary is now emitted by
  `report_structure_corpora.py`; next step is polishing it into a more stable
  review artifact.
- [x] Add Messenger test DBs as first-class inputs to the shared structure
  comparison/report path instead of keeping them on an isolated report script
  only.
- [ ] Add a compact speaker-inference summary surface alongside the structure
  reports (assigned vs abstained, confidence tiers, dominant reason codes, top
  inferred speakers) for transcript/chat/message corpora. Initial JSON report
  now exists in `scripts/report_speaker_inference_corpora.py`; next step is a
  tighter review-oriented summary artifact.
- [x] Add a deterministic top-k relation-neighborhood report for
  chat/context/transcript corpora that combines parser-local dependency /
  co-occurrence evidence with reviewed bridge/Wikidata matches where a pinned
  slice exists. Implemented in
  `scripts/report_relation_neighborhoods.py`.
- [x] Fix `scripts/migrate_wiki_timeline_to_itir_db.py` import-path/runtime
  assumptions so the eager rewrite/backfill command works directly against the
  shared root DB.
- [x] Drive canonical wiki-timeline residual JSON toward zero for route/report
  critical storage. Event/step/object/list tails now persist through typed
  path/value tables and the refreshed GWB storage report shows `0` residual
  blob bytes.
- [ ] Do not chase "lossless reconstruction" of unused legacy JSON export
  shapes as a storage goal. Only normalize/preserve fields that matter for
  route parity, queryability, reporting, or audit semantics; explicitly delete
  or ignore dead tails instead of carrying them forward as canonical DB blobs.
- [x] Normalize canonical structural atoms for DB dedupe, starting with the
  high-yield legal kinds (`case_ref`, `section_ref`, `act_ref`, `paragraph_ref`)
  and then layering in `institution_ref` / `court_ref` where useful.
  `VersionedStore` dictionary tables and root wiki-timeline DB atom tables now
  persist the high-yield structural kinds; `article_ref` and `instrument_ref`
  are now included as well.
- [x] Align main SB and SL docs so the lexer/compression boundary is explicit:
  SB is a personal state compiler feeding TiRC/ITIR and may use/extend SL
  lexer/compression outputs without inheriting semantic/legal authority.
- [x] Add Australian semantic seed/report lane on the frozen semantic v1.1
  spine using:
  - Mabo [No 2]
  - Plaintiff S157/2002 v Commonwealth
  - House v The King
  - Native Title (New South Wales) Act 1994
- [x] Extend Australian semantic actor extraction beyond the first
  document-local participant patterns into deterministic legal-representative
  and office lanes.
- [x] Broaden Australian relation candidate coverage for review/litigation and
  doctrinal reasoning while keeping promotion conservative.
- [x] Tighten Australian legal-representative extraction beyond the first
  `SC/KC/QC` and `counsel for ...` deterministic surfaces. Current AU lane now
  uses a versioned lexical cue catalog with clause-local named-representative
  gating instead of creating synthetic role-label actors from cue text alone.
- [ ] Promote the AU legal-representation cue catalog from versioned repo data
  into a shared DB-backed lexical-rule substrate only if multiple
  jurisdictions/extractors need the same runtime shape. Do not widen semantic
  schema or ontology tables for cue storage.
