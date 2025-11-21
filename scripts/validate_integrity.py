from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import yaml


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CORPUS_DIR = DATA_DIR / "corpus"
FLAGS_PATH = DATA_DIR / "cultural_flags.yaml"
RULES_PATH = DATA_DIR / "cultural_rules.yaml"


def _load_yaml(path: Path) -> Dict:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _build_flag_index(flags: Dict) -> Dict[str, str]:
    alias_index: Dict[str, str] = {}
    for key, meta in flags.items():
        candidates: Iterable[str] = [
            key,
            meta.get("canonical_name", ""),
            *meta.get("aliases", []),
        ]
        for candidate in candidates:
            if candidate:
                alias_index[candidate.lower()] = key
    return alias_index


def validate_legal_source_citations(corpus_dir: Path = CORPUS_DIR) -> List[str]:
    citations: Dict[str, Path] = {}
    errors: List[str] = []

    for path in sorted(corpus_dir.glob("*.json")):
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)

        metadata = payload.get("metadata", {})
        citation = metadata.get("citation")
        if not citation:
            errors.append(f"Missing citation in {path.name}")
            continue

        if citation in citations:
            errors.append(
                f"Duplicate citation '{citation}' in {path.name} and {citations[citation].name}"
            )
        else:
            citations[citation] = path

    return errors


def validate_cultural_flag_references(
    corpus_dir: Path = CORPUS_DIR,
    flags_path: Path = FLAGS_PATH,
    rules_path: Path = RULES_PATH,
) -> List[str]:
    errors: List[str] = []
    flags = _load_yaml(flags_path)
    rules = _load_yaml(rules_path)
    alias_index = _build_flag_index(flags)

    for path in sorted(corpus_dir.glob("*.json")):
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)

        for flag in payload.get("metadata", {}).get("cultural_flags", []):
            flag_key = alias_index.get(str(flag).lower())
            if not flag_key:
                errors.append(f"Unknown cultural flag '{flag}' in {path.name}")
                continue

            if flag_key not in rules:
                errors.append(
                    f"Cultural flag '{flag_key}' referenced in {path.name} is missing a handling rule"
                )

    for flag_key in flags:
        if flag_key not in rules:
            errors.append(f"Cultural flag '{flag_key}' is defined without a handling rule")

    return errors


def run_integrity_checks() -> Tuple[int, List[str]]:
    checks = [
        ("citation uniqueness", validate_legal_source_citations),
        ("cultural flag referential integrity", validate_cultural_flag_references),
    ]

    all_errors: List[str] = []
    for name, func in checks:
        errors = func()
        if errors:
            header = f"Failed {name}:"
            all_errors.append(header)
            all_errors.extend(f"- {error}" for error in errors)

    return (1 if all_errors else 0, all_errors)


def main() -> None:
    exit_code, errors = run_integrity_checks()
    if errors:
        print("\n".join(errors))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
