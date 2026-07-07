from __future__ import annotations

from src.policy.fragment_grammar import (
    BirthGrammar,
    EducationGrammar,
    FragmentGrammarRegistry,
    FragmentMatch,
    MarriageGrammar,
    OfficeRangeGrammar,
    OwnershipGrammar,
    ProclamationGrammar,
    classify_fragment_surface,
    fragment_matches_to_pnfs,
    get_default_registry,
)
from src.policy.fragment_pnf import (
    BraidRelevanceReceipt,
    ConnectednessLevel,
    DepthLevel,
    ExportClass,
    ExportLanePolicy,
    FragmentPNF,
    FragmentPNFDepthReceipt,
    FragmentPNFProjectionReceipt,
    GrammarMatchStrength,
    LinkageDepthLevel,
    PNFClosureLevel,
    ProjectionBasisLevel,
    ReferentialityLevel,
    ResidualCompatibilityLevel,
    SourceSpanLevel,
    SourceSpanRef,
    TimeAnchor,
    TypedRole,
    build_braid_relevance_receipt,
    classify_connectedness,
    classify_export_class,
    classify_pnf_closure,
    classify_referentiality,
    classify_source_span,
    projection_basis_from_fallback,
)


# ── fragment_pnf: dataclass construction ──────────────────────────────────

def test_typed_role_construction() -> None:
    role = TypedRole(canonical_key="actor:gwb", canonical_label="George W. Bush")
    assert role.canonical_key == "actor:gwb"
    assert role.canonical_label == "George W. Bush"


def test_time_anchor_construction() -> None:
    ta = TimeAnchor(start_date="2001-01-20", end_date="2009-01-20", precision="range")
    assert ta.start_date == "2001-01-20"
    assert ta.end_date == "2009-01-20"
    assert ta.precision == "range"


def test_source_span_construction() -> None:
    ss = SourceSpanRef(parent_event_id="evt:001", atom_id="atom:0000", fragment_surface_text="Governor 1995-2000")
    assert ss.parent_event_id == "evt:001"
    assert ss.atom_id == "atom:0000"
    assert ss.fragment_surface_text == "Governor 1995-2000"


def test_fragment_pnf_minimal() -> None:
    pnf = FragmentPNF(
        fragment_id="evt:001:frag:0000",
        parent_event_id="evt:001",
        fragment_surface="Governor 1995-2000",
        fragment_surface_class="cv_cell",
        fragment_subclass="office_range",
        grammar_id="office_range_grammar_v0",
        grammar_match_strength=GrammarMatchStrength.exact_pattern,
    )
    assert pnf.fragment_id == "evt:001:frag:0000"
    assert pnf.fallback_used is False
    assert pnf.subject_role is None
    assert pnf.modifiers == ()


def test_fragment_pnf_with_roles() -> None:
    pnf = FragmentPNF(
        fragment_id="evt:001:frag:0000",
        parent_event_id="evt:001",
        fragment_surface="Governor of Texas 1995-2000",
        fragment_surface_class="cv_cell",
        fragment_subclass="office_range",
        grammar_id="office_range_grammar_v0",
        grammar_match_strength=GrammarMatchStrength.exact_pattern,
        subject_role=TypedRole(canonical_key="actor:gwb", canonical_label="George W. Bush"),
        predicate_spine="served_as",
        object_role=TypedRole(canonical_key="office:governor_of_texas", canonical_label="Governor of Texas"),
        time_anchor=TimeAnchor(start_date="1995", end_date="2000", precision="range"),
        pnf_basis=("office_role_range_pattern", "inherited_actor_context"),
    )
    assert pnf.subject_role.canonical_key == "actor:gwb"
    assert pnf.predicate_spine == "served_as"
    assert pnf.object_role.canonical_key == "office:governor_of_texas"
    assert pnf.time_anchor.start_date == "1995"
    assert pnf.fallback_used is False


# ── fragment_pnf: level enums ────────────────────────────────────────────

def test_connectedness_level_order() -> None:
    assert ConnectednessLevel.isolated.value == "isolated"
    assert ConnectednessLevel.braid_connected.value == "braid_connected"


def test_classify_connectedness() -> None:
    assert classify_connectedness(0, False, 0) == ConnectednessLevel.isolated
    assert classify_connectedness(2, False, 0) == ConnectednessLevel.linked
    assert classify_connectedness(2, True, 2) == ConnectednessLevel.clustered
    assert classify_connectedness(2, True, 0) == ConnectednessLevel.braid_connected


