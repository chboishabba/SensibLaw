from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Rule:
    """A simple representation of a normative rule."""

    actor: str
    modality: str
    action: str
    conditions: Optional[str] = None
    scope: Optional[str] = None
    elements: Dict[str, List[str]] = field(default_factory=dict)

