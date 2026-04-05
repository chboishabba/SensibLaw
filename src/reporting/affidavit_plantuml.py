from __future__ import annotations

import re
from textwrap import wrap
from typing import Any, Iterable, Mapping


def _text(value: Any) -> str:
    return str(value or "").strip()


def _wrap(value: Any, *, width: int = 34, max_lines: int = 6) -> str:
    text = _text(value)
    if not text:
        return "-"
    parts = wrap(text, width=width, break_long_words=False, break_on_hyphens=False)
    if len(parts) > max_lines:
        parts = parts[: max_lines - 1] + ["..."]
    return "\\n".join(parts)


def _quote(value: Any) -> str:
    return '"' + _text(value).replace("\\", "\\\\").replace('"', "'").replace("\n", "\\n") + '"'


def _slug(value: Any) -> str:
    text = re.sub(r"[^A-Za-z0-9_]+", "_", _text(value))
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "node"


def _display_id(value: Any) -> str:
    text = _text(value)
    if text.startswith("aff-prop:"):
        return text.split(":", 1)[1]
    return text or "node"


def _lexical_atoms(text: Any, *, limit: int = 10) -> list[str]:
    atoms = re.findall(r"[A-Za-z0-9']+", _text(text).casefold())
    seen: list[str] = []
    for atom in atoms:
        if atom not in seen:
            seen.append(atom)
        if len(seen) >= limit:
            break
    return seen


def _status_fill(row: Mapping[str, Any]) -> str:
    coverage = _text(row.get("coverage_status"))
    relation_root = _text(row.get("relation_root"))
    if relation_root == "invalidates" or coverage in {"contested_source", "contested_affidavit"}:
        return "#FDE2E1"
    if relation_root == "supports" or coverage == "covered":
        return "#E4F4DD"
    if relation_root == "unanswered" or coverage == "unsupported_affidavit":
        return "#FFF4CC"
    return "#F3F3F3"


def _rows(payload: Mapping[str, Any], *, max_claims: int | None = None) -> list[Mapping[str, Any]]:
    raw = payload.get("affidavit_rows") if isinstance(payload.get("affidavit_rows"), list) else []
    rows = [row for row in raw if isinstance(row, Mapping)]
    if max_claims is not None:
        rows = rows[: max(0, int(max_claims))]
    return rows


