import pytest
import json

from src.policy.entity_resolution import (
    CandidateCatalogEntry,
    CoreferenceCluster,
    EntityCandidate,
    EntityCandidateSet,
    FormCompositionRule,
    FormLexiconEntry,
    LocalTypingRule,
    LocalTypeAlternative,
    MentionAliasEntry,
    MentionExpansionRequest,
    MentionLicense,
    MentionRecurrenceGroup,
    MentionSpan,
    PartialPNF,
    PartialPNFSlot,
    ResolutionConstraint,
    ResolutionBackendCapability,
    ResolutionCacheEntry,
    ResolutionSubjectDeclaration,
    build_entity_resolution_carrier,
    build_form_derivation_carrier,
    build_local_typing_carrier,
    build_partial_pnf_carrier,
    build_resolution_demand_carrier,
    build_resolution_subject_carrier,
    build_resolution_schedule_carrier,
    build_alias_expansion_requests,
    build_candidate_retrieval_carrier,
    build_mention_expansion_carrier,
    build_grammar_expansion_requests,
    build_mention_licensing_carrier,
    build_mention_recurrence_carrier,
)


def _mention(
    mention_ref: str, start_char: int, end_char: int, surface: str
) -> MentionSpan:
    return MentionSpan(
        mention_ref=mention_ref,
        source_ref="source:demo",
        document_ref="document:demo",
        start_char=start_char,
        end_char=end_char,
        canonical_surface=surface,
        generation_reason="alias_index",
    )


def test_builds_deterministic_candidate_only_carrier() -> None:
    bush = _mention("mention:bush", 0, 4, "Bush")
    president = _mention("mention:president", 9, 22, "the president")
    carrier = build_entity_resolution_carrier(
        mentions=[president, bush],
        candidate_sets=[
            EntityCandidateSet(
                mention_ref="mention:bush",
                candidates=(
                    EntityCandidate(
                        candidate_ref="candidate:bush:41",
                        candidate_kind="instance",
                        identity_ref="Q207",
                        label="George W. Bush",
                        registry_snapshot_ref="wikidata:Q207@123",
                    ),
                    EntityCandidate(
                        candidate_ref="candidate:bush:43",
                        candidate_kind="instance",
                        identity_ref="Q23505",
                        label="George H. W. Bush",
                    ),
                ),
            ),
            EntityCandidateSet(
                mention_ref="mention:president",
                candidates=(
                    EntityCandidate(
                        candidate_ref="candidate:president:role",
                        candidate_kind="role",
                        identity_ref="Q11696",
                        label="President of the United States",
                    ),
                ),
            ),
        ],
        coreference_clusters=[
            CoreferenceCluster(
                cluster_ref="cluster:president:1",
                document_ref="document:demo",
                member_mention_refs=("mention:president", "mention:bush"),
                candidate_set_refs=(
                    "candidate-set:mention:president",
                    "candidate-set:mention:bush",
                ),
            )
        ],
    )

    assert carrier["authority"] == "candidate_only"
    assert carrier["promotion_effect"] == "none"
    assert [row["mention_ref"] for row in carrier["mentions"]] == [
        "mention:bush",
        "mention:president",
    ]
    assert carrier["summary"] == {
        "mention_count": 2,
        "candidate_set_count": 2,
        "candidate_count": 3,
        "coreference_cluster_count": 1,
    }
    assert carrier == build_entity_resolution_carrier(
        mentions=list(reversed([bush, president])),
        candidate_sets=list(reversed(carrier["candidate_sets"])),
        coreference_clusters=carrier["coreference_clusters"],
    )


def test_rejects_cross_document_coreference_and_non_candidate_authority() -> None:
    first = _mention("mention:first", 0, 4, "Bush")
    second = MentionSpan(
        mention_ref="mention:second",
        source_ref="source:other",
        document_ref="document:other",
        start_char=0,
        end_char=4,
        canonical_surface="Bush",
        generation_reason="alias_index",
    )

    with pytest.raises(ValueError, match="cross document"):
        build_entity_resolution_carrier(
            mentions=[first, second],
            candidate_sets=[],
            coreference_clusters=[
                CoreferenceCluster(
                    cluster_ref="cluster:invalid",
                    document_ref="document:demo",
                    member_mention_refs=("mention:first", "mention:second"),
                )
            ],
        )

    with pytest.raises(ValueError, match="candidate_only"):
        build_entity_resolution_carrier(
            mentions=[first],
            candidate_sets=[],
            authority="promoted",
        )


def test_rejects_invalid_span_kind_and_unknown_candidate_set_reference() -> None:
    with pytest.raises(ValueError, match="character range"):
        build_entity_resolution_carrier(
            mentions=[_mention("mention:invalid", 4, 4, "Bush")],
            candidate_sets=[],
        )


def test_builds_deterministic_lazy_mention_licenses_with_lattice_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text = "George W. Bush met Blair in 2001."

    def parsed(_text: str) -> dict[str, object]:
        return {
            "sents": [
                {
                    "tokens": [
                        {"text": "George", "start": 0, "end": 6, "pos": "PROPN"},
                        {"text": "W.", "start": 7, "end": 9, "pos": "PROPN"},
                        {"text": "Bush", "start": 10, "end": 14, "pos": "PROPN"},
                        {"text": "met", "start": 15, "end": 18, "pos": "VERB"},
                        {"text": "Blair", "start": 19, "end": 24, "pos": "PROPN"},
                        {"text": "in", "start": 25, "end": 27, "pos": "ADP"},
                        {"text": "2001", "start": 28, "end": 32, "pos": "NUM"},
                        {"text": ".", "start": 32, "end": 33, "pos": "PUNCT"},
                    ]
                }
            ]
        }

    monkeypatch.setattr("src.policy.entity_resolution.parse_canonical_text", parsed)
    carrier = build_mention_licensing_carrier(
        canonical_text=text,
        source_ref="source:demo",
        document_ref="document:demo",
        context_refs=("context:sentence:1",),
    )

    assert carrier["authority"] == "candidate_only"
    assert carrier["resolution_effect"] == "none"
    assert carrier["promotion_effect"] == "none"
    assert carrier["execution_effect"] == "none"
    assert carrier["lattice"] == {
        "token_count": 9,
        "token_boundary_count": 10,
        "recoverable_contiguous_span_count": 45,
    }
    assert any(
        mention["canonical_surface"] == "George W. Bush"
        and mention["generation_reason"] == "named_entity_shape"
        for mention in carrier["mentions"]
    )
    assert any(
        row["license_kind"] == "eventuality_annotation"
        and row["local_type_hypotheses"] == ["linguistic_eventuality"]
        for row in carrier["licenses"]
    )
    assert any(
        row["license_kind"] == "numeric_literal"
        and row["expected_candidate_kinds"] == ["event_type", "literal"]
        for row in carrier["licenses"]
    )
    assert carrier["suppressed_spans"] == [
        {
            "start_token": 2,
            "end_token": 3,
            "suppression_reason": "punctuation_or_symbol",
        },
        {"start_token": 6, "end_token": 7, "suppression_reason": "structural_lexeme"},
        {
            "start_token": 8,
            "end_token": 9,
            "suppression_reason": "punctuation_or_symbol",
        },
    ]
    assert carrier == build_mention_licensing_carrier(
        canonical_text=text,
        source_ref="source:demo",
        document_ref="document:demo",
        context_refs=("context:sentence:1",),
    )


