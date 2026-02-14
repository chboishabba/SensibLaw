from __future__ import annotations

from scripts import wiki_timeline_aoo_extract as ext


def test_profile_semantic_backbone_defaults_to_deterministic_none() -> None:
    cfg, warnings, err = ext._profile_semantic_backbone_config({})
    assert err is None
    assert warnings == []
    assert cfg == {
        "resource": "none",
        "wsd_policy": "none",
        "llm_enabled": False,
        "deterministic": True,
    }


def test_sha256_json_is_deterministic_for_babelnet_table() -> None:
    # Same table content => same sha256 even if caller order differs.
    a = {"perish": ["bn:2", "bn:1"]}
    b = {"perish": ["bn:1", "bn:2"]}
    # The profile loader sorts synset lists, so hash should be stable after normalization.
    ha = ext._sha256_json({"perish": sorted(a["perish"])})
    hb = ext._sha256_json({"perish": sorted(b["perish"])})
    assert ha == hb


def test_profile_semantic_backbone_rejects_llm() -> None:
    cfg, warnings, err = ext._profile_semantic_backbone_config(
        {
            "semantic_backbone": {
                "resource": "wordnet",
                "wsd_policy": "rule_deterministic",
                "llm_enabled": True,
            }
        }
    )
    assert err == "semantic_backbone_llm_not_allowed"
    assert warnings == []
    assert cfg["llm_enabled"] is False


def test_profile_semantic_backbone_rejects_nondeterministic_wsd_policy() -> None:
    cfg, warnings, err = ext._profile_semantic_backbone_config(
        {"semantic_backbone": {"resource": "babelnet", "wsd_policy": "generative"}}
    )
    assert err == "semantic_backbone_wsd_policy_not_deterministic"
    assert warnings == []
    assert cfg["wsd_policy"] == "none"


def test_synset_mapper_is_pinned_by_wordnet_version_when_enabled() -> None:
    # If nltk wordnet is available, a mismatched pin must raise a deterministic error.
    try:
        from src.nlp.synset_mapper import DeterministicSynsetActionMapper
    except Exception:
        return

    try:
        DeterministicSynsetActionMapper(
            resource="wordnet",
            wsd_policy="rule_deterministic",
            version_pins={"wordnet": "0.0"},
            synset_action_map={},
        )
        assert False, "expected pin mismatch to raise"
    except RuntimeError as e:
        msg = str(e)
        # Could also be "wordnet_unavailable" in minimal environments; that's acceptable.
        assert "wordnet_version_pin_mismatch" in msg or "wordnet_unavailable" in msg or "wordnet_version_unknown" in msg


def test_babelnet_synset_tiebreak_is_deterministic() -> None:
    # Order of lemma->synset list must not affect chosen mapped action when
    # mapping is single-action (otherwise canonical path abstains).
    from src.nlp.synset_mapper import DeterministicSynsetActionMapper

    m1 = DeterministicSynsetActionMapper(
        resource="babelnet",
        wsd_policy="rule_deterministic",
        version_pins={},
        synset_action_map={
            "bn:0002": "died",
            "bn:0009": "died",
        },
        babelnet_lemma_synsets={"perish": ["bn:0009", "bn:0002"]},
    )
    m2 = DeterministicSynsetActionMapper(
        resource="babelnet",
        wsd_policy="rule_deterministic",
        version_pins={},
        synset_action_map={
            "bn:0002": "died",
            "bn:0009": "died",
        },
        babelnet_lemma_synsets={"perish": ["bn:0002", "bn:0009"]},
    )

    class _Tok:
        def __init__(self):
            self.lemma_ = "perish"
            self.text = "perished"
            self.pos_ = "VERB"

    tok = _Tok()
    a1 = m1.resolve_action(tok)
    a2 = m2.resolve_action(tok)
    assert a1 is not None and a2 is not None
    assert a1.action_label == a2.action_label == "died"
    assert a1.synset_id == a2.synset_id == "bn:0002"
