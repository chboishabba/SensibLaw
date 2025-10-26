"""Relational graph convolutional network utilities for legal graphs."""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple

from .models import EdgeType, LegalGraph, NodeType

try:  # pragma: no cover - optional dependency wiring
    import torch
    from torch import nn
    import torch.nn.functional as F
except ModuleNotFoundError:  # pragma: no cover - optional dependency wiring
    torch = None  # type: ignore[assignment]
    nn = None  # type: ignore[assignment]
    F = None  # type: ignore[assignment]

try:  # pragma: no cover - optional dependency wiring
    import dgl
    from dgl.nn import RelGraphConv
except ModuleNotFoundError:  # pragma: no cover - optional dependency wiring
    dgl = None  # type: ignore[assignment]
    RelGraphConv = None  # type: ignore[assignment]

if TYPE_CHECKING:  # pragma: no cover - typing helpers
    from dgl import DGLGraph


class RGCNBackendNotAvailableError(RuntimeError):
    """Raised when torch/DGL are missing for R-GCN operations."""


def _require_backend() -> None:
    """Ensure the torch and DGL backends are installed."""

    if torch is None or dgl is None or nn is None or RelGraphConv is None:
        raise RGCNBackendNotAvailableError(
            "The graph embedding utilities require the optional 'torch' and 'dgl' "
            "dependencies. Install them with 'pip install \"sensiblaw[graph]\"' "
            "before calling R-GCN helpers."
        )


@dataclass
class RGCNConfig:
    """Configuration for R-GCN training."""

    hidden_dim: int = 64
    num_layers: int = 2
    lr: float = 1e-2
    weight_decay: float = 1e-4
    epochs: int = 200
    validation_ratio: float = 0.1
    negative_ratio: int = 1
    dropout: float = 0.1
    device: str = "cpu"
    seed: int = 7
    checkpoint_path: Optional[Path] = None
    attach_to_graph: bool = True
    metadata_key: str = "embedding"

    def asdict(self) -> Dict[str, Any]:
        """Return a serialisable representation of the config."""

        payload = asdict(self)
        if self.checkpoint_path is not None:
            payload["checkpoint_path"] = str(self.checkpoint_path)
        return payload


@dataclass
class RGCNEpochResult:
    """Loss metrics recorded for a single epoch."""

    epoch: int
    train_loss: float
    val_loss: Optional[float]


@dataclass
class RGCNTrainingResult:
    """Container for the learned node embeddings."""

    embeddings: "torch.Tensor"
    node_ids: List[str]
    history: List[RGCNEpochResult]
    best_epoch: int
    config: RGCNConfig

    def to_mapping(self) -> Dict[str, List[float]]:
        """Return a JSON serialisable mapping of node identifiers to vectors."""

        return {
            node_id: [float(component) for component in self.embeddings[idx].detach().cpu().tolist()]
            for idx, node_id in enumerate(self.node_ids)
        }


@dataclass
class RGCNGraphData:
    """Converted tensors used as input for the R-GCN."""

    graph: "DGLGraph"
    features: "torch.Tensor"
    node_ids: List[str]
    node_index: Dict[str, int]
    relation_index: Dict[EdgeType, int]