def test_mention_licenses_reject_unknown_kind_and_do_not_accept_empty_text() -> None:
    with pytest.raises(ValueError, match="canonical_text"):
        build_mention_licensing_carrier(
            canonical_text="",
            source_ref="source:demo",
            document_ref="document:demo",
        )

    with pytest.raises(ValueError, match="unsupported mention license kind"):
        MentionLicense(
            license_ref="license:bad",
            mention_ref="mention:bad",
            license_kind="resolved_identity",
            expected_candidate_kinds=("instance",),
            priority=0,
        ).to_dict()

    mention = _mention("mention:bush", 0, 4, "Bush")
    with pytest.raises(ValueError, match="unsupported entity candidate kind"):
        build_entity_resolution_carrier(
            mentions=[mention],
            candidate_sets=[
                {
                    "mention_ref": "mention:bush",
                    "candidates": [
                        {
                            "candidate_ref": "candidate:bad",
                            "candidate_kind": "person",
                            "identity_ref": "Q207",
                            "label": "George W. Bush",
                        }
                    ],
                }
            ],
        )

    with pytest.raises(ValueError, match="known candidate sets"):
        build_entity_resolution_carrier(
            mentions=[mention],
            candidate_sets=[],
            coreference_clusters=[
                {
                    "cluster_ref": "cluster:unknown-set",
                    "document_ref": "document:demo",
                    "member_mention_refs": ["mention:bush"],
                    "candidate_set_refs": ["candidate-set:missing"],
                }
            ],
        )


def test_groups_exact_normalized_recurrences_without_coreference() -> None:
    mentions = [
        _mention("mention:bush:2", 10, 14, "BUSH"),
        _mention("mention:bush:1", 0, 4, "Bush"),
        _mention("mention:president", 20, 33, "the president"),
        MentionSpan(
            mention_ref="mention:bush:other-document",
            source_ref="source:other",
            document_ref="document:other",
            start_char=0,
            end_char=4,
            canonical_surface="Bush",
            generation_reason="lexical_token",
        ),
        _mention("mention:bush:3", 40, 44, "  Bush  "),
    ]

    carrier = build_mention_recurrence_carrier(mentions=mentions)

    assert carrier["authority"] == "candidate_only"
    assert carrier["resolution_effect"] == "none"
    assert carrier["promotion_effect"] == "none"
    assert carrier["execution_effect"] == "none"
    assert carrier["summary"] == {
        "input_mention_count": 5,
        "recurrence_group_count": 1,
        "recurrent_mention_count": 3,
    }
    assert carrier["recurrence_groups"][0]["document_ref"] == "document:demo"
    assert carrier["recurrence_groups"][0]["normalized_surface"] == "bush"
    assert carrier["recurrence_groups"][0]["member_mention_refs"] == [
        "mention:bush:1",
        "mention:bush:2",
        "mention:bush:3",
    ]
    assert carrier == build_mention_recurrence_carrier(
        mentions=list(reversed(mentions))
    )

    with pytest.raises(ValueError, match="document_local"):
        MentionRecurrenceGroup(
            group_ref="mention-recurrence:invalid",
            document_ref="document:demo",
            normalized_surface="bush",
            member_mention_refs=("mention:bush:1", "mention:bush:2"),
            scope="global",
        ).to_dict()


def test_materializes_bounded_expansion_requests_without_alias_or_pnf_decision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text = "President Bush spoke."

    def parsed(_text: str) -> dict[str, object]:
        return {
            "sents": [
                {
                    "tokens": [
                        {"text": "President", "start": 0, "end": 9, "pos": "NOUN"},
                        {"text": "Bush", "start": 10, "end": 14, "pos": "PROPN"},
                        {"text": "spoke", "start": 15, "end": 20, "pos": "VERB"},
                        {"text": ".", "start": 20, "end": 21, "pos": "PUNCT"},
                    ]
                }
            ]
        }

    monkeypatch.setattr("src.policy.entity_resolution.parse_canonical_text", parsed)
    licensing = build_mention_licensing_carrier(
        canonical_text=text,
        source_ref="source:demo",
        document_ref="document:demo",
    )
    requests = [
        MentionExpansionRequest(
            request_ref="request:grammar:president-bush",
            source_ref="source:demo",
            document_ref="document:demo",
            start_token=0,
            end_token=2,
            expansion_kind="grammar_phrase",
            expected_candidate_kinds=("instance", "role"),
            context_refs=("context:sentence:1",),
            local_type_hypotheses=("role_phrase",),
        ),
        MentionExpansionRequest(
            request_ref="request:pnf:bush",
            source_ref="source:demo",
            document_ref="document:demo",
            start_token=1,
            end_token=2,
            expansion_kind="pnf_demand",
            expected_candidate_kinds=("instance",),
            context_refs=("context:slot:subject",),
        ),
    ]

    carrier = build_mention_expansion_carrier(
        canonical_text=text,
        licensing_carrier=licensing,
        requests=requests,
    )

    assert carrier["authority"] == "candidate_only"
    assert carrier["resolution_effect"] == "none"
    assert carrier["promotion_effect"] == "none"
    assert carrier["execution_effect"] == "none"
    assert carrier["summary"] == {
        "request_count": 2,
        "created_mention_count": 1,
        "reused_mention_count": 1,
        "license_count": 2,
    }
    assert carrier["created_mentions"][0]["canonical_surface"] == "President Bush"
    assert {row["materialization"] for row in carrier["expansions"]} == {
        "created",
        "reused",
    }
    assert carrier == build_mention_expansion_carrier(
        canonical_text=text,
        licensing_carrier=licensing,
        requests=list(reversed(requests)),
    )


