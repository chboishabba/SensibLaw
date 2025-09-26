from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple


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
    glossary_id: Optional[int] = None

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
                dict(self.gloss_metadata) if self.gloss_metadata is not None else None
            ),
            "glossary_id": self.glossary_id,
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
            glossary_id=data.get("glossary_id"),
        )


@dataclass
class RuleReference:
    """A structured reference attached to a rule atom or element."""

    work: Optional[str] = None
    section: Optional[str] = None
    pinpoint: Optional[str] = None
    citation_text: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "work": self.work,
            "section": self.section,
            "pinpoint": self.pinpoint,
            "citation_text": self.citation_text,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RuleReference":
        return cls(
            work=data.get("work"),
            section=data.get("section"),
            pinpoint=data.get("pinpoint"),
            citation_text=data.get("citation_text"),
        )

    def to_legacy_text(self) -> str:
        """Best-effort legacy rendering for compatibility."""

        if self.citation_text:
            return self.citation_text
        parts = [self.work, self.section, self.pinpoint]
        return " ".join(part for part in parts if part) or ""


@dataclass
class RuleElement:
    """A granular fragment within a rule atom."""

    role: Optional[str] = None
    text: Optional[str] = None
    conditions: Optional[str] = None
    gloss: Optional[str] = None
    gloss_metadata: Optional[Dict[str, Any]] = None
    glossary_id: Optional[int] = None
    references: List[RuleReference] = field(default_factory=list)
    atom_type: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "text": self.text,
            "conditions": self.conditions,
            "gloss": self.gloss,
            "gloss_metadata": (
                dict(self.gloss_metadata) if self.gloss_metadata is not None else None
            ),
            "glossary_id": self.glossary_id,
            "references": [ref.to_dict() for ref in self.references],
            "atom_type": self.atom_type,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RuleElement":
        return cls(
            role=data.get("role"),
            text=data.get("text"),
            conditions=data.get("conditions"),
            gloss=data.get("gloss"),
            gloss_metadata=(
                dict(data["gloss_metadata"])
                if "gloss_metadata" in data and data["gloss_metadata"] is not None
                else None
            ),
            glossary_id=data.get("glossary_id"),
            references=[RuleReference.from_dict(r) for r in data.get("references", [])],
            atom_type=data.get("atom_type"),
        )


@dataclass
class RuleLint:
    """An issue surfaced while extracting a rule."""

    code: Optional[str] = None
    message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    atom_type: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "metadata": dict(self.metadata) if self.metadata is not None else None,
            "atom_type": self.atom_type,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RuleLint":
        return cls(
            code=data.get("code"),
            message=data.get("message"),
            metadata=(
                dict(data["metadata"])
                if "metadata" in data and data["metadata"] is not None
                else None
            ),
            atom_type=data.get("atom_type"),
        )