def _source_map(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    raw = payload.get("source_review_rows") if isinstance(payload.get("source_review_rows"), list) else []
    return {
        _text(row.get("source_row_id")): row
        for row in raw
        if isinstance(row, Mapping) and _text(row.get("source_row_id"))
    }


def _source_display_map(payload: Mapping[str, Any]) -> dict[str, str]:
    raw = payload.get("source_review_rows") if isinstance(payload.get("source_review_rows"), list) else []
    mapping: dict[str, str] = {}
    for index, row in enumerate(raw, start=1):
        if not isinstance(row, Mapping):
            continue
        source_row_id = _text(row.get("source_row_id"))
        if source_row_id:
            mapping[source_row_id] = f"s{index}"
    return mapping


def _zelph_map(payload: Mapping[str, Any]) -> dict[tuple[str, str], Mapping[str, Any]]:
    raw = payload.get("zelph_claim_state_facts") if isinstance(payload.get("zelph_claim_state_facts"), list) else []
    mapping: dict[tuple[str, str], Mapping[str, Any]] = {}
    for row in raw:
        if not isinstance(row, Mapping):
            continue
        claim_text = _text((row.get("claim_text_span") or {}).get("text") if isinstance(row.get("claim_text_span"), Mapping) else None)
        source_row_id = _text(row.get("best_source_row_id"))
        if claim_text or source_row_id:
            mapping[(claim_text, source_row_id)] = row
    return mapping


def _summary_note(payload: Mapping[str, Any]) -> str:
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
    lines = ["Current summary"]
    for key in (
        "affidavit_proposition_count",
        "covered_count",
        "contested_affidavit_count",
        "contested_source_count",
        "unsupported_affidavit_count",
        "missing_review_count",
        "supported_affidavit_count",
        "disputed_affidavit_count",
        "needs_clarification_affidavit_count",
    ):
        if key in summary:
            lines.append(f"{key}: {summary.get(key)}")
    return "\\n".join(lines)


def build_affidavit_resolution_plantuml(
    payload: Mapping[str, Any],
    *,
    title: str = "Affidavit Claim Resolution Graph",
    max_claims: int | None = None,
    candidate_limit: int = 3,
) -> str:
    rows = _rows(payload, max_claims=max_claims)
    source_rows = _source_map(payload)
    source_display = _source_display_map(payload)
    zelph_rows = _zelph_map(payload)

    lines = [
        "@startuml",
        f"title {title}",
        "",
        "skinparam backgroundColor white",
        "skinparam shadowing false",
        "skinparam packageStyle rectangle",
        "skinparam componentStyle rectangle",
        "skinparam defaultTextAlignment left",
        "top to bottom direction",
        "skinparam ArrowColor #444444",
        "skinparam packageBorderColor #666666",
        "skinparam componentBorderColor #666666",
        "skinparam noteBorderColor #888888",
        "",
        "package \"Affidavit Claims\" {",
    ]

    for index, row in enumerate(rows, start=1):
        proposition_id = _text(row.get("proposition_id")) or f"claim_{index}"
        display_id = _display_id(proposition_id)
        node_id = f"C_{_slug(proposition_id)}"
        fill = _status_fill(row)
        label = (
            f"{display_id}\\n"
            f"{_wrap(row.get('text'))}\\n"
            f"coverage: {_text(row.get('coverage_status')) or '-'}\\n"
            f"relation: {_text(row.get('relation_root')) or '-'} / {_text(row.get('relation_leaf')) or '-'}"
        )
        lines.append(f'  rectangle {_quote(label)} as {node_id} {fill}')
    lines.append("}")
    lines.append("")
    lines.append("package \"Claim Roots And Responses\" {")

    for index, row in enumerate(rows, start=1):
        proposition_id = _text(row.get("proposition_id")) or f"claim_{index}"
        display_id = _display_id(proposition_id)
        claim_id = f"C_{_slug(proposition_id)}"
        root_text = _text(row.get("claim_root_text"))
        if root_text:
            root_id = f"R_{_slug(proposition_id)}"
            root_label = (
                f"{display_id} claim_root\\n"
                f"{_wrap(root_text)}\\n"
                f"basis: {_text(row.get('claim_root_basis')) or '-'}"
            )
            lines.append(f"  artifact {_quote(root_label)} as {root_id}")
            lines.append(f"{claim_id} --> {root_id} : anchors")

        best_source_row_id = _text(row.get("best_source_row_id"))
        best_excerpt = _text(row.get("best_match_excerpt"))
        source_row = source_rows.get(best_source_row_id, {})
        source_text = _text(source_row.get("text")) or best_excerpt
        if best_source_row_id or source_text:
            source_id = f"S_{_slug(proposition_id)}"
            source_label = (
                f"{source_display.get(best_source_row_id, _display_id(best_source_row_id or 'best_source'))}\\n"
                f"{_wrap(source_text)}\\n"
                f"role: {_text(row.get('best_response_role')) or '-'}"
            )
            lines.append(f"  artifact {_quote(source_label)} as {source_id}")
            lines.append(f"{claim_id} --> {source_id} : best_match")

        status_id = f"T_{_slug(proposition_id)}"
        explanation = row.get("explanation") if isinstance(row.get("explanation"), Mapping) else {}
        status_label = (
            f"semantic_basis: {_text(row.get('semantic_basis')) or '-'}\\n"
            f"support: {_text(row.get('support_status')) or '-'}\\n"
            f"direction: {_text(row.get('support_direction')) or '-'}\\n"
            f"conflict: {_text(row.get('conflict_state')) or '-'}\\n"
            f"classification: {_text(explanation.get('classification')) or '-'}"
        )
        lines.append(f"  component {_quote(status_label)} as {status_id}")
        lines.append(f"{claim_id} --> {status_id} : classified_as")

        zelph_row = zelph_rows.get((_text(row.get("text")), best_source_row_id))
        if zelph_row:
            zelph_id = f"Z_{_slug(proposition_id)}"
            zelph_label = (
                f"{display_id} zelph_claim_state\\n"
                f"{_text(zelph_row.get('fact_id')) or '-'}\\n"
                f"promotion: {_text(zelph_row.get('promotion_status')) or '-'}\\n"
                f"basis: {_text(zelph_row.get('semantic_basis')) or '-'}"
            )
            lines.append(f"  component {_quote(zelph_label)} as {zelph_id}")
            lines.append(f"{status_id} --> {zelph_id} : projected")

        matched = row.get("matched_source_rows") if isinstance(row.get("matched_source_rows"), list) else []
        for cand_index, candidate in enumerate(
            [item for item in matched if isinstance(item, Mapping)][: max(0, int(candidate_limit))],
            start=1,
        ):
            candidate_id = f"M_{_slug(proposition_id)}_{cand_index}"
            candidate_label = (
                f"{source_display.get(_text(candidate.get('source_row_id')), _display_id(candidate.get('source_row_id')) or 'candidate')}\\n"
                f"{_wrap(candidate.get('match_excerpt'))}\\n"
                f"basis: {_text(candidate.get('match_basis')) or '-'}\\n"
                f"score: {_text(candidate.get('score')) or '-'}"
            )
            lines.append(f"  artifact {_quote(candidate_label)} as {candidate_id}")
            lines.append(f"{claim_id} ..> {candidate_id} : candidate_match")

    lines.extend(
        [
            "}",
            "",
            f'note right\n{_summary_note(payload)}\nend note',
            "@enduml",
            "",
        ]
    )
    return "\n".join(lines)


def build_affidavit_mechanical_plantuml(
    payload: Mapping[str, Any],
    *,
    title: str = "Affidavit Mechanical Parse Graph",
    max_claims: int | None = None,
    token_limit: int = 10,
    candidate_limit: int = 2,
) -> str:
    rows = _rows(payload, max_claims=max_claims)
    source_rows = _source_map(payload)
    source_display = _source_display_map(payload)

    lines = [
        "@startuml",
        f"title {title}",
        "",
        "skinparam backgroundColor white",
        "skinparam shadowing false",
        "skinparam packageStyle rectangle",
        "skinparam componentStyle rectangle",
        "skinparam defaultTextAlignment left",
        "top to bottom direction",
        "skinparam ArrowColor #444444",
        "skinparam packageBorderColor #666666",
        "skinparam componentBorderColor #666666",
        "skinparam noteBorderColor #888888",
        "",
        "legend right",
        "This graph is the mechanical lane, not a hand-drawn legal theory.",
        "It shows proposition text, lexical atoms, candidate match excerpts,",
        "duplicate-root handling, and the current response classification seam.",
        "endlegend",
        "",
    ]

    lines.append('package "Affidavit document" {')
    previous_sentence_id: str | None = None
    for index, row in enumerate(rows, start=1):
        proposition_id = _text(row.get("proposition_id")) or f"claim_{index}"
        display_id = _display_id(proposition_id)
        sentence_id = f"AF_{_slug(proposition_id)}"
        sentence_label = f"{display_id}\\n{_wrap(row.get('text'), width=30, max_lines=5)}"
        lines.append(f'  component {_quote(sentence_label)} as {sentence_id}')
        if previous_sentence_id is not None:
            lines.append(f"  {previous_sentence_id} --> {sentence_id} : next_sentence")
        previous_sentence_id = sentence_id
    lines.append("}")
    lines.append("")

    source_rows_in_order = [
        row for row in payload.get("source_review_rows", []) if isinstance(row, Mapping)
    ]
    if source_rows_in_order:
        lines.append('package "Response document" {')
        previous_source_id: str | None = None
        for index, row in enumerate(source_rows_in_order, start=1):
            source_row_id = _text(row.get("source_row_id")) or f"source_{index}"
            source_node_id = f"SR_{_slug(source_row_id)}"
            source_label = f"{source_display.get(source_row_id, f's{index}')}\\n{_wrap(row.get('text'), width=30, max_lines=5)}"
            lines.append(f'  component {_quote(source_label)} as {source_node_id}')
            if previous_source_id is not None:
                lines.append(f"  {previous_source_id} --> {source_node_id} : next_source")
            previous_source_id = source_node_id
        lines.append("}")
        lines.append("")

    for index, row in enumerate(rows, start=1):
        proposition_id = _text(row.get("proposition_id")) or f"claim_{index}"
        display_id = _display_id(proposition_id)
        sentence_id = f"AF_{_slug(proposition_id)}"
        text_id = f"P_{_slug(proposition_id)}"
        lines.append(f"' {display_id}")
        lines.append(
            f'  component {_quote("extracted " + display_id + "\\n" + _wrap(row.get("text"), width=28, max_lines=5))} as {text_id}'
        )
        lines.append(f"  {sentence_id} --> {text_id} : extracted_as")

        token_values = row.get("tokens") if isinstance(row.get("tokens"), list) else None
        atoms = [str(value) for value in token_values[:token_limit]] if token_values else _lexical_atoms(row.get("text"), limit=token_limit)
        token_id = f"T_{_slug(proposition_id)}"
        lines.append(f'  component {_quote(display_id + " tokens\\n" + "\\n".join(atoms or ["-"]))} as {token_id}')
        lines.append(f"  {text_id} --> {token_id} : tokenize")

        best_excerpt = _text(row.get("best_match_excerpt"))
        best_source_row_id = _text(row.get("best_source_row_id"))
        source_text = _text(source_rows.get(best_source_row_id, {}).get("text")) or best_excerpt
        match_id = f"B_{_slug(proposition_id)}"
        lines.append(
            f'  component {_quote("best_match " + source_display.get(best_source_row_id, _display_id(best_source_row_id or "source")) + "\\n" + _wrap(source_text, width=28, max_lines=5))} as {match_id}'
        )
        lines.append(
            f"  {token_id} --> {match_id} : {_text(row.get('best_match_basis')) or 'match'} / {_text(row.get('best_adjusted_match_score') or row.get('best_match_score')) or '-'}"
        )
        if best_source_row_id:
            lines.append(f"  {match_id} --> SR_{_slug(best_source_row_id)} : from_response_sentence")

        overlap = sorted(set(atoms) & set(_lexical_atoms(source_text, limit=token_limit * 2)))
        overlap_id = f"O_{_slug(proposition_id)}"
        lines.append(f'  component {_quote(display_id + " overlap\\n" + "\\n".join(overlap[:token_limit] or ["-"]))} as {overlap_id}')
        lines.append(f"  {match_id} --> {overlap_id} : overlap")

        duplicate_excerpt = _text(row.get("duplicate_match_excerpt"))
        if duplicate_excerpt:
            dup_id = f"D_{_slug(proposition_id)}"
            lines.append(f'  component {_quote(display_id + " duplicate_root\\n" + _wrap(duplicate_excerpt, width=28, max_lines=5))} as {dup_id}')
            lines.append(f"  {match_id} --> {dup_id} : duplicate_excerpt")

        root_text = _text(row.get("claim_root_text"))
        if root_text:
            root_id = f"R_{_slug(proposition_id)}"
            lines.append(
                f'  component {_quote(display_id + " claim_root\\n" + _wrap(root_text, width=28, max_lines=5) + "\\n" + "basis: " + (_text(row.get("claim_root_basis")) or "-"))} as {root_id}'
            )
            anchor_from = f"D_{_slug(proposition_id)}" if duplicate_excerpt else match_id
            lines.append(f"  {anchor_from} --> {root_id} : root_selection")

        classify_id = f"C_{_slug(proposition_id)}"
        lines.append(
            f'  component {_quote(display_id + " classification\\n" + "response_role: " + (_text(row.get("best_response_role")) or "-") + "\\n" + "semantic_basis: " + (_text(row.get("semantic_basis")) or "-") + "\\n" + "relation: " + ((_text(row.get("relation_root")) or "-") + " / " + (_text(row.get("relation_leaf")) or "-")))} as {classify_id}'
        )
        lines.append(f"  {match_id} --> {classify_id} : classify")

        matched = row.get("matched_source_rows") if isinstance(row.get("matched_source_rows"), list) else []
        for cand_index, candidate in enumerate(
            [item for item in matched if isinstance(item, Mapping)][: max(0, int(candidate_limit))],
            start=1,
        ):
            candidate_id = f"M_{_slug(proposition_id)}_{cand_index}"
            lines.append(
                f'  component {_quote((source_display.get(_text(candidate.get("source_row_id")), _display_id(candidate.get("source_row_id")) or "candidate")) + "\\n" + _wrap(candidate.get("match_excerpt"), width=28, max_lines=4))} as {candidate_id}'
            )
            lines.append(
                f"  {token_id} ..> {candidate_id} : {_text(candidate.get('match_basis')) or '-'} / {_text(candidate.get('score')) or '-'}"
            )

        lines.append("")

    lines.append("@enduml")
    lines.append("")
    return "\n".join(lines)


__all__ = [
    "build_affidavit_resolution_plantuml",
    "build_affidavit_mechanical_plantuml",
]