def test_rejects_unanchored_or_mismatched_expansion_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text = "Bush spoke."

    def parsed(_text: str) -> dict[str, object]:
        return {
            "sents": [
                {
                    "tokens": [
                        {"text": "Bush", "start": 0, "end": 4, "pos": "PROPN"},
                        {"text": "spoke", "start": 5, "end": 10, "pos": "VERB"},
                        {"text": ".", "start": 10, "end": 11, "pos": "PUNCT"},
                    ]
                }
            ]
        }

    monkeypatch.setattr("src.policy.entity_resolution.parse_canonical_text", parsed)
    licensing = build_mention_licensing_carrier(
        canonical_text=text,
        source_ref="source:demo",
        document_ref="document:demo",
    )
    with pytest.raises(ValueError, match="context references"):
        MentionExpansionRequest(
            request_ref="request:no-context",
            source_ref="source:demo",
            document_ref="document:demo",
            start_token=0,
            end_token=1,
            expansion_kind="alias_hint",
            expected_candidate_kinds=("instance",),
            context_refs=(),
        ).to_dict()

    with pytest.raises(ValueError, match="match the licensing source"):
        build_mention_expansion_carrier(
            canonical_text=text,
            licensing_carrier=licensing,
            requests=[
                {
                    "request_ref": "request:wrong-document",
                    "source_ref": "source:demo",
                    "document_ref": "document:other",
                    "start_token": 0,
                    "end_token": 1,
                    "expansion_kind": "alias_hint",
                    "expected_candidate_kinds": ["instance"],
                    "context_refs": ["context:test"],
                }
            ],
        )

    with pytest.raises(ValueError, match="canonical_text digest"):
        build_mention_expansion_carrier(
            canonical_text="Other text.",
            licensing_carrier=licensing,
            requests=[],
        )


def test_builds_exact_alias_hint_requests_without_identity_or_registry_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text = "9/11 differed from 911. 9/11 mattered."
    tokens = [
        ("9", 0, 1),
        ("/", 1, 2),
        ("11", 2, 4),
        ("differed", 5, 13),
        ("from", 14, 18),
        ("911", 19, 22),
        (".", 22, 23),
        ("9", 24, 25),
        ("/", 25, 26),
        ("11", 26, 28),
        ("mattered", 29, 37),
        (".", 37, 38),
    ]
    monkeypatch.setattr(
        "src.policy.entity_resolution.tokenize_canonical_with_spans",
        lambda _text: tokens,
    )
    entries = [
        MentionAliasEntry(
            alias_ref="alias:event-surface",
            token_sequence=("9", "/", "11"),
            expected_candidate_kinds=("event_type", "instance"),
            context_refs=("alias-index:demo@1",),
            local_type_hypotheses=("event_phrase",),
        ),
        MentionAliasEntry(
            alias_ref="alias:number-surface",
            token_sequence=("911",),
            expected_candidate_kinds=("literal",),
            context_refs=("alias-index:demo@1",),
        ),
    ]

    carrier = build_alias_expansion_requests(
        canonical_text=text,
        source_ref="source:demo",
        document_ref="document:demo",
        alias_entries=entries,
    )

    assert carrier["authority"] == "candidate_only"
    assert carrier["resolution_effect"] == "none"
    assert carrier["promotion_effect"] == "none"
    assert carrier["execution_effect"] == "none"
    assert carrier["summary"] == {
        "alias_entry_count": 2,
        "request_count": 3,
        "matched_alias_entry_count": 2,
    }
    assert [match["canonical_surface"] for match in carrier["matches"]] == [
        "9/11",
        "9/11",
        "911",
    ]
    assert {
        (request["start_token"], request["end_token"], request["expansion_kind"])
        for request in carrier["requests"]
    } == {(0, 3, "alias_hint"), (5, 6, "alias_hint"), (7, 10, "alias_hint")}
    assert "identity_ref" not in str(carrier)
    assert carrier == build_alias_expansion_requests(
        canonical_text=text,
        source_ref="source:demo",
        document_ref="document:demo",
        alias_entries=list(reversed(entries)),
    )


def test_alias_entries_reject_missing_context_or_registry_identity() -> None:
    with pytest.raises(ValueError, match="context references"):
        MentionAliasEntry(
            alias_ref="alias:missing-context",
            token_sequence=("Bush",),
            expected_candidate_kinds=("instance",),
            context_refs=(),
        ).to_dict()

    with pytest.raises(ValueError, match="candidate or registry identity"):
        build_alias_expansion_requests(
            canonical_text="Bush spoke.",
            source_ref="source:demo",
            document_ref="document:demo",
            alias_entries=[
                {
                    "alias_ref": "alias:bad",
                    "token_sequence": ["Bush"],
                    "expected_candidate_kinds": ["instance"],
                    "context_refs": ["alias-index:demo@1"],
                    "identity_ref": "Q207",
                }
            ],
        )


