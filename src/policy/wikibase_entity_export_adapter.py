"""Adapt a revision-pinned Wikibase entity export into generic observations.

This module understands the wire format of a Wikibase ``Special:EntityData``
export, but it does not resolve a local candidate or decide identity.  It emits
only bounded external observations which the provider-neutral bridge carrier can
attach, review, and pressure-test.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence


WIKIBASE_ENTITY_EXPORT_OBSERVATION_SCHEMA_VERSION = (
    "sl.wikibase_entity_export_observation.v0_1"
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _mapping_rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [deepcopy(dict(row)) for row in value if isinstance(row, Mapping)]


def _entity_from_document(
    document: Mapping[str, Any], *, external_ref: str
) -> Mapping[str, Any]:
    entities = document.get("entities")
    if isinstance(entities, Mapping):
        entity = entities.get(external_ref)
        if not isinstance(entity, Mapping):
            raise ValueError(f"entity export does not contain {external_ref}")
        return entity
    if _text(document.get("id")) != external_ref:
        raise ValueError(f"entity export id does not match {external_ref}")
    return document


def _language_values(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, Mapping):
        return []
    rows: list[dict[str, str]] = []
    for language, row in sorted(value.items()):
        candidates = [row] if isinstance(row, Mapping) else _mapping_rows(row)
        for candidate in candidates:
            text = _text(candidate.get("value"))
            if text:
                rows.append({"language": _text(language), "value": text})
    return rows


def build_entity_export_observation(
    entity_document: Mapping[str, Any],
    *,
    external_ref: str,
    external_revision_ref: str,
    source_ref: str | None = None,
) -> dict[str, Any]:
    """Validate a pinned export and expose bounded generic graph observations.

    ``external_ref`` and ``external_revision_ref`` are required inputs rather
    than inferred selectors. This prevents a successfully parsed but wrong or
    latest export from being silently treated as the requested observation.
    Property absence is intentionally *not* emitted: an entity export is not a
    closed graph view, so callers only receive positive property observations.
    """

    ref = _text(external_ref)
    revision = _text(external_revision_ref)
    if not ref:
        raise ValueError("external_ref is required")
    if not revision:
        raise ValueError("external_revision_ref is required")
    if not isinstance(entity_document, Mapping):
        raise ValueError("entity_document must be a mapping")

    entity = _entity_from_document(entity_document, external_ref=ref)
    if _text(entity.get("id")) != ref:
        raise ValueError(f"entity export id does not match {ref}")
    observed_revision = _text(entity.get("lastrevid"))
    if observed_revision != revision:
        raise ValueError(
            f"entity export revision {observed_revision or '<missing>'} does not match {revision}"
        )

    observed_properties: list[dict[str, Any]] = []
    claims = entity.get("claims")
    if isinstance(claims, Mapping):
        for property_ref, statements in sorted(claims.items()):
            normalized_property = _text(property_ref)
            if not normalized_property:
                continue
            statement_refs = [
                _text(statement.get("id"))
                for statement in _mapping_rows(statements)
                if _text(statement.get("id"))
            ]
            entity_value_refs = sorted(
                {
                    _text(
                        statement.get("mainsnak", {})
                        .get("datavalue", {})
                        .get("value", {})
                        .get("id")
                    )
                    for statement in _mapping_rows(statements)
                    if isinstance(statement.get("mainsnak"), Mapping)
                    and isinstance(statement["mainsnak"].get("datavalue"), Mapping)
                    and isinstance(
                        statement["mainsnak"]["datavalue"].get("value"), Mapping
                    )
                    and _text(statement["mainsnak"]["datavalue"]["value"].get("id"))
                }
            )
            observed_properties.append(
                {
                    "property_ref": normalized_property,
                    "state": "present",
                    "statement_refs": statement_refs,
                    "entity_value_refs": entity_value_refs,
                }
            )

    payload = {
        "schema_version": WIKIBASE_ENTITY_EXPORT_OBSERVATION_SCHEMA_VERSION,
        "provider_id": "wikibase_entity_export",
        "external_ref": ref,
        "external_revision_ref": revision,
        "labels": _language_values(entity.get("labels")),
        "aliases": _language_values(entity.get("aliases")),
        "observed_properties": observed_properties,
        "source": {"source_kind": "revision_pinned_entity_export"},
        "candidate_only": True,
        "identity_authority": False,
        "role_authority": False,
        "legal_authority": False,
        "promotion_authority": False,
    }
    if _text(source_ref):
        payload["source"]["source_ref"] = _text(source_ref)
    return payload


__all__ = [
    "WIKIBASE_ENTITY_EXPORT_OBSERVATION_SCHEMA_VERSION",
    "build_entity_export_observation",
]