def test_classify_referentiality() -> None:
    assert classify_referentiality(0, 0, 0) == ReferentialityLevel.single_source
    assert classify_referentiality(1, 2, 0) == ReferentialityLevel.same_family_multi_span
    assert classify_referentiality(2, 0, 0) == ReferentialityLevel.multi_family
    assert classify_referentiality(2, 0, 2) == ReferentialityLevel.cross_source


def test_classify_pnf_closure_open() -> None:
    assert classify_pnf_closure(False, False, False, False, False, False) == PNFClosureLevel.open


def test_classify_pnf_closure_role_closed() -> None:
    assert classify_pnf_closure(True, True, True, False, False, False) == PNFClosureLevel.role_closed


def test_classify_pnf_closure_span_receipt_closed() -> None:
    assert classify_pnf_closure(True, True, True, True, True, True) == PNFClosureLevel.span_receipt_closed


def test_classify_source_span_missing() -> None:
    assert classify_source_span(False, False, False) == SourceSpanLevel.missing


def test_classify_source_span_has_raw() -> None:
    assert classify_source_span(True, False, False) == SourceSpanLevel.raw_span


def test_projection_basis_from_fallback() -> None:
    assert projection_basis_from_fallback(False, 3) == ProjectionBasisLevel.grammar_projected
    assert projection_basis_from_fallback(True, 3) == ProjectionBasisLevel.fallback_projected
    assert projection_basis_from_fallback(False, 1) == ProjectionBasisLevel.partial_projected


# ── fragment_pnf: export classification ───────────────────────────────────

def test_classify_export_blocked_when_pnf_open() -> None:
    cls, reasons = classify_export_class(
        PNFClosureLevel.open,
        ProjectionBasisLevel.grammar_projected,
        ResidualCompatibilityLevel.exact,
        LinkageDepthLevel.braid_node,
        ReferentialityLevel.cross_source,
        ExportLanePolicy(lane_id="test"),
    )
    assert cls == ExportClass.blocked


def test_classify_export_high_confidence() -> None:
    cls, reasons = classify_export_class(
        PNFClosureLevel.span_receipt_closed,
        ProjectionBasisLevel.grammar_projected,
        ResidualCompatibilityLevel.exact,
        LinkageDepthLevel.braid_node,
        ReferentialityLevel.cross_source,
        ExportLanePolicy(lane_id="test"),
    )
    assert cls == ExportClass.high_confidence_exportable
    assert reasons == []


def test_classify_export_exportable() -> None:
    cls, reasons = classify_export_class(
        PNFClosureLevel.role_time_closed,
        ProjectionBasisLevel.fallback_projected,
        ResidualCompatibilityLevel.partial,
        LinkageDepthLevel.braid_node,
        ReferentialityLevel.multi_family,
        ExportLanePolicy(lane_id="test"),
    )
    assert cls == ExportClass.exportable


# ── fragment_pnf: build_braid_relevance_receipt ──────────────────────────

def test_build_braid_relevance_receipt_defaults_blocked() -> None:
    r = build_braid_relevance_receipt()
    assert r.export_class == ExportClass.blocked
    assert len(r.blocked_reasons) > 0


def test_build_braid_relevance_receipt_high_confidence() -> None:
    r = build_braid_relevance_receipt(
        connectedness_level=ConnectednessLevel.braid_connected,
        referentiality_level=ReferentialityLevel.cross_source,
        depth_level=DepthLevel.braid_depth,
        pnf_closure_level=PNFClosureLevel.span_receipt_closed,
        residual_compatibility_level=ResidualCompatibilityLevel.exact,
        projection_basis_level=ProjectionBasisLevel.grammar_projected,
        linkage_depth_level=LinkageDepthLevel.braid_node,
        source_span_level=SourceSpanLevel.receipt_backed_span,
        connected_component_size=5,
        source_family_count=3,
        longest_path_len=4,
        closed_role_count=2,
        total_role_count=2,
    )
    assert r.export_class == ExportClass.high_confidence_exportable


# ── fragment_grammar: classify_fragment_surface ──────────────────────────

def test_classify_cv_cell_with_office_keyword() -> None:
    assert classify_fragment_surface("Governor of Texas 1995-2000") == "cv_cell"


def test_classify_cv_cell_with_education_keyword() -> None:
    assert classify_fragment_surface("Yale University 1968") == "cv_cell"


def test_classify_cv_cell_with_dash_prefix() -> None:
    assert classify_fragment_surface("- Governor 1995-2000") == "cv_cell"


def test_classify_caption_fragment_proclamation() -> None:
    assert classify_fragment_surface("Proclaimed to be White House Office") == "caption_fragment"


def test_classify_prose_fragment() -> None:
    assert classify_fragment_surface("He attended the meeting.") == "prose_fragment"


