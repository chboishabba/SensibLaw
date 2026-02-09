"""Knowledge graph inference helpers built on top of PyKEEN."""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .models import EdgeType, LegalGraph, NodeType


@dataclass(frozen=True)
class TriplePack:
    """Container for triples and their accompanying relation labels."""

    triples: List[Tuple[str, str, str]]
    relation_labels: List[str]

    def iter_with_labels(self) -> Iterable[Tuple[Tuple[str, str, str], str]]:
        """Iterate over triples alongside their human readable labels."""

        return zip(self.triples, self.relation_labels)


@dataclass(frozen=True)
class TrainingArtifacts:
    """Outcome of a PyKEEN training run."""

    model_name: str
    pipeline_result: Any
    triples_factory: Any


@dataclass(frozen=True)
class RawPrediction:
    """Unranked prediction score for a case/provision pair."""

    case_id: str
    provision_id: str
    score: float


@dataclass(frozen=True)
class PredictionRecord:
    """Ranked prediction for persistence and display."""

    case_id: str
    provision_id: str
    score: float
    rank: int
    relation: str


@dataclass(frozen=True)
class PredictionSet:
    """Collection of ranked predictions with shared metadata."""

    relation: str
    generated_at: str
    predictions: List[PredictionRecord]
    non_deterministic: bool = True

    def for_case(self, case_id: str, *, top_k: Optional[int] = None) -> List[PredictionRecord]:
        """Return ranked predictions for ``case_id`` limited to ``top_k`` results."""

        items = [prediction for prediction in self.predictions if prediction.case_id == case_id]
        if top_k is not None:
            return items[:top_k]
        return items


@dataclass(frozen=True)
class SemanticRecommendation:
    """Recommendation for an ontology entity (Milestones 3–5)."""

    identifier: str
    node_type: NodeType
    score: float
    rationale: str


@dataclass(frozen=True)
class SemanticRecommendations:
    """Bundle of semantic recommendations across ontology layers."""

    wrong_types: List[SemanticRecommendation]
    protected_interests: List[SemanticRecommendation]
    events: List[SemanticRecommendation]
    remedies: List[SemanticRecommendation]


PREDICTION_VERSION = 1


def _relation_label(edge: Any) -> str:
    metadata = getattr(edge, "metadata", None) or {}
    for key in ("label", "relation", "name"):
        value = metadata.get(key)
        if value:
            return str(value)
    return edge.type.value if hasattr(edge, "type") else str(metadata.get("type", ""))


def _external_ref_targets(metadata: Mapping[str, object]) -> Iterable[str]:
    refs = metadata.get("external_refs", [])
    if isinstance(refs, Mapping):
        refs = [refs]
    if not isinstance(refs, Iterable) or isinstance(refs, (str, bytes)):
        return []

    targets: List[str] = []
    url_prefix = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")
    for ref in refs:
        if isinstance(ref, str):
            targets.append(ref)
            continue
        if not isinstance(ref, Mapping):
            continue
        provider = ref.get("provider") or ref.get("source")
        external_id = ref.get("external_id") or ref.get("id") or ref.get("identifier")
        if external_id is None:
            continue
        target = str(external_id).strip()
        if not target:
            continue

        provider_text = str(provider).rstrip(":") if provider else ""
        provider_lower = provider_text.lower() if provider_text else ""

        # If the external_id is already a URL/IRI, keep it as-is (important for DBpedia).
        if url_prefix.match(target):
            targets.append(target)
            continue

        # If the identifier is already a CURIE (e.g., wikidata:Q42), keep it.
        if provider_lower and target.lower().startswith(f"{provider_lower}:"):
            targets.append(target)
            continue

        if provider_lower == "wikidata":
            # Canonicalize to a consistent CURIE form.
            targets.append(f"wikidata:{target}")
            continue

        if provider_text:
            targets.append(f"{provider_text}:{target}")
            continue

        targets.append(target)
    return targets


