#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any
import re

_THIS_DIR = Path(__file__).resolve().parent
_SENSIBLAW_ROOT = _THIS_DIR.parent
_DEMO_DIR = _SENSIBLAW_ROOT / "sl_zelph_demo"

if str(_SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(_SENSIBLAW_ROOT))


_ERROR_MARKERS = ("Error in line", "Could not open file")
_DERIVATION_RE = re.compile(r"^\(\s*(.*?)\s*\)\s*⇐")


def _normalize_triple_parts(parts: list[str]) -> dict[str, str] | None:
    if len(parts) != 3:
        return None
    return {
        "subject": parts[0].strip(),
        "predicate": parts[1].strip(),
        "object": parts[2].strip(),
    }


def _parse_column_triple(payload: str) -> dict[str, str] | None:
    parts = [part for part in re.split(r"\s{2,}", payload.strip()) if part.strip()]
    return _normalize_triple_parts(parts)


def _parse_zelph_output(stdout: str) -> dict[str, Any]:
    parsed_triples: list[dict[str, str]] = []
    derived_triples: list[dict[str, str]] = []
    proofs: list[str] = []
    raw_lines: list[str] = []
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        raw_lines.append(line)
        derivation_match = _DERIVATION_RE.match(line)
        if derivation_match:
            proofs.append(line)
            triple = _parse_column_triple(derivation_match.group(1))
            if triple:
                derived_triples.append(triple)
            continue
        if "=>" in line or line.startswith("{"):
            continue
        triple = _parse_column_triple(line)
        if triple:
            parsed_triples.append(triple)
    return {
        "parsed_triples": _dedupe_triples(parsed_triples),
        "derived_triples": _dedupe_triples(derived_triples),
        "proofs": proofs,
        "raw_lines": raw_lines,
    }