def test_classify_fallback_empty() -> None:
    assert classify_fragment_surface("") == "fallback"
    assert classify_fragment_surface("   ") == "fallback"


# ── fragment_grammar: FragmentMatch → FragmentPNF ────────────────────────

def test_fragment_match_to_pnf() -> None:
    match = FragmentMatch(
        grammar_id="office_range_grammar_v0",
        fragment_surface_class="cv_cell",
        fragment_subclass="office_range",
        grammar_match_strength=GrammarMatchStrength.exact_pattern,
        subject_role=TypedRole(canonical_key="actor:gwb", canonical_label="GWB"),
        predicate_spine="served_as",
        object_role=TypedRole(canonical_key="office:gov", canonical_label="Governor"),
        time_anchor=TimeAnchor(start_date="1995", precision="year"),
    )
    pnf = match.to_fragment_pnf(
        fragment_id="test:frag:0000",
        parent_event_id="test",
        fragment_surface="Governor 1995",
    )
    assert pnf.fragment_id == "test:frag:0000"
    assert pnf.predicate_spine == "served_as"
    assert pnf.subject_role.canonical_key == "actor:gwb"
    assert pnf.fallback_used is False


def test_fragment_matches_to_pnfs_multiple() -> None:
    m1 = FragmentMatch(
        grammar_id="g1", fragment_surface_class="cv_cell", fragment_subclass="s1",
        grammar_match_strength=GrammarMatchStrength.exact_pattern,
    )
    m2 = FragmentMatch(
        grammar_id="g2", fragment_surface_class="prose_fragment", fragment_subclass="s2",
        grammar_match_strength=GrammarMatchStrength.fallback_bundle, fallback_used=True,
    )
    pnfs = fragment_matches_to_pnfs([m1, m2], parent_event_id="evt", fragment_surface="test")
    assert len(pnfs) == 2
    assert pnfs[0].fragment_id == "evt:frag:0000"
    assert pnfs[1].fragment_id == "evt:frag:0001"
    assert pnfs[0].fallback_used is False
    assert pnfs[1].fallback_used is True


# ── fragment_grammar: OfficeRangeGrammar ─────────────────────────────────

def _parent_row(actor_key: str = "actor:george_w_bush", actor_label: str = "George W. Bush") -> dict:
    return {
        "event_roles": [
            {"entity": {"canonical_key": actor_key, "canonical_label": actor_label}},
        ],
    }


def test_office_range_matches_governor() -> None:
    g = OfficeRangeGrammar()
    matches = list(g.iter_matches("Governor of Texas 1995-2000", _parent_row()))
    assert len(matches) == 1
    m = matches[0]
    assert m.grammar_id == "office_range_grammar_v0"
    assert m.predicate_spine == "served_as"
    assert m.subject_role.canonical_key == "actor:george_w_bush"
    assert m.object_role.canonical_label == "Governor of Texas"
    assert m.time_anchor.start_date == "1995"
    assert m.time_anchor.end_date == "2000"


def test_office_range_single_year() -> None:
    g = OfficeRangeGrammar()
    matches = list(g.iter_matches("President 2001", _parent_row()))
    assert len(matches) == 1
    assert matches[0].time_anchor.start_date == "2001"
    assert matches[0].time_anchor.end_date is None


def test_office_range_no_match_with_birth_keyword() -> None:
    g = OfficeRangeGrammar()
    matches = list(g.iter_matches("Born in 1946 President later", _parent_row()))
    assert len(matches) == 0


def test_office_range_no_keyword() -> None:
    g = OfficeRangeGrammar()
    matches = list(g.iter_matches("Some random text 1995-2000", _parent_row()))
    assert len(matches) == 0


# ── fragment_grammar: ProclamationGrammar ────────────────────────────────

def test_proclamation_matches_to_be() -> None:
    g = ProclamationGrammar()
    matches = list(g.iter_matches("Proclaimed to be White House Office on January 20, 2001", _parent_row()))
    assert len(matches) == 1
    m = matches[0]
    assert m.predicate_spine == "proclaimed"
    assert "White House Office" in m.object_role.canonical_label
    assert m.time_anchor is not None
    assert m.time_anchor.start_date == "2001-01-20"


def test_proclamation_matches_no_to_be() -> None:
    g = ProclamationGrammar()
    matches = list(g.iter_matches("Proclaimed Homeland Security 2002", _parent_row()))
    assert len(matches) == 1
    assert "Homeland Security" in matches[0].object_role.canonical_label


def test_proclamation_no_match() -> None:
    g = ProclamationGrammar()
    matches = list(g.iter_matches("Regular sentence without keyword", _parent_row()))
    assert len(matches) == 0