def legal_graph_to_dgl(legal_graph: LegalGraph) -> RGCNGraphData:
    """Convert a :class:`LegalGraph` into tensors for R-GCN training."""

    _require_backend()
    assert torch is not None  # mypy hint
    assert dgl is not None

    if not legal_graph.nodes:
        raise ValueError("The graph must contain at least one node.")

    node_ids = sorted(legal_graph.nodes.keys())
    node_index = {identifier: idx for idx, identifier in enumerate(node_ids)}

    relation_types = [edge.type for edge in legal_graph.edges if edge.source in node_index and edge.target in node_index]
    if not relation_types:
        raise ValueError("The graph must contain at least one edge before training.")

    relation_index: Dict[EdgeType, int] = {
        edge_type: idx for idx, edge_type in enumerate(sorted(set(relation_types), key=lambda et: et.value))
    }

    sources: List[int] = []
    targets: List[int] = []
    edge_types: List[int] = []
    for edge in legal_graph.edges:
        source_idx = node_index.get(edge.source)
        target_idx = node_index.get(edge.target)
        if source_idx is None or target_idx is None:
            continue
        sources.append(source_idx)
        targets.append(target_idx)
        edge_types.append(relation_index[edge.type])

    src_tensor = torch.tensor(sources, dtype=torch.int64)
    dst_tensor = torch.tensor(targets, dtype=torch.int64)
    edge_type_tensor = torch.tensor(edge_types, dtype=torch.int64)

    graph = dgl.graph((src_tensor, dst_tensor), num_nodes=len(node_ids))
    graph.edata["rel_type"] = edge_type_tensor
    graph.edata["norm"] = _edge_norm(graph)

    node_type_lookup: Dict[NodeType, int] = {
        node_type: idx for idx, node_type in enumerate(sorted(NodeType, key=lambda nt: nt.value))
    }
    node_type_indices = torch.tensor(
        [node_type_lookup[legal_graph.nodes[identifier].type] for identifier in node_ids],
        dtype=torch.int64,
    )
    type_features = F.one_hot(node_type_indices, num_classes=len(node_type_lookup)).to(torch.float32)
    degree_features = graph.in_degrees().to(torch.float32).unsqueeze(1)
    features = torch.cat([type_features, degree_features], dim=1)

    return RGCNGraphData(
        graph=graph,
        features=features,
        node_ids=node_ids,
        node_index=node_index,
        relation_index=relation_index,
    )


if torch is not None and nn is not None and RelGraphConv is not None:

    class RGCNEncoder(nn.Module):
        """Stacked :class:`dgl.nn.RelGraphConv` layers for node embeddings."""

        def __init__(self, in_dim: int, hidden_dim: int, num_rels: int, num_layers: int, dropout: float) -> None:
            super().__init__()
            if num_layers < 1:
                raise ValueError("R-GCN must have at least one layer")

            layers: List[RelGraphConv] = []
            for layer_index in range(num_layers):
                input_dim = in_dim if layer_index == 0 else hidden_dim
                activation = F.relu if layer_index < num_layers - 1 else None
                current_dropout = dropout if layer_index < num_layers - 1 else 0.0
                layers.append(
                    RelGraphConv(
                        input_dim,
                        hidden_dim,
                        num_rels,
                        activation=activation,
                        dropout=current_dropout,
                    )
                )
            self.layers = nn.ModuleList(layers)

        def forward(self, graph: "DGLGraph", features: "torch.Tensor") -> "torch.Tensor":
            x = features
            rel_types = graph.edata["rel_type"]
            norms = graph.edata["norm"]
            for layer in self.layers:
                x = layer(graph, x, rel_types, norms)
            return x