def test_builds_nominal_grammar_requests_from_public_annotations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text = "The former President Bush met the prime minister."
    tokens = [
        ("The", 0, 3),
        ("former", 4, 10),
        ("President", 11, 20),
        ("Bush", 21, 25),
        ("met", 26, 29),
        ("the", 30, 33),
        ("prime", 34, 39),
        ("minister", 40, 48),
        (".", 48, 49),
    ]

    def parsed(_text: str) -> dict[str, object]:
        return {
            "sents": [
                {
                    "tokens": [
                        {"text": "The", "start": 0, "end": 3, "pos": "DET"},
                        {"text": "former", "start": 4, "end": 10, "pos": "ADJ"},
                        {
                            "text": "President",
                            "start": 11,
                            "end": 20,
                            "pos": "NOUN",
                        },
                        {"text": "Bush", "start": 21, "end": 25, "pos": "PROPN"},
                        {"text": "met", "start": 26, "end": 29, "pos": "VERB"},
                        {"text": "the", "start": 30, "end": 33, "pos": "DET"},
                        {"text": "prime", "start": 34, "end": 39, "pos": "ADJ"},
                        {
                            "text": "minister",
                            "start": 40,
                            "end": 48,
                            "pos": "NOUN",
                        },
                        {"text": ".", "start": 48, "end": 49, "pos": "PUNCT"},
                    ]
                }
            ]
        }

    monkeypatch.setattr(
        "src.policy.entity_resolution.tokenize_canonical_with_spans",
        lambda _text: tokens,
    )
    monkeypatch.setattr("src.policy.entity_resolution.parse_canonical_text", parsed)
    carrier = build_grammar_expansion_requests(
        canonical_text=text,
        source_ref="source:demo",
        document_ref="document:demo",
        context_refs=("context:sentence:1",),
    )

    assert carrier["authority"] == "candidate_only"
    assert carrier["grammar_profile"] == "nominal_phrase.v0_1"
    assert carrier["summary"] == {"phrase_count": 2, "request_count": 2}
    assert [phrase["canonical_surface"] for phrase in carrier["phrases"]] == [
        "The former President Bush",
        "the prime minister",
    ]
    assert carrier["phrases"][0]["pos_tags"] == ["DET", "ADJ", "NOUN", "PROPN"]
    assert set(carrier["requests"][0]) >= {
        "request_ref",
        "start_token",
        "end_token",
        "expansion_kind",
        "authority",
    }
    assert {request["expansion_kind"] for request in carrier["requests"]} == {
        "grammar_phrase"
    }
    assert carrier["resolution_effect"] == "none"
    assert carrier["promotion_effect"] == "none"
    assert carrier == build_grammar_expansion_requests(
        canonical_text=text,
        source_ref="source:demo",
        document_ref="document:demo",
        context_refs=("context:sentence:1",),
    )


def test_grammar_expansion_rejects_missing_context_and_omits_unannotated_spans(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValueError, match="context references"):
        build_grammar_expansion_requests(
            canonical_text="Bush spoke.",
            source_ref="source:demo",
            document_ref="document:demo",
            context_refs=(),
        )

    monkeypatch.setattr(
        "src.policy.entity_resolution.tokenize_canonical_with_spans",
        lambda _text: [("Bush", 0, 4), ("spoke", 5, 10), (".", 10, 11)],
    )
    monkeypatch.setattr(
        "src.policy.entity_resolution.parse_canonical_text",
        lambda _text: {"sents": [{"tokens": []}]},
    )
    carrier = build_grammar_expansion_requests(
        canonical_text="Bush spoke.",
        source_ref="source:demo",
        document_ref="document:demo",
        context_refs=("context:sentence:1",),
    )
    assert carrier["phrases"] == []
    assert carrier["requests"] == []


def test_retrieves_exact_catalog_candidates_without_resolution_or_token_collapse() -> (
    None
):
    mentions = [
        _mention("mention:attacks", 0, 4, "9/11"),
        _mention("mention:number", 5, 8, "911"),
        _mention("mention:unknown", 9, 13, "Bush"),
    ]
    catalog_entries = [
        CandidateCatalogEntry(
            catalog_entry_ref="catalog:event:9-11",
            candidate_kind="instance",
            identity_ref="external:event:9-11",
            label="September 11 attacks",
            match_token_sequences=(("9", "/", "11"),),
            evidence_refs=("snapshot:events@1",),
            registry_snapshot_ref="snapshot:events@1",
        ),
        CandidateCatalogEntry(
            catalog_entry_ref="catalog:number:911",
            candidate_kind="literal",
            identity_ref="literal:911",
            label="911",
            match_token_sequences=(("911",),),
            evidence_refs=("catalog:telephony@1",),
        ),
        CandidateCatalogEntry(
            catalog_entry_ref="catalog:event:9-11:alternate",
            candidate_kind="event_type",
            identity_ref="external:event-type:attack",
            label="attack event",
            match_token_sequences=(("9", "/", "11"),),
            evidence_refs=("snapshot:event-types@1",),
        ),
    ]

    carrier = build_candidate_retrieval_carrier(
        mentions=mentions,
        catalog_entries=catalog_entries,
    )

    assert carrier["authority"] == "candidate_only"
    assert carrier["resolution_effect"] == "none"
    assert carrier["promotion_effect"] == "none"
    assert carrier["execution_effect"] == "none"
    assert carrier["summary"] == {
        "input_mention_count": 3,
        "catalog_entry_count": 3,
        "candidate_set_count": 3,
        "candidate_count": 3,
        "unmatched_mention_count": 1,
    }
    candidate_sets = {
        candidate_set["mention_ref"]: candidate_set["candidates"]
        for candidate_set in carrier["candidate_sets"]
    }
    assert {
        candidate["identity_ref"] for candidate in candidate_sets["mention:attacks"]
    } == {
        "external:event:9-11",
        "external:event-type:attack",
    }
    assert [
        candidate["identity_ref"] for candidate in candidate_sets["mention:number"]
    ] == ["literal:911"]
    assert candidate_sets["mention:unknown"] == []
    assert carrier == build_candidate_retrieval_carrier(
        mentions=list(reversed(mentions)),
        catalog_entries=list(reversed(catalog_entries)),
    )


