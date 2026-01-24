# Sprint: S3 — Reference Identity & Stability Layer

## Goal
Add a stability layer *above* extraction so statute references can be compared, diffed, and explained across documents without changing LT-REF-1…6 behavior.

## Scope
- Derive a deterministic `identity_hash` for each reference from existing canonical fields (work, family key, year, jurisdiction hint) without external registries.
- Produce proof-safe diffs on `identity_hash` sets (added/removed/unchanged) for document or version comparisons.
- Attach a lightweight provenance envelope (clause span id, page numbers, source, anchor used) for auditability; provenance must not affect identity.

## Constraints
- Extraction invariants **frozen** (LT-REF-1…6); no behavior changes to link precedence or anchor-core dominance.
- Identity is text-derived only; no statute dictionary, no network lookups.
- Deterministic and monotone: adding identity/diff/provenance cannot create or remove references.
- Keep outputs serializable and backward-compatible (field additions only).

## Deliverables
- `ReferenceIdentity` helper that computes `identity_hash` and exposes family/year/jurisdiction hints from canonical text.
- `ReferenceDiff` primitive operating on `identity_hash` sets with added/removed/unchanged buckets.
- Provenance envelope stored alongside references for debugging (clause id, pages, source, anchor used).
- Docs updated to include CR-ID invariants and diff/provenance rules; S2 invariants remain intact.
- Tests: identity stability across runs/docs, OCR-variant collapse to same identity, distinct Acts produce distinct identities, diff correctness, provenance presence without behavior change.

## Plan
1) **Identity spec:** Define CR-ID invariants (text-derived, deterministic, non-invasive) and map canonical fields → identity components.  
2) **Identity helper:** Implement `ReferenceIdentity` + `identity_hash`; thread through existing reference objects without changing extraction.  
3) **Diff primitive:** Add `ReferenceDiff` operating on identity sets; expose helpers for doc-to-doc comparison.  
4) **Provenance envelope:** Attach clause span id + page numbers + source/anchor used; ensure it is optional and non-behavioral.  
5) **Tests:** Add pytest coverage for identity stability, distinctness, OCR variant collapse, diff correctness, and provenance presence; rerun focused + relevant suites.  
6) **Docs:** Update `docs/logic_tree_ir.md` (CR-ID invariants + diff/provenance guarantees); update changelog/notes if required.

## Acceptance Criteria
- Two PDFs naming the same Act/section yield the same `identity_hash`; OCR variants do not change identity.
- Distinct Acts in the same clause produce distinct identities (no over-collapse).
- Diffs report only genuine reference changes; reordering/pagination changes yield empty diffs.
- Provenance is emitted but does **not** alter reference count/content; backward compatibility maintained.
- All new tests pass; existing suites remain green.

## Risks / Mitigations
- **Over-collapse in identity:** keep family key + year in hash to separate near names.  
- **Backward compatibility:** add fields instead of mutating existing ones; guard serialization.  
- **Performance:** compute identity once per reference; cache if needed.  
- **Spec drift:** freeze LT-REF-1…6; require new invariant to change extraction.

## Open Questions
- Do we want optional jurisdiction hints now, or defer until a registry layer exists?  
- Should identity hash include section/pinpoint or remain work-scoped for some use cases?  
- How should provenance be exposed downstream (debug-only vs API field)?
