"""Canonical source-family projection for complete tranche runs.

This layer preserves raw artifacts and emits compiler-ready canonical text while
retaining a manifest that links every derived document to its original source.
It does not perform semantic extraction, entity resolution, or network access.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from html.parser import HTMLParser
from pathlib import Path
import shutil
from typing import Any, Iterable, Sequence
import zipfile

from src.ingestion.media_adapter import HtmlDocumentMediaAdapter, adapt_text_content


SOURCE_PROJECTION_CONTRACT = "source-family-canonical-projection:v0_1"
_SUPPORTED_SUFFIXES = {".html", ".htm", ".txt", ".text", ".md", ".markdown", ".pdf", ".epub"}


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._suppressed = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag.lower() in {"script", "style", "noscript"}:
            self._suppressed += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"} and self._suppressed:
            self._suppressed -= 1

    def handle_data(self, data: str) -> None:
        if not self._suppressed and data.strip():
            self.parts.append(data)

    def text(self) -> str:
        return " ".join(" ".join(self.parts).split())


@dataclass(frozen=True)
class SourceProjectionRow:
    source_ref: str
    source_path: str
    raw_path: str
    canonical_path: str
    media_type: str
    adapter_ref: str
    raw_sha256: str
    canonical_sha256: str
    raw_bytes: int
    canonical_chars: int
    anchor_state: str
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "warnings": list(self.warnings)}


@dataclass(frozen=True)
class SourceProjectionManifest:
    roots: tuple[str, ...]
    documents: tuple[SourceProjectionRow, ...]
    ignored_paths: tuple[str, ...] = ()
    failures: tuple[dict[str, str], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "sl.source_projection_manifest.v0_1",
            "contract_ref": SOURCE_PROJECTION_CONTRACT,
            "roots": list(self.roots),
            "documents": [row.to_dict() for row in self.documents],
            "ignored_paths": list(self.ignored_paths),
            "failures": [dict(row) for row in self.failures],
            "summary": {
                "document_count": len(self.documents),
                "failure_count": len(self.failures),
                "raw_bytes": sum(row.raw_bytes for row in self.documents),
                "canonical_chars": sum(row.canonical_chars for row in self.documents),
            },
            "authority": "document_projection_only",
        }


def _extract_pdf(path: Path) -> tuple[str, tuple[str, ...]]:
    try:
        from pdfminer.high_level import extract_text  # type: ignore[import-not-found]
    except ImportError:
        return "", ("pdfminer_unavailable",)
    try:
        return str(extract_text(str(path)) or "").strip(), ()
    except Exception as error:  # pragma: no cover - backend-specific failure
        return "", (f"pdf_extract_failed:{type(error).__name__}",)


def _extract_epub(path: Path) -> tuple[str, tuple[str, ...]]:
    parts: list[str] = []
    warnings: list[str] = []
    try:
        with zipfile.ZipFile(path) as archive:
            names = sorted(
                name
                for name in archive.namelist()
                if name.lower().endswith((".html", ".htm", ".xhtml"))
            )
            for name in names:
                try:
                    raw = archive.read(name).decode("utf-8", errors="replace")
                    parser = _HTMLTextExtractor()
                    parser.feed(raw)
                    text = parser.text()
                    if text:
                        parts.append(text)
                except Exception as error:  # pragma: no cover - corrupt member
                    warnings.append(f"epub_member_failed:{name}:{type(error).__name__}")
    except Exception as error:
        return "", (f"epub_extract_failed:{type(error).__name__}",)
    return "\n\n".join(parts).strip(), tuple(warnings)


def _canonicalize(path: Path, raw: bytes) -> tuple[str, str, tuple[str, ...], str]:
    suffix = path.suffix.lower()
    if suffix in {".html", ".htm"}:
        source_ref = f"source:{_sha256_bytes(raw)}"
        adapter = HtmlDocumentMediaAdapter(source_artifact_ref=source_ref)
        canonical = adapter.adapt(raw.decode("utf-8", errors="replace"))
        return canonical.text, "text/html", tuple(canonical.warnings), "media:html:v0_1"
    if suffix in {".txt", ".text", ".md", ".markdown"}:
        canonical = adapt_text_content(
            raw.decode("utf-8", errors="replace"),
            provenance={"source_path": str(path)},
        )
        media_type = "text/markdown" if suffix in {".md", ".markdown"} else "text/plain"
        return canonical.text, media_type, tuple(canonical.warnings), "media:utf8-text:v0_1"
    if suffix == ".pdf":
        text, warnings = _extract_pdf(path)
        return text, "application/pdf", warnings, "media:pdf-text:v0_1"
    if suffix == ".epub":
        text, warnings = _extract_epub(path)
        return text, "application/epub+zip", warnings, "media:epub-text:v0_1"
    raise ValueError(f"unsupported source suffix: {suffix}")


def _iter_sources(roots: Sequence[Path]) -> Iterable[tuple[Path, Path]]:
    for root in roots:
        resolved = root.resolve()
        if resolved.is_file():
            yield resolved.parent, resolved
            continue
        if not resolved.exists():
            continue
        for path in sorted(resolved.rglob("*")):
            if path.is_file():
                yield resolved, path


def project_source_families(
    roots: Sequence[Path],
    *,
    output_dir: Path,
    max_files: int | None = None,
    max_file_bytes: int | None = None,
) -> SourceProjectionManifest:
    """Project source families into raw evidence and compiler-ready text.

    PDF and EPUB content is emitted as canonical text but the manifest retains
    the original media type, source path, content hash, and an explicit
    ``derived_text_with_source_anchor`` state. No derived text is allowed to
    masquerade as an original text artifact.
    """

    raw_dir = output_dir / "raw"
    canonical_dir = output_dir / "canonical"
    raw_dir.mkdir(parents=True, exist_ok=True)
    canonical_dir.mkdir(parents=True, exist_ok=True)
    documents: list[SourceProjectionRow] = []
    ignored: list[str] = []
    failures: list[dict[str, str]] = []
    seen_raw: set[str] = set()

    for root, path in _iter_sources(roots):
        relative = path.relative_to(root)
        if path.suffix.lower() not in _SUPPORTED_SUFFIXES:
            ignored.append(str(path))
            continue
        if max_files is not None and len(documents) >= max_files:
            ignored.append(str(path))
            continue
        try:
            raw = path.read_bytes()
            if max_file_bytes is not None and len(raw) > max_file_bytes:
                ignored.append(str(path))
                continue
            raw_sha = _sha256_bytes(raw)
            if raw_sha in seen_raw:
                ignored.append(str(path))
                continue
            canonical_text, media_type, warnings, adapter_ref = _canonicalize(path, raw)
            if not canonical_text.strip():
                failures.append({"path": str(path), "reason": "empty_canonical_text"})
                continue
            seen_raw.add(raw_sha)
            ordinal = len(documents) + 1
            stem = f"{ordinal:04d}_{raw_sha[:12]}"
            raw_target = raw_dir / f"{stem}{path.suffix.lower()}"
            canonical_target = canonical_dir / f"{stem}.txt"
            shutil.copyfile(path, raw_target)
            canonical_target.write_text(canonical_text, encoding="utf-8")
            source_ref = f"source:{raw_sha}"
            anchor_state = (
                "derived_text_with_source_anchor"
                if path.suffix.lower() in {".pdf", ".epub", ".html", ".htm"}
                else "source_text_coordinate_preserved"
            )
            documents.append(
                SourceProjectionRow(
                    source_ref=source_ref,
                    source_path=str(path),
                    raw_path=str(raw_target.relative_to(output_dir)),
                    canonical_path=str(canonical_target.relative_to(output_dir)),
                    media_type=media_type,
                    adapter_ref=adapter_ref,
                    raw_sha256=raw_sha,
                    canonical_sha256=_sha256_text(canonical_text),
                    raw_bytes=len(raw),
                    canonical_chars=len(canonical_text),
                    anchor_state=anchor_state,
                    warnings=warnings,
                )
            )
        except Exception as error:
            failures.append({"path": str(path), "reason": f"{type(error).__name__}:{error}"})

    return SourceProjectionManifest(
        roots=tuple(str(path.resolve()) for path in roots),
        documents=tuple(documents),
        ignored_paths=tuple(sorted(ignored)),
        failures=tuple(failures),
    )


__all__ = [
    "SOURCE_PROJECTION_CONTRACT",
    "SourceProjectionManifest",
    "SourceProjectionRow",
    "project_source_families",
]