def test_derives_form_alternatives_and_relations_without_entity_selection() -> None:
    mentions = [
        _mention("mention:date", 0, 16, "September Eleven"),
        _mention("mention:slash", 17, 21, "9/11"),
        _mention("mention:number", 22, 25, "911"),
        _mention("mention:abbreviation", 26, 29, "S11"),
    ]
    lexicon_entries = [
        FormLexiconEntry(
            entry_ref="form-lexicon:month-september",
            token_sequence=("September",),
            form_type="calendar_month",
            normalized_payload={"value": 9},
            relation_kind="orthographic_variant_of",
            evidence_refs=("profile:english-calendar@1",),
        ),
        FormLexiconEntry(
            entry_ref="form-lexicon:cardinal-eleven",
            token_sequence=("Eleven",),
            form_type="cardinal",
            normalized_payload={"value": 11},
            relation_kind="spoken_form_of",
            evidence_refs=("profile:english-cardinals@1",),
        ),
    ]
    composition_rules = [
        FormCompositionRule(
            rule_ref="form-rule:month-day",
            component_form_types=("calendar_month", "cardinal"),
            output_form_type="month_day",
            payload_keys=("month", "day"),
        )
    ]

    carrier = build_form_derivation_carrier(
        mentions=mentions,
        lexicon_entries=lexicon_entries,
        composition_rules=composition_rules,
    )

    assert carrier["authority"] == "candidate_only"
    assert carrier["resolution_effect"] == "none"
    assert carrier["pnf_effect"] == "none"
    assert carrier["promotion_effect"] == "none"
    assert carrier["serialization_order"] == "form_ref_nonsemantic"
    assert carrier["summary"] == {
        "mention_count": 4,
        "form_count": 14,
        "relation_count": 11,
        "lexicon_entry_count": 2,
        "composition_rule_count": 1,
    }
    forms_by_mention = {}
    for form in carrier["forms"]:
        forms_by_mention.setdefault(form["mention_ref"], []).append(form)
        assert "identity_ref" not in form["normalized_payload"]
    date_forms = forms_by_mention["mention:date"]
    assert {
        (form["form_type"], json.dumps(form["normalized_payload"], sort_keys=True))
        for form in date_forms
    } == {
        ("surface_text", '{"text": "September Eleven"}'),
        ("token_sequence", '{"tokens": ["september", "eleven"]}'),
        ("calendar_month", '{"value": 9}'),
        ("cardinal", '{"value": 11}'),
        ("month_day", '{"day": 11, "month": 9}'),
    }
    assert {form["form_type"] for form in forms_by_mention["mention:slash"]} == {
        "surface_text",
        "token_sequence",
        "rational",
    }
    assert {form["form_type"] for form in forms_by_mention["mention:number"]} == {
        "surface_text",
        "token_sequence",
        "integer",
    }
    assert {form["form_type"] for form in forms_by_mention["mention:abbreviation"]} == {
        "surface_text",
        "token_sequence",
        "abbreviation",
    }
    assert all(
        relation["relation_kind"] != "metonymic_reference_to"
        for relation in carrier["relations"]
    )
    assert carrier == build_form_derivation_carrier(
        mentions=list(reversed(mentions)),
        lexicon_entries=list(reversed(lexicon_entries)),
        composition_rules=list(reversed(composition_rules)),
    )


def test_form_derivation_rejects_entity_or_promotion_in_language_profiles() -> None:
    with pytest.raises(ValueError, match="entity resolution or promotion"):
        build_form_derivation_carrier(
            mentions=[_mention("mention:bad", 0, 3, "911")],
            lexicon_entries=[
                {
                    "entry_ref": "form-lexicon:bad",
                    "token_sequence": ["911"],
                    "form_type": "integer",
                    "normalized_payload": {"value": 911},
                    "relation_kind": "numeric_rendering_of",
                    "evidence_refs": ["profile:numeric@1"],
                    "identity_ref": "external:emergency-number",
                }
            ],
        )


def test_form_composition_preserves_all_compatible_paths() -> None:
    carrier = build_form_derivation_carrier(
        mentions=[_mention("mention:date", 0, 16, "September Eleven")],
        lexicon_entries=[
            FormLexiconEntry(
                entry_ref="form-lexicon:month-september-a",
                token_sequence=("September",),
                form_type="calendar_month",
                normalized_payload={"value": 9},
                relation_kind="orthographic_variant_of",
                evidence_refs=("profile:calendar-a@1",),
            ),
            FormLexiconEntry(
                entry_ref="form-lexicon:month-september-b",
                token_sequence=("September",),
                form_type="calendar_month",
                normalized_payload={"value": "09"},
                relation_kind="orthographic_variant_of",
                evidence_refs=("profile:calendar-b@1",),
            ),
            FormLexiconEntry(
                entry_ref="form-lexicon:cardinal-eleven",
                token_sequence=("Eleven",),
                form_type="cardinal",
                normalized_payload={"value": 11},
                relation_kind="spoken_form_of",
                evidence_refs=("profile:cardinals@1",),
            ),
        ],
        composition_rules=[
            FormCompositionRule(
                rule_ref="form-rule:month-day",
                component_form_types=("calendar_month", "cardinal"),
                output_form_type="month_day",
                payload_keys=("month", "day"),
            )
        ],
    )

    month_days = [
        form["normalized_payload"]
        for form in carrier["forms"]
        if form["form_type"] == "month_day"
    ]
    assert {json.dumps(payload, sort_keys=True) for payload in month_days} == {
        '{"day": 11, "month": "09"}',
        '{"day": 11, "month": 9}',
    }
    assert carrier == build_form_derivation_carrier(
        mentions=[_mention("mention:date", 0, 16, "September Eleven")],
        lexicon_entries=list(
            reversed(
                [
                    FormLexiconEntry(
                        entry_ref="form-lexicon:month-september-a",
                        token_sequence=("September",),
                        form_type="calendar_month",
                        normalized_payload={"value": 9},
                        relation_kind="orthographic_variant_of",
                        evidence_refs=("profile:calendar-a@1",),
                    ),
                    FormLexiconEntry(
                        entry_ref="form-lexicon:month-september-b",
                        token_sequence=("September",),
                        form_type="calendar_month",
                        normalized_payload={"value": "09"},
                        relation_kind="orthographic_variant_of",
                        evidence_refs=("profile:calendar-b@1",),
                    ),
                    FormLexiconEntry(
                        entry_ref="form-lexicon:cardinal-eleven",
                        token_sequence=("Eleven",),
                        form_type="cardinal",
                        normalized_payload={"value": 11},
                        relation_kind="spoken_form_of",
                        evidence_refs=("profile:cardinals@1",),
                    ),
                ]
            )
        ),
        composition_rules=[
            FormCompositionRule(
                rule_ref="form-rule:month-day",
                component_form_types=("calendar_month", "cardinal"),
                output_form_type="month_day",
                payload_keys=("month", "day"),
            )
        ],
    )