# ── fragment_grammar: OwnershipGrammar ───────────────────────────────────

def test_ownership_matches_co_owned() -> None:
    g = OwnershipGrammar()
    matches = list(g.iter_matches("Co-owned the Texas Rangers 1994-1998", _parent_row()))
    assert len(matches) == 1
    assert matches[0].predicate_spine == "co_owned"
    assert "Texas Rangers" in matches[0].object_role.canonical_label
    assert matches[0].time_anchor.start_date == "1994"


def test_ownership_no_match() -> None:
    g = OwnershipGrammar()
    matches = list(g.iter_matches("No ownership text", _parent_row()))
    assert len(matches) == 0


# ── fragment_grammar: EducationGrammar ───────────────────────────────────

def test_education_matches_university() -> None:
    g = EducationGrammar()
    matches = list(g.iter_matches("Graduated from Yale University 1968", _parent_row()))
    assert len(matches) == 1
    assert matches[0].predicate_spine == "graduated_from"
    assert "Yale" in matches[0].object_role.canonical_label


def test_education_matches_harvard_fallback() -> None:
    g = EducationGrammar()
    matches = list(g.iter_matches("Attended Harvard 1964-1968", _parent_row()))
    assert len(matches) == 1
    assert "Harvard" in matches[0].object_role.canonical_label


def test_education_no_keyword() -> None:
    g = EducationGrammar()
    matches = list(g.iter_matches("No education keywords", _parent_row()))
    assert len(matches) == 0


# ── fragment_grammar: MarriageGrammar ────────────────────────────────────

def test_marriage_matches_married() -> None:
    g = MarriageGrammar()
    matches = list(g.iter_matches("Married Laura Welch 1977", _parent_row()))
    assert len(matches) == 1
    assert matches[0].predicate_spine == "married"
    assert "Laura" in matches[0].object_role.canonical_label


def test_marriage_default_spouse() -> None:
    g = MarriageGrammar()
    matches = list(g.iter_matches("Married 1977", _parent_row()))
    assert len(matches) == 1
    assert matches[0].object_role.canonical_label == "Laura Welch"


def test_marriage_no_match() -> None:
    g = MarriageGrammar()
    matches = list(g.iter_matches("Hello world", _parent_row()))
    assert len(matches) == 0


# ── fragment_grammar: BirthGrammar ───────────────────────────────────────

def test_birth_matches() -> None:
    g = BirthGrammar()
    matches = list(g.iter_matches("Born in 1946 in New Haven", _parent_row()))
    assert len(matches) == 1
    assert matches[0].predicate_spine == "birth"
    assert matches[0].time_anchor.start_date == "1946"
    assert matches[0].object_role.canonical_key == "event:birth"


def test_birth_no_match() -> None:
    g = BirthGrammar()
    matches = list(g.iter_matches("No birth keyword", _parent_row()))
    assert len(matches) == 0


# ── fragment_grammar: FragmentGrammarRegistry ────────────────────────────

def test_registry_default_grammars() -> None:
    reg = get_default_registry()
    assert len(reg.grammars) == 7  # all 6 specific + fallback


def test_registry_first_match_finds_office() -> None:
    reg = FragmentGrammarRegistry()
    match = reg.first_match("Governor of Texas 1995-2000", _parent_row())
    assert match is not None
    assert match.grammar_id == "office_range_grammar_v0"


def test_registry_first_match_finds_proclamation() -> None:
    reg = FragmentGrammarRegistry()
    match = reg.first_match("Proclaimed a national holiday 2002", _parent_row())
    assert match is not None
    assert match.grammar_id == "proclamation_grammar_v0"


def test_registry_first_match_falls_back() -> None:
    reg = FragmentGrammarRegistry()
    match = reg.first_match("Bush signed the bill", _parent_row())
    # fallback grammar uses collect_canonical_relational_bundle
    assert match is not None
    assert match.grammar_id == "fallback_grammar_v0"


def test_registry_register() -> None:
    reg = FragmentGrammarRegistry(grammars=[])
    assert len(reg.grammars) == 0
    reg.register(OfficeRangeGrammar())
    assert len(reg.grammars) == 1


def test_registry_register_front() -> None:
    reg = FragmentGrammarRegistry()
    first = reg.grammars[0].grammar_id
    class _PriorityStub:
        grammar_id = "priority_stub"
        fragment_subclass = "stub"
        def iter_matches(self, text, parent_row):
            return []
    reg.register_front(_PriorityStub())
    assert reg.grammars[0].grammar_id == "priority_stub"
    assert reg.grammars[1].grammar_id == first


# ── cross_source_event_braid: bind_atom_pnf integration ──────────────────

