"""OPA Gateway for evaluating cultural policies.

This module provides a thin wrapper that "compiles" Rego policies and
evaluates records against them.  The compilation step here is intentionally
light‑weight: it parses a Rego policy for the list of sensitive cultural flags
and caches them for subsequent evaluations.  This keeps the interface similar
to using a real OPA instance while avoiding a heavy dependency for tests.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Iterable, Set


class OPAGateway:
    """Simple policy gateway based on Rego files.

    Parameters
    ----------
    policy_path:
        Path to the Rego policy file defining ``sensitive_flags`` and rules for
        consent.  The policy is parsed once at instantiation time.
    """

    def __init__(self, policy_path: str | Path) -> None:
        self.policy_path = Path(policy_path)
        self.sensitive_flags: Set[str] = self._compile_policy(self.policy_path)

    @staticmethod
    def _compile_policy(path: Path) -> Set[str]:
        """Extract the ``sensitive_flags`` set from a Rego policy."""
        text = path.read_text(encoding="utf8")
        match = re.search(r"sensitive_flags\s*=\s*{([^}]*)}", text)
        if not match:
            return set()
        items = match.group(1).split(",")
        flags = {item.strip().strip('"') for item in items if item.strip()}
        return flags

    # ------------------------------------------------------------------
    def is_allowed(self, record: Dict[str, Any]) -> bool:
        """Evaluate ``record`` against the policy.

        The policy denies records that contain any sensitive cultural flags or
        explicitly require consent unless a ``consent`` field is present and
        truthy.  Returns ``True`` when the record is allowed for storage or
        publication, ``False`` otherwise.
        """

        flags = set(record.get("cultural_flags", []))
        consent_required = bool(record.get("consent_required", False))
        consent = bool(record.get("consent", False))

        if (flags & self.sensitive_flags or consent_required) and not consent:
            return False
        return True
