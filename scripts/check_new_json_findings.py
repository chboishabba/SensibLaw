#!/usr/bin/env python3
"""Fail when a branch introduces a JSON finding absent from its Git base."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import subprocess
import tarfile
import tempfile
from typing import Iterable

from audit_json_sin_bin import Finding, ROOT, scan


# The scanner and its direct guard tests necessarily contain search tokens.
# They remain excluded from delta comparison only; the authority test still
# scans every actual execution module.
META_PATHS = {
    "scripts/audit_json_sin_bin.py",
    "scripts/check_new_json_findings.py",
    "tests/architecture/test_no_json_execution_authority.py",
    "tests/storage/test_durable_work_item_migration.py",
}


@dataclass(frozen=True, order=True)
class FindingIdentity:
    path: str
    category: str
    symbol: str
    snippet: str

    @classmethod
    def from_finding(cls, finding: Finding) -> "FindingIdentity":
        return cls(
            path=finding.path,
            category=finding.category,
            symbol=finding.symbol,
            snippet=" ".join(finding.snippet.split()),
        )


def _production(findings: Iterable[Finding]) -> set[FindingIdentity]:
    return {
        FindingIdentity.from_finding(finding)
        for finding in findings
        if finding.path not in META_PATHS
    }


def _extract_git_tree(ref: str, destination: Path) -> None:
    archive = subprocess.run(
        ["git", "archive", "--format=tar", ref],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout
    tar_path = destination / "tree.tar"
    tar_path.write_bytes(archive)
    root = destination / "tree"
    root.mkdir()
    with tarfile.open(tar_path, mode="r:") as stream:
        # Git archive paths come from a trusted repository tree. Refuse links
        # nevertheless so a malformed history cannot escape the temp root.
        for member in stream.getmembers():
            if member.issym() or member.islnk() or member.name.startswith("/"):
                raise ValueError(f"unsafe archive member: {member.name}")
            resolved = (root / member.name).resolve()
            resolved.relative_to(root.resolve())
        stream.extractall(root, filter="data")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ref", required=True)
    args = parser.parse_args()

    current = _production(scan(ROOT))
    with tempfile.TemporaryDirectory(prefix="sensiblaw-json-base-") as raw:
        temporary = Path(raw)
        _extract_git_tree(args.base_ref, temporary)
        baseline = _production(scan(temporary / "tree"))

    introduced = sorted(current - baseline)
    if not introduced:
        print(
            f"No new JSON findings relative to {args.base_ref}; "
            f"current={len(current)} baseline={len(baseline)}"
        )
        return 0

    print(
        f"New JSON findings relative to {args.base_ref}: {len(introduced)}",
    )
    for finding in introduced:
        print(
            f"{finding.path}: {finding.category}: "
            f"{finding.symbol}: {finding.snippet}"
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