def test_bind_atom_pnf_office_range_emits_fragment_pnfs() -> None:
    from src.policy.cross_source_event_braid import bind_atom_pnf

    parent = _parent_row()
    row = {
        "text": "Governor of Texas 1995-2000",
        "source_family": "gwb",
        "event_id": "evt001",
    }
    bind_atom_pnf(row, parent)
    assert row.get("pnf") is not None
    assert row["pnf"]["predicate"] == "predicate:served_as"
    assert row.get("pnf_status") == "canonicalized"
    assert row.get("fragment_pnfs") is not None
    assert len(row["fragment_pnfs"]) >= 1
    first = row["fragment_pnfs"][0]
    assert first.fragment_subclass == "office_range"
    assert first.predicate_spine == "served_as"
    assert first.fallback_used is False
    assert first.fragment_surface_class == "cv_cell"


def test_bind_atom_pnf_proclamation_emits_fragment_pnfs() -> None:
    from src.policy.cross_source_event_braid import bind_atom_pnf

    parent = _parent_row()
    row = {"text": "Proclaimed January 20, 2001 to be White House Office", "source_family": "gwb", "event_id": "evt002"}
    bind_atom_pnf(row, parent)
    assert row.get("pnf") is not None
    assert row["pnf"]["predicate"] == "predicate:proclaimed"
    assert row.get("fragment_pnfs") is not None
    assert row["fragment_pnfs"][0].fragment_subclass == "proclamation"


def test_bind_atom_pnf_birth_marks_blocked() -> None:
    from src.policy.cross_source_event_braid import bind_atom_pnf

    parent = _parent_row()
    row = {
        "text": "Born in 1946",
        "source_family": "gwb",
        "event_id": "evt003",
        "event_roles": [
            {"entity": {"canonical_key": "actor:different", "canonical_label": "Different Person"}},
        ],
    }
    bind_atom_pnf(row, parent)
    assert row.get("is_blocked_birth_event") is True
    assert row.get("fragment_pnfs") is not None
    assert row["fragment_pnfs"][0].fragment_subclass == "birth"


def test_bind_atom_pnf_fallback_for_unmatched_text() -> None:
    from src.policy.cross_source_event_braid import bind_atom_pnf

    parent = _parent_row()
    row = {"text": "The committee approved the plan", "source_family": "gwb", "event_id": "evt004"}
    bind_atom_pnf(row, parent)
    assert row.get("pnf") is not None
    assert row.get("fragment_pnfs") is not None
    first = row["fragment_pnfs"][0]
    assert first.fallback_used is True
    assert first.grammar_id == "fallback_grammar_v0"


def test_bind_atom_pnf_marriage_emits_fragment_pnfs() -> None:
    from src.policy.cross_source_event_braid import bind_atom_pnf

    parent = _parent_row()
    row = {"text": "Married Laura Welch 1977", "source_family": "gwb", "event_id": "evt005"}
    bind_atom_pnf(row, parent)
    assert row.get("fragment_pnfs") is not None
    assert row["fragment_pnfs"][0].fragment_subclass == "marriage"


def test_bind_atom_pnf_education_emits_fragment_pnfs() -> None:
    from src.policy.cross_source_event_braid import bind_atom_pnf

    parent = _parent_row()
    row = {"text": "Graduated from Yale University 1968", "source_family": "gwb", "event_id": "evt006"}
    bind_atom_pnf(row, parent)
    assert row.get("fragment_pnfs") is not None
    assert row["fragment_pnfs"][0].fragment_subclass == "education"


def test_bind_atom_pnf_setup_event_roles_and_relation_candidates() -> None:
    from src.policy.cross_source_event_braid import bind_atom_pnf

    parent = _parent_row()
    row = {"text": "Governor of Texas 1995-2000", "source_family": "gwb", "event_id": "evt007"}
    bind_atom_pnf(row, parent)
    assert row.get("event_roles") == [{"entity": {"canonical_key": "actor:george_w_bush", "canonical_label": "George W. Bush"}}]
    assert row.get("relation_candidates") is not None
    assert len(row["relation_candidates"]) == 1
    assert row["relation_candidates"][0]["predicate_key"] == "served_as"


# ── cross_source_event_braid: component-level receipts in braid ──────────

