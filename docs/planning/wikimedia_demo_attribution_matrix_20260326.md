# Wikimedia Demo Attribution Matrix

Last updated: 2026-03-26

## Purpose
Record, in one place, how the Wikimedia grant/demo lane should talk about case
origin, method lineage, and repo contribution.

This note exists to prevent the submission from blurring:
- who surfaced a case or paper
- what the repo actually implemented
- what is safe to foreground as a repo contribution

## Rules
- Unless repo docs explicitly support repo-original discovery, do not claim it.
- Distinguish:
  - `method lineage`
  - `case/example attribution`
  - `repo contribution`
- When uncertain, prefer attributed use over ownership claims.

For broader novelty/method-overlap wording, also use:
- `docs/planning/wikimedia_prior_work_and_originality_note_20260326.md`

## Matrix

| Surface | Likely source / lineage | Repo contribution | Grant-safe wording |
| --- | --- | --- | --- |
| `software_entity_kind_collapse_pack_v0` (`GNU` / `GNU Project`) | Attributed reviewed example; not safe to frame as repo-original discovery. User note says GNU was initially found by Rosario. | Page-review integration, bounded fixture pack, benchmark/report framing, reviewer-facing demo packaging. | `GNU / GNU Project` is an attributed reviewed example used to demonstrate entity-kind collapse; the repo contribution is the deterministic review-pack/reporting surface built around it. |
| `finance_entity_kind_collapse_pack_v0` (`financial product` / `financial services` / `product`) | Likely same hotspot/page-review wave as the GNU case and likely Rosario-shaped benchmark framing; not currently safe to frame as repo-original discovery. | Bounded fixture pack, benchmark/report framing, cross-domain comparison surface. | The finance pack is an attributed entity-kind-collapse example used to show the lane is not software-only; the repo contribution is the bounded deterministic packaging and review surface. |
| `mixed_order_live_pack_v1` | Repo-backed structural diagnostic surface; no current doc ties first discovery to Rosario/Ege/Peter/Zhang. | Deterministic slice, projection/report surfaces, benchmark-pack promotion. | Repo-backed mixed-order structural diagnostic pack over pinned Wikidata slices. |
| `p279_scc_live_pack_v1` | Repo-backed structural diagnostic surface; no current doc ties first discovery to Rosario/Ege/Peter/Zhang. | Deterministic slice, SCC reporting, benchmark-pack promotion. | Repo-backed SCC/circular-subclass structural diagnostic pack over pinned Wikidata slices. |
| `qualifier_drift_p166_live_pack_v1` and pinned qualifier-drift cases | Repo-pinned live revision-pair work; not currently tied in docs to Rosario/Ege/Peter/Zhang discovery. | Live-first discovery, pinned revision-pair fixtures, deterministic drift reporting. | Repo-backed pinned qualifier-drift cases with deterministic revision-pair reporting. |
| `P2738` disjointness lane (`fixed_construction_contradiction`, `working_fluid_contradiction`, nucleon baseline) | Method/problem lineage should credit Ege Doğan and Peter Patel-Schneider. | Bounded deterministic disjointness lane, fixture packs, culprit-oriented review reports, live-first candidate discovery script. | This bounded disjointness lane is method-adjacent to Ege/Peter; the repo contribution is the narrower fixture-backed review/reporting implementation. |
| Classification-hierarchy inconsistency framing around `P31` / `P279` | Recent hierarchy-diagnosis context should credit Shixiong Zhao and Hideaki Takeda. Earlier broad conceptual-disarray context is also cited in that paper. | Grant framing, bounded demo selection, provenance-preserving review-support story. | The proposal sits alongside recent classification-hierarchy inconsistency work by Zhao/Takeda, while contributing a bounded provenance-aware review surface. |
| Hotspot benchmark lane as a whole | Partial parity / adjacent framing with Rosario's IBM-affiliated consistency-benchmark work. | Hotspot family taxonomy, deterministic pack selection, cluster generation, score-only evaluator, pathology-preserving provenance. | The repo has partial parity with Rosario on benchmark/scorer shape, but preserves structural pathology provenance rather than flattening it away. |

## Specific answer on "other ones around GNU"
The clearest explicit neighboring case in the same hotspot/page-review wave is:
- `finance_entity_kind_collapse_pack_v0`

Repo evidence:
- `docs/planning/wikidata_page_review_candidate_index_v1.json`
  - only two explicit page-review candidates are listed:
    - `finance_entity_kind_collapse_page_review`
    - `software_entity_kind_collapse_page_review`

So if GNU is treated as Rosario-linked, the finance entity-kind-collapse case is
the strongest adjacent case to treat cautiously in the same way unless better
provenance later shows otherwise.

## Safe foreground set
Safest repo-owned foreground surfaces for a grant story:
- mixed-order pack
- `P279` SCC pack
- pinned qualifier-drift pack
- bounded disjointness implementation/reporting surface

These are safer because the current docs primarily describe them as repo-backed
diagnostic/reporting artifacts rather than as externally surfaced example cases.

## Include-with-attribution set
- `GNU` / `GNU Project`
- finance entity-kind-collapse pack
- broader `P2738` method/problem context
- broader classification-hierarchy inconsistency framing

## Open caution
This matrix is suitable for grant/demo wording, but if any later evidence shows
different case provenance, update this file before submission rather than
leaving the wording to chat memory.
