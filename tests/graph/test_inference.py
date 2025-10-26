from __future__ import annotations

from pathlib import Path

import pytest

import src.graph.inference as inference
from src.graph.inference import (
    PredictionSet,
    RawPrediction,
    PredictionRecord,
    build_prediction_set,
    legal_graph_to_triples,
    load_predictions_json,
    load_predictions_sqlite,
    persist_predictions_json,
    persist_predictions_sqlite,
    rank_predictions,
    score_applies_predictions,
    train_transe,
    train_complex,
    train_distmult,
    train_mure,
    train_rotate,
)
from src.graph.models import EdgeType, GraphEdge, GraphNode, LegalGraph, NodeType


class DummyModel:
    def __init__(self, score: float) -> None:
        self.score = score
        self.last_batch = None

    def score_hrt(self, batch):  # noqa: ANN001 - duck-typed to avoid torch import
        self.last_batch = batch
        return [self.score]


class DummyTriplesFactory:
    def __init__(self, triples) -> None:
        self.triples = triples
        self.entity_to_id = {"case-1": 0, "prov-1": 1}
        self.relation_to_id = {EdgeType.APPLIES.value: 0}

    @classmethod
    def from_labeled_triples(cls, triples):  # noqa: D401 - pykeen signature
        return cls(triples)


class DummyPipelineResult:
    def __init__(self, model: DummyModel) -> None:
        self.model = model


def test_legal_graph_to_triples_includes_relation_labels() -> None:
    graph = LegalGraph()
    graph.add_node(GraphNode(type=NodeType.CASE, identifier="case-1"))
    graph.add_node(GraphNode(type=NodeType.PROVISION, identifier="prov-1"))
    graph.add_edge(
        GraphEdge(
            type=EdgeType.APPLIES,
            source="case-1",
            target="prov-1",
            metadata={"label": "applies relationship"},
        )
    )

    triples = legal_graph_to_triples(graph)
    assert triples.triples == [("case-1", EdgeType.APPLIES.value, "prov-1")]
    assert triples.relation_labels == ["applies relationship"]


def test_train_transe_and_score_predictions(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded = {}

    def fake_pipeline(**kwargs):  # noqa: ANN001
        recorded.update(kwargs)
        return DummyPipelineResult(DummyModel(0.875))

    def fake_import() -> tuple:
        return fake_pipeline, DummyTriplesFactory

    monkeypatch.setattr(inference, "_import_pykeen_components", fake_import)
    monkeypatch.setattr(inference, "_as_labeled_triples", lambda triples: triples)

    triples = [("case-1", EdgeType.APPLIES.value, "prov-1")]
    artifacts = train_transe(
        triples,
        training_kwargs={"num_epochs": 10},
        optimizer_kwargs={"lr": 0.1},
    )

    assert recorded["model"] == "TransE"
    assert recorded["training_kwargs"]["num_epochs"] == 10
    assert isinstance(artifacts.pipeline_result, DummyPipelineResult)

    scores = score_applies_predictions(
        artifacts.pipeline_result,
        artifacts.triples_factory,
        cases=["case-1"],
        provisions=["prov-1"],
        relation=EdgeType.APPLIES.value,
    )
    assert scores == [RawPrediction(case_id="case-1", provision_id="prov-1", score=0.875)]


@pytest.mark.parametrize(
    "trainer, expected_model",
    [
        (train_transe, "TransE"),
        (train_distmult, "DistMult"),
        (train_complex, "ComplEx"),
        (train_rotate, "RotatE"),
        (train_mure, "MuRE"),
    ],
)
def test_train_wrappers_select_models(
    trainer, expected_model, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorded = {}

    def fake_pipeline(**kwargs):  # noqa: ANN001
        recorded.update(kwargs)
        return DummyPipelineResult(DummyModel(0.875))

    def fake_import() -> tuple:
        return fake_pipeline, DummyTriplesFactory

    monkeypatch.setattr(inference, "_import_pykeen_components", fake_import)
    monkeypatch.setattr(inference, "_as_labeled_triples", lambda triples: triples)

    triples = [("case-1", EdgeType.APPLIES.value, "prov-1")]
    trainer(triples)

    assert recorded["model"] == expected_model


def test_build_prediction_set_marks_determinism() -> None:
    ranked = [
        PredictionRecord(
            case_id="case-1",
            provision_id="prov-1",
            score=1.0,
            rank=1,
            relation=EdgeType.APPLIES.value,
        )
    ]

    deterministic = build_prediction_set(
        ranked,
        relation=EdgeType.APPLIES.value,
        generated_at="2024-01-01T00:00:00+00:00",
        random_seed=42,
    )
    assert deterministic.non_deterministic is False

    synthesized = build_prediction_set(
        ranked,
        relation=EdgeType.APPLIES.value,
        random_seed=42,
    )
    assert synthesized.non_deterministic is True

    no_seed = build_prediction_set(
        ranked,
        relation=EdgeType.APPLIES.value,
        generated_at="2024-01-01T00:00:00+00:00",
    )
    assert no_seed.non_deterministic is True


def test_prediction_persistence_roundtrip(tmp_path: Path) -> None:
    raw_predictions = [
        RawPrediction(case_id="case-1", provision_id="prov-1", score=0.9),
        RawPrediction(case_id="case-1", provision_id="prov-2", score=0.4),
        RawPrediction(case_id="case-2", provision_id="prov-1", score=0.7),
    ]
    ranked = rank_predictions(raw_predictions, relation=EdgeType.APPLIES.value, top_k=2)
    prediction_set = build_prediction_set(
        ranked,
        relation=EdgeType.APPLIES.value,
        generated_at="2024-01-01T00:00:00Z",
        random_seed=7,
    )

    json_path = tmp_path / "predictions.json"
    sqlite_path = tmp_path / "predictions.sqlite"

    persist_predictions_json(prediction_set, json_path)
    loaded_json = load_predictions_json(json_path)
    assert loaded_json == PredictionSet(
        relation=EdgeType.APPLIES.value,
        generated_at="2024-01-01T00:00:00Z",
        predictions=prediction_set.predictions,
        non_deterministic=False,
    )

    persist_predictions_sqlite(prediction_set, sqlite_path)
    loaded_sqlite = load_predictions_sqlite(sqlite_path, relation=EdgeType.APPLIES.value)
    assert loaded_sqlite == PredictionSet(
        relation=EdgeType.APPLIES.value,
        generated_at="2024-01-01T00:00:00Z",
        predictions=prediction_set.predictions,
        non_deterministic=False,
    )
