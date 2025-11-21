"""Registry loader for cultural flag metadata."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional, Tuple

import yaml


@dataclass(frozen=True)
class CulturalFlagMetadata:
    """Metadata describing a cultural flag entry."""

    identifier: str
    canonical_name: str
    description: str
    redaction: str
    consent_required: bool
    policy_text: str
    aliases: Tuple[str, ...] = ()

    def render_policy(self, *, redaction: Optional[str] = None, consent: Optional[bool] = None, transform: Optional[str] = None) -> str:
        """Render a policy string for annotations."""

        if self.policy_text:
            return self.policy_text

        applied_redaction = redaction if redaction is not None else self.redaction
        applied_consent = consent if consent is not None else self.consent_required
        applied_transform = transform or "none"
        consent_text = "requires consent" if applied_consent else "does not require consent"
        return (
            f"{self.canonical_name}: {self.description} "
            f"(redaction={applied_redaction}, {consent_text}, transform={applied_transform})"
        )


@dataclass(frozen=True)
class CulturalFlagRegistry:
    """In-memory index of cultural flags and alias mappings."""

    flags: Mapping[str, CulturalFlagMetadata]
    aliases: Mapping[str, str]

    def canonical_ids(self) -> Iterable[str]:
        return self.flags.keys()

    def resolve(self, name: str) -> Optional[CulturalFlagMetadata]:
        key = name.upper()
        identifier = self.aliases.get(key)
        if identifier is None:
            return None
        return self.flags.get(identifier)


def load_registry(path: Path) -> CulturalFlagRegistry:
    """Load the cultural flag registry from ``path``."""

    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}

    flags: Dict[str, CulturalFlagMetadata] = {}
    aliases: Dict[str, str] = {}
    for identifier, raw in payload.items():
        metadata = _parse_flag(identifier, raw or {})
        flags[identifier] = metadata
        aliases[identifier.upper()] = identifier
        for alias in metadata.aliases:
            aliases[alias.upper()] = identifier

    return CulturalFlagRegistry(flags=flags, aliases=aliases)


def _parse_flag(identifier: str, raw: Mapping[str, object]) -> CulturalFlagMetadata:
    canonical_name = str(raw.get("canonical_name") or identifier.replace("_", " ").title())
    description = str(raw.get("description") or "")
    defaults = raw.get("defaults")
    redaction = "none"
    consent_required = False
    if isinstance(defaults, Mapping):
        redaction = str(defaults.get("redaction", "none"))
        consent_required = bool(defaults.get("consent_required", False))
    annotation = raw.get("annotation")
    policy_text = ""
    if isinstance(annotation, Mapping):
        policy_text = str(annotation.get("policy") or "")
    aliases: Tuple[str, ...] = ()
    raw_aliases = raw.get("aliases", ())
    if isinstance(raw_aliases, (list, tuple)):
        aliases = tuple(str(item) for item in raw_aliases if item)
    return CulturalFlagMetadata(
        identifier=identifier,
        canonical_name=canonical_name,
        description=description,
        redaction=redaction,
        consent_required=consent_required,
        policy_text=policy_text,
        aliases=aliases,
    )


__all__ = [
    "CulturalFlagMetadata",
    "CulturalFlagRegistry",
    "load_registry",
]

