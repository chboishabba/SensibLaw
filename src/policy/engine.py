"""Minimal cultural policy engine.

This module evaluates simple policy mappings against graph nodes to
determine how culturally sensitive content should be handled.  It is a
light‑weight reimplementation that covers the limited functionality
exercised in the tests.
"""

from __future__ import annotations

from dataclasses import replace
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Set

try:  # pragma: no cover - optional dependency
    import yaml
except Exception:  # pragma: no cover
    yaml = None

from src.culture.registry import CulturalFlagRegistry, load_registry
from src.graph.models import GraphNode

Action = str
StorageHook = Callable[["CulturalFlags", Action], None]
InferenceHook = Callable[["CulturalFlags", Action], None]


_FLAGS_PATH = Path(__file__).resolve().parents[2] / "data" / "cultural_flags.yaml"


@lru_cache(maxsize=1)
def _get_flag_registry() -> CulturalFlagRegistry:
    return load_registry(_FLAGS_PATH)


def _build_flag_enum() -> Enum:
    registry = _get_flag_registry()
    members = {identifier: identifier for identifier in registry.canonical_ids()}
    return Enum("CulturalFlags", members)


CulturalFlags = _build_flag_enum()


def resolve_cultural_flag(name: str) -> Optional[CulturalFlags]:
    """Resolve ``name`` to a :class:`CulturalFlags` member if known."""

    if not name:
        return None
    metadata = _get_flag_registry().resolve(name)
    if not metadata:
        return None
    try:
        return CulturalFlags[metadata.identifier]
    except KeyError:  # pragma: no cover - defensive guard
        return None


class PolicyEngine:
    """Apply cultural rules to :class:`GraphNode` instances."""

    def __init__(
        self,
        policy: Dict[str, Any],
        *,
        storage_hook: Optional[StorageHook] = None,
        inference_hook: Optional[InferenceHook] = None,
    ) -> None:
        self.policy = policy
        self.storage_hook = storage_hook
        self.inference_hook = inference_hook
        # Extract direct flag rules for enforcement convenience
        self.rules = {
            k.upper(): v for k, v in policy.items() if isinstance(v, dict)
        }

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------
    @classmethod
    def from_yaml(cls, path: str) -> "PolicyEngine":
        """Build an engine from a YAML file."""
        if yaml is not None:  # pragma: no branch
            with open(path, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
        else:
            data = cls._parse_simple_yaml(path)
        return cls(data)

    @staticmethod
    def _parse_simple_yaml(path: str) -> Dict[str, Dict[str, Any]]:
        """Parse a very small subset of YAML used in tests."""
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

    # ------------------------------------------------------------------
    # Policy evaluation
    # ------------------------------------------------------------------
    def _apply_hooks(self, flag: CulturalFlags, action: Action) -> None:
        if action == "transform" and self.inference_hook:
            self.inference_hook(flag, action)
        if action in {"deny", "log"} and self.storage_hook:
            self.storage_hook(flag, action)

    def _evaluate_nested(
        self, rule: Dict[str, Any], flag_set: Set[CulturalFlags]
    ) -> Action:
        cond = rule.get("if")
        flag = resolve_cultural_flag(cond) if cond else None
        match = flag in flag_set if flag else False
        branch = rule.get("then" if match else "else")
        if isinstance(branch, dict):
            return self._evaluate_nested(branch, flag_set)
        action: Action = (
            branch if isinstance(branch, str) else self.policy.get("default", "allow")
        )
        if match and flag:
            self._apply_hooks(flag, action)
        return action

    def evaluate(self, flags: Iterable[CulturalFlags]) -> Action:
        """Evaluate ``flags`` against the policy and return an action."""
        flag_set: Set[CulturalFlags] = set(flags)

        if "rules" in self.policy:
            for rule in self.policy.get("rules", []):
                flag_name = rule.get("flag")
                action = rule.get("action")
                if not flag_name or not action:
                    continue
                flag = resolve_cultural_flag(flag_name)
                if not flag:
                    continue
                if flag in flag_set:
                    self._apply_hooks(flag, action)
                    return action
            return self.policy.get("default", "allow")

        if "if" in self.policy:
            return self._evaluate_nested(self.policy, flag_set)

        return self.policy.get("default", "allow")

    # ------------------------------------------------------------------
    # Enforcement
    # ------------------------------------------------------------------
    def _transform_value(self, value: Any, kind: str) -> Any:
        if kind == "hash":
            import hashlib

            return hashlib.sha256(str(value).encode()).hexdigest()
        return value

    def enforce(
        self,
        node: GraphNode,
        *,
        consent: bool = True,
        phase: str = "ingest",
    ) -> Optional[GraphNode]:
        """Apply policy rules to ``node``."""

        redaction: str = "none"
        transform: Optional[str] = None
        consent_required: bool = node.consent_required
        resolved_members: List[CulturalFlags] = []
        for raw in node.cultural_flags or []:
            member = resolve_cultural_flag(raw)
            if member and member not in resolved_members:
                resolved_members.append(member)
        canonical_names = [member.value for member in resolved_members]

        for name in canonical_names:
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
            return replace(
                node,
                metadata={"summary": "Content withheld due to policy"},
                consent_required=consent_required,
            )

        if redaction == "omit":
            return None

        metadata = node.metadata
        if transform and phase != "export":
            metadata = {
                k: self._transform_value(v, transform) for k, v in metadata.items()
            }
            if transform and self.inference_hook:
                for member in resolved_members:
                    self._apply_hooks(member, "transform")

        return replace(
            node,
            metadata=metadata,
            consent_required=consent_required,
            cultural_flags=canonical_names or node.cultural_flags,
        )

