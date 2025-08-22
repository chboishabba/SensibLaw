from __future__ import annotations

from dataclasses import replace
from typing import Any, Dict, Optional

try:  # pragma: no cover - optional dependency
    import yaml
except ModuleNotFoundError:  # pragma: no cover
    yaml = None

from src.graph.models import GraphNode


class PolicyEngine:
    """Apply cultural rules to graph nodes.

    The engine loads per-flag policies from a YAML mapping where each flag can
    declare ``redaction`` behaviour, whether ``consent_required`` and an optional
    ``transform`` to apply when consent is absent. These rules are applied
    consistently across ingestion, rendering and export by the :meth:`enforce`
    method.
    """

    def __init__(self, rules: Dict[str, Dict[str, Any]]) -> None:
        self.rules = {k.upper(): v for k, v in rules.items()}

    @classmethod
    def from_yaml(cls, path: str) -> "PolicyEngine":
        """Construct a :class:`PolicyEngine` from a YAML file."""
        if yaml is not None:  # pragma: no branch
            with open(path, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
        else:
            data = cls._parse_simple_yaml(path)
        return cls(data)

    @staticmethod
    def _parse_simple_yaml(path: str) -> Dict[str, Dict[str, Any]]:
        """Very small YAML subset parser used when PyYAML is unavailable."""
        result: Dict[str, Dict[str, Any]] = {}
        current: Optional[str] = None
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.rstrip()
                if not line or line.lstrip().startswith("#"):
                    continue
                if not line.startswith(" "):
                    current = line.rstrip(":")
                    result[current] = {}
                elif current:
                    key, value = line.strip().split(":", 1)
                    value = value.strip()
                    if value in {"true", "false"}:
                        val: Any = value == "true"
                    elif value == "null":
                        val = None
                    else:
                        val = value
                    result[current][key] = val
        return result

    def _transform_value(self, value: Any, kind: str) -> Any:
        if kind == "hash":
            import hashlib

            return hashlib.sha256(str(value).encode()).hexdigest()
        return value

    def enforce(
        self,
        node: GraphNode,
        *,
        consent: bool = False,
        phase: str = "ingest",
    ) -> Optional[GraphNode]:
        """Apply policy rules to ``node``.

        Parameters
        ----------
        node:
            The :class:`GraphNode` under evaluation.
        consent:
            Whether explicit consent or an override has been supplied.
        phase:
            Processing phase. Included for API consistency; rules are identical
            across phases.
        """

        redaction: str = "none"
        transform: Optional[str] = None
        consent_required: bool = node.consent_required
        for name in node.cultural_flags or []:
            rule = self.rules.get(name.upper())
            if not rule:
                continue
            if rule.get("consent_required"):
                consent_required = True
            r = rule.get("redaction", "none")
            if r == "omit":
                redaction = "omit"
            elif r == "redact" and redaction != "omit":
                redaction = "redact"
            if transform is None:
                transform = rule.get("transform")

        if consent_required and not consent:
            if redaction == "omit":
                return None
            if redaction == "redact":
                return replace(
                    node,
                    metadata={},
                    consent_required=consent_required,
                )

        if redaction == "omit":
            return None

        metadata = node.metadata
        if redaction == "redact" and not consent:
            metadata = {}
        if transform and not consent:
            metadata = {
                k: self._transform_value(v, transform) for k, v in metadata.items()
            }
        return replace(node, metadata=metadata, consent_required=consent_required)
