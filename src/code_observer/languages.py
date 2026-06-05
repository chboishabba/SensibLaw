from __future__ import annotations

from pathlib import Path
from typing import Any

from tree_sitter import Language, Parser


EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
}


def language_for_path(path: Path) -> str | None:
    return EXTENSIONS.get(path.suffix.lower())


def parser_for_language(language: str) -> Parser:
    parser = Parser()
    parser.language = _tree_sitter_language(language)
    return parser


def parser_name(language: str) -> str:
    if language == "python":
        return "tree-sitter-python"
    if language == "javascript":
        return "tree-sitter-javascript"
    if language in {"typescript", "tsx"}:
        return "tree-sitter-typescript"
    return f"tree-sitter-{language}"


def _tree_sitter_language(language: str) -> Language:
    if language == "python":
        import tree_sitter_python

        return Language(tree_sitter_python.language())
    if language == "javascript":
        import tree_sitter_javascript

        return Language(tree_sitter_javascript.language())
    if language in {"typescript", "tsx"}:
        import tree_sitter_typescript

        fn: Any = tree_sitter_typescript.language_tsx if language == "tsx" else tree_sitter_typescript.language_typescript
        return Language(fn())
    raise ValueError(f"unsupported language: {language}")