def test_local_typing_keeps_type_alternatives_and_coverage_separate_from_pnf() -> None:
    mentions = [
        _mention("mention:slash", 0, 4, "9/11"),
        _mention("mention:role", 5, 18, "the president"),
        _mention("mention:abbreviation", 19, 22, "S11"),
        _mention("mention:weak", 23, 27, "Bush"),
        MentionSpan(
            mention_ref="mention:eventuality",
            source_ref="source:demo",
            document_ref="document:demo",
            start_char=28,
            end_char=37,
            canonical_surface="announced",
            generation_reason="eventuality_annotation",
            grammatical_role="eventuality_predicate",
        ),
    ]
    form_carrier = build_form_derivation_carrier(
        mentions=mentions,
        lexicon_entries=[
            FormLexiconEntry(
                entry_ref="form-lexicon:president-role",
                token_sequence=("the", "president"),
                form_type="office_role_phrase",
                normalized_payload={"value": "president"},
                relation_kind="orthographic_variant_of",
                evidence_refs=("profile:roles@1",),
            )
        ],
    )
    carrier = build_local_typing_carrier(
        mentions=mentions,
        forms=form_carrier["forms"],
        typing_rules=[
            LocalTypingRule(
                rule_ref="local-type-rule:office-role",
                form_type="office_role_phrase",
                semantic_family="role",
                local_type="office_holder_role",
                evidence_refs=("profile:roles@1",),
            )
        ],
    )

    assert carrier["authority"] == "candidate_only"
    assert carrier["resolution_effect"] == "none"
    assert carrier["pnf_effect"] == "none"
    assert carrier["promotion_effect"] == "none"
    assert carrier["serialization_order"] == "reference_nonsemantic"
    assert {
        (row["semantic_family"], row["local_type"])
        for row in carrier["local_type_alternatives"]
    } == {
        ("quantity", "numeric_quantity"),
        ("role", "office_holder_role"),
        ("literal", "abbreviation_form"),
        ("eventuality", "linguistic_eventuality"),
    }
    coverage = {
        row["mention_ref"]: row["coverage_state"]
        for row in carrier["coverage_pressure"]
    }
    assert coverage == {
        "mention:abbreviation": "typed",
        "mention:eventuality": "typed",
        "mention:role": "typed",
        "mention:slash": "typed",
        "mention:weak": "weakly_typed",
    }
    assert carrier["summary"]["coverage_state_counts"] == {
        "not_applicable": 0,
        "typed": 4,
        "untyped": 0,
        "weakly_typed": 1,
    }
    assert carrier == build_local_typing_carrier(
        mentions=list(reversed(mentions)),
        forms=list(reversed(form_carrier["forms"])),
        typing_rules=[
            {
                "rule_ref": "local-type-rule:office-role",
                "form_type": "office_role_phrase",
                "semantic_family": "role",
                "local_type": "office_holder_role",
                "evidence_refs": ["profile:roles@1"],
            }
        ],
    )


def test_local_typing_rejects_authority_and_identity_in_profile_rules() -> None:
    with pytest.raises(ValueError, match="candidate_only"):
        build_local_typing_carrier(
            mentions=[_mention("mention:one", 0, 3, "911")],
            forms=[],
            authority="resolved",
        )
    with pytest.raises(ValueError, match="entity resolution or promotion"):
        build_local_typing_carrier(
            mentions=[_mention("mention:one", 0, 3, "911")],
            forms=[],
            typing_rules=[
                {
                    "rule_ref": "bad-rule",
                    "form_type": "integer",
                    "semantic_family": "quantity",
                    "local_type": "numeric_quantity",
                    "evidence_refs": ["profile:numeric@1"],
                    "identity_ref": "external:911",
                }
            ],
        )


def test_factorizes_partial_pnf_slots_and_receipts_closure_pressure() -> None:
    mentions = [
        _mention("mention:subject", 0, 4, "Bush"),
        _mention("mention:predicate", 5, 14, "announced"),
        _mention("mention:time", 15, 19, "2001"),
        _mention("mention:object", 20, 26, "policy"),
    ]
    local_types = [
        {
            "type_ref": "local-type:subject-person",
            "mention_ref": "mention:subject",
            "semantic_family": "entity",
            "local_type": "person",
            "derivation_basis": "profile_local_typing",
            "evidence_refs": ["profile:people@1"],
        },
        {
            "type_ref": "local-type:subject-office-holder",
            "mention_ref": "mention:subject",
            "semantic_family": "entity",
            "local_type": "office_holder",
            "derivation_basis": "profile_local_typing",
            "evidence_refs": ["profile:roles@1"],
        },
        {
            "type_ref": "local-type:predicate",
            "mention_ref": "mention:predicate",
            "semantic_family": "relation",
            "local_type": "speech_act",
            "derivation_basis": "profile_local_typing",
            "evidence_refs": ["profile:eventualities@1"],
        },
        {
            "type_ref": "local-type:time",
            "mention_ref": "mention:time",
            "semantic_family": "literal",
            "local_type": "year_expression",
            "derivation_basis": "profile_local_typing",
            "evidence_refs": ["profile:time@1"],
        },
    ]
    pnf = PartialPNF(
        pnf_ref="pnf:announcement:1",
        document_ref="document:demo",
        slots=(
            PartialPNFSlot(
                slot_ref="slot:subject",
                slot_kind="subject",
                mention_ref="mention:subject",
                expected_semantic_families=("entity",),
                closure_requirement="external_identity",
            ),
            PartialPNFSlot(
                slot_ref="slot:predicate",
                slot_kind="predicate",
                mention_ref="mention:predicate",
                expected_semantic_families=("relation",),
                closure_requirement="local_type",
            ),
            PartialPNFSlot(
                slot_ref="slot:time",
                slot_kind="time",
                mention_ref="mention:time",
                expected_semantic_families=("literal",),
                closure_requirement="local_type",
            ),
            PartialPNFSlot(
                slot_ref="slot:object",
                slot_kind="object",
                mention_ref="mention:object",
                expected_semantic_families=("entity", "property"),
                closure_requirement="external_identity",
            ),
            PartialPNFSlot(
                slot_ref="slot:location",
                slot_kind="location",
                expected_semantic_families=("entity",),
                closure_requirement="external_identity",
                required=False,
            ),
        ),
    )

    carrier = build_partial_pnf_carrier(
        mentions=mentions,
        local_type_alternatives=local_types,
        partial_pnfs=[pnf],
    )

    assert carrier["authority"] == "candidate_only"
    assert carrier["resolution_effect"] == "none"
    assert carrier["demand_effect"] == "none"
    assert carrier["promotion_effect"] == "none"
    assert carrier["summary"] == {
        "partial_pnf_count": 1,
        "slot_count": 5,
        "slot_alternative_count": 4,
        "closure_state_counts": {
            "locally_closed": 2,
            "not_required": 1,
            "requires_external_resolution": 1,
            "requires_local_typing": 1,
        },
    }
    assert {
        (row["slot_ref"], row["closure_state"]) for row in carrier["closure_pressure"]
    } == {
        ("slot:subject", "requires_external_resolution"),
        ("slot:predicate", "locally_closed"),
        ("slot:time", "locally_closed"),
        ("slot:object", "requires_local_typing"),
        ("slot:location", "not_required"),
    }
    assert (
        len(
            [
                row
                for row in carrier["slot_alternatives"]
                if row["slot_ref"] == "slot:subject"
            ]
        )
        == 2
    )
    assert carrier == build_partial_pnf_carrier(
        mentions=list(reversed(mentions)),
        local_type_alternatives=list(reversed(local_types)),
        partial_pnfs=[pnf.to_dict()],
    )
    demands = build_resolution_demand_carrier(
        partial_pnf_carrier=carrier,
        budget_class="review",
    )
    assert demands["backend_effect"] == "none"
    assert demands["resolution_effect"] == "none"
    assert demands["pnf_effect"] == "none"
    assert demands["promotion_effect"] == "none"
    assert demands["summary"] == {
        "demand_count": 2,
        "source_closure_state_counts": {
            "requires_external_resolution": 1,
            "requires_local_typing": 1,
        },
    }
    assert {
        (row["slot_ref"], tuple(row["requested_facets"])) for row in demands["demands"]
    } == {
        ("slot:subject", ("identity", "type_compatibility")),
        ("slot:object", ("local_semantic_typing",)),
    }
    assert demands == build_resolution_demand_carrier(
        partial_pnf_carrier=carrier,
        budget_class="review",
    )


