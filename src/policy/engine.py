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
        storage_hook: Optional[StorageHook] = None,
        inference_hook: Optional[InferenceHook] = None,
    ) -> "PolicyEngine":
        """Create a policy engine from a JSON string."""
        policy = json.loads(policy_json)
        return cls(
            policy,
            storage_hook=storage_hook,
            inference_hook=inference_hook,
        )

    def evaluate(self, flags: Iterable[CulturalFlags]) -> Action:
        """Evaluate ``flags`` against the policy and return an action."""
        flag_set: Set[CulturalFlags] = set(flags)

        if "rules" in self.policy:
            for rule in self.policy.get("rules", []):
                flag_name = rule.get("flag")
                action = rule.get("action")
                if not flag_name or not action:
                    continue
                try:
                    flag = CulturalFlags[flag_name]
                except KeyError:
                    continue
                if flag in flag_set:
                    self._apply_hooks(flag, action)
                    return action
            return self.policy.get("default", "allow")

        if "if" in self.policy:
            return self._evaluate_nested(self.policy, flag_set)

        return self.policy.get("default", "allow")

    def _evaluate_nested(self, rule: Dict[str, Any], flag_set: Set[CulturalFlags]) -> Action:
        """Recursively evaluate nested ``if``/``then`` rules."""

        cond = rule.get("if")
        flag = None
        if cond:
            try:
                flag = CulturalFlags[cond]
            except KeyError:
                flag = None
        match = flag in flag_set if flag else False
        branch = rule.get("then" if match else "else")
        if isinstance(branch, dict):
            return self._evaluate_nested(branch, flag_set)
        action: Action = branch if isinstance(branch, str) else self.policy.get(
            "default", "allow"
        )
        if match and flag:
            self._apply_hooks(flag, action)
        return action

    def enforce(self, node: GraphNode, *, consent: bool = False) -> Optional[GraphNode]:
        "Apply policy and consent rules to ``node``."

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

        require = node.consent_required or action == "require"
        if action == "transform" or (require and not consent):
            return GraphNode(
                type=node.type,
                identifier=node.identifier,
                metadata={"summary": "Content withheld due to policy"},
                date=node.date,
                cultural_flags=node.cultural_flags,
                consent_required=require,
            )

        return node

    def _apply_hooks(self, flag: CulturalFlags, action: Action) -> None:
        ""Invoke any registered hooks for ``action``.""
        if action == "transform" and self.inference_hook:
            self.inference_hook(flag, action)
        if action in {"deny", "log"} and self.storage_hook:
            self.storage_hook(flag, action)

        metadata = node.metadata
        if redaction == "redact" and not consent:
            metadata = {}
        if transform and not consent:
            metadata = {
                k: self._transform_value(v, transform) for k, v in metadata.items()
            }
        return replace(node, metadata=metadata, consent_required=consent_required)
