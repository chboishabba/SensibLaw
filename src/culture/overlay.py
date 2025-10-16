"""Apply cultural overlays to documents based on configured rules."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Sequence, Tuple

import yaml

from src.models.document import Document
from src.models.provision import Provision


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

        body_text, _, transforms = self._apply_rules_to_text(document.body, flags)
        document.body = body_text

        for provision in document.provisions:
            self._apply_to_provision(provision, flags, dict(transforms))

        return document

    def _apply_to_provision(
        self,
        provision: Provision,
        flags: Sequence[str],
        transforms: Dict[str, str],
    ) -> None:
        """Apply overlay rules recursively to provisions."""

        transformed, redacted_flag, applied = self._apply_rules_to_text(
            provision.text, flags, transforms
        )
        provision.text = transformed
        if redacted_flag:
            provision.principles.clear()
            provision.atoms.clear()
        next_transforms = dict(transforms)
        next_transforms.update(applied)
        for child in provision.children:
            self._apply_to_provision(child, flags, next_transforms)

    def _apply_rules_to_text(
        self,
        text: str,
        flags: Sequence[str],
        transforms: Optional[Dict[str, str]] = None,
    ) -> Tuple[str, Optional[str], Dict[str, str]]:
        """Apply rules for ``flags`` to ``text`` returning the new text."""

        result = text
        redacted_by: Optional[str] = None
        applied: Dict[str, str] = {}
        for flag in flags:
            rule = self._rules.get(flag)
            if not rule:
                continue
            if rule.redaction == "omit":
                result = f"[REDACTED: {flag}]"
                redacted_by = flag
                break
            if rule.transform == "hash":
                if transforms and "hash" in transforms:
                    result = transforms["hash"]
                else:
                    result = hashlib.sha256(result.encode("utf-8")).hexdigest()
                    applied["hash"] = result
        return result, redacted_by, applied

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
