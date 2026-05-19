from __future__ import annotations

from src.semantic_memory import build_semantic_memory_index, retrieve_semantic_memory


def _grounding_catalog() -> dict:
    return {
        "groundings": {
            "great dane": [
                {
                    "grounded_node": "QGreatDane",
                    "grounded_label": "Great Dane",
                    "grounding_residual": "exact_grounding",
                    "topic_closure": [
                        {
                            "topic_id": "QGreatDane",
                            "topic_label": "Great Dane",
                            "ontology_path": ["Great Dane"],
                            "topic_depth": 0,
                        },
                        {
                            "topic_id": "QDogBreed",
                            "topic_label": "dog breed",
                            "ontology_path": ["Great Dane", "dog breed"],
                            "relation_path": ["P31/P279 closure"],
                            "topic_depth": 1,
                        },
                        {
                            "topic_id": "QDog",
                            "topic_label": "dog",
                            "ontology_path": ["Great Dane", "dog breed", "dog"],
                            "relation_path": ["P31/P279 closure"],
                            "topic_depth": 2,
                        },
                    ],
                }
            ],
            "dogs": [
                {
                    "grounded_node": "QDog",
                    "grounded_label": "dog",
                    "grounding_residual": "exact_grounding",
                    "topic_closure": [
                        {
                            "topic_id": "QDog",
                            "topic_label": "dog",
                            "ontology_path": ["dog"],
                            "topic_depth": 0,
                        }
                    ],
                }
            ],
            "park": [
                {
                    "grounded_node": "QPark",
                    "grounded_label": "park",
                    "grounding_residual": "partial_grounding",
                    "topic_closure": [
                        {
                            "topic_id": "QPark",
                            "topic_label": "park",
                            "ontology_path": ["park"],
                            "topic_depth": 0,
                        }
                    ],
                }
            ],
        }
    }


def test_semantic_memory_retrieves_great_dane_note_for_dog_query() -> None:
    documents = [
        {
            "doc_id": "note_2026_05_06",
            "source_type": "note",
            "segments": [
                {
                    "segment_id": "note_2026_05_06:s1",
                    "text": "I went to the park today and saw a great dane.",
                    "atoms": [
                        {
                            "atom_id": "a1",
                            "predicate": "saw",
                            "roles": {
                                "experiencer": "speaker",
                                "observed": "great dane",
                                "location": "park",
                            },
                            "wrapper_state": "asserted_personal_observation",
                            "qualifiers": {"time": "today"},
                        }
                    ],
                    "wrapper_state": "asserted_personal_observation",
                }
            ],
            "provenance": {"source": "personal_note"},
        }
    ]

    index = build_semantic_memory_index(
        documents=documents,
        grounding_catalog=_grounding_catalog(),
        ontology_snapshot_id="wikidata_snapshot_test",
    )
    result = retrieve_semantic_memory(
        query="Where else in my notes do I talk about dogs?",
        memory_index=index,
        grounding_catalog=_grounding_catalog(),
    )

    assert index["schema_version"] == "sl.semantic_memory_index.v0_1"
    assert index["authority_boundary"]["private_memory_index"] is True
    assert index["authority_boundary"]["public_wikidata_claim"] is False
    assert result["match_count"] == 1
    match = result["matches"][0]
    assert match["doc_id"] == "note_2026_05_06"
    assert match["matched_span"] == "great dane"
    assert match["grounded_node"] == "QGreatDane"
    assert match["wrapper_state"] == "asserted_personal_observation"
    dog_path = next(path for path in match["explanation_paths"] if path["topic_id"] == "QDog")
    assert dog_path["ontology_path"] == ["Great Dane", "dog breed", "dog"]


def test_semantic_memory_can_filter_by_wrapper_without_public_claims() -> None:
    documents = [
        {
            "doc_id": "question_note",
            "text": "Did I see a great dane?",
            "atoms": [
                {
                    "atom_id": "a1",
                    "predicate": "saw",
                    "roles": {"observed": "great dane"},
                    "wrapper_state": "question",
                }
            ],
            "wrapper_state": "question",
        }
    ]
    index = build_semantic_memory_index(
        documents=documents,
        grounding_catalog=_grounding_catalog(),
        ontology_snapshot_id="wikidata_snapshot_test",
    )

    assert retrieve_semantic_memory(
        query="Where did I actually see dogs?",
        memory_index=index,
        grounding_catalog=_grounding_catalog(),
        require_wrapper_state="asserted_personal_observation",
    )["match_count"] == 0
    unfiltered = retrieve_semantic_memory(
        query="Where do I mention dogs?",
        memory_index=index,
        grounding_catalog=_grounding_catalog(),
    )
    assert unfiltered["match_count"] == 1
    assert unfiltered["authority_boundary"]["no_belief_inference"] is True