def test_partial_pnf_rejects_cross_document_slot_binding() -> None:
    other_document_mention = MentionSpan(
        mention_ref="mention:other",
        source_ref="source:other",
        document_ref="document:other",
        start_char=0,
        end_char=4,
        canonical_surface="Bush",
        generation_reason="alias_index",
    )
    with pytest.raises(ValueError, match="document-bounded"):
        build_partial_pnf_carrier(
            mentions=[other_document_mention],
            local_type_alternatives=[],
            partial_pnfs=[
                PartialPNF(
                    pnf_ref="pnf:invalid",
                    document_ref="document:demo",
                    slots=(
                        PartialPNFSlot(
                            slot_ref="slot:subject",
                            slot_kind="subject",
                            mention_ref="mention:other",
                            expected_semantic_families=("entity",),
                            closure_requirement="external_identity",
                        ),
                    ),
                )
            ],
        )


def test_types_resolution_subjects_before_semantic_demand_deduplication() -> None:
    mentions = [
        _mention("mention:bush", 0, 4, "Bush"),
        _mention("mention:attack", 5, 9, "9/11"),
    ]
    local_types = [
        {
            "type_ref": "local-type:bush-person",
            "mention_ref": "mention:bush",
            "semantic_family": "entity",
            "local_type": "person",
            "derivation_basis": "profile_local_typing",
            "evidence_refs": ["profile:people@1"],
        },
        {
            "type_ref": "local-type:attack-eventuality",
            "mention_ref": "mention:attack",
            "semantic_family": "eventuality",
            "local_type": "bounded_event",
            "derivation_basis": "profile_local_typing",
            "evidence_refs": ["profile:events@1"],
        },
    ]
    partial = build_partial_pnf_carrier(
        mentions=mentions,
        local_type_alternatives=local_types,
        partial_pnfs=[
            PartialPNF(
                pnf_ref="pnf:bush:one",
                document_ref="document:demo",
                slots=(
                    PartialPNFSlot(
                        slot_ref="slot:bush:one",
                        slot_kind="subject",
                        mention_ref="mention:bush",
                        expected_semantic_families=("entity",),
                        closure_requirement="external_identity",
                    ),
                ),
            ),
            PartialPNF(
                pnf_ref="pnf:bush:two",
                document_ref="document:demo",
                slots=(
                    PartialPNFSlot(
                        slot_ref="slot:bush:two",
                        slot_kind="subject",
                        mention_ref="mention:bush",
                        expected_semantic_families=("entity",),
                        closure_requirement="external_identity",
                    ),
                ),
            ),
            PartialPNF(
                pnf_ref="pnf:event:occurrence",
                document_ref="document:demo",
                slots=(
                    PartialPNFSlot(
                        slot_ref="slot:event:occurrence",
                        slot_kind="eventuality",
                        mention_ref="mention:attack",
                        expected_semantic_families=("eventuality",),
                        closure_requirement="external_identity",
                    ),
                ),
            ),
            PartialPNF(
                pnf_ref="pnf:event:observation",
                document_ref="document:demo",
                slots=(
                    PartialPNFSlot(
                        slot_ref="slot:event:observation",
                        slot_kind="eventuality",
                        mention_ref="mention:attack",
                        expected_semantic_families=("eventuality",),
                        closure_requirement="external_identity",
                    ),
                ),
            ),
        ],
    )
    demands = build_resolution_demand_carrier(partial_pnf_carrier=partial)
    demand_by_pnf = {row["pnf_ref"]: row["demand_ref"] for row in demands["demands"]}
    shared_time_payload = {"start": "2001-01-01", "end": "2009-01-20"}
    declarations = [
        ResolutionSubjectDeclaration(
            declaration_ref="subject-declaration:bush:one",
            demand_ref=demand_by_pnf["pnf:bush:one"],
            target_ref="local-cluster:bush",
            subject_kind="entity",
            constraints=(
                ResolutionConstraint(
                    constraint_ref="constraint:bush:one:time",
                    constraint_kind="temporal",
                    payload=shared_time_payload,
                    evidence_refs=("source:one",),
                ),
            ),
        ),
        ResolutionSubjectDeclaration(
            declaration_ref="subject-declaration:bush:two",
            demand_ref=demand_by_pnf["pnf:bush:two"],
            target_ref="local-cluster:bush",
            subject_kind="entity",
            constraints=(
                ResolutionConstraint(
                    constraint_ref="constraint:bush:two:time",
                    constraint_kind="temporal",
                    payload=shared_time_payload,
                    evidence_refs=("source:two",),
                ),
            ),
        ),
        ResolutionSubjectDeclaration(
            declaration_ref="subject-declaration:event:occurrence",
            demand_ref=demand_by_pnf["pnf:event:occurrence"],
            target_ref="local-event:9-11",
            subject_kind="event_occurrence",
            formal_role="occurrence",
        ),
        ResolutionSubjectDeclaration(
            declaration_ref="subject-declaration:event:observation",
            demand_ref=demand_by_pnf["pnf:event:observation"],
            target_ref="local-event:9-11",
            subject_kind="event_artifact",
            formal_role="observation",
        ),
    ]

    carrier = build_resolution_subject_carrier(
        partial_pnf_carrier=partial,
        resolution_demand_carrier=demands,
        subject_declarations=declarations,
    )

    assert carrier["authority"] == "candidate_only"
    assert carrier["deduplication_effect"] == "receipt_only"
    assert carrier["backend_effect"] == "none"
    assert carrier["resolution_effect"] == "none"
    assert carrier["pnf_effect"] == "none"
    assert carrier["summary"] == {
        "demand_count": 4,
        "resolution_subject_count": 4,
        "equivalence_group_count": 3,
        "coalescible_demand_count": 1,
        "grouped_equivalence_count": 1,
    }
    grouped = [
        group for group in carrier["equivalence_groups"] if group["member_count"] == 2
    ]
    assert len(grouped) == 1
    assert set(grouped[0]["member_demand_refs"]) == {
        demand_by_pnf["pnf:bush:one"],
        demand_by_pnf["pnf:bush:two"],
    }
    event_subjects = {
        subject.get("formal_role"): subject["subject_kind"]
        for subject in carrier["resolution_subjects"]
        if subject["target_ref"] == "local-event:9-11"
    }
    assert event_subjects == {
        "occurrence": "event_occurrence",
        "observation": "event_artifact",
    }
    assert carrier == build_resolution_subject_carrier(
        partial_pnf_carrier=partial,
        resolution_demand_carrier=demands,
        subject_declarations=list(reversed(declarations)),
    )
    divergent_declarations = [
        declarations[0],
        ResolutionSubjectDeclaration(
            declaration_ref="subject-declaration:bush:two",
            demand_ref=demand_by_pnf["pnf:bush:two"],
            target_ref="local-cluster:bush",
            subject_kind="entity",
            constraints=(
                ResolutionConstraint(
                    constraint_ref="constraint:bush:two:time",
                    constraint_kind="temporal",
                    payload={"start": "1989-01-20", "end": "1993-01-20"},
                    evidence_refs=("source:two",),
                ),
            ),
        ),
        *declarations[2:],
    ]
    divergent = build_resolution_subject_carrier(
        partial_pnf_carrier=partial,
        resolution_demand_carrier=demands,
        subject_declarations=divergent_declarations,
    )
    assert divergent["summary"]["equivalence_group_count"] == 4
    assert divergent["summary"]["coalescible_demand_count"] == 0


