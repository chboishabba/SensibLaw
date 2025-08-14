"""Utilities for creating cryptographic proof packs."""

from __future__ import annotations

import hashlib
from pathlib import Path


def build_pack(dest: Path, content: str) -> Path:
    """Create a simple proof pack verifying ``content``.

    The pack consists of a ``data.txt`` file containing the supplied
    content, a ``SHA256SUMS`` manifest and a small ``verify.sh`` helper
    script which checks the hash.  The function returns the path to the
    verification script.
    """

    dest.mkdir(parents=True, exist_ok=True)
    data_file = dest / "data.txt"
    data_file.write_text(content + "\n", encoding="utf-8")
    digest = hashlib.sha256(data_file.read_bytes()).hexdigest()
    sums = dest / "SHA256SUMS"
    sums.write_text(f"{digest}  {data_file.name}\n", encoding="utf-8")
    verify = dest / "verify.sh"
    verify.write_text("#!/bin/sh\nsha256sum -c SHA256SUMS\n", encoding="utf-8")
    verify.chmod(0o755)
    return verify


__all__ = ["build_pack"]
