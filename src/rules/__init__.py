from dataclasses import dataclass
from typing import Optional


@dataclass
class Rule:
    """A simple representation of a normative rule."""

    actor: str
    modality: str
    action: str
    conditions: Optional[str] = None
    scope: Optional[str] = None

