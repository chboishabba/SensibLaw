from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple
import hashlib
import json
import re

from .text_span import TextSpan


def _clone_metadata(metadata: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if metadata is None:
        return None
    return dict(metadata)


@dataclass
class GlossaryLink:
    """Shared glossary linkage metadata."""

    text: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    glossary_id: Optional[int] = None

    def clone(self) -> "GlossaryLink":
        return GlossaryLink(
            text=self.text,
            metadata=_clone_metadata(self.metadata),
            glossary_id=self.glossary_id,
        )


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
    glossary: Optional[GlossaryLink] = None

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
            "gloss_metadata": _clone_metadata(self.gloss_metadata),
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
            glossary=GlossaryLink(
                text=data.get("gloss"),
                metadata=(
                    dict(data["gloss_metadata"])
                    if "gloss_metadata" in data and data["gloss_metadata"] is not None
                    else None
                ),
                glossary_id=data.get("glossary_id"),
            )
        )

    @property
    def gloss(self) -> Optional[str]:
        return self.glossary.text if self.glossary else None

    @gloss.setter
    def gloss(self, value: Optional[str]) -> None:
        if value is None and self.glossary is None:
            return
        if self.glossary is None:
            self.glossary = GlossaryLink()
        self.glossary.text = value

    @property
    def gloss_metadata(self) -> Optional[Dict[str, Any]]:
        return self.glossary.metadata if self.glossary else None

    @gloss_metadata.setter
    def gloss_metadata(self, value: Optional[Dict[str, Any]]) -> None:
        if value is None and self.glossary is None:
            return
        if self.glossary is None:
            self.glossary = GlossaryLink()
        self.glossary.metadata = _clone_metadata(value)

    @property
    def glossary_id(self) -> Optional[int]:
        return self.glossary.glossary_id if self.glossary else None

    @glossary_id.setter
    def glossary_id(self, value: Optional[int]) -> None:
        if value is None and self.glossary is None:
            return
        if self.glossary is None:
            self.glossary = GlossaryLink()
        self.glossary.glossary_id = value


