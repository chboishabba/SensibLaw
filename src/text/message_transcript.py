from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MessageHeader:
    speaker: str
    timestamp_norm: str
    header_end: int


@dataclass(frozen=True, slots=True)
class TimeRangeHeader:
    range_norm: str
    header_end: int


def _skip_spaces(text: str, index: int) -> int:
    while index < len(text) and text[index] in {" ", "\t", "\u202f"}:
        index += 1
    return index


def _parse_int(text: str, index: int, *, min_digits: int, max_digits: int) -> tuple[int, int] | None:
    start = index
    digits = 0
    while index < len(text) and text[index].isdigit() and digits < max_digits:
        index += 1
        digits += 1
    if digits < min_digits:
        return None
    return int(text[start:index]), index


def _normalize_message_timestamp(date_text: str, time_text: str) -> str:
    date_bits = [bit for bit in date_text.split("/") if bit]
    if len(date_bits) != 3:
        return f"ts:{date_text}_{time_text}".replace(" ", "_")
    day = int(date_bits[0])
    month = int(date_bits[1])
    year = int(date_bits[2])
    if year < 100:
        year += 2000 if year < 70 else 1900

    bits = time_text.lower().replace("\u202f", " ").split()
    clock = bits[0]
    meridiem = bits[1] if len(bits) > 1 else ""
    clock_parts = clock.split(":")
    hour = int(clock_parts[0])
    minute = int(clock_parts[1])
    second = int(clock_parts[2]) if len(clock_parts) > 2 else None
    if meridiem == "pm" and hour < 12:
        hour += 12
    elif meridiem == "am" and hour == 12:
        hour = 0
    if second is None:
        return f"ts:{year:04d}_{month:02d}_{day:02d}_{hour:02d}_{minute:02d}"
    return f"ts:{year:04d}_{month:02d}_{day:02d}_{hour:02d}_{minute:02d}_{second:02d}"


def _normalize_clock_timestamp(raw: str) -> str:
    main, millis = raw.split(",", 1)
    hour_s, minute_s, second_s = main.split(":")
    return f"ts:{int(hour_s):02d}_{int(minute_s):02d}_{int(second_s):02d}_{int(millis):03d}"


def parse_message_header(line: str) -> MessageHeader | None:
    if not line:
        return None
    index = 0
    opened = False
    if line[index] == "[":
        opened = True
        index += 1

    date_start = index
    parsed = _parse_int(line, index, min_digits=1, max_digits=2)
    if parsed is None:
        return None
    _, index = parsed
    if index >= len(line) or line[index] != "/":
        return None
    index += 1
    parsed = _parse_int(line, index, min_digits=1, max_digits=2)
    if parsed is None:
        return None
    _, index = parsed
    if index >= len(line) or line[index] != "/":
        return None
    index += 1
    parsed = _parse_int(line, index, min_digits=2, max_digits=4)
    if parsed is None:
        return None
    _, index = parsed
    date_text = line[date_start:index]

    if index < len(line) and line[index] == ",":
        index += 1
    index = _skip_spaces(line, index)

    time_start = index
    parsed = _parse_int(line, index, min_digits=1, max_digits=2)
    if parsed is None:
        return None
    _, index = parsed
    if index >= len(line) or line[index] != ":":
        return None
    index += 1
    parsed = _parse_int(line, index, min_digits=2, max_digits=2)
    if parsed is None:
        return None
    _, index = parsed
    if index < len(line) and line[index] == ":":
        index += 1
        parsed = _parse_int(line, index, min_digits=2, max_digits=2)
        if parsed is None:
            return None
        _, index = parsed
    meridiem_start = _skip_spaces(line, index)
    if meridiem_start + 1 < len(line) and line[meridiem_start : meridiem_start + 2].casefold() in {"am", "pm"}:
        index = meridiem_start + 2
    time_text = " ".join(line[time_start:index].replace("\u202f", " ").split())

    if opened:
        index = _skip_spaces(line, index)
        if index >= len(line) or line[index] != "]":
            return None
        index += 1

    index = _skip_spaces(line, index)
    if index < len(line) and line[index] == "-":
        index += 1
        index = _skip_spaces(line, index)

    speaker_start = index
    while index < len(line) and line[index] != ":" and line[index] != "\n":
        index += 1
    if index >= len(line) or line[index] != ":":
        return None
    speaker = line[speaker_start:index].strip().strip("[]")
    if not speaker or len(speaker) > 120:
        return None
    return MessageHeader(
        speaker=speaker,
        timestamp_norm=_normalize_message_timestamp(date_text, time_text),
        header_end=index + 1,
    )


def parse_time_range_header(line: str) -> TimeRangeHeader | None:
    if not line:
        return None
    index = 0
    if line[index] == "[":
        index += 1
    start_clock_start = index
    parsed = _parse_int(line, index, min_digits=1, max_digits=2)
    if parsed is None:
        return None
    _, index = parsed
    for expected in (":", None, ":", None, ",", None):
        if expected is None:
            parsed = _parse_int(line, index, min_digits=2 if line[index - 1] != "," else 3, max_digits=2 if line[index - 1] != "," else 3)
            if parsed is None:
                return None
            _, index = parsed
        else:
            if index >= len(line) or line[index] != expected:
                return None
            index += 1
    start_clock = line[start_clock_start:index]
    index = _skip_spaces(line, index)
    if line[index : index + 3] == "-->":
        index += 3
    elif line[index : index + 2] == "->":
        index += 2
    else:
        return None
    index = _skip_spaces(line, index)
    end_clock_start = index
    parsed = _parse_int(line, index, min_digits=1, max_digits=2)
    if parsed is None:
        return None
    _, index = parsed
    for expected in (":", None, ":", None, ",", None):
        if expected is None:
            parsed = _parse_int(line, index, min_digits=2 if line[index - 1] != "," else 3, max_digits=2 if line[index - 1] != "," else 3)
            if parsed is None:
                return None
            _, index = parsed
        else:
            if index >= len(line) or line[index] != expected:
                return None
            index += 1
    end_clock = line[end_clock_start:index]
    index = _skip_spaces(line, index)
    if index < len(line) and line[index] == "]":
        index += 1
    return TimeRangeHeader(
        range_norm=f"tsrange:{_normalize_clock_timestamp(start_clock)[3:]}__{_normalize_clock_timestamp(end_clock)[3:]}",
        header_end=index,
    )