def test_braid_relevance_receipts_present_in_payload() -> None:
    from src.policy.cross_source_event_braid import build_cross_source_event_braid

    payload = build_cross_source_event_braid([
        {
            "source_family": "gwb",
            "source_event_rows": [
                {
                    "source_family": "gwb",
                    "doc_id": "bio1",
                    "doc_title": "Biography",
                    "event_id": "A",
                    "source_event_key": "gwb:A",
                    "local_order_index": 1,
                    "anchor": {"year": 2006, "text": "2006-01-01"},
                    "text": "Governor of Texas 1995-2000",
                    "source_path": "/tmp/bio1.txt",
                    "source_url": "",
                    "source_id": "bio1",
                    "citation_refs": [],
                    "event_roles": [
                        {"entity": {"canonical_key": "actor:george_w_bush", "canonical_label": "George W. Bush"}},
                    ],
                    "relation_candidates": [],
                    "promoted_relations": [],
                    "candidate_only_relations": [],
                    "abstained_relation_candidates": [],
                    "mentions": [],
                },
                {
                    "source_family": "gwb",
                    "doc_id": "bio1",
                    "doc_title": "Biography",
                    "event_id": "B",
                    "source_event_key": "gwb:B",
                    "local_order_index": 2,
                    "anchor": {"year": 2006, "text": "2006-01-01"},
                    "text": "President of the United States 2001-2009",
                    "source_path": "/tmp/bio1.txt",
                    "source_url": "",
                    "source_id": "bio1",
                    "citation_refs": [],
                    "event_roles": [
                        {"entity": {"canonical_key": "actor:george_w_bush", "canonical_label": "George W. Bush"}},
                    ],
                    "relation_candidates": [],
                    "promoted_relations": [],
                    "candidate_only_relations": [],
                    "abstained_relation_candidates": [],
                    "mentions": [],
                },
            ],
        },
    ])
    for row in payload["source_event_rows"]:
        assert "braid_metrics" in row, f"Missing braid_metrics in {row.get('event_id')}"
        assert "relevance" in row, f"Missing relevance in {row.get('event_id')}"
        fpnfs = row.get("fragment_pnfs")
        if fpnfs:
            receipts = row.get("fragment_pnf_receipts")
            assert receipts is not None, f"Missing fragment_pnf_receipts in {row.get('event_id')}"
            assert len(receipts) == len(fpnfs), f"Receipt count {len(receipts)} != fragment count {len(fpnfs)}"
            for r in receipts:
                assert "fragment_id" in r
                assert "export_class" in r
                assert "blocked_reasons" in r
                assert "basis" in r


# ── FragmentPNFProjectionReceipt ─────────────────────────────────────────

def test_fragment_pnf_projection_receipt() -> None:
    receipt = FragmentPNFProjectionReceipt(
        fragment_id="test:frag:0000",
        projection_status=ProjectionBasisLevel.grammar_projected,
        projection_basis=("grammar_projected",),
    )
    assert receipt.fragment_id == "test:frag:0000"
    assert receipt.projection_status == ProjectionBasisLevel.grammar_projected


# ── project_fragment_pnf adapter ─────────────────────────────────────────

def _make_test_fragment(
    *,
    subclass: str = "office_range",
    predicate: str = "served_as",
    subject_key: str = "actor:gwb",
    subject_label: str = "GWB",
    object_key: str = "office:governor",
    object_label: str = "Governor",
    fallback: bool = False,
) -> FragmentPNF:
    return FragmentPNF(
        fragment_id="test:frag:0000",
        parent_event_id="evt:001",
        fragment_surface="test surface",
        fragment_surface_class="cv_cell",
        fragment_subclass=subclass,
        grammar_id="test_grammar_v0",
        grammar_match_strength=GrammarMatchStrength.fallback_bundle if fallback else GrammarMatchStrength.exact_pattern,
        subject_role=TypedRole(canonical_key=subject_key, canonical_label=subject_label),
        predicate_spine=predicate,
        object_role=TypedRole(canonical_key=object_key, canonical_label=object_label),
        time_anchor=TimeAnchor(start_date="1995", end_date="2000", precision="range"),
        pnf_basis=("test_basis",),
        fallback_used=fallback,
    )


def test_project_single_fragment_to_predicate_atom() -> None:
    from src.policy.project_fragment_pnf import project_fragment_pnf

    fragment = _make_test_fragment()
    atom, receipt = project_fragment_pnf(fragment)

    assert atom is not None
    assert atom.predicate == "served_as"
    assert atom.domain == "fragment_pnf_projection"
    assert atom.wrapper.evidence_only is True
    assert atom.wrapper.status == "fragment_projection"
    assert "subject" in atom.roles
    assert "object" in atom.roles
    assert "action" in atom.roles
    assert atom.roles["subject"].value == "actor:gwb"
    assert atom.roles["object"].value == "office:governor"
    assert atom.roles["action"].value == "served_as"
    assert atom.atom_id == "test:frag:0000"

    assert receipt.fragment_id == "test:frag:0000"
    assert receipt.projection_status == ProjectionBasisLevel.grammar_projected
    assert receipt.predicate_atom_ref == "test:frag:0000"


