from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from src.reporting.source_loaders import list_message_export_json_paths
from src.reporting.structure_report import TextUnit
from src.reporting.source_identity import build_hashed_source_id, format_utc_iso_from_timestamp_ms
from src.reporting.text_unit_builders import build_indexed_text_unit, build_timestamped_speaker_text


SYSTEM_MESSAGE_FRAGMENTS = (
    "left the group.",
    "started this chat.",
    "sent an attachment.",
    "sent a photo.",
    "sent a video.",
    "sent a voice message.",
    "shared a post.",
    "shared a reel.",
    "named the group thread",
    "call started:",
    "call ended:",
    "call participants:",
    "reacted ",
    "device manufacturer",
    "device model",
    "device type",
    "ip address",
)
EXCLUDED_SENDERS = {
    "Unknown Sender",
    "Autofill information",
    "Messenger Contacts You've Blocked",
    "Facebook user",
    "Facebook Marketplace Assistant",
}
EXCLUDED_CONVERSATIONS = {
    "Messenger Contacts You've Blocked",
    "Your messages",
    "Autofill information",
}
EXCLUDED_SENDER_PREFIXES = (
    "a list of",
    "group invite link",
    "audio call",
    "you anonymously reported ",
    "marketplace",
)
MIN_MEANINGFUL_CHARS = 8
MESSAGE_STARTERS = (
    "We ",
    "We'",
    "I ",
    "I'",
    "Thanks",
    "Thank ",
    "Here ",
    "Your ",
    "You ",
    "Please ",
    "Download ",
    "View ",
    "Includes ",
    "Check ",
    "The ",
)


def _meaningful_char_count(text: str) -> int:
    return sum(1 for ch in text if ch.isalnum())


def _split_sender_message_contamination(sender: str, message: str) -> tuple[str, str]:
    sender = sender.strip()
    message = message.strip()
    if not sender:
        return sender, message
    for index in range(1, len(sender)):
        prev = sender[index - 1]
        curr = sender[index]
        if not prev.islower() or not curr.isupper():
            continue
        prefix = sender[:index].strip()
        suffix = sender[index:].strip()
        if len(prefix) < 2 or len(suffix) < 4:
            continue
        if not any(suffix.startswith(starter) for starter in MESSAGE_STARTERS):
            continue
        merged_message = suffix if not message else f"{suffix} {message}"
        return prefix, merged_message.strip()
    return sender, message


def _classify_message(*, sender: str, message: str, conversation: str, ts: str) -> str | None:
    if not sender or not message:
        return "missing_sender_or_message"
    if not ts:
        return "missing_timestamp"
    if sender in EXCLUDED_SENDERS or conversation in EXCLUDED_CONVERSATIONS:
        return "excluded_sender_or_conversation"
    sender_lowered = sender.casefold()
    if any(sender_lowered.startswith(prefix) for prefix in EXCLUDED_SENDER_PREFIXES):
        return "excluded_sender_prefix"
    lowered = message.casefold()
    if any(fragment in lowered for fragment in SYSTEM_MESSAGE_FRAGMENTS):
        return "system_fragment"
    if lowered.startswith(("you sent ", "you replied to ", "you unsent ", "you missed ", "you can now ")):
        return "system_prefix"
    if "marketplace" in lowered and "http" not in lowered and "https" not in lowered:
        return "marketplace_noise"
    if _meaningful_char_count(message) < MIN_MEANINGFUL_CHARS:
        return "too_short"
    return None


def _thread_key(payload: Mapping[str, Any], export_path: Path) -> str:
    thread_path = str(payload.get("thread_path") or "").strip()
    title = str(payload.get("title") or "").strip()
    basis = thread_path or title or export_path.name
    return build_hashed_source_id(prefix="messenger_export", raw=basis)


def _iter_export_paths(export_path: Path) -> list[Path]:
    return list_message_export_json_paths(export_path)


def load_messenger_export_units(export_path: str | Path, *, limit: int | None = None) -> list[TextUnit]:
    paths = _iter_export_paths(Path(export_path))
    units: list[TextUnit] = []
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            continue
        source_id = _thread_key(payload, path)
        conversation = str(payload.get("title") or path.stem).strip() or path.stem
        messages = payload.get("messages")
        if not isinstance(messages, list):
            continue
        rows: list[tuple[int, TextUnit]] = []
        for index, raw_message in enumerate(messages, start=1):
            if not isinstance(raw_message, Mapping):
                continue
            content = str(raw_message.get("content") or "").strip()
            sender = str(raw_message.get("sender_name") or "").strip()
            sender, content = _split_sender_message_contamination(sender, content)
            if not content:
                continue
            ts = format_utc_iso_from_timestamp_ms(raw_message.get("timestamp_ms"))
            reason = _classify_message(sender=sender, message=content, conversation=conversation, ts=ts)
            if reason is not None:
                continue
            sort_key = int(raw_message.get("timestamp_ms"))
            rows.append(
                (
                    sort_key,
                    build_indexed_text_unit(
                        source_id=source_id,
                        source_type="facebook_messages_archive_sample",
                        index=index,
                        text=build_timestamped_speaker_text(ts=ts, speaker=sender, text=content),
                    ),
                )
            )
        rows.sort(key=lambda item: (item[0], item[1].unit_id))
        for _, unit in rows:
            units.append(unit)
            if limit is not None and len(units) >= int(limit):
                return units
    return units


__all__ = ["load_messenger_export_units"]
