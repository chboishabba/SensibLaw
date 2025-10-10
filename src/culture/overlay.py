"""Apply cultural overlays to documents based on configured rules."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Sequence, Tuple

import yaml

from ..models.document import Document
from ..models.provision import Atom, Provision


@dataclass(frozen=True)
class CulturalRule:
    """Single overlay rule loaded from the YAML configuration."""

    redaction: str = "none"
    consent_required: bool = False
    transform: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "CulturalRule":
        return cls(
            redaction=str(data.get("redaction", "none")),
            consent_required=bool(data.get("consent_required", False)),
            transform=(data.get("transform") or None),
        )


class CulturalOverlay:
    """Apply cultural sensitivity rules to documents and provisions."""

    def __init__(self, rules: Dict[str, CulturalRule]):
        self._rules = dict(rules)

    @classmethod
    def from_yaml(cls, path: Path) -> "CulturalOverlay":
        """Load overlay rules from ``path``."""

        with path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}

        rules = {
            str(flag): CulturalRule.from_dict(config or {})
            for flag, config in payload.items()
        }
        return cls(rules)

    def apply(self, document: Document) -> Document:
        """Apply overlay rules to ``document`` in-place and return it."""

        flags = [
            flag for flag in (document.metadata.cultural_flags or []) if flag in self._rules
        ]
        if not flags:
            return document

        metadata = document.metadata
        existing_annotations = set(metadata.cultural_annotations)
        existing_redactions = set(metadata.cultural_redactions)

        for flag in flags:
            rule = self._rules[flag]
            annotation = self._build_annotation(flag, rule)
            if annotation not in existing_annotations:
                metadata.cultural_annotations.append(annotation)
                existing_annotations.add(annotation)
            if rule.redaction == "omit" and flag not in existing_redactions:
                metadata.cultural_redactions.append(flag)
                existing_redactions.add(flag)
            if rule.consent_required:
                metadata.cultural_consent_required = True

        transformed_body, _, _ = self._apply_rules_to_text(document.body, flags)
        document.body = transformed_body

        for provision in document.provisions:
            self._apply_to_provision(provision, flags)

        return document

    def _apply_to_provision(self, provision: Provision, flags: Sequence[str]) -> None:
        """Apply overlay rules recursively to provisions."""

        transformed, redacted_flag, transforms = self._apply_rules_to_text(
            provision.text, flags
        )
        provision.text = transformed
        if redacted_flag:
            self._clear_provision_metadata(provision)
        elif transforms:
            self._transform_provision_metadata(provision, transforms)
        for child in provision.children:
            self._apply_to_provision(child, flags)

    def _apply_rules_to_text(
        self, text: str, flags: Sequence[str]
    ) -> Tuple[str, Optional[str], Sequence[str]]:
        """Apply rules for ``flags`` to ``text`` returning the new text."""

        result = text
        redacted_by: Optional[str] = None
        transforms_applied: list[str] = []
        for flag in flags:
            rule = self._rules.get(flag)
            if not rule:
                continue
            if rule.redaction == "omit":
                result = f"[REDACTED: {flag}]"
                redacted_by = flag
                break
            if rule.transform == "hash":
                result = self._apply_transform(rule.transform, result)
                transforms_applied.append(rule.transform)
        return result, redacted_by, transforms_applied

    def _clear_provision_metadata(self, provision: Provision) -> None:
        """Remove extracted metadata from ``provision``."""

        provision.principles.clear()
        provision.atoms.clear()

    def _transform_provision_metadata(
        self, provision: Provision, transforms: Sequence[str]
    ) -> None:
        """Keep provision metadata in sync with applied transforms."""

        for transform in transforms:
            if transform == "hash":
                self._hash_provision_metadata(provision)
            else:
                self._clear_provision_metadata(provision)
                break

    def _hash_provision_metadata(self, provision: Provision) -> None:
        """Hash all extracted metadata for ``provision``."""

        provision.principles = [
            self._apply_transform("hash", principle)
            for principle in provision.principles
        ]
        for atom in provision.atoms:
            self._hash_atom_fields(atom)

    def _hash_atom_fields(self, atom: Atom) -> None:
        """Hash sensitive text fields on ``atom`` in-place."""

        if atom.text is not None:
            atom.text = self._apply_transform("hash", atom.text)
        if atom.who is not None:
            atom.who = self._apply_transform("hash", atom.who)
        if atom.conditions is not None:
            atom.conditions = self._apply_transform("hash", atom.conditions)
        if atom.refs:
            atom.refs = [self._apply_transform("hash", ref) for ref in atom.refs]

    @staticmethod
    def _apply_transform(transform: str, value: str) -> str:
        """Apply ``transform`` to ``value`` returning the transformed string."""

        if transform == "hash":
            return hashlib.sha256(value.encode("utf-8")).hexdigest()
        return value

    @staticmethod
    def _build_annotation(flag: str, rule: CulturalRule) -> str:
        transform = rule.transform or "none"
        return (
            f"{flag}: redaction={rule.redaction}, "
            f"consent_required={str(rule.consent_required)}, transform={transform}"
        )


_DEFAULT_RULES_PATH = Path(__file__).resolve().parents[2] / "data" / "cultural_rules.yaml"
_default_overlay: Optional[CulturalOverlay] = None


def get_default_overlay() -> CulturalOverlay:
    """Return a default overlay instance backed by the project configuration."""

    global _default_overlay
    if _default_overlay is None:
        _default_overlay = CulturalOverlay.from_yaml(_DEFAULT_RULES_PATH)
    return _default_overlay


__all__ = ["CulturalOverlay", "get_default_overlay", "CulturalRule"]