else:  # pragma: no cover - backend guard

    class RGCNEncoder:  # type: ignore[too-many-ancestors]
        """Placeholder encoder used when the backend is unavailable."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: D401
            raise RGCNBackendNotAvailableError(
                "Install the optional 'torch' and 'dgl' extras to train graph embeddings."
            )

        def forward(self, *args: Any, **kwargs: Any) -> "torch.Tensor":  # type: ignore[override]
            raise RGCNBackendNotAvailableError(
                "Install the optional 'torch' and 'dgl' extras to train graph embeddings."
            )


class RGCNTrainer:
    """Manage R-GCN training and persistence."""

    def __init__(self, legal_graph: LegalGraph, config: Optional[RGCNConfig] = None) -> None:
        _require_backend()
        assert torch is not None

        self.legal_graph = legal_graph
        self.config = config or RGCNConfig()
        self.graph_data = legal_graph_to_dgl(legal_graph)

        requested_device = self.config.device
        if requested_device != "cpu" and torch.cuda.is_available():
            self.device = torch.device(requested_device)
        else:
            self.device = torch.device("cpu")

    def train(self) -> RGCNTrainingResult:
        """Run the optimisation loop and return learned embeddings."""

        assert torch is not None

        rng = random.Random(self.config.seed)
        torch.manual_seed(self.config.seed)

        graph = self.graph_data.graph.to(self.device)
        features = self.graph_data.features.to(self.device)

        num_rels = len(self.graph_data.relation_index)
        model = RGCNEncoder(
            in_dim=features.shape[1],
            hidden_dim=self.config.hidden_dim,
            num_rels=num_rels,
            num_layers=self.config.num_layers,
            dropout=self.config.dropout,
        ).to(self.device)

        optimizer = torch.optim.Adam(
            model.parameters(), lr=self.config.lr, weight_decay=self.config.weight_decay
        )

        edges_src, edges_dst = graph.edges()
        edge_pairs = torch.stack((edges_src, edges_dst), dim=1)
        num_edges = edge_pairs.shape[0]
        if num_edges == 0:
            raise ValueError("At least one edge is required for training.")

        generator = torch.Generator(device=self.device)
        generator.manual_seed(self.config.seed)
        permutation = torch.randperm(num_edges, generator=generator)

        val_size = int(num_edges * max(0.0, min(self.config.validation_ratio, 0.5)))
        train_size = num_edges - val_size
        if train_size <= 0:
            raise ValueError("Validation split left no edges for training; reduce validation_ratio.")

        train_indices = permutation[:train_size]
        val_indices = permutation[train_size:] if val_size else torch.empty(0, dtype=torch.int64)

        train_edges = edge_pairs.index_select(0, train_indices).to(self.device)
        val_edges = (
            edge_pairs.index_select(0, val_indices).to(self.device) if val_size else torch.empty(0, 2, device=self.device)
        )

        edge_set = {
            (int(edge[0]), int(edge[1]))
            for edge in edge_pairs.cpu().tolist()
        }

        history: List[RGCNEpochResult] = []
        best_state: Optional[Dict[str, Any]] = None
        best_metric: Optional[float] = None
        best_epoch = 0

        for epoch in range(1, self.config.epochs + 1):
            model.train()
            optimizer.zero_grad()
            embeddings = model(graph, features)

            positive_edges = train_edges
            negative_edges = _sample_negative_edges(
                num_nodes=len(self.graph_data.node_ids),
                num_samples=max(positive_edges.shape[0] * max(1, self.config.negative_ratio), 1),
                existing=edge_set,
                rng=rng,
                device=self.device,
            )
            loss = _binary_link_loss(embeddings, positive_edges, negative_edges)
            loss.backward()
            optimizer.step()

            with torch.no_grad():
                val_loss: Optional[float] = None
                if val_size:
                    val_negatives = _sample_negative_edges(
                        num_nodes=len(self.graph_data.node_ids),
                        num_samples=max(val_edges.shape[0] * max(1, self.config.negative_ratio), 1),
                        existing=edge_set,
                        rng=rng,
                        device=self.device,
                    )
                    val_loss = float(_binary_link_loss(embeddings, val_edges, val_negatives).item())

                history.append(
                    RGCNEpochResult(
                        epoch=epoch,
                        train_loss=float(loss.item()),
                        val_loss=val_loss,
                    )
                )

                metric = val_loss if val_loss is not None else float(loss.item())
                if best_metric is None or metric < best_metric:
                    best_metric = metric
                    best_state = {key: value.detach().cpu() for key, value in model.state_dict().items()}
                    best_epoch = epoch
                    if self.config.checkpoint_path:
                        self._save_checkpoint(self.config.checkpoint_path, best_state, history)

        if best_state is not None:
            model.load_state_dict(best_state)

        model.eval()
        with torch.no_grad():
            final_embeddings = model(graph, features).detach().cpu()

        result = RGCNTrainingResult(
            embeddings=final_embeddings,
            node_ids=self.graph_data.node_ids,
            history=history,
            best_epoch=best_epoch or self.config.epochs,
            config=self.config,
        )

        if self.config.attach_to_graph:
            attach_embeddings(self.legal_graph, result, metadata_key=self.config.metadata_key)

        return result

    def _save_checkpoint(
        self,
        path: Path,
        state_dict: Mapping[str, "torch.Tensor"],
        history: Sequence[RGCNEpochResult],
    ) -> None:
        """Persist the current model state to ``path``."""

        assert torch is not None

        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "state_dict": state_dict,
                "config": self.config.asdict(),
                "node_ids": list(self.graph_data.node_ids),
                "relation_index": {edge_type.value: idx for edge_type, idx in self.graph_data.relation_index.items()},
                "history": [epoch.__dict__ for epoch in history],
            },
            path,
        )


def attach_embeddings(
    legal_graph: LegalGraph,
    result: RGCNTrainingResult,
    *,
    metadata_key: str = "embedding",
) -> None:
    """Attach the embeddings to node metadata for downstream use."""

    for node_id, vector in result.to_mapping().items():
        node = legal_graph.get_node(node_id)
        if node is None:
            continue
        if not isinstance(node.metadata, MutableMapping):
            continue
        node.metadata[metadata_key] = vector


def export_embeddings(result: RGCNTrainingResult, destination: Path) -> None:
    """Serialise embeddings to ``destination`` as JSON."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as handle:
        json.dump(result.to_mapping(), handle, indent=2)


