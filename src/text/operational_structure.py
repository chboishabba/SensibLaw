from __future__ import annotations

from dataclasses import dataclass
import itertools
import re

from src.text.message_transcript import parse_message_header, parse_time_range_header


@dataclass(frozen=True, slots=True)
class StructureOccurrence:
    text: str
    norm_text: str
    kind: str
    start_char: int
    end_char: int
    flags: int = 0


_ROLE_LINE_RE = re.compile(r"(?m)^(User|Assistant|System|Developer|Tool)\s*:\s*", re.IGNORECASE)
_SPEAKER_LINE_RE = re.compile(
    r"(?m)^(?:Q|A|THE COURT|WITNESS|COUNSEL|JUDGE|MAGISTRATE|REGISTRAR|SPEAKER|CHAIR|MR|MS|DR)\b[^:\n]{0,40}:"
)
_TIMESTAMP_RE = re.compile(r"(?<!\d)(?:\[\s*)?(?:\d{1,2}:\d{2}(?::\d{2})?)(?:\s*\])?(?!\d)")
_PROMPT_COMMAND_RE = re.compile(r"(?m)^(?:\$|%|❯)\s+([A-Za-z0-9_.:/-]+)")
_BACKTICK_COMMAND_RE = re.compile(r"`((?:npm|python|pytest|node|bash|cd|git|cargo|uv|pnpm|yarn)\b[^`]*)`")
_FLAG_RE = re.compile(r"(?<!\w)(--[a-z0-9][a-z0-9-]*|-[A-Za-z])(?!\w)", re.IGNORECASE)
_PATH_RE = re.compile(
    r"(?<![\w])("
    r"(?:/|~\/|\.\.?/)[A-Za-z0-9._/\-]+"
    r"|[A-Za-z0-9_.\-]+(?:/[A-Za-z0-9._\-]+)+"
    r"|[A-Za-z0-9_.\-]+\.(?:md|txt|json|py|sh|sqlite|yaml|yml|ts|js)"
    r")"
)
_ENV_ASSIGN_RE = re.compile(r"(?<!\w)([A-Z][A-Z0-9_]{2,})(?==)")
_ENV_DOLLAR_RE = re.compile(r"\$([A-Z][A-Z0-9_]{2,})")
_ENV_BACKTICK_RE = re.compile(r"`([A-Z][A-Z0-9_]*_[A-Z0-9_]+)`")
_CODE_FENCE_RE = re.compile(r"(?ms)^```[^\n]*\n.*?^```$")
_QUOTE_BLOCK_RE = re.compile(r"(?m)^>\s+.*$")
_HEADING_RE = re.compile(r"(?m)^#{1,6}\s+.+$")
_NUMBERED_STEP_RE = re.compile(r"(?m)^(?:\d+)\.\s+.+$")
_QA_RE = re.compile(r"(?m)^(Q|A)\s*:\s*", re.IGNORECASE)
_EXIT_CODE_RE = re.compile(r"\bexit code\s+(\d+)\b", re.IGNORECASE)
_TRACE_RE = re.compile(r"(?m)^\s*File\s+\"[^\"]+\", line \d+")
_PROCEDURE_RE = re.compile(
    r"(?im)^(?:cross-examination|re-examination|adjourned|submission|objection|witness sworn)\b.*$"
)
_EXHIBIT_RE = re.compile(r"(?im)\bexhibit\s+[A-Z]?\d+[A-Z]?\b")


def _norm_slug(value: str) -> str:
    out: list[str] = []
    last_underscore = False
    for ch in value.casefold():
        if ch.isalnum():
            out.append(ch)
            last_underscore = False
        else:
            if not last_underscore:
                out.append("_")
                last_underscore = True
    return "".join(out).strip("_") or "unknown"


def _emit(matches: list[StructureOccurrence], match: re.Match[str], kind: str, norm_text: str, text: str | None = None) -> None:
    start, end = match.span()
    matches.append(
        StructureOccurrence(
            text=text if text is not None else match.group(),
            norm_text=norm_text,
            kind=kind,
            start_char=start,
            end_char=end,
        )
    )


def _looks_like_path(raw: str) -> bool:
    if raw.startswith(("/", "./", "../", "~/")):
        return True
    segments = [segment for segment in raw.split("/") if segment]
    if len(segments) < 2:
        return False
    if "://" in raw:
        return True
    plain_segments = [segment for segment in segments if segment]
    if all(segment.replace("-", "").replace("_", "").isalpha() for segment in plain_segments):
        allow_plain_roots = {
            "src",
            "docs",
            "tests",
            "test",
            "outputs",
            "output",
            "data",
            "scripts",
            "sensiblaw",
            "itir",
            "statibaker",
            "seameinit",
            "__context",
            "context",
        }
        if plain_segments[0].casefold() not in allow_plain_roots:
            return False
    joined = "".join(segments)
    if joined.isdigit():
        return False
    if all(segment.isdigit() for segment in segments):
        return False
    if all(segment.upper() == segment and any(ch.isalpha() for ch in segment) for segment in segments):
        return False
    if all(re.fullmatch(r"[A-Z]\d+", segment) for segment in segments):
        return False
    if raw.count("/") >= 2 and all(re.fullmatch(r"[A-Za-z]?\d+", segment) for segment in segments):
        return False
    if any("." in segment for segment in segments):
        return True
    return any(any(ch.isalpha() for ch in segment) for segment in segments)