def legal_graph_to_triples(
    graph: LegalGraph, *, include_external_refs: bool = False
) -> TriplePack:
    """Convert the in-memory ``graph`` into PyKEEN compatible triples."""

    triples: List[Tuple[str, str, str]] = []
    labels: List[str] = []
    for edge in graph.edges:
        triples.append((edge.source, edge.type.value, edge.target))
        labels.append(_relation_label(edge))

    if include_external_refs:
        for node in graph.nodes.values():
            targets = _external_ref_targets(node.metadata)
            if not targets:
                continue
            predicates = ["owl:sameAs"]
            if node.type == NodeType.CONCEPT:
                predicates.append("skos:exactMatch")
            for target in targets:
                for predicate in predicates:
                    triples.append((node.identifier, predicate, target))
                    labels.append(predicate)

    return TriplePack(triples=triples, relation_labels=labels)


def _collect_corpus(graph: LegalGraph) -> str:
    """Collect textual metadata from nodes to use for heuristic scoring."""

    parts: List[str] = []
    for node in graph.nodes.values():
        parts.append(str(node.identifier))
        metadata = getattr(node, "metadata", {}) or {}
        for value in metadata.values():
            if isinstance(value, str):
                parts.append(value)
    return " \n".join(parts).lower()


def _score_catalog(
    *,
    catalog: Mapping[str, Iterable[str]],
    corpus: str,
    node_type: NodeType,
    base_score: float = 0.1,
    rationale_prefix: str,
) -> List[SemanticRecommendation]:
    recommendations: List[SemanticRecommendation] = []
    for identifier, keywords in catalog.items():
        tokens = list(keywords) or [identifier]
        score = sum(corpus.count(token.lower()) for token in tokens)
        if score == 0:
            score = base_score
        rationale = f"{rationale_prefix}: matched {', '.join(tokens)}"
        recommendations.append(
            SemanticRecommendation(
                identifier=identifier,
                node_type=node_type,
                score=float(score),
                rationale=rationale,
            )
        )
    recommendations.sort(key=lambda rec: rec.score, reverse=True)
    return recommendations


def get_case_identifiers(graph: LegalGraph) -> List[str]:
    """Return sorted identifiers for case nodes in ``graph``."""

    return sorted(
        identifier
        for identifier, node in graph.nodes.items()
        if getattr(node, "type", None) == NodeType.CASE
    )


def get_provision_identifiers(graph: LegalGraph) -> List[str]:
    """Return sorted identifiers for provision-like nodes in ``graph``."""

    provision_types = {NodeType.PROVISION, NodeType.STATUTE_SECTION}
    return sorted(
        identifier
        for identifier, node in graph.nodes.items()
        if getattr(node, "type", None) in provision_types
    )


def _import_pykeen_components() -> Tuple[Callable[..., Any], Any]:
    try:  # pragma: no cover - exercised via unit tests with monkeypatching
        from pykeen.pipeline import pipeline
        from pykeen.triples import TriplesFactory
    except ImportError as exc:  # pragma: no cover - handled by CLI/tests
        raise RuntimeError(
            "PyKEEN is required for graph inference but is not installed."
        ) from exc
    return pipeline, TriplesFactory


def _as_labeled_triples(triples: Sequence[Tuple[str, str, str]]):
    if not triples:
        raise ValueError("At least one triple is required for training")
    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover - surfaced to caller
        raise RuntimeError("NumPy is required to build triples for PyKEEN") from exc
    return np.array(triples, dtype=str)


