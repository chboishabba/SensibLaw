"""Source-admission and exact-object cut for Woogaroo EPBC 2019/8575.

Reuses src.sources.admission. This is a source-written CASE SPECIMEN.
It cannot fetch URLs, persist source revisions, inspect private records,
appoint a plaintiff, prove standing, infer adverse legal findings or
convert a downloaded page into a paid case fact.

Legal grounds originate in dashi_agda PR #1276.
SLR MATTER-CONTROVERSY-1 owns adversarial runtime projection.
The sibling PR #494 owns a general ternary legal-atom registry; this
module does NOT duplicate or import that unmerged authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.sources.admission import (
    AU_PRIMARY_LEGAL_SOURCE_PROFILE,
    SourceAdmissionProfile,
    admit_source,
)

SPRINGVIEW = "2019/8575"
SCENIC = "2020/8651"
MATTER_REF = "matter:au:epbc:2019-8575:postapproval"

# Reuse the original primary-law policy, extending only case-evidence
# sources. Other publications never become law merely by appearing in repo.
WOOGAROO_ADMISSION = SourceAdmissionProfile(
    profile_ref="profile:woogaroo-2019-8575:evidence-classification:v1",
    admitted_roles=AU_PRIMARY_LEGAL_SOURCE_PROFILE.admitted_roles,
    evidence_only_roles={
        **AU_PRIMARY_LEGAL_SOURCE_PROFILE.evidence_only_roles,
        "official_case_notice": "case_status_not_signed_instrument",
        "original_submission": "author_claim_not_authoritative_decision",
        "developer_statement": "publisher_claim_not_regulator_finding",
        "approved_conservation_advice": "statutory_advice_not_proof_of_consideration",
        "recovery_plan": "recovery_plan_not_proof_of_decision_consistency",
    },
    excluded_roles={
        **AU_PRIMARY_LEGAL_SOURCE_PROFILE.excluded_roles,
        "synthetic_receipt": "fabricated_delivery_not_evidence",
        "generated_counsel_memo": "analysis_not_filed_pleading",
    },
)


@dataclass(frozen=True)
class LocatedSource:
    key: str
    action_ref: str
    originator: str
    role: str
    original_url: str
    date_label: str
    can_support_activity_for_standing: bool = False

    def __post_init__(self) -> None:
        if not all((self.key, self.action_ref, self.originator, self.role, self.original_url, self.date_label)):
            raise ValueError("original source needs explicit identity, originator and date")
        if not self.original_url.startswith("https://"):
            raise ValueError("source must carry unchanged public original URL")


SOURCES: tuple[LocatedSource, ...] = (
    LocatedSource(
        key="epbc-approval-status",
        action_ref=SPRINGVIEW,
        originator="DCCEEW / EPBC Public Portal",
        role="official_case_notice",
        original_url="https://epbcpublicportal.environment.gov.au/all-notices/",
        date_label="15 October 2026 published approval with conditions",
    ),
    LocatedSource(
        key="epbc-operative-law",
        action_ref=SPRINGVIEW,
        originator="Commonwealth Parliament / Federal Register",
        role="primary_legislation",
        original_url="https://www.legislation.gov.au/C2004A00485/2026-08-24",
        date_label="24 August 2026 C70; exact transitional provisions still require review",
    ),
    LocatedSource(
        key="koala-conservation-advice-2022",
        action_ref=SPRINGVIEW,
        originator="Australian Government / Threatened Species Scientific Committee",
        role="approved_conservation_advice",
        original_url="https://epbcpublicportal.environment.gov.au/_entity/sharepointdocumentlocation/ca34e3c6-b216-ed11-b83e-00224818a528/2ab10dab-d681-4911-b881-cc99413f07b6?file=Att+H+-+DAWE+%282022%29+Conservation+Advice+for+Phascolarctos+cinereus+%28Koala%29.pdf",
        date_label="12 February 2022",
    ),
    LocatedSource(
        key="koala-recovery-plan-2022",
        action_ref=SPRINGVIEW,
        originator="DAWE / Australian Government",
        role="recovery_plan",
        original_url="https://www.dcceew.gov.au/sites/default/files/documents/recovery-plan-koala-2022.pdf",
        date_label="2022",
    ),
    LocatedSource(
        key="qut-springview-letter-2026",
        action_ref=SPRINGVIEW,
        originator="Monica Taylor, Rowena Maguire, Bridget Lewis",
        role="original_submission",
        original_url="https://img1.wsimg.com/blobby/go/c204ebbc-02bb-46d9-ad71-ed7d494e752a/QUT%20LTR%20EPBC%20referral%20Woogaroo%20-%2012032026.pdf",
        date_label="12 March 2026",
    ),
    LocatedSource(
        key="stockland-springview-faq",
        action_ref=SPRINGVIEW,
        originator="Stockland (proponent publisher)",
        role="developer_statement",
        original_url="https://www.stockland.com.au/residential/qld/springview",
        date_label="October 2026 site text; exact revision unacquired",
    ),
    LocatedSource(
        key="swfg-scenic-letter",
        action_ref=SCENIC,
        originator="Save Woogaroo Forest Group Inc; Keith McCosh printed attribution",
        role="original_submission",
        original_url="https://img1.wsimg.com/blobby/go/c204ebbc-02bb-46d9-ad71-ed7d494e752a/downloads/5b140ad8-accf-4ef6-971d-07dc07d315ea/Response%20by%20SWF%20on%20Scenic%208651.pdf?ver=1792152994924",
        date_label="15 December 2025; different EPBC action",
        can_support_activity_for_standing=True,
    ),
)


# Candidate-only, no directional witness, no claim of a filed court case.
# Use the sibling atomic registry when it merges, rather than reimplement it.
GROUNDS: tuple[tuple[str, str, str], ...] = (
    ("advice-consideration", "139(2)", "15 October delegate advice briefing/95C and correct 2022 advice"),
    ("recovery-plan", "139(1)", "applicable plan obligation compared with actual signed conditions"),
    ("incremental-habitat", "136;139", "same-action baseline and final PD Item 4.6(c) decision analysis"),
    ("comment-transmission", "95B;95C", "original recipient delivery, copied public comments and Secretary report"),
    ("approval-scope", "133;134", "signed condition text, spatial approvals and operative transition"),
    ("local-prestart", "Ipswich 9281 Condition 6(a)", "Council actual submission, acceptance and staged works"),
    ("improper-influence", "ADJR s5 if legally applicable", "direct relevant officer communication and legal duty; no speculation"),
)


def source_admission_snapshot() -> tuple[dict[str, Any], ...]:
    """Classifies locator roles; neither loads nor pays exact source spans."""
    rows: list[dict[str, Any]] = []
    for source in sorted(SOURCES, key=lambda item: item.key):
        receipt = admit_source(
            {
                # Synthetic *locator identity*, explicitly not a persisted
                # legal_source_revision or canonical-content document ref.
                "source_revision_ref": f"locator-only:woogaroo:{source.key}",
                "source_role": source.role,
                "semantic_scope": "public-original-locator-no-exact-span",
            },
            profile=WOOGAROO_ADMISSION,
        )
        rows.append({
            "key": source.key,
            "epbc_action": source.action_ref,
            "originator": source.originator,
            "original_url": source.original_url,
            "date_label": source.date_label,
            "admission": receipt.to_dict(),
            "persisted_revision_paid": False,
            # Legal authority by role is NOT a retrieved or executable record.
            "source_bytes_materialised": False,
            "canonical_content_sha256": None,
            "exact_span_ref": None,
            "parser_execution_authorised": False,
            "exact_span_paid": False,
            "case_fact_paid": False,
            "minister_delivery_paid": False,
            "standing_activity_candidate": source.can_support_activity_for_standing,
        })
    return tuple(rows)


def eligible_as_springview_merits_evidence(key: str) -> bool:
    """Same-action guard, independent of environmental-activity standing."""
    source = next((row for row in SOURCES if row.key == key), None)
    if source is None:
        raise KeyError(key)
    return source.action_ref == SPRINGVIEW


def case_cut_packet() -> dict[str, Any]:
    """Deterministic pre-filing planning packet; not a judgment or admission."""
    return {
        "contract": "woogaroo-case-cut:v0_1",
        "matter_ref": MATTER_REF,
        "action_ref": SPRINGVIEW,
        "case_stage": "source_written_candidate_unfiled",
        "sources": list(source_admission_snapshot()),
        "grounds": [
            {
                "ground_ref": f"candidate-ground:{id_}",
                "statutory_hook": hook,
                "requested_discriminator": discriminator,
                "gate": 0,
                "positive_witness_refs": [],
                "negative_witness_refs": [],
                "case_error_proved": False,
            }
            for id_, hook, discriminator in GROUNDS
        ],
        "all_seven_grounds_unresolved": True,
        "signed_federal_approval_paid": False,
        "secretary_95c_paid": False,
        "applicant_standing_paid": False,
        "actual_filing_paid": False,
        "reviewed_slr_span_paid": False,
        "creates_legal_authority": False,
    }


__all__ = ["SPRINGVIEW", "SCENIC", "MATTER_REF", "WOOGAROO_ADMISSION",
           "SOURCES", "GROUNDS", "source_admission_snapshot",
           "eligible_as_springview_merits_evidence", "case_cut_packet"]