@dataclass
class RuleAtom:
    """A richer representation of a rule with associated fragments."""

    toc_id: Optional[int] = None
    atom_type: Optional[str] = "rule"
    role: Optional[str] = None
    party: Optional[str] = None
    who: Optional[str] = None
    who_text: Optional[str] = None
    actor: Optional[str] = None
    modality: Optional[str] = None
    action: Optional[str] = None
    conditions: Optional[str] = None
    scope: Optional[str] = None
    text: Optional[str] = None
    subject_gloss: Optional[str] = None
    subject_gloss_metadata: Optional[Dict[str, Any]] = None
    glossary_id: Optional[int] = None
    subject: Optional[Atom] = None
    references: List[RuleReference] = field(default_factory=list)
    elements: List[RuleElement] = field(default_factory=list)
    lints: List[RuleLint] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "toc_id": self.toc_id,
            "atom_type": self.atom_type,
            "role": self.role,
            "party": self.party,
            "who": self.who,
            "who_text": self.who_text,
            "actor": self.actor,
            "modality": self.modality,
            "action": self.action,
            "conditions": self.conditions,
            "scope": self.scope,
            "text": self.text,
            "subject_gloss": self.subject_gloss,
            "subject_gloss_metadata": (
                dict(self.subject_gloss_metadata)
                if self.subject_gloss_metadata is not None
                else None
            ),
            "glossary_id": self.glossary_id,
            "subject": self.subject.to_dict() if self.subject is not None else None,
            "references": [ref.to_dict() for ref in self.references],
            "elements": [element.to_dict() for element in self.elements],
            "lints": [lint.to_dict() for lint in self.lints],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RuleAtom":
        return cls(
            toc_id=data.get("toc_id"),
            atom_type=data.get("atom_type"),
            role=data.get("role"),
            party=data.get("party"),
            who=data.get("who"),
            who_text=data.get("who_text"),
            actor=data.get("actor"),
            modality=data.get("modality"),
            action=data.get("action"),
            conditions=data.get("conditions"),
            scope=data.get("scope"),
            text=data.get("text"),
            subject_gloss=data.get("subject_gloss"),
            subject_gloss_metadata=(
                dict(data["subject_gloss_metadata"])
                if "subject_gloss_metadata" in data
                and data["subject_gloss_metadata"] is not None
                else None
            ),
            glossary_id=data.get("glossary_id"),
            subject=(Atom.from_dict(data["subject"]) if data.get("subject") else None),
            references=[RuleReference.from_dict(r) for r in data.get("references", [])],
            elements=[RuleElement.from_dict(e) for e in data.get("elements", [])],
            lints=[
                RuleLint.from_dict(lint_data) for lint_data in data.get("lints", [])
            ],
        )

    def get_subject_atom(self) -> Atom:
        """Return the canonical subject representation for this rule atom."""

        base_atom = self.subject
        atom_type = (
            (base_atom.type if base_atom and base_atom.type is not None else None)
            or self.atom_type
            or "rule"
        )
        role = (
            base_atom.role if base_atom and base_atom.role is not None else None
        ) or (self.role if self.role is not None else None)
        if role is None and atom_type == "rule":
            role = "principle"
        party = (
            base_atom.party if base_atom and base_atom.party is not None else self.party
        )
        who = base_atom.who if base_atom and base_atom.who is not None else self.who
        who_text = (
            base_atom.who_text
            if base_atom and base_atom.who_text is not None
            else self.who_text
        )
        conditions = (
            base_atom.conditions
            if base_atom and base_atom.conditions is not None
            else self.conditions
        )
        text = base_atom.text if base_atom and base_atom.text is not None else self.text
        gloss = (
            base_atom.gloss
            if base_atom and base_atom.gloss is not None
            else self.subject_gloss
        )
        gloss_metadata = (
            base_atom.gloss_metadata
            if base_atom and base_atom.gloss_metadata is not None
            else self.subject_gloss_metadata
        )
        glossary_id = (
            base_atom.glossary_id
            if base_atom and base_atom.glossary_id is not None
            else self.glossary_id
        )
        if base_atom and base_atom.refs:
            refs = list(base_atom.refs)
        else:
            refs = [ref.to_legacy_text() for ref in self.references]
        return Atom(
            type=atom_type,
            role=role,
            party=party,
            who=who,
            who_text=who_text,
            conditions=conditions,
            text=text,
            refs=refs,
            gloss=gloss,
            gloss_metadata=gloss_metadata,
            glossary_id=glossary_id,
        )

    def to_atoms(self) -> List[Atom]:
        """Flatten the rule atom into legacy :class:`Atom` records."""

        flattened: List[Atom] = []

        subject_atom = self.get_subject_atom()
        flattened.append(
            Atom(
                type=subject_atom.type,
                role=subject_atom.role,
                party=subject_atom.party,
                who=subject_atom.who,
                who_text=subject_atom.who_text,
                conditions=subject_atom.conditions,
                text=subject_atom.text,
                refs=list(subject_atom.refs),
                gloss=subject_atom.gloss,
                gloss_metadata=subject_atom.gloss_metadata,
                glossary_id=subject_atom.glossary_id,
            )
        )

        for element in self.elements:
            flattened.append(
                Atom(
                    type=element.atom_type or "element",
                    role=element.role,
                    party=subject_atom.party,
                    who=subject_atom.who,
                    who_text=subject_atom.who_text,
                    conditions=element.conditions,
                    text=element.text,
                    refs=[ref.to_legacy_text() for ref in element.references],
                    gloss=element.gloss,
                    gloss_metadata=element.gloss_metadata,
                    glossary_id=element.glossary_id,
                )
            )

        for lint in self.lints:
            flattened.append(
                Atom(
                    type=lint.atom_type or "lint",
                    role=lint.code,
                    party=subject_atom.party,
                    who=subject_atom.who,
                    who_text=subject_atom.who_text,
                    text=lint.message,
                    gloss=subject_atom.gloss,
                    gloss_metadata=lint.metadata,
                    glossary_id=subject_atom.glossary_id,
                )
            )

        return flattened


