# Woogaroo EPBC 2019/8575 — source-payment to SLR Matter bridge

**28 October 2026. Source-written, not an uploaded Court application or production source revision.**

This case-specific proof packet reuses [SensibLaw source admission](../../src/sources/admission.py) without making source links into authority. The [Python module](../../src/sources/woogaroo_case_cut.py) classifies seven public source locators by authored role and emits seven candidate legal grounds with `gate=0`. The [case tests](../../tests/sources/test_woogaroo_case_cut.py) check identity, receipt and non-promotion.

## Source roles are deliberately separate

- **Primary law:** Commonwealth EPBC Act as operative on 15 October 2026. Its `compile` admission classification applies to the *kind of authority*, not to a fetched exact law text. `persisted_revision_paid=false` and `exact_span_paid=false` remain true for the locator-only packet.
- **Original agency notice:** the EPBC public portal identifies the 2019/8575 approval with conditions. The notice is not the signed approval, actual final conditions, reasons or section 95C recommendation.
- **Original 2022 advice and recovery plan:** source-authored legal/ecological references. An original downloadable plan is not evidence that the final approving officer genuinely considered it or that a particular condition violated it.
- **QUT original 12 March 2026 letter:** named legal academic authors, original 2019/8575 objection, but public hosting is not proponent inbox delivery or the section 95B bundle.
- **Stockland first-party statement:** source for what the developer publicly asserts about retained corridor and staging, not an independent Commonwealth finding or ecological field measurement.
- **SWFG's 15 December 2025 Scenic 2020/8651 submission:** genuine *other-action environmental activity* lead for possible EPBC s487 standing; **never** Springview 2019/8575 merits, geometry, public-comment transmission or statutory facts.

All original URLs remain unchanged from identified source links. The `source_revision_ref` strings intentionally start with `locator-only:`: they are **not** a fictitious PostgreSQL `legal_source_revision`. No canonical content SHA, span offset or `reviewed_evidence_ref` has been created by this packet.

## Same-Matter path

[SLR PR #59](https://github.com/chboishabba/slr/pull/59) owns the canonical Rust `MatterControversyDraft` (not this Python module). Its [Woogaroo candidate-only fixture](https://github.com/chboishabba/slr/blob/agent/matter-controversy-1/crates/sl-pg-source-store/tests/woogaroo_2019_8575_candidate_controversy.rs) contains five proposition fibres and two residual queries: the **2022 koala approved-advice consideration** and **action-specific habitat-function** comparison against Stockland's publicly asserted retained corridor. No respondent admission, judicial ruling, reviewed evidence or persisted controversy is claimed. The SLR reverse search must only produce an **acquisition plan**, not source access or paid proof.

The [DASHI Woogaroo PR #1276](https://github.com/chboishabba/dashi_agda/pull/1276) owns the seven potential grounds and legal/review evidence cut, including statutory source authorship and favourable **Tarkine [2013]** versus adverse **Tarkine [2015]** and later cases. It also tracks the no-automated-filing rules and separate first/second/third-order political/financial evidence.

The existing [SensibLaw PR #494](https://github.com/chboishabba/SensibLaw/pull/494) is the exact ternary atomic legal registry owner (+1/0/−1). This case module **does not duplicate** that in-flight API or import it before merge. [SensibLaw PR #496](https://github.com/chboishabba/SensibLaw/pull/496) owns exact persisted-source-span reader payment, which is also **not** silently considered merged or executed.

## Residual gates to build a real case

1. Signed 15 October approval, delegate and conditions, actual Part 9 transition.
2. Correct 2022 endangered-koala conservation advice and evidence of actual consideration under the applicable s139(2) text.
3. The Secretary's original s95C report, final s95B proponent response and actual copies of comments *transmitted*.
4. Signed Council 9281/2024/OW Condition 6(a) satisfaction and exact same-stage site works timeline, if enforcement is considered.
5. Applicable 2022 recovery plan consistency and the final decision's treatment of local koala population connectivity.
6. Original SWFG objects as at decision, authorised applicant and its actual two-year conservation activity record.
7. Any applicant-specific receipt/furnishing of written decision and reasons, filing/time extension, interim relief and undertaking exposure.

No part of this packet can pay those original objects without the independent source material, reviewer approval and, for legal process, counsel/court action. Distinct Scenic EPBC 2020/8651 and historical gas/asset/meeting records cannot silently become same-case statutory evidence.

**Attribution:** legal authors and dated original documents retain authority; SensibLaw source admission, SLR PR #59 Matter engine, SLR PR #54 live matter reopening, SLR PR #75 candidate fleet and DASHI prior Agda/Ibrahim ownership all remain unchanged and distinct. Source-written code alone does not establish a judgment, actual source payment, executed test or kernel-verified theorem.
