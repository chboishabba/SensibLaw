"""CLI helpers for building the brief prep pack."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.briefing import BriefPackBuilder, MatterProfile, render_brief_pack_pdf


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``brief`` command hierarchy."""

    brief_parser = subparsers.add_parser("brief", help="Brief preparation utilities")
    brief_sub = brief_parser.add_subparsers(dest="brief_command")
    pack_parser = brief_sub.add_parser(
        "pack", help="Build the brief prep & critique pack"
    )
    pack_parser.add_argument(
        "--matter", type=Path, required=True, help="Matter JSON payload"
    )
    pack_parser.add_argument("--out", type=Path, required=True, help="Output directory")
    pack_parser.add_argument(
        "--pdf-name",
        default="brief_pack.pdf",
        help="Filename for the generated PDF inside the output directory",
    )
    pack_parser.set_defaults(func=_handle_pack)


def _handle_pack(args: argparse.Namespace) -> None:
    data = json.loads(args.matter.read_text(encoding="utf-8"))
    matter = MatterProfile.from_dict(data)
    builder = BriefPackBuilder()
    pack = builder.build(matter)

    out_dir: Path = args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    pack_json = out_dir / "brief_pack.json"
    pack_json.write_text(
        json.dumps(pack.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )

    first_cut = out_dir / "first_cut_brief.txt"
    first_cut.write_text(pack.first_cut_brief + "\n", encoding="utf-8")

    pdf_path = out_dir / args.pdf_name
    render_brief_pack_pdf(pack, pdf_path)

    result = {
        "pack_json": str(pack_json),
        "first_cut_brief": str(first_cut),
        "pdf": str(pdf_path),
    }
    print(json.dumps(result))


__all__ = ["register"]
