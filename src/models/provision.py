from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class Atom:
    """A minimal knowledge atom extracted from a provision."""

    type: Optional[str] = None
    role: Optional[str] = None
    party: Optional[str] = None
    who: Optional[str] = None
    who_text: Optional[str] = None
    conditions: Optional[str] = None
    text: Optional[str] = None
    refs: List[str] = field(default_factory=list)
    gloss: Optional[str] = None
    gloss_metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialise the atom to a dictionary."""

        return {
            "type": self.type,
            "role": self.role,
            "party": self.party,
            "who": self.who,
            "who_text": self.who_text,
            "conditions": self.conditions,
            "text": self.text,
            "refs": list(self.refs),
            "gloss": self.gloss,
            "gloss_metadata": (
                dict(self.gloss_metadata)
                if self.gloss_metadata is not None
                else None
            ),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Atom":
        """Deserialise an :class:`Atom` from ``data``."""

        return cls(
            type=data.get("type"),
            role=data.get("role"),
            party=data.get("party"),
            who=data.get("who"),
            who_text=data.get("who_text"),
            conditions=data.get("conditions"),
            text=data.get("text"),
            refs=list(data.get("refs", [])),
            gloss=data.get("gloss"),
            gloss_metadata=(
                dict(data["gloss_metadata"])
                if "gloss_metadata" in data and data["gloss_metadata"] is not None
                else None
            ),
        )


@dataclass
class Provision:
    """A discrete provision within a legal document."""

    text: str
    identifier: Optional[str] = None
    heading: Optional[str] = None
    node_type: Optional[str] = None
    rule_tokens: Dict[str, Any] = field(default_factory=dict)
    references: List[Tuple[str, Optional[str], Optional[str], Optional[str], str]] = (
        field(default_factory=list)
    )
    children: List["Provision"] = field(default_factory=list)
    principles: List[str] = field(default_factory=list)
    customs: List[str] = field(default_factory=list)
    atoms: List[Atom] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the provision to a dictionary."""
        return {
            "text": self.text,
            "identifier": self.identifier,
            "heading": self.heading,
            "node_type": self.node_type,
            "rule_tokens": dict(self.rule_tokens),
            "references": [tuple(ref) for ref in self.references],
            "children": [c.to_dict() for c in self.children],
            "principles": list(self.principles),
            "customs": list(self.customs),
            "atoms": [atom.to_dict() for atom in self.atoms],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Provision":
        """Deserialize a provision from a dictionary."""
        return cls(
            text=data["text"],
            identifier=data.get("identifier"),
            heading=data.get("heading"),
            node_type=data.get("node_type"),
            rule_tokens=dict(data.get("rule_tokens", {})),
            references=[
                tuple(ref) if isinstance(ref, (list, tuple)) else tuple(ref)
                for ref in data.get("references", [])
            ],
            children=[cls.from_dict(c) for c in data.get("children", [])],
            principles=list(data.get("principles", [])),
            customs=list(data.get("customs", [])),
            atoms=[Atom.from_dict(a) for a in data.get("atoms", [])],
        )
