from __future__ import annotations

from typing import Any


_NUMERIC_UNITS = {
    "percent",
    "million",
    "billion",
    "trillion",
    "thousand",
    "hundred",
    "year",
    "month",
    "day",
    "line",
    "point",
    "usd",
    "aud",
    "eur",
    "gbp",
}
_NUMERIC_SCALE_UNITS = {"hundred", "thousand", "million", "billion", "trillion"}
_NUMERIC_CURRENCY_UNITS = {"usd", "aud", "eur", "gbp"}
_NUMERIC_SCALE_POW = {"hundred": 2, "thousand": 3, "million": 6, "billion": 9, "trillion": 12}


def _collapse_whitespace(raw: Any) -> str:
    return " ".join(str(raw or "").split())


def _canonical_unit_token(raw: Any) -> str:
    token = str(raw or "").strip().lower()
    if token in {"%", "percentage", "percent"}:
        return "percent"
    if token in {"dollar", "dollars", "usd"}:
        return "usd"
    if token in {"years", "year"}:
        return "year"
    if token in {"months", "month"}:
        return "month"
    if token in {"days", "day"}:
        return "day"
    if token in {"lines", "line"}:
        return "line"
    if token in {"points", "point"}:
        return "point"
    if token in {"aud", "eur", "gbp"}:
        return token
    return token


def _parse_numeric_value_token(raw: Any) -> str:
    compact = str(raw or "").strip().replace(",", "")
    if not compact:
        return ""

    i = 0
    sign = ""
    if compact[0] in {"+", "-"}:
        sign = compact[0]
        i = 1

    seen_digit = False
    seen_dot = False
    int_part = ""
    frac_part = ""

    while i < len(compact):
        ch = compact[i]
        if "0" <= ch <= "9":
            seen_digit = True
            if seen_dot:
                frac_part += ch
            else:
                int_part += ch
            i += 1
            continue
        if ch == "." and not seen_dot:
            seen_dot = True
            i += 1
            continue
        return ""
    if not seen_digit:
        return ""

    while len(int_part) > 1 and int_part.startswith("0"):
        int_part = int_part[1:]
    while frac_part.endswith("0"):
        frac_part = frac_part[:-1]

    value = f"{int_part}.{frac_part}" if frac_part else int_part
    if value == "0":
        sign = ""
    if sign == "-":
        value = f"-{value}"
    return value


def _scientific_from_scaled(value: str, power: int) -> str:
    try:
        scaled = float(value) * (10 ** power)
    except (TypeError, ValueError):
        return ""
    if scaled == 0:
        return "0"
    raw = f"{scaled:e}"
    mantissa, _, exponent = raw.partition("e")
    if not exponent:
        return ""
    while "." in mantissa and mantissa.endswith("0"):
        mantissa = mantissa[:-1]
    if mantissa.endswith("."):
        mantissa = mantissa[:-1]
    try:
        exp_num = int(exponent)
    except ValueError:
        return ""
    return f"{mantissa}e{exp_num}"


def normalize_numeric_mention(raw: Any) -> str:
    text = _collapse_whitespace(raw)
    if not text:
        return ""

    src = [part for part in text.split(" ") if part]
    toks: list[str] = []
    i = 0
    while i < len(src):
        low = src[i].lower()
        nxt = src[i + 1].lower() if i + 1 < len(src) else ""
        if low == "per" and nxt == "cent":
            toks.append("percent")
            i += 2
            continue
        toks.append(src[i])
        i += 1

    currency = ""
    if toks:
        first = toks[0]
        low = first.lower()
        if low in {"$", "us$", "a$", "€", "£", "usd", "aud", "eur", "gbp"}:
            currency = {"$": "usd", "us$": "usd", "a$": "aud", "€": "eur", "£": "gbp"}.get(low, low)
            toks = toks[1:]
        else:
            strip = None
            if low.startswith("us$"):
                currency = "usd"
                strip = 3
            elif low.startswith("a$"):
                currency = "aud"
                strip = 2
            elif low.startswith("$"):
                currency = "usd"
                strip = 1
            elif low.startswith("€"):
                currency = "eur"
                strip = 1
            elif low.startswith("£"):
                currency = "gbp"
                strip = 1
            if strip is not None:
                rem = first[strip:]
                toks[0] = rem

    if not toks:
        return ""

    if len(toks) == 1:
        single = toks[0]
        j = 1 if single and single[0] in {"+", "-"} else 0
        seen_digit = False
        seen_dot = False
        while j < len(single):
            ch = single[j]
            if "0" <= ch <= "9":
                seen_digit = True
                j += 1
                continue
            if ch == "," or (ch == "." and not seen_dot):
                seen_dot = seen_dot or (ch == ".")
                j += 1
                continue
            break
        if seen_digit and j < len(single):
            left = single[:j]
            right = single[j:].lower()
            if right in _NUMERIC_UNITS:
                if currency:
                    return f"{left} {right} {currency}"
                return f"{left} {right}"

    for idx in range(1, len(toks)):
        toks[idx] = _canonical_unit_token(toks[idx])

    if currency and currency not in {part.lower() for part in toks}:
        toks.append(currency)
    return " ".join([part for part in toks if part])


