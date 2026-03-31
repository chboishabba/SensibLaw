from __future__ import annotations

from pathlib import Path
from urllib.request import Request, urlopen


def resolve_loader_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def list_message_export_json_paths(export_path: str | Path) -> list[Path]:
    resolved = resolve_loader_path(export_path)
    if resolved.is_file():
        return [resolved]
    if resolved.is_dir():
        return sorted(path for path in resolved.rglob("message_*.json") if path.is_file())
    raise FileNotFoundError(str(resolved))


def fetch_text_url(url: str, *, headers: dict[str, str] | None = None, timeout: int = 20) -> str:
    request = Request(str(url), headers=headers or {})
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def find_timestamped_artifact_path(
    *,
    search_roots: list[Path],
    timestamp: int,
    suffix: str = ".webp",
) -> Path | None:
    for root in search_roots:
        if not root.exists():
            continue
        exact = sorted(root.glob(f"{int(timestamp)}{suffix}"))
        if exact:
            return exact[0]
        indexed = sorted(root.glob(f"{int(timestamp)}_*{suffix}"))
        if indexed:
            return indexed[0]
    return None


__all__ = [
    "fetch_text_url",
    "find_timestamped_artifact_path",
    "list_message_export_json_paths",
    "resolve_loader_path",
]