def _train_model(
    *,
    model_name: str,
    triples: Sequence[Tuple[str, str, str]],
    training_kwargs: Optional[Dict[str, Any]] = None,
    model_kwargs: Optional[Dict[str, Any]] = None,
    optimizer_kwargs: Optional[Dict[str, Any]] = None,
    loss_kwargs: Optional[Dict[str, Any]] = None,
    random_seed: Optional[int] = None,
) -> TrainingArtifacts:
    pipeline, triples_factory_cls = _import_pykeen_components()
    labeled = _as_labeled_triples(triples)
    triples_factory = triples_factory_cls.from_labeled_triples(labeled)

    pipeline_kwargs: Dict[str, Any] = {
        "model": model_name,
        "training": triples_factory,
    }
    if training_kwargs:
        pipeline_kwargs["training_kwargs"] = training_kwargs
    if model_kwargs:
        pipeline_kwargs["model_kwargs"] = model_kwargs
    if optimizer_kwargs:
        pipeline_kwargs["optimizer_kwargs"] = optimizer_kwargs
    if loss_kwargs:
        pipeline_kwargs["loss_kwargs"] = loss_kwargs
    if random_seed is not None:
        pipeline_kwargs["random_seed"] = random_seed

    result = pipeline(**pipeline_kwargs)
    return TrainingArtifacts(
        model_name=model_name,
        pipeline_result=result,
        triples_factory=triples_factory,
    )


def train_transe(
    triples: Sequence[Tuple[str, str, str]],
    *,
    training_kwargs: Optional[Dict[str, Any]] = None,
    model_kwargs: Optional[Dict[str, Any]] = None,
    optimizer_kwargs: Optional[Dict[str, Any]] = None,
    loss_kwargs: Optional[Dict[str, Any]] = None,
    random_seed: Optional[int] = None,
) -> TrainingArtifacts:
    """Train a TransE embedding model using the supplied ``triples``."""

    return _train_model(
        model_name="TransE",
        triples=triples,
        training_kwargs=training_kwargs,
        model_kwargs=model_kwargs,
        optimizer_kwargs=optimizer_kwargs,
        loss_kwargs=loss_kwargs,
        random_seed=random_seed,
    )


def train_distmult(
    triples: Sequence[Tuple[str, str, str]],
    *,
    training_kwargs: Optional[Dict[str, Any]] = None,
    model_kwargs: Optional[Dict[str, Any]] = None,
    optimizer_kwargs: Optional[Dict[str, Any]] = None,
    loss_kwargs: Optional[Dict[str, Any]] = None,
    random_seed: Optional[int] = None,
) -> TrainingArtifacts:
    """Train a DistMult embedding model using the supplied ``triples``."""

    return _train_model(
        model_name="DistMult",
        triples=triples,
        training_kwargs=training_kwargs,
        model_kwargs=model_kwargs,
        optimizer_kwargs=optimizer_kwargs,
        loss_kwargs=loss_kwargs,
        random_seed=random_seed,
    )


def train_complex(
    triples: Sequence[Tuple[str, str, str]],
    *,
    training_kwargs: Optional[Dict[str, Any]] = None,
    model_kwargs: Optional[Dict[str, Any]] = None,
    optimizer_kwargs: Optional[Dict[str, Any]] = None,
    loss_kwargs: Optional[Dict[str, Any]] = None,
    random_seed: Optional[int] = None,
) -> TrainingArtifacts:
    """Train a ComplEx embedding model using the supplied ``triples``."""

    return _train_model(
        model_name="ComplEx",
        triples=triples,
        training_kwargs=training_kwargs,
        model_kwargs=model_kwargs,
        optimizer_kwargs=optimizer_kwargs,
        loss_kwargs=loss_kwargs,
        random_seed=random_seed,
    )


def train_rotate(
    triples: Sequence[Tuple[str, str, str]],
    *,
    training_kwargs: Optional[Dict[str, Any]] = None,
    model_kwargs: Optional[Dict[str, Any]] = None,
    optimizer_kwargs: Optional[Dict[str, Any]] = None,
    loss_kwargs: Optional[Dict[str, Any]] = None,
    random_seed: Optional[int] = None,
) -> TrainingArtifacts:
    """Train a RotatE embedding model using the supplied ``triples``."""

    return _train_model(
        model_name="RotatE",
        triples=triples,
        training_kwargs=training_kwargs,
        model_kwargs=model_kwargs,
        optimizer_kwargs=optimizer_kwargs,
        loss_kwargs=loss_kwargs,
        random_seed=random_seed,
    )


