from __future__ import annotations


def build_indexed_text_unit(
    *,
    source_id: str,
    source_type: str,
    index: str | int,
    text: str,
    separator: str = ":",
) -> object:
    from .structure_report import TextUnit

    return TextUnit(
        unit_id=f"{source_id}{separator}{index}",
        source_id=source_id,
        source_type=source_type,
        text=text,
    )


def build_timestamped_speaker_text(*, ts: str, speaker: str, text: str) -> str:
    return f"[{ts}] {speaker}: {text}"


def build_header_body_text(*, header: str, body: str, separator: str = "\n") -> str:
    header = str(header).strip()
    body = str(body).strip()
    if header and body:
        return f"{header}{separator}{body}"
    return header or body


def build_canonical_conversation_text(
    *,
    text: str,
    speaker: str | None = None,
    ts: str | None = None,
    reply_to: str | None = None,
    context: tuple[str, ...] | list[str] | None = None,
) -> str:
    body = str(text).strip()
    if not body:
        raise ValueError("text must not be blank")
    is_question = "?" in body and not body.lstrip().startswith(("Q:", "q:", "A:", "a:"))

    lines: list[str] = []
    for item in context or ():
        normalized = str(item).strip()
        if normalized:
            lines.append(f"[context] {normalized}")

    normalized_reply = str(reply_to or "").strip()
    if normalized_reply:
        lines.append(f"[reply_to] {normalized_reply}")

    normalized_speaker = str(speaker or "").strip()
    normalized_ts = str(ts or "").strip()
    if normalized_ts and normalized_speaker and not is_question:
        lines.append(build_timestamped_speaker_text(ts=normalized_ts, speaker=normalized_speaker, text=body))
    elif normalized_speaker and not is_question:
        lines.append(f"{normalized_speaker}: {body}")
    elif normalized_ts and not is_question:
        lines.append(f"[{normalized_ts}] {body}")
    elif is_question:
        if normalized_ts and normalized_speaker:
            lines.append(f"[{normalized_ts}] {normalized_speaker}:")
        elif normalized_speaker:
            lines.append(f"{normalized_speaker}:")
        elif normalized_ts:
            lines.append(f"[{normalized_ts}]")
        lines.append(f"Q: {body}")
    else:
        lines.append(body)

    return "\n".join(lines)
