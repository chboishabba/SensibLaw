from __future__ import annotations

import json
from enum import Enum
from typing import Any, Callable, Dict, Iterable, Optional, Set


class CulturalFlags(Enum):
    """Flags representing culturally sensitive content."""

    SACRED_DATA = "sacred_data"
    PERSONALLY_IDENTIFIABLE_INFORMATION = "pii"
    PUBLIC_DOMAIN = "public_domain"


Action = str
StorageHook = Callable[[CulturalFlags, Action], None]
InferenceHook = Callable[[CulturalFlags, Action], None]


class PolicyEngine:
    """Evaluate cultural policies against flags.

    Parameters
    ----------
    policy:
        A dictionary representing the policy. It must contain a ``rules`` list
        where each rule has ``flag`` and ``action`` fields. An optional
        ``default`` action is used when no rules match.
    storage_hook:
        Optional callable invoked when actions ``deny`` or ``log`` are
        triggered.
    inference_hook:
        Optional callable invoked when action ``transform`` is triggered.
    """

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

    @classmethod
    def from_json(
        cls,
        policy_json: str,
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
        default_action: Action = self.policy.get("default", "allow")
        return default_action

    def _apply_hooks(self, flag: CulturalFlags, action: Action) -> None:
        """Invoke any registered hooks for ``action``."""
        if action == "transform" and self.inference_hook:
            self.inference_hook(flag, action)
        if action in {"deny", "log"} and self.storage_hook:
            self.storage_hook(flag, action)
