from __future__ import annotations

import re
from typing import Any

from src.sensiblaw.interfaces.shared_reducer import tokenize_canonical_with_spans


_REVISION_LINE_RE = re.compile(
    r"^Revision by (?P<author>.*?): (?P<comment>.+)$",
    re.IGNORECASE,
)

_REVERSION_KEYWORDS = {
    "revert",
    "reverted",
    "reverting",
    "undo",
    "undid",
    "undone",
    "rv",
    "remove",
    "removed",
    "removing",
    "vandalism",
    "dispute",
    "disputed",
    "contested",
    "unverified",
    "unsourced",
}
_ARCHIVE_KEYWORDS = {"archive", "archived", "archiving"}
_ADMIN_KEYWORDS = {"protect", "protected", "protection", "block", "blocked", "warn", "warning"}


def _quote_zelph_text(value: Any) -> str:
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _lexeme_node(token: str) -> str:
    return f"lex_{token.encode('utf-8').hex()}"


def revision_node_id(revision_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_]+", "_", revision_id.strip() or "unknown")
    return f"rev_{safe}"


def _token_texts(text: str) -> list[str]:
    return [token for token, _start, _end in tokenize_canonical_with_spans(text)]


def parse_revision_statement(statement_text: str) -> dict[str, str] | None:
    match = _REVISION_LINE_RE.match(statement_text.strip())
    if not match:
        return None
    author = match.group("author").strip() or "unknown"
    comment = match.group("comment").strip()
    if not comment:
        return None
    return {"author": author, "comment": comment}


def classify_revision_comment(comment_text: str) -> list[str]:
    tokens = [token.casefold() for token in _token_texts(comment_text)]
    tags: list[str] = []
    if any(token in _REVERSION_KEYWORDS for token in tokens):
        tags.append("reversion_edit")
        tags.append("volatility_signal")
    if any(token in _ARCHIVE_KEYWORDS for token in tokens):
        tags.append("archive_management_edit")
    if any(token in _ADMIN_KEYWORDS for token in tokens):
        tags.append("administrative_edit")
    return list(dict.fromkeys(tags))


def build_revision_comment_zelph_facts(
    *,
    revision_id: str,
    author: str,
    comment_text: str,
) -> list[str]:
    tokens = _token_texts(comment_text)
    revision_node = revision_node_id(revision_id)
    facts = [
        f'{_quote_zelph_text(revision_node)} "is a" "wikipedia revision".',
        f'{_quote_zelph_text(revision_node)} "by user" {_quote_zelph_text(author)}.',
    ]
    lexeme_nodes = [_lexeme_node(token) for token in tokens]
    for token, node in zip(tokens, lexeme_nodes, strict=False):
        facts.append(f'{_quote_zelph_text(node)} "has text" {_quote_zelph_text(token)}.')
        facts.append(f'{_quote_zelph_text(node)} "kind" "lexeme".')
        facts.append(f'{_quote_zelph_text(revision_node)} "has comment lexeme" {_quote_zelph_text(token.casefold())}.')
    comment_list = "<" + " ".join(lexeme_nodes) + ">" if lexeme_nodes else "nil"
    facts.append(f'{_quote_zelph_text(revision_node)} "has comment" {comment_list}.')
    return facts
