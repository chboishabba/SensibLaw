# Source-backed property-proposal governance and real Wikidata consumer replay

Date: 2026-11-01
Status: **implemented candidate source capture and review overlay; external witness/adjudication still required**.

## Original authorship and actual primary material

Marcin Roszkowski, *Navigating change: an exploration of socio-epistemic process of extending Wikidata ontology with new properties*, **Journal of Documentation** 80(6), 1291–1312 (2024), DOI [10.1108/JD-01-2024-0008](https://doi.org/10.1108/JD-01-2024-0008). His initiation → collaborative knowledge-work → closure analysis motivates this workflow. It is **not** the source or author of our code, the local proof, or a decision that any particular proposal was compliant.

Primary Wikidata source and attribution:
- [Archived proposal at original oldid=1572799769](https://www.wikidata.org/w/index.php?title=Wikidata:Property_proposal/time_in_the_pouch&oldid=1572799769), last rendered revision 4 February 2022 at 13:07 UTC; authored by several Wikidata contributors.
- [P10322 live property](https://www.wikidata.org/wiki/Property:P10322) links the original proposal and example values; a 2026 property snapshot is **not** the original 2022 property state.
- [Wikidata property-proposal February 2022 archive](https://www.wikidata.org/wiki/Wikidata:Property_proposal/Archive/2022/02) records Arbnos as proposer, 28 January to 4 February and P10322 as the output.
- [Property creation policy](https://www.wikidata.org/wiki/Wikidata:Property_creation) is a **versioned** normative document. The present-day page is not evidence that its exact conditions, role criteria and exceptions already applied in February 2022. The historical revision has **not yet been fetched and checked** in this PR.

Historical observation details now pinned in `tests/fixtures/wikidata/p10322_history_primary_20220204.json` (derived from the **archived page**, not synthetic):
- Arbnos proposes on **28 Jan 2022, 12:41 UTC**.
- UWashPrincipalCataloger queries the generic kangaroo example at **18:36**; this is a critical comment, **not** necessarily a vote to oppose.
- Arbnos answers with an uncertainty-marked example amendment at **22:12**.
- UWashPrincipalCataloger supports aliases at **29 Jan 02:26**.
- Germartin1 supports at **29 Jan 03:35**.
- Gymnicus supports at **31 Jan 16:01**.
- Jura marks **Done as P10322** at **4 Feb 13:07 UTC**.
- The *rendered minute* is known; **the exact second of page-revision creation is not assumed**. The archive page is additionally pinned by its real oldid.
- Raw wikitext byte hashes, source acceptance/reopen, the **then-effective** policy revision, Jura's actor-rights receipt at decision time and an independent community-consensus adjudication remain *unverified*. `minimum_age_seconds=604800` is a candidate one-week criterion, not an already-verified historical rule.

## Concrete read-only source acquisition (reuse existing owner)

Do not add a new scraper or commit an unbounded wiki dump. `scripts/wiki_pull_api.py` already owns MediaWiki revision pulling; this PR extends it with `wikidata` and `--at-or-before`, checks precise requested oldids and titles, and rejects missing wikitext. Only this curation-time maintenance script writes gitignored local snapshots; the product API remains `python -m src.cli`.

```sh
# From the SensibLaw checkout; outputs only to .cache_local/
python scripts/wiki_pull_api.py --wiki wikidata --driver api \
  --title 'Wikidata:Property proposal/time in the pouch' \
  --revid 1572799769 --out-dir .cache_local/wiki_snapshots

# Historical policy: independently inspect both the proposal-time and
# closure-time versions. The API selects the last revision no later than
# each supplied UTC instant. Do not silently reuse today's rules.
python scripts/wiki_pull_api.py --wiki wikidata --driver api \
  --title 'Wikidata:Property creation' \
  --at-or-before '2022-01-28T12:40:00Z' --out-dir .cache_local/wiki_snapshots
python scripts/wiki_pull_api.py --wiki wikidata --driver api \
  --title 'Wikidata:Property creation' \
  --at-or-before '2022-02-04T13:06:59Z' --out-dir .cache_local/wiki_snapshots
```

Operator acceptance:
1. Inspect exact `pageid`, returned `revid`, UTC `rev_timestamp`, original `wikitext` and `warnings` for all snapshots. Reject page moves, deleted revisions, ambiguous source signatures and unexpected content.
2. Supply the pinned proposal snapshot plus JSON observation manifest to `project_historical_source_anchors(snapshot, case)`, an optional **pure projection on the existing signal bundle**. It derives one exact original wikitext byte interval and SHA-256 per observed event, plus full text digest, not a fabricated proof of actor roles.
3. Review evidence for the historical policy text, contributor roles, authentic property creation log and objections. Do **not** use the fact that a page is marked Done as a substitute for all of these.
4. The existing SLR `persist_generic_text_source` must ingest the original **same canonical wikitext** at its independently named `SourceIngestEnvelope` before SLR #76 can create a durable deliberation sidecar. The original source bytes and acquisition receipt must reopen at exact revisions. The raw per-event text spans are a candidate claim; SLR checks the hashes again.
5. Admit the real event/policy packet only after the then-effective historical source is pinned; unverified actor/time/consensus rules remain separate typed holds.
6. Repeat under existing S30 consumer/knowledge-cut scope and do not broadcast a private matter packet merely because the Wikidata proposal is public.

## Existing concrete Wikidata consumer integration

`src/ontology/wikidata_signal_review_bundle.py:attach_deliberation_context` is a **pure, opt-in overlay on the existing generic bundle builder**, not a new semantic compiler or selector. It checks actual bundle `candidate_properties[].pid` **and** `dependency_cone.focus_pids` for an exact `P[1-9][0-9]*` match to the *created property* claimed by a validated candidate ITIR deliberation assessment. A bare proposal ref, source ID, score, hotspot family or abstract repair obligation is not a PID match.

On an explicit matching property, it exposes a **candidate-only navigation edge** while keeping exactly the original bundle's `residuals`, `receipts`, `candidate_properties`, original A–E dispositions, `promotion_status` and structural pressure. No source-correlation `source_alignment_ref` is called verified merely because a caller supplied it. The original `source_revision_refs` field sometimes contains packet IDs rather than literal wiki revisions; this is not a valid basis for silently declaring the proposal and consumer source to be the same.

The join is real on **five existing lane-built reports**:
- Nat climate `P5991 → P14143` climate-review-demonstrator: original migration/split gate retained;
- `ChangeReviewPacket` candidate-repair report: original class/statement/pressure and QID obligations retained;
- Ege/Peter bounded `P2738/P11260` disjointness report: same extracted pairs, instance/subclass violations and culprit pressure retained;
- Rosario-style hotspot evaluation: original benchmark/scorer and cluster pathologies retained;
- live-follow preflight: source-revision coverage and blockers retained.

It does not fabricate a link when an unrelated P10322 discussion is overlaid on these P2738/climate/hotspot examples. Run the existing public CLI:

```sh
python -m src.cli wikidata lane-bundle \
  --lane disjointness_report \
  --deliberation-assessment .cache_local/review/p10322_assessment.json \
  --consumer-ref 'consumer:ontology-review' \
  --consumer-scope-ref 'matter:scoped-ontology-review' \
  --source-alignment-ref 'candidate:unverified-external-proposal-link' \
  --output .cache_local/review/review-with-discussion.json
```

The example `p10322_assessment.json` is **an operator-produced input**, not a committed fabricated receipt. The ITIR assessment must first pass its own fail-closed checks. This command generates a sidecar with **no matching PID** on P2738 by design.

## O/R/C/S/L/P/G/F and remaining receipts

O: historical wiki community owns its property governance; SLR native source/S29 review and DASHI Agda exact conditional obligations are the other source owners; SensibLaw projects existing review lanes; ITIR adapts/read-only.

R: source revision must match, signatures unique and exact, policy selected in time, event chronology preserved, ambiguous/contested statements not converted to a support count.

C: original Wiki pull, original generic `sl.wikidata_signal_review_bundle.v0_1`, existing CLI, original SLR PG source and S29 reducer; no new ontology model.

S: `WikiPageSnapshot` carries revid + original wikitext; source byte span hashes are *produced after* fetched exact revision. SLR must ingest/reopen same canonical bytes.

L: original pressure and structure stay independent of the added proposal discussion evidence. Critical comment, support and amendment are distinct.

P: only candidate interpretation is emitted. No external property creation/approval is authorised.

G: exact historic policy, roles, consensus and external creation log require independent evidence, not local inferred truth.

F: tests written for P10322 snapshot anchors, mismatched revision/title/time/duplicate signatures, real five-lane report equality, false authority flags, and end-to-end opt-in PG in companion SLR #76. **Tests not run by this GitHub-only worker.**

Companion PRs: [ITIR-suite #70](https://github.com/chboishabba/ITIR-suite/pull/70), [SLR #76](https://github.com/chboishabba/slr/pull/76), [DASHI Agda #1447](https://github.com/chboishabba/dashi_agda/pull/1447).


## Source-to-native transport now implemented, no manual rekeying required

The original generic bundle owner also exposes `build_historical_source_handoff(proposal_snapshot, policy_snapshot, case, policy_minimum_age_seconds=...)`. It requires two original Wikidata `PageSnapshot` values with real wikitext, the archived proposal oldid and observed revision minute, a separately revision-pinned policy page older than closure, and an explicitly supplied rule-age candidate. It produces **the exact ITIR input shape** under `itir_slr_input`: `deliberation`, `source_seals` and `event_anchors`. Each digest is recomputed from the supplied canonical UTF-8 bytes and every event excerpt is located uniquely; proposed editor timestamps and assigned event kinds remain interpretive *claims* pending human review.

This is available through the existing `src.cli` gateway, not a second CLI:

```sh
python -m src.cli wikidata history-snapshot-handoff \
  --proposal-snapshot .cache_local/wiki_snapshots/ACTUAL_PROPOSAL_FILE.json \
  --policy-snapshot .cache_local/wiki_snapshots/ACTUAL_HISTORICAL_POLICY_FILE.json \
  --case-manifest tests/fixtures/wikidata/p10322_history_primary_20220204.json \
  --policy-minimum-age-seconds 604800 \
  --output .cache_local/review/p10322_source_handoff.json
```

The ALL-CAPS filenames above are placeholders for the **actual files returned** by the existing wiki snapshot pull; they are not claims that such files were created or that an exact historical-policy revision has been fetched. The `604800` value is a **candidate one-week policy interpretation** whose applicability in 2022 remains independently unverified.

The resulting wrapper is consumed by ITIR-suite PR #70's read-only `itir.governance.wikidata_source_replay_handoff`, which delegates to its existing exact `deliberation_slr_handoff` ABI. SLR PR #76 now exposes `persist_deliberation_from_source_inputs`: the original `SourceIngestEnvelope` + canonical text from the **same** captured snapshots is submitted to the existing INGEST-1 writer before S29 sidecar persistence. No HTTP or permission verification is performed by a caller-supplied JSON hash; independent source acquisition/provenance, creator rights and historical consensus remain separately held. The opt-in physical PG regression now invokes this new ingestion-to-review entrypoint.

**End-to-end source-code path:** exact MediaWiki revision fetch → canonical wikitext/source anchors → `src.cli wikidata history-snapshot-handoff` → ITIR read-only native validation → SLR generic source ingest and byte reopen → one atomic S29 + sidecar write → scoped S29 review/reopen → optional existing `sl.wikidata_signal_review_bundle` consumer overlay. Actual live P10322 replay and S30-authorized consumer publication are **not yet executed**.


### Canonical synchronized K00–K13 / A00–A07 status (2026-11-01)

See the [single four-repo max-cut roadmap](https://github.com/chboishabba/ITIR-suite/blob/agent/epistemic-deliberation-candidate-governance-20261101/docs/planning/wikidata_deliberation_maxcut_exact_20261101.md) for each exact owner, source-written code, and remaining primary-source acceptance. The latest canonical source ABI uses SensibLaw's length-framed SHA-256 INGEST-1 source identity, independently reverified by ITIR against original UTF-8 text and byte anchors, and SLR's full typed JSON replay into existing INGEST-1 + atomic S29 review. This is committed source code, not an executed kernel/PG check. Historical P10322 original bytes, applicable policy, creator rights, consensus, actual S30 permission and cross-language formal proof remain independent obligations; no external Wikidata edits are authorised.