def load_embeddings(path: Path) -> Dict[str, List[float]]:
    """Load previously exported embeddings."""

    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("Embedding file must contain a JSON object of node vectors.")
    result: Dict[str, List[float]] = {}
    for key, value in payload.items():
        if not isinstance(value, list) or not value:
            continue
        vector: List[float] = []
        for component in value:
            if isinstance(component, (int, float)):
                vector.append(float(component))
        if vector:
            result[str(key)] = vector
    return result


def _edge_norm(graph: "dgl.DGLGraph") -> "torch.Tensor":
    """Compute the inverse in-degree normalisation for each edge."""

    assert torch is not None

    with graph.local_scope():
        dst = graph.edges()[1]
        degrees = graph.in_degrees().to(torch.float32)
        degrees = torch.clamp(degrees, min=1)
        norm = degrees[dst]
        return torch.pow(norm, -1)


def _sample_negative_edges(
    *,
    num_nodes: int,
    num_samples: int,
    existing: Iterable[Tuple[int, int]],
    rng: random.Random,
    device: "torch.device",
) -> "torch.Tensor":
    """Sample ``num_samples`` negative edges avoiding ``existing``."""

    assert torch is not None

    existing_set = set(existing)
    negatives: List[Tuple[int, int]] = []
    attempts = 0
    max_attempts = max(num_samples * 10, 100)
    while len(negatives) < num_samples and attempts < max_attempts:
        attempts += 1
        source = rng.randrange(num_nodes)
        target = rng.randrange(num_nodes)
        if source == target:
            continue
        candidate = (source, target)
        if candidate in existing_set or candidate in negatives:
            continue
        negatives.append(candidate)

    if not negatives:
        raise RuntimeError("Unable to sample negative edges; the graph may be fully connected.")

    while len(negatives) < num_samples:
        negatives.append(negatives[len(negatives) % len(negatives)])

    return torch.tensor(negatives, dtype=torch.int64, device=device)


def _binary_link_loss(
    embeddings: "torch.Tensor",
    positive_edges: "torch.Tensor",
    negative_edges: "torch.Tensor",
) -> "torch.Tensor":
    """Binary cross-entropy loss for link prediction."""

    assert torch is not None

    positive_scores = _edge_scores(embeddings, positive_edges)
    negative_scores = _edge_scores(embeddings, negative_edges)
    scores = torch.cat([positive_scores, negative_scores], dim=0)
    labels = torch.cat(
        [
            torch.ones_like(positive_scores),
            torch.zeros_like(negative_scores),
        ],
        dim=0,
    )
    return F.binary_cross_entropy_with_logits(scores, labels)


def _edge_scores(embeddings: "torch.Tensor", edges: "torch.Tensor") -> "torch.Tensor":
    """Dot-product decoder for edge likelihood."""

    if edges.numel() == 0:
        return torch.zeros(0, device=embeddings.device)
    source = edges[:, 0]
    target = edges[:, 1]
    source_vectors = embeddings.index_select(0, source)
    target_vectors = embeddings.index_select(0, target)
    return torch.sum(source_vectors * target_vectors, dim=1)


__all__ = [
    "RGCNConfig",
    "RGCNEpochResult",
    "RGCNTrainingResult",
    "RGCNTrainer",
    "RGCNGraphData",
    "RGCNBackendNotAvailableError",
    "attach_embeddings",
    "export_embeddings",
    "legal_graph_to_dgl",
    "load_embeddings",
]