def numeric_key(raw: Any) -> str:
    mention = normalize_numeric_mention(raw)
    if not mention:
        return ""
    toks = [part for part in mention.split(" ") if part]
    if not toks:
        return ""
    value = _parse_numeric_value_token(toks[0])
    if not value:
        return ""
    units = [_canonical_unit_token(unit) for unit in toks[1:] if _canonical_unit_token(unit)]
    if not units:
        return f"{value}|"
    uniq = list(dict.fromkeys(units))
    if any(unit not in _NUMERIC_UNITS for unit in uniq):
        return ""
    out_value = value
    if len(uniq) == 1:
        unit = uniq[0]
    elif len(uniq) == 2:
        scale = next((unit for unit in uniq if unit in _NUMERIC_SCALE_UNITS), "")
        ccy = next((unit for unit in uniq if unit in _NUMERIC_CURRENCY_UNITS), "")
        if not scale or not ccy:
            return ""
        sci = _scientific_from_scaled(value, _NUMERIC_SCALE_POW.get(scale, 0))
        if not sci:
            return ""
        out_value = sci
        unit = ccy
    else:
        return ""
    return f"{out_value}|{unit}"


def _project_numeric_values(values: Any) -> tuple[list[str], list[dict[str, str]]]:
    by_key: dict[str, str] = {}
    plain: list[str] = []
    plain_seen: set[str] = set()
    for raw in values or []:
        label = normalize_numeric_mention(raw)
        if not label:
            continue
        key = numeric_key(label)
        if key:
            by_key.setdefault(key, label)
            continue
        if label not in plain_seen:
            plain_seen.add(label)
            plain.append(label)
    mentions = [{"key": key, "label": label} for key, label in by_key.items()]
    return [*by_key.values(), *plain], mentions


def _project_event(event: dict[str, Any]) -> None:
    nums, mentions = _project_numeric_values(event.get("numeric_objects") or [])
    event["numeric_objects"] = nums
    if mentions:
        event["numeric_mentions"] = mentions
    elif "numeric_mentions" in event:
        event.pop("numeric_mentions", None)

    steps = event.get("steps")
    if isinstance(steps, list):
        for step in steps:
            if not isinstance(step, dict):
                continue
            step_nums, step_mentions = _project_numeric_values(step.get("numeric_objects") or [])
            step["numeric_objects"] = step_nums
            if step_mentions:
                step["numeric_mentions"] = step_mentions
            elif "numeric_mentions" in step:
                step.pop("numeric_mentions", None)

    facts = event.get("timeline_facts")
    if isinstance(facts, list):
        for fact in facts:
            if not isinstance(fact, dict):
                continue
            fact_nums, _ = _project_numeric_values(fact.get("numeric_objects") or [])
            fact["numeric_objects"] = fact_nums


def apply_numeric_projection(payload: dict[str, Any]) -> dict[str, Any]:
    events = payload.get("events")
    if isinstance(events, list):
        for event in events:
            if isinstance(event, dict):
                _project_event(event)

    facts = payload.get("fact_timeline")
    if isinstance(facts, list):
        for fact in facts:
            if not isinstance(fact, dict):
                continue
            fact_nums, _ = _project_numeric_values(fact.get("numeric_objects") or [])
            fact["numeric_objects"] = fact_nums
    return payload