def test_resolution_subjects_reject_event_role_collapse() -> None:
    with pytest.raises(ValueError, match="occurrence formal role"):
        ResolutionSubjectDeclaration(
            declaration_ref="subject-declaration:bad-occurrence",
            demand_ref="demand:one",
            target_ref="event:one",
            subject_kind="event_occurrence",
            formal_role="observation",
        ).to_dict()


def test_resolution_schedule_is_cache_aware_and_identity_blind() -> None:
    partial = build_partial_pnf_carrier(
        mentions=[_mention("mention:bush", 0, 4, "Bush")],
        local_type_alternatives=[
            LocalTypeAlternative(
                type_ref="type:bush:entity",
                mention_ref="mention:bush",
                semantic_family="entity",
                local_type="proper_name",
                derivation_basis="test",
                evidence_refs=("source:demo",),
            )
        ],
        partial_pnfs=[
            PartialPNF(
                pnf_ref="pnf:bush",
                document_ref="document:demo",
                slots=(
                    PartialPNFSlot(
                        slot_ref="slot:bush",
                        slot_kind="subject",
                        mention_ref="mention:bush",
                        expected_semantic_families=("entity",),
                        closure_requirement="external_identity",
                    ),
                ),
            ),
        ],
    )
    demands = build_resolution_demand_carrier(partial_pnf_carrier=partial)
    demand_ref = demands["demands"][0]["demand_ref"]
    subjects = build_resolution_subject_carrier(
        partial_pnf_carrier=partial,
        resolution_demand_carrier=demands,
        subject_declarations=[
            ResolutionSubjectDeclaration(
                declaration_ref="declaration:bush",
                demand_ref=demand_ref,
                target_ref="local:bush",
                subject_kind="entity",
            )
        ],
    )
    group = subjects["equivalence_groups"][0]
    cache_key = f"resolution:{group['semantic_key_sha256']}"
    plan = build_resolution_schedule_carrier(
        resolution_subject_carrier=subjects,
        cache_entries=[
            ResolutionCacheEntry(
                cache_key=cache_key,
                backend_ref="local",
                cache_state="fresh",
                evidence_ref="evidence:local:bush",
                provenance_refs=("source:demo",),
            )
        ],
        backend_capabilities=[
            ResolutionBackendCapability(
                backend_ref="wikidata",
                subject_kinds=("entity",),
                facets=("identity",),
            )
        ],
    )
    assert plan["plans"][0]["state"] == "fresh_cache_hit"
    assert plan["backend_effect"] == "plan_only"
    assert plan["resolution_effect"] == "none"


def test_resolution_schedule_reports_unavailable_and_batches_deterministically() -> (
    None
):
    entry = ResolutionBackendCapability(
        backend_ref="local",
        subject_kinds=("entity",),
        facets=("identity",),
        available=False,
    )
    assert entry.to_dict()["available"] is False
    with pytest.raises(ValueError, match="positive cache entries"):
        ResolutionCacheEntry(
            cache_key="k", backend_ref="local", cache_state="fresh"
        ).to_dict()
    with pytest.raises(ValueError, match="artifact formal role"):
        ResolutionSubjectDeclaration(
            declaration_ref="subject-declaration:bad-artifact",
            demand_ref="demand:two",
            target_ref="event:two",
            subject_kind="event_artifact",
            formal_role="occurrence",
        ).to_dict()


def test_candidate_retrieval_rejects_unprovenanced_or_decided_catalog_entries() -> None:
    with pytest.raises(ValueError, match="evidence references"):
        CandidateCatalogEntry(
            catalog_entry_ref="catalog:no-evidence",
            candidate_kind="instance",
            identity_ref="external:missing",
            label="Missing evidence",
            match_token_sequences=(("Missing",),),
            evidence_refs=(),
        ).to_dict()

    with pytest.raises(ValueError, match="resolution or promotion state"):
        build_candidate_retrieval_carrier(
            mentions=[_mention("mention:bush", 0, 4, "Bush")],
            catalog_entries=[
                {
                    "catalog_entry_ref": "catalog:bad",
                    "candidate_kind": "instance",
                    "identity_ref": "external:bush",
                    "label": "Bush",
                    "match_token_sequences": [["Bush"]],
                    "evidence_refs": ["catalog:demo@1"],
                    "selected_candidate_ref": "external:bush",
                }
            ],
        )