def collect_operational_structure_occurrences(text: str) -> list[StructureOccurrence]:
    matches: list[StructureOccurrence] = []
    transcript_timestamp_spans: list[tuple[int, int]] = []
    offset = 0
    for line in text.splitlines(True):
        content = line.rstrip("\n")
        range_header = parse_time_range_header(content)
        if range_header is not None:
            header_start = offset
            header_end = offset + range_header.header_end
            transcript_timestamp_spans.append((header_start, header_end))
            matches.append(
                StructureOccurrence(
                    text=content[: range_header.header_end].strip(),
                    norm_text=range_header.range_norm,
                    kind="timestamp_range_ref",
                    start_char=header_start,
                    end_char=header_end,
                )
            )
        message_header = parse_message_header(content)
        if message_header is not None:
            header_start = offset
            header_end = offset + message_header.header_end
            transcript_timestamp_spans.append((header_start, header_end))
            speaker = message_header.speaker.strip()
            matches.append(
                StructureOccurrence(
                    text=speaker,
                    norm_text=f"speaker:{_norm_slug(speaker)}",
                    kind="speaker_ref",
                    start_char=header_start,
                    end_char=header_end,
                )
            )
            matches.append(
                StructureOccurrence(
                    text=content[: message_header.header_end].rstrip(),
                    norm_text=f"msg:{_norm_slug(speaker)}",
                    kind="message_boundary_ref",
                    start_char=header_start,
                    end_char=header_end,
                )
            )
            matches.append(
                StructureOccurrence(
                    text=content[: message_header.header_end].rstrip(),
                    norm_text=message_header.timestamp_norm,
                    kind="timestamp_ref",
                    start_char=header_start,
                    end_char=header_end,
                )
            )
        offset += len(line)

    for match in _ROLE_LINE_RE.finditer(text):
        role = match.group(1).casefold()
        _emit(matches, match, "role_ref", f"role:{role}", text=match.group().rstrip())
        _emit(matches, match, "turn_ref", f"turn:{role}", text=match.group().rstrip())

    for match in _SPEAKER_LINE_RE.finditer(text):
        label = match.group().rstrip(":").strip()
        _emit(matches, match, "speaker_ref", f"speaker:{_norm_slug(label)}", text=match.group().rstrip())

    for match in _TIMESTAMP_RE.finditer(text):
        if any(start <= match.start() and match.end() <= end for start, end in transcript_timestamp_spans):
            continue
        raw = match.group().strip("[] ").casefold()
        _emit(matches, match, "timestamp_ref", f"ts:{raw}")

    for match in _PROMPT_COMMAND_RE.finditer(text):
        command = match.group(1).split()[0].split("/")[-1]
        _emit(matches, match, "command_ref", f"cmd:{_norm_slug(command)}")

    for match in _BACKTICK_COMMAND_RE.finditer(text):
        command = match.group(1).strip().split()[0].split("/")[-1]
        _emit(matches, match, "command_ref", f"cmd:{_norm_slug(command)}", text=match.group(1).strip())

    for match in _FLAG_RE.finditer(text):
        _emit(matches, match, "flag_ref", f"flag:{match.group(1).casefold()}")

    for match in _PATH_RE.finditer(text):
        raw = match.group(1)
        if raw.startswith("--"):
            continue
        if not _looks_like_path(raw):
            continue
        _emit(matches, match, "path_ref", f"path:{_norm_slug(raw)}", text=raw)

    for pattern in (_ENV_ASSIGN_RE, _ENV_DOLLAR_RE, _ENV_BACKTICK_RE):
        for match in pattern.finditer(text):
            raw = match.group(1)
            _emit(matches, match, "env_var_ref", f"env:{raw.casefold()}", text=raw)

    for match in _CODE_FENCE_RE.finditer(text):
        _emit(matches, match, "code_block_ref", "code:fenced_block")

    for match in _QUOTE_BLOCK_RE.finditer(text):
        _emit(matches, match, "quote_block_ref", "quote:markdown_block")

    for match in _HEADING_RE.finditer(text):
        heading = match.group().lstrip("#").strip()
        _emit(matches, match, "message_boundary_ref", f"heading:{_norm_slug(heading)}")

    for match in _NUMBERED_STEP_RE.finditer(text):
        number = match.group().split(".", 1)[0]
        _emit(matches, match, "task_ref", f"task:{number}")

    for match in _QA_RE.finditer(text):
        qa = match.group(1).casefold()
        _emit(matches, match, "qa_ref", f"qa:{qa}", text=match.group().rstrip())

    for match in _EXIT_CODE_RE.finditer(text):
        _emit(matches, match, "exit_code_ref", f"exit:{match.group(1)}")

    for match in _TRACE_RE.finditer(text):
        _emit(matches, match, "trace_ref", f"trace:{_norm_slug(match.group())}")

    for match in _PROCEDURE_RE.finditer(text):
        label = match.group().split()[0].casefold()
        _emit(matches, match, "procedure_ref", f"procedure:{_norm_slug(label)}")

    for match in _EXHIBIT_RE.finditer(text):
        _emit(matches, match, "exhibit_ref", f"exhibit:{_norm_slug(match.group())}")

    deduped: dict[tuple[str, str, int, int], StructureOccurrence] = {}
    for occ in matches:
        deduped[(occ.kind, occ.norm_text, occ.start_char, occ.end_char)] = occ
    return sorted(
        deduped.values(),
        key=lambda occ: (occ.start_char, occ.end_char, occ.kind, occ.norm_text),
    )


def summarize_operational_occurrences(texts: list[str]) -> dict[str, int]:
    counter: dict[str, int] = {}
    for text in texts:
        for kind, group in itertools.groupby(
            collect_operational_structure_occurrences(text),
            key=lambda occ: occ.kind,
        ):
            counter[kind] = counter.get(kind, 0) + len(list(group))
    return dict(sorted(counter.items()))