def train_mure(
    triples: Sequence[Tuple[str, str, str]],
    *,
    training_kwargs: Optional[Dict[str, Any]] = None,
    model_kwargs: Optional[Dict[str, Any]] = None,
    optimizer_kwargs: Optional[Dict[str, Any]] = None,
    loss_kwargs: Optional[Dict[str, Any]] = None,
    random_seed: Optional[int] = None,
) -> TrainingArtifacts:
    """Train a MuRE embedding model using the supplied ``triples``."""

    return _train_model(
        model_name="MuRE",
        triples=triples,
        training_kwargs=training_kwargs,
        model_kwargs=model_kwargs,
        optimizer_kwargs=optimizer_kwargs,
        loss_kwargs=loss_kwargs,
        random_seed=random_seed,
    )


def _to_score(value: Any) -> float:
    if hasattr(value, "detach"):
        tensor = value.detach()
        if hasattr(tensor, "cpu"):
            tensor = tensor.cpu()
        array = tensor.view(-1)
        if array.numel():
            return float(array[0].item())
    if hasattr(value, "tolist"):
        data = value.tolist()
        if isinstance(data, list) and data:
            return float(data[0])
    if isinstance(value, (list, tuple)) and value:
        return float(value[0])
    return float(value)


def score_applies_predictions(
    pipeline_result: Any,
    triples_factory: Any,
    *,
    cases: Sequence[str],
    provisions: Sequence[str],
    relation: str = EdgeType.APPLIES.value,
) -> List[RawPrediction]:
    """Score all ``(case, relation, provision)`` triples using the trained model."""

    if not hasattr(pipeline_result, "model"):
        raise ValueError("The pipeline result does not expose a model for scoring")

    model = pipeline_result.model
    entity_to_id = getattr(triples_factory, "entity_to_id", {})
    relation_to_id = getattr(triples_factory, "relation_to_id", {})

    if relation not in relation_to_id:
        return []

    relation_id = relation_to_id[relation]

    predictions: List[RawPrediction] = []
    for case_id in cases:
        if case_id not in entity_to_id:
            continue
        head_id = entity_to_id[case_id]
        for provision_id in provisions:
            if provision_id not in entity_to_id:
                continue
            tail_id = entity_to_id[provision_id]
            if hasattr(model, "score_hrt"):
                try:
                    import torch
                except ImportError:  # pragma: no cover - torch is a PyKEEN dependency
                    batch = [[head_id, relation_id, tail_id]]
                else:  # pragma: no cover - executed when torch present
                    device = getattr(model, "device", None)
                    batch = torch.tensor(
                        [[head_id, relation_id, tail_id]],
                        dtype=torch.long,
                        device=device if device is not None else None,
                    )
                score_tensor = model.score_hrt(batch)
                score = _to_score(score_tensor)
            elif hasattr(model, "predict_hrt"):
                score = _to_score(model.predict_hrt([(head_id, relation_id, tail_id)]))
            else:
                raise ValueError("The trained model does not support scoring triples")
            predictions.append(RawPrediction(case_id=case_id, provision_id=provision_id, score=score))
    return predictions


def rank_predictions(
    predictions: Iterable[RawPrediction],
    *,
    relation: str = EdgeType.APPLIES.value,
    top_k: Optional[int] = None,
) -> List[PredictionRecord]:
    """Assign per-case ranks to ``predictions`` sorted by score descending."""

    per_case: Dict[str, List[RawPrediction]] = {}
    for prediction in predictions:
        per_case.setdefault(prediction.case_id, []).append(prediction)

    ranked: List[PredictionRecord] = []
    for case_id in sorted(per_case.keys()):
        items = per_case[case_id]
        items.sort(key=lambda pred: pred.score, reverse=True)
        for index, prediction in enumerate(items, start=1):
            if top_k is not None and index > top_k:
                break
            ranked.append(
                PredictionRecord(
                    case_id=prediction.case_id,
                    provision_id=prediction.provision_id,
                    score=prediction.score,
                    rank=index,
                    relation=relation,
                )
            )
    return ranked


