from __future__ import annotations


def test_mapper_metadata_is_stable() -> None:
    from src.nlp.synset_mapper import DeterministicSynsetActionMapper

    m = DeterministicSynsetActionMapper(
        resource="babelnet",
        wsd_policy="rule_deterministic",
        version_pins={"babelnet": "2024-01"},
        synset_action_map={"bn:x": "died"},
        babelnet_lemma_synsets={"perish": ["bn:x"]},
    )
    assert m.metadata() == m.metadata()


def test_mapper_does_not_depend_on_synset_map_iteration_order() -> None:
    from src.nlp.synset_mapper import DeterministicSynsetActionMapper

    # Single-action mapping so canonical path selects deterministically.
    synset_action_map_a = {"bn:0002": "died", "bn:0009": "died"}
    synset_action_map_b = {"bn:0009": "died", "bn:0002": "died"}  # reversed insertion order

    m1 = DeterministicSynsetActionMapper(
        resource="babelnet",
        wsd_policy="rule_deterministic",
        version_pins={},
        synset_action_map=synset_action_map_a,
        babelnet_lemma_synsets={"perish": ["bn:0009", "bn:0002"]},
    )
    m2 = DeterministicSynsetActionMapper(
        resource="babelnet",
        wsd_policy="rule_deterministic",
        version_pins={},
        synset_action_map=synset_action_map_b,
        babelnet_lemma_synsets={"perish": ["bn:0009", "bn:0002"]},
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
    assert (a1.action_label, a1.synset_id) == (a2.action_label, a2.synset_id)