def test_project_fallback_fragment() -> None:
    from src.policy.project_fragment_pnf import project_fragment_pnf

    fragment = _make_test_fragment(fallback=True)
    atom, receipt = project_fragment_pnf(fragment)

    assert atom is not None
    assert receipt.projection_status == ProjectionBasisLevel.fallback_projected
    assert "fragment_projection" in atom.wrapper.status


def test_project_missing_predicate_returns_none() -> None:
    from src.policy.project_fragment_pnf import project_fragment_pnf

    fragment = _make_test_fragment(predicate="")
    atom, receipt = project_fragment_pnf(fragment)
    assert atom is None
    assert receipt.projection_status == ProjectionBasisLevel.unprojectable
    assert "missing_predicate_spine" in receipt.blocked_reasons


def test_project_missing_roles_returns_none() -> None:
    from src.policy.project_fragment_pnf import project_fragment_pnf

    fragment = FragmentPNF(
        fragment_id="test:frag:0000",
        parent_event_id="evt:001",
        fragment_surface="blank",
        fragment_surface_class="fallback",
        fragment_subclass="generic",
        grammar_id="fallback_grammar_v0",
        grammar_match_strength=GrammarMatchStrength.fallback_bundle,
        predicate_spine="some_action",
    )
    atom, receipt = project_fragment_pnf(fragment)
    assert atom is None
    assert receipt.projection_status == ProjectionBasisLevel.partial_projected
    assert "missing_roles" in receipt.blocked_reasons


def test_project_multiple_fragments() -> None:
    from src.policy.project_fragment_pnf import project_fragment_pnfs

    f1 = _make_test_fragment(predicate="served_as", object_key="office:gov")
    f2 = _make_test_fragment(predicate="graduated_from", object_key="edu:yale", subclass="education")
    f3 = FragmentPNF(
        fragment_id="test:frag:0002",
        parent_event_id="evt:001",
        fragment_surface="empty",
        fragment_surface_class="fallback",
        fragment_subclass="generic",
        grammar_id="fallback_grammar_v0",
        grammar_match_strength=GrammarMatchStrength.fallback_bundle,
    )

    atoms, receipts = project_fragment_pnfs([f1, f2, f3])
    assert len(atoms) == 2
    assert len(receipts) == 3
    assert atoms[0].predicate == "served_as"
    assert atoms[1].predicate == "graduated_from"
    assert receipts[2].projection_status == ProjectionBasisLevel.unprojectable


def test_project_row_fragment_pnfs() -> None:
    from src.policy.project_fragment_pnf import project_row_fragment_pnfs

    row = {
        "fragment_pnfs": [
            _make_test_fragment(predicate="served_as", object_key="office:gov"),
            _make_test_fragment(predicate="graduated_from", object_key="edu:yale", subclass="education"),
        ],
    }
    result = project_row_fragment_pnfs(row)
    assert "projected_predicate_atoms" in result
    assert "fragment_projection_receipts" in result
    assert len(result["projected_predicate_atoms"]) == 2
    assert result["projected_predicate_atoms"][0]["predicate"] == "served_as"
    assert result["projected_predicate_atoms"][1]["predicate"] == "graduated_from"
    assert result["projected_predicate_atoms"][0]["domain"] == "fragment_pnf_projection"


def test_project_row_no_fragments() -> None:
    from src.policy.project_fragment_pnf import project_row_fragment_pnfs

    row: dict[str, Any] = {}
    result = project_row_fragment_pnfs(row)
    assert result["projected_predicate_atoms"] == []
    assert result["fragment_projection_receipts"] == []


def test_project_row_empty_list() -> None:
    from src.policy.project_fragment_pnf import project_row_fragment_pnfs

    row = {"fragment_pnfs": []}
    result = project_row_fragment_pnfs(row)
    assert result["projected_predicate_atoms"] == []
    assert result["fragment_projection_receipts"] == []


# ── linkage_depth layer ──────────────────────────────────────────────────

def test_linkage_depth_flat_shortcut() -> None:
    from src.policy.fragment_linkage_depth import assess_linkage_depth

    row = {
        "source_path": "/tmp/doc.txt",
        "text": "Bush was president",
        "anchor": {"text": "2001"},
    }
    receipt = assess_linkage_depth(row)
    assert receipt.source_span_present is True
    assert receipt.fragment_pnf_present is False
    assert receipt.sentence_pnf_present is False
    assert receipt.braid_attachment_present is False
    assert receipt.flat_shortcut_detected is True
    assert receipt.role_erasure_detected is False