def build_prediction_set(
    predictions: Iterable[PredictionRecord],
    *,
    relation: str = EdgeType.APPLIES.value,
    generated_at: Optional[str] = None,
    random_seed: Optional[int] = None,
) -> PredictionSet:
    """Create a :class:`PredictionSet` with a consistent timestamp."""

    timestamp = generated_at
    synthesized_timestamp = False
    if timestamp is None:
        timestamp = datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()
        synthesized_timestamp = True
    non_deterministic = synthesized_timestamp or random_seed is None
    return PredictionSet(
        relation=relation,
        generated_at=timestamp,
        predictions=list(predictions),
        non_deterministic=non_deterministic,
    )


def infer_semantic_recommendations(
    graph: LegalGraph,
    *,
    wrong_type_catalog: Mapping[str, Iterable[str]],
    protected_interest_catalog: Mapping[str, Iterable[str]],
    remedy_catalog: Mapping[str, Iterable[str]],
    event_labels: Optional[Iterable[str]] = None,
) -> SemanticRecommendations:
    """Emit Milestones 3–5 recommendations from a populated :class:`LegalGraph`."""

    corpus = _collect_corpus(graph)
    wrong_types = _score_catalog(
        catalog=wrong_type_catalog,
        corpus=corpus,
        node_type=NodeType.WRONG_TYPE,
        rationale_prefix="WrongType heuristic",
    )
    protected_interests = _score_catalog(
        catalog=protected_interest_catalog,
        corpus=corpus,
        node_type=NodeType.PROTECTED_INTEREST,
        rationale_prefix="Protected interest heuristic",
    )

    if event_labels is None:
        event_labels = [
            f"event:{identifier}"
            for identifier, node in graph.nodes.items()
            if getattr(node, "type", None) in {NodeType.CASE, NodeType.DOCUMENT, NodeType.EVENT}
        ]
    events = [
        SemanticRecommendation(
            identifier=label,
            node_type=NodeType.EVENT,
            score=1.0 + index * 0.01,
            rationale="Seeded from case/provision context",
        )
        for index, label in enumerate(event_labels)
    ]

    remedy_base = 0.05 + (protected_interests[0].score if protected_interests else 0.0)
    remedies = _score_catalog(
        catalog=remedy_catalog,
        corpus=corpus,
        node_type=NodeType.REMEDY,
        base_score=remedy_base,
        rationale_prefix="Remedy heuristic",
    )

    return SemanticRecommendations(
        wrong_types=wrong_types,
        protected_interests=protected_interests,
        events=events,
        remedies=remedies,
    )


