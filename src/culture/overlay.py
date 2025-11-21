"""Apply cultural overlays to documents based on configured rules."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import yaml

from src.models.document import Document
from src.models.provision import Provision
from .registry import CulturalFlagMetadata, CulturalFlagRegistry, load_registry


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

    def __init__(
        self,
        registry: CulturalFlagRegistry,
        rules: Dict[str, CulturalRule],
    ):
        self._registry = registry
        self._rules = dict(rules)

    @classmethod
    def from_yaml(cls, registry_path: Path, rules_path: Path) -> "CulturalOverlay":
        """Load overlay rules and registry configuration."""

        registry = load_registry(registry_path)

        with rules_path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}

        rules = {
            str(flag): CulturalRule.from_dict(config or {})
            for flag, config in payload.items()
        }
        return cls(registry, rules)

    def apply(self, document: Document) -> Document:
        """Apply overlay rules to ``document`` in-place and return it."""

        metadata = document.metadata
        resolved_flags = self._resolve_flags(metadata.cultural_flags or [])
        if not resolved_flags:
            return document

        metadata.cultural_flags = [flag.identifier for flag in resolved_flags]

        existing_annotations = {
            ann.get("flag")
            for ann in metadata.cultural_annotations
            if isinstance(ann, dict) and ann.get("kind") == "flag"
        }
        normalized_redactions: List[str] = []
        existing_redactions = set()
        for recorded in metadata.cultural_redactions:
            resolved = self._registry.resolve(recorded)
            identifier = resolved.identifier if resolved else str(recorded)
            if identifier not in existing_redactions:
                normalized_redactions.append(identifier)
                existing_redactions.add(identifier)
        metadata.cultural_redactions = normalized_redactions

        for flag in resolved_flags:
            rule = self._rules.get(flag.identifier) or CulturalRule(
                redaction=flag.redaction,
                consent_required=flag.consent_required,
                transform=None,
            )
            annotation = self._build_annotation(flag, rule)
            if flag.identifier not in existing_annotations:
                metadata.cultural_annotations.append(annotation)
                existing_annotations.add(flag.identifier)
            if rule.redaction == "omit" and flag.identifier not in existing_redactions:
                metadata.cultural_redactions.append(flag.identifier)
                existing_redactions.add(flag.identifier)
            if rule.consent_required:
                metadata.cultural_consent_required = True

        canonical_flags = [flag.identifier for flag in resolved_flags]

        body_text, _, transforms = self._apply_rules_to_text(
            document.body, canonical_flags
        )
        document.body = body_text

        for provision in document.provisions:
            self._apply_to_provision(provision, canonical_flags, dict(transforms))

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

    def _build_annotation(
        self, flag: CulturalFlagMetadata, rule: CulturalRule
    ) -> Dict[str, str]:
        transform = rule.transform or "none"
        policy_text = flag.render_policy(
            redaction=rule.redaction,
            consent=rule.consent_required,
            transform=transform,
        )
        return {"kind": "flag", "flag": flag.identifier, "policy": policy_text}

    def _resolve_flags(self, raw_flags: Sequence[str]) -> List[CulturalFlagMetadata]:
        resolved: List[CulturalFlagMetadata] = []
        seen = set()
        for flag in raw_flags:
            if not flag:
                continue
            metadata = self._registry.resolve(flag)
            if metadata and metadata.identifier not in seen:
                resolved.append(metadata)
                seen.add(metadata.identifier)
        return resolved


_BASE_PATH = Path(__file__).resolve().parents[2] / "data"
_DEFAULT_FLAGS_PATH = _BASE_PATH / "cultural_flags.yaml"
_DEFAULT_RULES_PATH = _BASE_PATH / "cultural_rules.yaml"
_default_overlay: Optional[CulturalOverlay] = None


def get_default_overlay() -> CulturalOverlay:
    """Return a default overlay instance backed by the project configuration."""

    global _default_overlay
    if _default_overlay is None:
        _default_overlay = CulturalOverlay.from_yaml(
            _DEFAULT_FLAGS_PATH, _DEFAULT_RULES_PATH
        )
    return _default_overlay


__all__ = ["CulturalOverlay", "get_default_overlay", "CulturalRule"]