def test_linkage_depth_with_fragment_pnf() -> None:
    from src.policy.fragment_linkage_depth import assess_linkage_depth

    row = {
        "source_path": "/tmp/doc.txt",
        "fragment_pnfs": [{"fragment_id": "test"}],
        "text": "Governor 1995-2000",
    }
    receipt = assess_linkage_depth(row)
    assert receipt.source_span_present is True
    assert receipt.fragment_pnf_present is True
    assert receipt.flat_shortcut_detected is False
    assert receipt.role_erasure_detected is True


def test_linkage_depth_with_predicate_atoms() -> None:
    from src.policy.fragment_linkage_depth import assess_linkage_depth

    row = {
        "source_path": "/tmp/doc.txt",
        "fragment_pnfs": [{"fragment_id": "test"}],
        "projected_predicate_atoms": [{"predicate": "served_as"}],
        "text": "Governor 1995-2000",
    }
    receipt = assess_linkage_depth(row)
    assert receipt.sentence_pnf_present is True
    assert receipt.flat_shortcut_detected is False
    assert receipt.role_erasure_detected is False


def test_linkage_depth_with_braid_attachment() -> None:
    from src.policy.fragment_linkage_depth import assess_linkage_depth

    row = {
        "source_path": "/tmp/doc.txt",
        "fragment_pnfs": [{"fragment_id": "test"}],
        "projected_predicate_atoms": [{"predicate": "served_as"}],
        "braid_metrics": {"connectedness": 2},
        "text": "Governor 1995-2000",
    }
    receipt = assess_linkage_depth(row)
    assert receipt.braid_attachment_present is True
    assert receipt.flat_shortcut_detected is False


def test_linkage_depth_no_source_span() -> None:
    from src.policy.fragment_linkage_depth import assess_linkage_depth

    row = {"text": "some text"}
    receipt = assess_linkage_depth(row)
    assert receipt.source_span_present is False
    assert receipt.flat_shortcut_detected is False
    assert receipt.role_erasure_detected is False


def test_classify_linkage_depth_level() -> None:
    from src.policy.fragment_linkage_depth import classify_linkage_depth_level

    r0 = FragmentPNFDepthReceipt(braid_attachment_present=True)
    assert classify_linkage_depth_level(r0) == LinkageDepthLevel.braid_node

    r1 = FragmentPNFDepthReceipt(document_pnf_present=True)
    assert classify_linkage_depth_level(r1) == LinkageDepthLevel.document_pnf

    r2 = FragmentPNFDepthReceipt(sentence_pnf_present=True)
    assert classify_linkage_depth_level(r2) == LinkageDepthLevel.sentence_pnf

    r3 = FragmentPNFDepthReceipt(fragment_pnf_present=True)
    assert classify_linkage_depth_level(r3) == LinkageDepthLevel.fragment_pnf

    r4 = FragmentPNFDepthReceipt(source_span_present=True)
    assert classify_linkage_depth_level(r4) == LinkageDepthLevel.source_span

    r5 = FragmentPNFDepthReceipt()
    assert classify_linkage_depth_level(r5) == LinkageDepthLevel.flat_shortcut


def test_assess_and_store_linkage_depth() -> None:
    from src.policy.fragment_linkage_depth import assess_and_store_linkage_depth

    row = {
        "source_path": "/tmp/doc.txt",
        "anchor": {"text": "2001"},
        "fragment_pnfs": [{"fragment_id": "test"}],
        "projected_predicate_atoms": [{"predicate": "served_as"}],
        "braid_metrics": {"connectedness": 3},
        "text": "Governor 1995-2000",
    }
    assess_and_store_linkage_depth(row)
    assert "linkage_depth_receipt" in row
    assert "linkage_depth_level" in row
    assert "flat_shortcut_detected" in row
    assert row["linkage_depth_level"] == "braid_node"
    assert row["flat_shortcut_detected"] is False
    assert row["linkage_depth_receipt"]["braid_attachment_present"] is True


def test_assess_rows_linkage_depth() -> None:
    from src.policy.fragment_linkage_depth import assess_rows_linkage_depth

    rows = [
        {"source_path": "/tmp/a.txt", "text": "flat"},
        {"source_path": "/tmp/b.txt", "fragment_pnfs": [{"fragment_id": "t"}], "text": "deep"},
    ]
    assess_rows_linkage_depth(rows)
    assert rows[0]["flat_shortcut_detected"] is True
    assert rows[0]["linkage_depth_level"] == "source_span"
    assert rows[1]["flat_shortcut_detected"] is False
    assert rows[1]["linkage_depth_level"] == "fragment_pnf"
