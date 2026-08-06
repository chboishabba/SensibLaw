"""Install pre-decode integrity verification for reused binary families."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import pickle
from typing import Any, Mapping

from src.pnf.streaming_build_reader import (
    BINARY_FAMILY_ENCODING,
    family_descriptor,
)
from src.policy.carriers.canonical import canonical_bytes


_INSTALL_MARKER = "_binary_family_integrity_installed"


def _raw_digest(path: Path) -> tuple[str, int]:
    digest = sha256()
    byte_count = 0
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
            byte_count += len(chunk)
    return digest.hexdigest(), byte_count


def hardened_existing_binary_descriptor(
    path: Path,
    *,
    family: str,
    record_count: int,
) -> dict[str, Any]:
    artifact_digest, artifact_byte_count = _raw_digest(path)
    semantic_digest = sha256()
    semantic_byte_count = 0
    observed = 0
    with path.open("rb") as handle:
        while True:
            length_bytes = handle.read(8)
            if not length_bytes:
                break
            if len(length_bytes) != 8:
                raise ValueError(f"{family} checkpoint has a truncated frame")
            length = int.from_bytes(length_bytes, "big")
            encoded = handle.read(length)
            if len(encoded) != length:
                raise ValueError(f"{family} checkpoint has a truncated payload")
            try:
                value = pickle.loads(encoded)
            except (EOFError, pickle.PickleError, AttributeError, ValueError) as error:
                raise ValueError(f"{family} checkpoint frame decode failed") from error
            if not isinstance(value, Mapping):
                raise ValueError(f"{family} checkpoint row is not a mapping")
            semantic = canonical_bytes(dict(value))
            frame = len(semantic).to_bytes(8, "big") + semantic
            semantic_digest.update(frame)
            semantic_byte_count += len(frame)
            observed += 1
    if observed != record_count:
        raise ValueError(f"{family} checkpoint count changed")
    return family_descriptor(
        family=family,
        storage_kind="binary",
        record_count=observed,
        byte_count=semantic_byte_count,
        artifact_byte_count=artifact_byte_count,
        artifact_digest=artifact_digest,
        ordered_digest=semantic_digest.hexdigest(),
        path=str(path),
        encoding_ref=BINARY_FAMILY_ENCODING,
    )


def install_binary_family_integrity_execution() -> bool:
    from src.policy import reference_backed_finalization as reference

    if getattr(reference, _INSTALL_MARKER, False):
        return False
    reference._existing_binary_descriptor = hardened_existing_binary_descriptor
    setattr(reference, _INSTALL_MARKER, True)
    return True


__all__ = [
    "hardened_existing_binary_descriptor",
    "install_binary_family_integrity_execution",
]