@dataclass
class Provision:
    """A discrete provision within a legal document."""

    text: str
    identifier: Optional[str] = None
    heading: Optional[str] = None
    node_type: Optional[str] = None
    toc_id: Optional[int] = None
    rule_tokens: Dict[str, Any] = field(default_factory=dict)
    cultural_flags: List[str] = field(default_factory=list)
    references: List[Tuple[str, Optional[str], Optional[str], Optional[str], str]] = (
        field(default_factory=list)
    )
    children: List["Provision"] = field(default_factory=list)
    principles: List[str] = field(default_factory=list)
    customs: List[str] = field(default_factory=list)
    rule_atoms: List[RuleAtom] = field(default_factory=list)
    atoms: List[Atom] = field(default_factory=list)
    legacy_atoms_factory: Optional[Callable[..., List[Atom]]] = field(
        default=None, repr=False, compare=False
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the provision to a dictionary."""
        self.ensure_rule_atoms()
        return {
            "text": self.text,
            "identifier": self.identifier,
            "heading": self.heading,
            "node_type": self.node_type,
            "toc_id": self.toc_id,
            "rule_tokens": dict(self.rule_tokens),
            "cultural_flags": list(self.cultural_flags),
            "references": [tuple(ref) for ref in self.references],
            "children": [c.to_dict() for c in self.children],
            "principles": list(self.principles),
            "customs": list(self.customs),
            "rule_atoms": [atom.to_dict() for atom in self.rule_atoms],
            "atoms": [atom.to_dict() for atom in self.atoms],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Provision":
        """Deserialize a provision from a dictionary."""
        provision = cls(
            text=data["text"],
            identifier=data.get("identifier"),
            heading=data.get("heading"),
            node_type=data.get("node_type"),
            toc_id=data.get("toc_id"),
            rule_tokens=dict(data.get("rule_tokens", {})),
            cultural_flags=list(data.get("cultural_flags", [])),
            references=[
                tuple(ref) if isinstance(ref, (list, tuple)) else tuple(ref)
                for ref in data.get("references", [])
            ],
            children=[cls.from_dict(c) for c in data.get("children", [])],
            principles=list(data.get("principles", [])),
            customs=list(data.get("customs", [])),
            rule_atoms=[RuleAtom.from_dict(a) for a in data.get("rule_atoms", [])],
            atoms=[Atom.from_dict(a) for a in data.get("atoms", [])],
        )
        provision.ensure_rule_atoms()
        return provision

    # ------------------------------------------------------------------
    # Compatibility helpers
    # ------------------------------------------------------------------
    def flatten_rule_atoms(self) -> List[Atom]:
        """Return the flattened legacy atoms generated from ``rule_atoms``."""

        if not self.rule_atoms:
            return list(self._resolve_legacy_atoms())

        flattened: List[Atom] = []
        for rule_atom in self.rule_atoms:
            flattened.extend(rule_atom.to_atoms())
        return flattened

    def _resolve_legacy_atoms(self, context: Any | None = None) -> List[Atom]:
        """Load legacy atoms from the compatibility view if needed."""

        if not self.atoms and self.legacy_atoms_factory is not None:
            factory = self.legacy_atoms_factory
            try:
                signature = inspect.signature(factory)
            except (TypeError, ValueError):
                signature = None

            if signature is None or len(signature.parameters) == 0:
                atoms = factory()  # type: ignore[misc]
            else:
                atoms = factory(context)
            self.atoms = list(atoms)
        return self.atoms

    def ensure_rule_atoms(self) -> None:
        """Ensure that ``rule_atoms`` exists, deriving from legacy atoms when necessary."""

        legacy_atoms = self._resolve_legacy_atoms()

        if not self.rule_atoms and legacy_atoms:
            self.rule_atoms = self._derive_rule_atoms_from_legacy(legacy_atoms)

        if self.rule_atoms and not self.atoms:
            self.atoms = self.flatten_rule_atoms()

        if self.rule_atoms:
            for rule_atom in self.rule_atoms:
                if rule_atom.toc_id is None:
                    rule_atom.toc_id = self.toc_id

    def sync_legacy_atoms(self) -> None:
        """Refresh ``atoms`` based on the structured rule representation."""

        if self.rule_atoms:
            self.atoms = self.flatten_rule_atoms()
            self.legacy_atoms_factory = None

    @staticmethod
    def _derive_rule_atoms_from_legacy(atoms: Iterable[Atom]) -> List[RuleAtom]:
        """Derive structured rule atoms from a sequence of legacy atoms."""

        structured: List[RuleAtom] = []
        current_rule: Optional[RuleAtom] = None

        def build_reference(value: Any) -> RuleReference:
            if isinstance(value, RuleReference):
                return RuleReference(
                    work=value.work,
                    section=value.section,
                    pinpoint=value.pinpoint,
                    citation_text=value.citation_text,
                )
            if isinstance(value, dict):
                return RuleReference(
                    work=value.get("work"),
                    section=value.get("section"),
                    pinpoint=value.get("pinpoint"),
                    citation_text=(
                        value.get("citation_text")
                        or value.get("text")
                        or value.get("citation")
                    ),
                )
            if isinstance(value, (list, tuple)):
                parts = list(value)
                work = parts[0] if parts else None
                section = parts[1] if len(parts) > 1 else None
                pinpoint = parts[2] if len(parts) > 2 else None
                citation_text = parts[3] if len(parts) > 3 else None
                if citation_text is None and len(parts) == 3:
                    citation_text = parts[2]
                return RuleReference(
                    work=work,
                    section=section,
                    pinpoint=pinpoint,
                    citation_text=citation_text,
                )
            if value is None:
                return RuleReference()
            return RuleReference(citation_text=str(value))

        def start_new_rule(base_atom: Atom) -> RuleAtom:
            subject_atom = Atom(
                type=base_atom.type,
                role=base_atom.role,
                party=base_atom.party,
                who=base_atom.who,
                who_text=base_atom.who_text,
                conditions=base_atom.conditions,
                text=base_atom.text,
                refs=list(base_atom.refs),
                gloss=base_atom.gloss,
                gloss_metadata=(
                    dict(base_atom.gloss_metadata)
                    if base_atom.gloss_metadata is not None
                    else None
                ),
            )
            rule = RuleAtom(
                atom_type=base_atom.type or "rule",
                role=base_atom.role,
                party=base_atom.party,
                who=base_atom.who,
                who_text=base_atom.who_text,
                conditions=base_atom.conditions,
                text=base_atom.text,
                subject_gloss=base_atom.gloss,
                subject_gloss_metadata=base_atom.gloss_metadata,
                subject=subject_atom,
                references=[build_reference(ref) for ref in base_atom.refs],
            )
            structured.append(rule)
            return rule

        for atom in atoms:
            atom_type = (atom.type or "").lower()
            if atom_type == "rule":
                current_rule = start_new_rule(atom)
                continue

            if atom_type == "lint":
                if current_rule is None:
                    current_rule = start_new_rule(atom)
                current_rule.lints.append(
                    RuleLint(
                        code=atom.role,
                        message=atom.text,
                        metadata=atom.gloss_metadata,
                        atom_type=atom.type,
                    )
                )
                continue

            if atom_type == "element":
                if current_rule is None:
                    current_rule = start_new_rule(Atom(type="rule"))
                current_rule.elements.append(
                    RuleElement(
                        role=atom.role,
                        text=atom.text,
                        conditions=atom.conditions,
                        gloss=atom.gloss,
                        gloss_metadata=atom.gloss_metadata,
                        references=[build_reference(ref) for ref in atom.refs],
                        atom_type=atom.type,
                    )
                )
                continue

            # Fallback: treat the atom as a standalone rule-level entry.
            current_rule = start_new_rule(atom)

        return structured