def _dedupe_triples(triples: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str, str]] = set()
    out: list[dict[str, str]] = []
    for triple in triples:
        key = (
            str(triple.get("subject") or ""),
            str(triple.get("predicate") or ""),
            str(triple.get("object") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append({"subject": key[0], "predicate": key[1], "object": key[2]})
    return out


def _build_bundle_text(*parts: str) -> str:
    cleaned = [part.strip() for part in parts if part and part.strip()]
    return "\n\n".join(cleaned) + "\n"


def _run_python_tool(script_path: Path, args: list[str], *, extra_env: dict[str, str] | None = None) -> dict[str, Any]:
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    result = subprocess.run(
        [sys.executable, str(script_path), *args],
        capture_output=True,
        text=True,
        cwd=str(script_path.parent),
        env=env,
    )
    return {
        "command": [sys.executable, str(script_path), *args],
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _run_zelph_bundle(bundle_text: str, *, save_bundle_path: Path | None = None) -> dict[str, Any]:
    if save_bundle_path is not None:
        save_bundle_path.parent.mkdir(parents=True, exist_ok=True)
        save_bundle_path.write_text(bundle_text, encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        bundle_name = save_bundle_path.name if save_bundle_path is not None else "zelph_bundle.zlp"
        bundle_path = tmpdir_path / bundle_name
        bundle_path.write_text(bundle_text, encoding="utf-8")
        result = subprocess.run(
            ["zelph", bundle_path.name],
            capture_output=True,
            text=True,
            cwd=str(tmpdir_path),
        )
    combined_output = "\n".join(part for part in (result.stdout, result.stderr) if part)
    status = "ok"
    if any(marker in combined_output for marker in _ERROR_MARKERS):
        status = "engine_error"
    parsed = _parse_zelph_output(result.stdout)
    return {
        "ok": status == "ok",
        "status": status,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "bundle_path": str(save_bundle_path.resolve()) if save_bundle_path is not None else None,
        **parsed,
    }


def _facts_and_rules_payload(
    *,
    facts_text: str,
    rules_text: str,
    mode: str,
    save_bundle_path: Path | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "mode": mode,
        "facts_line_count": len([line for line in facts_text.splitlines() if line.strip()]),
        "rules_line_count": len([line for line in rules_text.splitlines() if line.strip()]),
    }
    if extra:
        payload.update(extra)
    payload["engine"] = _run_zelph_bundle(
        _build_bundle_text(facts_text, rules_text),
        save_bundle_path=save_bundle_path,
    )
    payload["ok"] = bool(payload["engine"]["ok"])
    return payload


def _run_bundle_mode(bundle_path: Path) -> dict[str, Any]:
    engine = _run_zelph_bundle(bundle_path.read_text(encoding="utf-8"))
    return {
        "mode": "bundle",
        "source_bundle_path": str(bundle_path.resolve()),
        "engine": engine,
        "ok": bool(engine["ok"]),
    }


def _run_files_mode(
    *,
    facts_path: Path,
    rule_paths: list[Path],
    save_bundle_path: Path | None = None,
) -> dict[str, Any]:
    rule_blocks = [path.read_text(encoding="utf-8").strip() for path in rule_paths]
    rules_text = "\n\n".join(block for block in rule_blocks if block)
    return _facts_and_rules_payload(
        facts_text=facts_path.read_text(encoding="utf-8"),
        rules_text=rules_text,
        mode="files",
        save_bundle_path=save_bundle_path,
        extra={
            "facts_path": str(facts_path.resolve()),
            "rule_paths": [str(path.resolve()) for path in rule_paths],
        },
    )


def _run_db_mode(
    *,
    db_path: Path,
    save_bundle_path: Path | None = None,
) -> dict[str, Any]:
    bundle_path = save_bundle_path or (Path(tempfile.mkdtemp()) / "db_bundle.zlp")
    compile_result = _run_python_tool(
        _DEMO_DIR / "compile_db.py",
        [str(db_path.resolve()), str(bundle_path.resolve())],
    )
    payload = {
        "mode": "db",
        "db_path": str(db_path.resolve()),
        "compile": compile_result,
    }
    if compile_result["returncode"] != 0:
        payload["ok"] = False
        payload["engine"] = None
        return payload
    payload["engine"] = _run_zelph_bundle(bundle_path.read_text(encoding="utf-8"), save_bundle_path=bundle_path)
    payload["ok"] = bool(payload["engine"]["ok"])
    return payload


def _run_wiki_mode(
    *,
    wiki_json_path: Path,
    save_bundle_path: Path | None = None,
) -> dict[str, Any]:
    facts_path = (save_bundle_path.parent / "wiki_facts.zlp") if save_bundle_path is not None else (Path(tempfile.mkdtemp()) / "wiki_facts.zlp")
    lex_result = _run_python_tool(
        _DEMO_DIR / "lex_to_zelph.py",
        [str(wiki_json_path.resolve()), str(facts_path.resolve())],
        extra_env={"PYTHONPATH": str((_SENSIBLAW_ROOT / "src").resolve())},
    )
    payload = {
        "mode": "wiki",
        "wiki_json_path": str(wiki_json_path.resolve()),
        "lex": lex_result,
    }
    if lex_result["returncode"] != 0:
        payload["ok"] = False
        payload["engine"] = None
        return payload
    rules_text = (_DEMO_DIR / "wiki_lex_rules.zlp").read_text(encoding="utf-8")
    facts_text = facts_path.read_text(encoding="utf-8")
    payload.update(
        _facts_and_rules_payload(
            facts_text=facts_text,
            rules_text=rules_text,
            mode="wiki",
            save_bundle_path=save_bundle_path,
            extra={
                "facts_path": str(facts_path.resolve()),
                "rule_paths": [str((_DEMO_DIR / "wiki_lex_rules.zlp").resolve())],
            },
        )
    )
    payload["lex"] = lex_result
    payload["wiki_json_path"] = str(wiki_json_path.resolve())
    return payload


def _run_text_mode(
    *,
    comment: str,
    user: str,
    revid: str,
    title: str,
    save_bundle_path: Path | None = None,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        wiki_json_path = tmpdir_path / "wiki_input.json"
        wiki_json_path.write_text(
            json.dumps(
                {
                    "title": title,
                    "rows": [
                        {
                            "revid": revid,
                            "user": user,
                            "comment": comment,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        payload = _run_wiki_mode(wiki_json_path=wiki_json_path, save_bundle_path=save_bundle_path)
    payload["mode"] = "text"
    payload["input"] = {
        "title": title,
        "revid": revid,
        "user": user,
        "comment": comment,
    }
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Zelph deterministically against the working SensibLaw demo bundle surface.")
    sub = parser.add_subparsers(dest="command", required=True)

    bundle_p = sub.add_parser("bundle", help="Run an existing combined .zlp bundle")
    bundle_p.add_argument("--bundle-path", type=Path, required=True)

    files_p = sub.add_parser("files", help="Combine facts and rule files into a single Zelph bundle and run it")
    files_p.add_argument("--facts-path", type=Path, required=True)
    files_p.add_argument("--rule-path", dest="rule_paths", action="append", type=Path, required=True)
    files_p.add_argument("--save-bundle-path", type=Path, default=None)

    db_p = sub.add_parser("db", help="Compile SensibLaw rule_atoms into a Zelph bundle and run it")
    db_p.add_argument("--db-path", type=Path, required=True)
    db_p.add_argument("--save-bundle-path", type=Path, default=None)

    wiki_p = sub.add_parser("wiki", help="Compile a wiki revision JSON surface to Zelph facts and run wiki lexical rules")
    wiki_p.add_argument("--wiki-json-path", type=Path, required=True)
    wiki_p.add_argument("--save-bundle-path", type=Path, default=None)

    text_p = sub.add_parser("text", help="Build a one-revision wiki lexical bundle from inline text and run it")
    text_p.add_argument("--comment", required=True)
    text_p.add_argument("--user", default="Sentinel33")
    text_p.add_argument("--revid", default="1")
    text_p.add_argument("--title", default="Ad hoc Zelph Runner")
    text_p.add_argument("--save-bundle-path", type=Path, default=None)

    args = parser.parse_args(argv)

    if args.command == "bundle":
        payload = _run_bundle_mode(args.bundle_path)
    elif args.command == "files":
        payload = _run_files_mode(
            facts_path=args.facts_path,
            rule_paths=args.rule_paths,
            save_bundle_path=args.save_bundle_path,
        )
    elif args.command == "db":
        payload = _run_db_mode(
            db_path=args.db_path,
            save_bundle_path=args.save_bundle_path,
        )
    elif args.command == "wiki":
        payload = _run_wiki_mode(
            wiki_json_path=args.wiki_json_path,
            save_bundle_path=args.save_bundle_path,
        )
    else:
        payload = _run_text_mode(
            comment=args.comment,
            user=args.user,
            revid=args.revid,
            title=args.title,
            save_bundle_path=args.save_bundle_path,
        )

    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
