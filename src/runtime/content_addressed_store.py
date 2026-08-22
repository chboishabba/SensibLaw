"""Content-addressed storage for large immutable semantic payloads.

PostgreSQL remains the authority for identities, availability and publication.
This interface stores large immutable bodies behind digest-bound locators so a
local filesystem can be replaced by S3-compatible object storage without
changing graph or receipt identity.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import os
from pathlib import Path
import shutil
from tempfile import NamedTemporaryFile
from typing import BinaryIO, Protocol


CONTENT_ADDRESSED_DESCRIPTOR_SCHEMA = "sensiblaw.content-addressed-payload.v1"
COPY_CHUNK_BYTES = 1024 * 1024


@dataclass(frozen=True)
class ContentAddressedPayload:
    payload_ref: str
    sha256_hex: str
    byte_count: int
    media_type: str
    storage_kind: str
    locator: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": CONTENT_ADDRESSED_DESCRIPTOR_SCHEMA,
            **asdict(self),
        }


class ContentAddressedStore(Protocol):
    def put_stream(
        self,
        stream: BinaryIO,
        *,
        media_type: str,
    ) -> ContentAddressedPayload: ...

    def open_payload(self, payload: ContentAddressedPayload) -> BinaryIO: ...

    def verify(self, payload: ContentAddressedPayload) -> bool: ...


class FilesystemContentAddressedStore:
    """Atomic local implementation suitable for one host or shared filesystem."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, digest: str) -> Path:
        if len(digest) != 64 or any(
            character not in "0123456789abcdef" for character in digest
        ):
            raise ValueError("content digest must be lower-case SHA-256")
        return self.root / "sha256" / digest[:2] / digest

    def put_stream(
        self,
        stream: BinaryIO,
        *,
        media_type: str,
    ) -> ContentAddressedPayload:
        digest = sha256()
        byte_count = 0
        temporary_root = self.root / ".tmp"
        temporary_root.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(dir=temporary_root, delete=False) as temporary:
            temporary_path = Path(temporary.name)
            while chunk := stream.read(COPY_CHUNK_BYTES):
                digest.update(chunk)
                temporary.write(chunk)
                byte_count += len(chunk)
            temporary.flush()
            os.fsync(temporary.fileno())
        digest_hex = digest.hexdigest()
        target = self._path(digest_hex)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            temporary_path.unlink(missing_ok=True)
        else:
            temporary_path.replace(target)
        payload_ref = "content-sha256:" + digest_hex
        return ContentAddressedPayload(
            payload_ref=payload_ref,
            sha256_hex=digest_hex,
            byte_count=byte_count,
            media_type=media_type,
            storage_kind="filesystem-content-addressed",
            locator=str(target),
        )

    def put_file(
        self,
        path: str | Path,
        *,
        media_type: str,
    ) -> ContentAddressedPayload:
        with Path(path).open("rb") as stream:
            return self.put_stream(stream, media_type=media_type)

    def open_payload(self, payload: ContentAddressedPayload) -> BinaryIO:
        expected = self._path(payload.sha256_hex)
        if Path(payload.locator).resolve() != expected.resolve():
            raise ValueError("payload locator does not match its digest path")
        return expected.open("rb")

    def verify(self, payload: ContentAddressedPayload) -> bool:
        try:
            stream = self.open_payload(payload)
        except (OSError, ValueError):
            return False
        digest = sha256()
        byte_count = 0
        with stream:
            while chunk := stream.read(COPY_CHUNK_BYTES):
                digest.update(chunk)
                byte_count += len(chunk)
        return (
            byte_count == payload.byte_count
            and digest.hexdigest() == payload.sha256_hex
        )

    def materialize(
        self,
        payload: ContentAddressedPayload,
        destination: str | Path,
    ) -> Path:
        if not self.verify(payload):
            raise ValueError("content-addressed payload failed verification")
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        with self.open_payload(payload) as source, target.open("wb") as output:
            shutil.copyfileobj(source, output, length=COPY_CHUNK_BYTES)
        return target


def register_payload_segment(
    cursor: object,
    *,
    segment_ref: str,
    manifest_ref: str,
    family_ref: str,
    sequence_start: int,
    sequence_end: int,
    record_count: int,
    payload: ContentAddressedPayload,
    encoding_ref: str,
) -> None:
    """Register a payload atomically with its PostgreSQL graph manifest."""

    execute = getattr(cursor, "execute")
    execute(
        """
        INSERT INTO execution.semantic_graph_family_segment
            (segment_ref, manifest_ref, family_ref, sequence_start,
             sequence_end, record_count, byte_count, segment_sha256,
             storage_kind_ref, storage_locator, encoding_ref, availability_ref)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'available')
        ON CONFLICT (segment_ref) DO NOTHING
        """,
        (
            segment_ref,
            manifest_ref,
            family_ref,
            sequence_start,
            sequence_end,
            record_count,
            payload.byte_count,
            bytes.fromhex(payload.sha256_hex),
            payload.storage_kind,
            payload.locator,
            encoding_ref,
        ),
    )


__all__ = [
    "CONTENT_ADDRESSED_DESCRIPTOR_SCHEMA",
    "ContentAddressedPayload",
    "ContentAddressedStore",
    "FilesystemContentAddressedStore",
    "register_payload_segment",
]