def persist_predictions_json(predictions: PredictionSet, path: Path) -> None:
    """Serialise ``predictions`` to ``path`` in JSON format."""

    payload = {
        "version": PREDICTION_VERSION,
        "relation": predictions.relation,
        "generated_at": predictions.generated_at,
        "non_deterministic": predictions.non_deterministic,
        "predictions": [
            {
                "case_id": item.case_id,
                "provision_id": item.provision_id,
                "score": item.score,
                "rank": item.rank,
            }
            for item in predictions.predictions
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def persist_predictions_sqlite(predictions: PredictionSet, path: Path) -> None:
    """Persist ``predictions`` into a SQLite database at ``path``."""

    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path))
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS applies_predictions (
                case_id TEXT NOT NULL,
                provision_id TEXT NOT NULL,
                relation TEXT NOT NULL,
                score REAL NOT NULL,
                rank INTEGER NOT NULL,
                generated_at TEXT NOT NULL,
                non_deterministic INTEGER NOT NULL DEFAULT 1,
                version INTEGER NOT NULL,
                PRIMARY KEY (case_id, provision_id, relation)
            )
            """
        )
        _ensure_sqlite_schema(connection)
        connection.execute(
            "DELETE FROM applies_predictions WHERE relation = ?",
            (predictions.relation,),
        )
        rows = [
            (
                item.case_id,
                item.provision_id,
                item.relation,
                item.score,
                item.rank,
                predictions.generated_at,
                int(predictions.non_deterministic),
                PREDICTION_VERSION,
            )
            for item in predictions.predictions
        ]
        if rows:
            connection.executemany(
                """
                INSERT OR REPLACE INTO applies_predictions (
                    case_id,
                    provision_id,
                    relation,
                    score,
                    rank,
                    generated_at,
                    non_deterministic,
                    version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        connection.commit()
    finally:
        connection.close()


def _ensure_sqlite_schema(connection: sqlite3.Connection) -> None:
    """Ensure the SQLite schema contains the non-deterministic column."""

    result = connection.execute("PRAGMA table_info(applies_predictions)").fetchall()
    column_names = {row[1] for row in result}
    if "non_deterministic" not in column_names:
        connection.execute(
            "ALTER TABLE applies_predictions ADD COLUMN non_deterministic INTEGER NOT NULL DEFAULT 1"
        )


def load_predictions_json(path: Path) -> PredictionSet:
    """Load predictions persisted via :func:`persist_predictions_json`."""

    data = json.loads(path.read_text(encoding="utf-8"))
    version = data.get("version", 0)
    if version != PREDICTION_VERSION:
        raise ValueError(
            f"Unsupported prediction format version: {version} (expected {PREDICTION_VERSION})"
        )
    relation = str(data.get("relation", EdgeType.APPLIES.value))
    generated_at = str(data.get("generated_at", ""))
    predictions = [
        PredictionRecord(
            case_id=item["case_id"],
            provision_id=item["provision_id"],
            score=float(item["score"]),
            rank=int(item["rank"]),
            relation=relation,
        )
        for item in data.get("predictions", [])
    ]
    non_deterministic = bool(data.get("non_deterministic", True))
    return PredictionSet(
        relation=relation,
        generated_at=generated_at,
        predictions=predictions,
        non_deterministic=non_deterministic,
    )


def load_predictions_sqlite(
    path: Path,
    *,
    relation: str = EdgeType.APPLIES.value,
) -> PredictionSet:
    """Load predictions from the SQLite store at ``path``."""

    connection = sqlite3.connect(str(path))
    try:
        _ensure_sqlite_schema(connection)
        rows = connection.execute(
            """
            SELECT case_id, provision_id, score, rank, generated_at, non_deterministic, version
            FROM applies_predictions
            WHERE relation = ?
            ORDER BY case_id ASC, rank ASC
            """,
            (relation,),
        ).fetchall()
    finally:
        connection.close()

    if not rows:
        return PredictionSet(relation=relation, generated_at="", predictions=[])

    version = rows[0][6]
    if version != PREDICTION_VERSION:
        raise ValueError(
            f"Unsupported prediction format version: {version} (expected {PREDICTION_VERSION})"
        )
    generated_at = rows[0][4]
    non_deterministic = bool(rows[0][5])
    predictions = [
        PredictionRecord(
            case_id=row[0],
            provision_id=row[1],
            score=float(row[2]),
            rank=int(row[3]),
            relation=relation,
        )
        for row in rows
    ]
    return PredictionSet(
        relation=relation,
        generated_at=generated_at,
        predictions=predictions,
        non_deterministic=non_deterministic,
    )


__all__ = [
    "TriplePack",
    "TrainingArtifacts",
    "RawPrediction",
    "PredictionRecord",
    "PredictionSet",
    "legal_graph_to_triples",
    "get_case_identifiers",
    "get_provision_identifiers",
    "train_transe",
    "train_distmult",
    "train_complex",
    "train_rotate",
    "train_mure",
    "score_applies_predictions",
    "rank_predictions",
    "build_prediction_set",
    "persist_predictions_json",
    "persist_predictions_sqlite",
    "load_predictions_json",
    "load_predictions_sqlite",
    "PREDICTION_VERSION",
    "SemanticRecommendation",
    "SemanticRecommendations",
    "infer_semantic_recommendations",
]
