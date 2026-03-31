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
