from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.briefing import (  # noqa: E402
    BriefPackBuilder,
    IssueProfile,
    MatterAuthority,
    MatterExhibit,
    MatterFactor,
    MatterProfile,
    render_brief_pack_pdf,
)


def _sample_matter() -> MatterProfile:
    return MatterProfile(
        title="Smith v Smith",
        issues=[
            IssueProfile(
                issue="parenting", statement="Secure primary residence orders"
            ),
            IssueProfile(issue="property", statement="Adjust interests under s 79"),
        ],
        factors=[
            MatterFactor(
                id="f1",
                issue="parenting",
                section="s 60CC(2)(a)",
                proposition="Benefit of a meaningful relationship",
                assertion="Child thrives with the father",
                exhibits=["E1", "E2"],
            ),
            MatterFactor(
                id="f2",
                issue="property",
                section="s 79",
                proposition="Financial and homemaker contributions",
                assertion="Mother made the bulk of homemaker contributions",
                exhibits=["E3"],
            ),
        ],
        authorities=[
            MatterAuthority(
                id="A1",
                issue="parenting",
                name="Goode & Goode",
                citation="[2006] FamCA 1346",
                pin_cite="[65]-[70]",
                anchors=["f1"],
                proposition="Framework for interim parenting decisions",
            ),
            MatterAuthority(
                id="A2",
                issue="property",
                name="Stanford v Stanford",
                citation="[2012] HCA 52",
                pin_cite="[37]",
                anchors=["f2"],
                proposition="Two-step inquiry for s 79",
            ),
        ],
        exhibits=[
            MatterExhibit(
                id="E1",
                description="2019 school report",
                source="E1.pdf",
                annexed=True,
                pages="12-18",
            ),
            MatterExhibit(
                id="E2",
                description="Counsellor letter",
                source="E2.pdf",
                annexed=False,
            ),
            MatterExhibit(
                id="E3",
                description="Bank statements",
                source="E3.pdf",
                annexed=False,
            ),
            MatterExhibit(
                id="E4",
                description="Photographs of home",
                source="E4.pdf",
                annexed=True,
            ),
        ],
    )


def test_brief_pack_builder_generates_expected_structures(tmp_path: Path) -> None:
    matter = _sample_matter()
    builder = BriefPackBuilder()
    pack = builder.build(matter)

    assert "parenting" in pack.submission_skeletons
    parenting = pack.submission_skeletons["parenting"]
    assert parenting.sections
    parenting_slot_citations = {
        slot.citation for section in parenting.sections for slot in section.authorities
    }
    assert "[2006] FamCA 1346" in parenting_slot_citations
    assert any("f1" in section.anchors for section in parenting.sections)

    coverage = {row.factor_id: row for row in pack.coverage_grid.rows}
    assert coverage["f1"].status == "supported"
    assert coverage["f2"].status == "thin"
    assert "E1" in coverage["f1"].exhibits
    assert "E3" in coverage["f2"].exhibits

    counters = pack.counter_arguments["f1"]
    assert len(counters) == 3
    assert any(
        "E1" in {ev.exhibit_id for ev in counter.evidence} for counter in counters
    )

    missing_ids = [issue.exhibit_id for issue in pack.bundle_report.missing_annexures]
    assert set(missing_ids) == {"E2", "E3"}
    assert "E4" in pack.bundle_report.unreferenced_exhibits

    assert "[2006] FamCA 1346" in pack.first_cut_brief
    assert "E1" in pack.first_cut_brief

    pdf_path = tmp_path / "brief_pack.pdf"
    render_brief_pack_pdf(pack, pdf_path)
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 0
