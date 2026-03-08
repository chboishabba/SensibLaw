from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlparse, urlunparse


def parse_source_url(url: str | None) -> dict[str, Any] | None:
    raw = str(url or "").strip()
    if not raw:
        return None
    parsed = urlparse(raw)
    scheme = (parsed.scheme or "").lower()
    host = (parsed.netloc or "").lower()
    path = parsed.path or ""
    query = parse_qs(parsed.query or "", keep_blank_values=False)
    normalized_host = host.removeprefix("www.")

    if scheme not in {"http", "https"} or not normalized_host:
        return {
            "kind": "unknown",
            "host": normalized_host or host or None,
            "canonical_url": raw,
        }

    if normalized_host in {"youtube.com", "m.youtube.com"}:
        video_id = (query.get("v") or [None])[0]
        if video_id:
            canonical_url = f"https://www.youtube.com/watch?v={video_id}"
            return {
                "kind": "youtube_video",
                "host": "youtube.com",
                "video_id": video_id,
                "canonical_url": canonical_url,
            }
        if path.startswith("/watch"):
            canonical_url = urlunparse(("https", "www.youtube.com", "/watch", "", parsed.query, ""))
            return {"kind": "youtube_watch", "host": "youtube.com", "canonical_url": canonical_url}

    if normalized_host == "youtu.be":
        video_id = path.lstrip("/").split("/", 1)[0] or None
        if video_id:
            canonical_url = f"https://www.youtube.com/watch?v={video_id}"
            return {
                "kind": "youtube_video",
                "host": "youtube.com",
                "video_id": video_id,
                "canonical_url": canonical_url,
            }

    if normalized_host == "chatgpt.com" and path.startswith("/c/"):
        conversation_id = path.split("/c/", 1)[1].split("/", 1)[0] or None
        canonical_url = f"https://chatgpt.com/c/{conversation_id}" if conversation_id else raw
        return {
            "kind": "chatgpt_conversation",
            "host": "chatgpt.com",
            "conversation_id": conversation_id,
            "canonical_url": canonical_url,
        }

    if normalized_host:
        canonical_path = path or "/"
        canonical_url = urlunparse(("https", normalized_host, canonical_path, "", "", ""))
        return {
            "kind": "web_article",
            "host": normalized_host,
            "canonical_url": canonical_url,
        }

    return {"kind": "unknown", "host": normalized_host or None, "canonical_url": raw}