@dataclass
class RuleReference:
    """A structured reference attached to a rule atom or element."""

    work: Optional[str] = None
    section: Optional[str] = None
    pinpoint: Optional[str] = None
    citation_text: Optional[str] = None
    source: Optional[str] = None
    uri: Optional[str] = None
    identity_hash: Optional[str] = None
    family_key: Optional[str] = None
    year: Optional[int] = None
    jurisdiction_hint: Optional[str] = None
    provenance: Optional[Dict[str, Any]] = None
    glossary: Optional[GlossaryLink] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "work": self.work,
            "section": self.section,
            "pinpoint": self.pinpoint,
            "citation_text": self.citation_text,
            "source": self.source,
            "uri": self.uri,
            "identity_hash": self.identity_hash,
            "family_key": self.family_key,
            "year": self.year,
            "jurisdiction_hint": self.jurisdiction_hint,
            "provenance": dict(self.provenance) if self.provenance is not None else None,
            "glossary_id": self.glossary_id,
        }

    def to_citation_dict(self) -> Dict[str, Any]:
        """Serialise a lean citation payload for graph/export consumers."""

        return {
            "work": self.work,
            "section": self.section,
            "pinpoint": self.pinpoint,
            "citation_text": self.citation_text,
            "glossary_id": self.glossary_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RuleReference":
        glossary_id = data.get("glossary_id")
        return cls(
            work=data.get("work"),
            section=data.get("section"),
            pinpoint=data.get("pinpoint"),
            citation_text=data.get("citation_text"),
            source=data.get("source"),
            uri=data.get("uri"),
            identity_hash=data.get("identity_hash"),
            family_key=data.get("family_key"),
            year=data.get("year"),
            jurisdiction_hint=data.get("jurisdiction_hint"),
            provenance=(
                dict(data["provenance"])
                if "provenance" in data and data["provenance"] is not None
                else None
            ),
            glossary=(
                GlossaryLink(glossary_id=glossary_id) if glossary_id is not None else None
            ),
        )

    def to_legacy_text(self) -> str:
        """Best-effort legacy rendering for compatibility."""

        if self.citation_text:
            return self.citation_text
        parts = [self.work, self.section, self.pinpoint]
        return " ".join(part for part in parts if part) or ""

    @property
    def glossary_id(self) -> Optional[int]:
        return self.glossary.glossary_id if self.glossary else None

    @glossary_id.setter
    def glossary_id(self, value: Optional[int]) -> None:
        if value is None and self.glossary is None:
            return
        if self.glossary is None:
            self.glossary = GlossaryLink()
        self.glossary.glossary_id = value

    # Identity helpers (metadata-only; do not affect extraction behaviour)
    def compute_identity(self) -> "RuleReference":
        """Populate identity-related metadata deterministically."""

        canonical_work = (self.work or "").strip().lower()

        family_key = _build_family_key(canonical_work)
        year_match = re.search(r"\b(\d{4})\b", canonical_work)
        year = int(year_match.group(1)) if year_match else None
        jurisdiction_hint = _extract_jurisdiction_hint(canonical_work)

        identity_payload = {
            "work": canonical_work or None,
            "section": (self.section or "").strip().lower() or None,
            "pinpoint": (self.pinpoint or "").strip().lower() or None,
            "family_key": family_key,
            "year": year,
            "jurisdiction_hint": jurisdiction_hint,
        }
        identity_json = json.dumps(identity_payload, sort_keys=True, separators=(",", ":"))
        identity_hash = hashlib.sha1(identity_json.encode("utf-8")).hexdigest()

        self.family_key = family_key
        self.year = year
        self.jurisdiction_hint = jurisdiction_hint
        self.identity_hash = identity_hash
        return self


def _build_family_key(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    cleaned = re.sub(r"\b\d{4}(?:-\d{4})?\b", "", value.lower())
    cleaned = cleaned.replace("(", " ").replace(")", " ")
    cleaned = re.sub(r"[^a-z&\s-]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.;:-")
    return cleaned or None


def _extract_jurisdiction_hint(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    match = re.search(
        r"\b(cth|commonwealth|aust|australia|nsw|vic|qld|wa|sa|tas|act|nt|hca)\b",
        value,
        re.IGNORECASE,
    )
    if match:
        token = match.group(1).upper()
        if token == "COMMONWEALTH" or token == "AUST" or token == "AUSTRALIA":
            return "CTH"
        return token
    return None


@dataclass
class RuleElement:
    """A granular fragment within a rule atom."""

    role: Optional[str] = None
    text: Optional[str] = None
    conditions: Optional[str] = None
    glossary: Optional[GlossaryLink] = None
    references: List[RuleReference] = field(default_factory=list)
    atom_type: Optional[str] = None
    text_span: Optional[TextSpan] = None
    span_status: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "text": self.text,
            "conditions": self.conditions,
            "gloss": self.gloss,
            "gloss_metadata": _clone_metadata(self.gloss_metadata),
            "glossary_id": self.glossary_id,
            "references": [ref.to_dict() for ref in self.references],
            "atom_type": self.atom_type,
            "text_span": self.text_span.to_dict() if self.text_span else None,
            "span_status": self.span_status,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RuleElement":
        return cls(
            role=data.get("role"),
            text=data.get("text"),
            conditions=data.get("conditions"),
            glossary=GlossaryLink(
                text=data.get("gloss"),
                metadata=(
                    dict(data["gloss_metadata"])
                    if "gloss_metadata" in data and data["gloss_metadata"] is not None
                    else None
                ),
                glossary_id=data.get("glossary_id"),
            ),
            references=[RuleReference.from_dict(r) for r in data.get("references", [])],
            atom_type=data.get("atom_type"),
            text_span=TextSpan.from_dict(data["text_span"])
            if data.get("text_span")
            else None,
            span_status=data.get("span_status"),
        )

    @property
    def gloss(self) -> Optional[str]:
        return self.glossary.text if self.glossary else None

    @gloss.setter
    def gloss(self, value: Optional[str]) -> None:
        if value is None and self.glossary is None:
            return
        if self.glossary is None:
            self.glossary = GlossaryLink()
        self.glossary.text = value

    @property
    def gloss_metadata(self) -> Optional[Dict[str, Any]]:
        return self.glossary.metadata if self.glossary else None

    @gloss_metadata.setter
    def gloss_metadata(self, value: Optional[Dict[str, Any]]) -> None:
        if value is None and self.glossary is None:
            return
        if self.glossary is None:
            self.glossary = GlossaryLink()
        self.glossary.metadata = _clone_metadata(value)

    @property
    def glossary_id(self) -> Optional[int]:
        return self.glossary.glossary_id if self.glossary else None

    @glossary_id.setter
    def glossary_id(self, value: Optional[int]) -> None:
        if value is None and self.glossary is None:
            return
        if self.glossary is None:
            self.glossary = GlossaryLink()
        self.glossary.glossary_id = value


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
    stable_id: Optional[str] = None
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
    subject_link: Optional[GlossaryLink] = None
    subject: Optional[Atom] = None
    references: List[RuleReference] = field(default_factory=list)
    elements: List[RuleElement] = field(default_factory=list)
    lints: List[RuleLint] = field(default_factory=list)
    text_span: Optional[TextSpan] = None
    span_status: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "toc_id": self.toc_id,
            "stable_id": self.stable_id,
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
            "subject_gloss_metadata": _clone_metadata(self.subject_gloss_metadata),
            "glossary_id": self.glossary_id,
            "subject": self.subject.to_dict() if self.subject is not None else None,
            "references": [ref.to_dict() for ref in self.references],
            "elements": [element.to_dict() for element in self.elements],
            "lints": [lint.to_dict() for lint in self.lints],
            "text_span": self.text_span.to_dict() if self.text_span else None,
            "span_status": self.span_status,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RuleAtom":
        return cls(
            toc_id=data.get("toc_id"),
            stable_id=data.get("stable_id"),
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
            subject_link=GlossaryLink(
                text=data.get("subject_gloss"),
                metadata=(
                    dict(data["subject_gloss_metadata"])
                    if "subject_gloss_metadata" in data
                    and data["subject_gloss_metadata"] is not None
                    else None
                ),
                glossary_id=data.get("glossary_id"),
            ),
            subject=(Atom.from_dict(data["subject"]) if data.get("subject") else None),
            references=[RuleReference.from_dict(r) for r in data.get("references", [])],
            elements=[RuleElement.from_dict(e) for e in data.get("elements", [])],
            lints=[
                RuleLint.from_dict(lint_data) for lint_data in data.get("lints", [])
            ],
            text_span=TextSpan.from_dict(data["text_span"])
            if data.get("text_span")
            else None,
            span_status=data.get("span_status"),
        )

    @property
    def subject_gloss(self) -> Optional[str]:
        return self.subject_link.text if self.subject_link else None

    @subject_gloss.setter
    def subject_gloss(self, value: Optional[str]) -> None:
        if value is None and self.subject_link is None:
            return
        if self.subject_link is None:
            self.subject_link = GlossaryLink()
        self.subject_link.text = value

    @property
    def subject_gloss_metadata(self) -> Optional[Dict[str, Any]]:
        return self.subject_link.metadata if self.subject_link else None

    @subject_gloss_metadata.setter
    def subject_gloss_metadata(self, value: Optional[Dict[str, Any]]) -> None:
        if value is None and self.subject_link is None:
            return
        if self.subject_link is None:
            self.subject_link = GlossaryLink()
        self.subject_link.metadata = _clone_metadata(value)

    @property
    def glossary_id(self) -> Optional[int]:
        return self.subject_link.glossary_id if self.subject_link else None

    @glossary_id.setter
    def glossary_id(self, value: Optional[int]) -> None:
        if value is None and self.subject_link is None:
            return
        if self.subject_link is None:
            self.subject_link = GlossaryLink()
        self.subject_link.glossary_id = value

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
        glossary: Optional[GlossaryLink]
        if (
            gloss is not None
            or gloss_metadata is not None
            or glossary_id is not None
        ):
            glossary = GlossaryLink(
                text=gloss,
                metadata=_clone_metadata(gloss_metadata),
                glossary_id=glossary_id,
            )
        elif base_atom and base_atom.glossary is not None:
            glossary = base_atom.glossary.clone()
        elif self.subject_link is not None:
            glossary = self.subject_link.clone()
        else:
            glossary = None
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
            glossary=glossary,
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
                glossary=(
                    subject_atom.glossary.clone()
                    if subject_atom.glossary is not None
                    else None
                ),
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
                    glossary=(
                        element.glossary.clone()
                        if element.glossary is not None
                        else None
                    ),
                )
            )

        for lint in self.lints:
            lint_glossary: Optional[GlossaryLink]
            if (
                subject_atom.gloss is not None
                or subject_atom.glossary_id is not None
                or lint.metadata is not None
            ):
                lint_glossary = GlossaryLink(
                    text=subject_atom.gloss,
                    metadata=_clone_metadata(lint.metadata),
                    glossary_id=subject_atom.glossary_id,
                )
            else:
                lint_glossary = (
                    subject_atom.glossary.clone()
                    if subject_atom.glossary is not None
                    else None
                )
            flattened.append(
                Atom(
                    type=lint.atom_type or "lint",
                    role=lint.code,
                    party=subject_atom.party,
                    who=subject_atom.who,
                    who_text=subject_atom.who_text,
                    text=lint.message,
                    glossary=lint_glossary,
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
    stable_id: Optional[str] = None
    position: Optional[int] = None
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
            "stable_id": self.stable_id,
            "position": self.position,
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
            stable_id=data.get("stable_id"),
            position=data.get("position"),
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
                if rule_atom.stable_id is None:
                    rule_atom.stable_id = self.stable_id

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
                    glossary_id=value.glossary_id,
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
                    glossary_id=value.get("glossary_id"),
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
                glossary=(
                    base_atom.glossary.clone()
                    if base_atom.glossary is not None
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
                subject_link=subject_atom.glossary,
                subject=subject_atom,
                references=[build_reference(ref) for ref in base_atom.refs],
                span_status="legacy_missing",
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
                        glossary=(
                            atom.glossary.clone()
                            if atom.glossary is not None
                            else None
                        ),
                        references=[build_reference(ref) for ref in atom.refs],
                        atom_type=atom.type,
                        span_status="legacy_missing",
                    )
                )
                continue

            # Fallback: treat the atom as a standalone rule-level entry.
            current_rule = start_new_rule(atom)

        return structured
