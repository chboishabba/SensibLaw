"""Project explicit source-role metadata from catalogue glob declarations."""

from __future__ import annotations

from fnmatch import fnmatch
from pathlib import PurePosixPath
from typing import Any, Iterable, Mapping


def source_metadata_from_rules(
    relative_paths: Iterable[str],
    *,
    rules: Iterable[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Assign one explicit role to each path; unmatched/ambiguous paths fail closed."""

    ordered_rules = tuple(
        sorted(
            (dict(row) for row in rules),
            key=lambda row: (str(row.get("glob") or ""), str(row.get("source_role") or "")),
        )
    )
    result: dict[str, dict[str, Any]] = {}
    for raw_path in sorted({str(path) for path in relative_paths}):
        path = PurePosixPath(raw_path).as_posix()
        matches = [row for row in ordered_rules if fnmatch(path, str(row.get("glob") or ""))]
        if len(matches) > 1:
            distinct_roles = {str(row.get("source_role") or "") for row in matches}
            if len(distinct_roles) > 1:
                raise ValueError(f"ambiguous source admission role for {path}")
        rule = matches[0] if matches else {}
        result[path] = {
            "source_role": str(rule.get("source_role") or "unclassified"),
            "semantic_scope": str(rule.get("semantic_scope") or "source_material"),
            "jurisdiction_ref": str(rule.get("jurisdiction_ref") or ""),
            "authority_level": str(rule.get("authority_level") or ""),
            "provider_profile_refs": tuple(
                sorted(str(value) for value in rule.get("provider_profile_refs") or ())
            ),
            "temporal_refs": tuple(
                sorted(str(value) for value in rule.get("temporal_refs") or ())
            ),
        }
    return result


__all__ = ["source_metadata_from_rules"]
