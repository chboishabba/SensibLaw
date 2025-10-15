from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, Iterable

ASSET_DIR = Path(__file__).with_suffix('').parent / 'assets'


def _load_pack(pack_path: Path) -> Dict[str, Any]:
    """Load graph pack from ``pack_path``.

    The pack is expected to be a JSON file with ``nodes`` and ``edges``
    lists.  Each node should at minimum provide an ``id`` field.
    """

    data = json.loads(pack_path.read_text())
    return {
        "nodes": data.get("nodes", []),
        "edges": data.get("edges", []),
    }


def _write_assets(dst: Path) -> None:
    dst.mkdir(exist_ok=True, parents=True)
    for asset in ASSET_DIR.iterdir():
        shutil.copy(asset, dst / asset.name)


def _write_verify_script(out_dir: Path) -> None:
    verify = """#!/bin/sh
set -e
# Ensure no external resources are referenced
if grep -R "http[s]://" index.html assets >/dev/null 2>&1; then
  echo "External references found" >&2
  exit 1
fi
exit 0
"""
    path = out_dir / "verify.sh"
    path.write_text(verify)
    path.chmod(0o755)


def _write_docker_files(out_dir: Path) -> None:
    dockerfile = """FROM python:3.11-slim
WORKDIR /site
COPY . /site
EXPOSE 8000
CMD [\"python\", \"-m\", \"http.server\", \"8000\"]
"""
    compose = """version: '3'
services:
  web:
    build: .
    ports:
      - \"8000:8000\"
"""
    (out_dir / "Dockerfile").write_text(dockerfile)
    (out_dir / "docker-compose.yml").write_text(compose)


def generate_site(seed: str, out_dir: Path, pack_path: Path | None = None) -> None:
    """Generate a static site in ``out_dir`` using data from ``pack_path``.

    ``pack_path`` may be supplied directly or via the ``SENSIBLAW_PACK``
    environment variable.  The function will raise :class:`ValueError` if the
    seed node is not present in the pack.
    """

    if pack_path is None:
        pack_env = os.environ.get("SENSIBLAW_PACK")
        if not pack_env:
            raise ValueError("Pack path not specified via argument or SENSIBLAW_PACK")
        pack_path = Path(pack_env)

    pack = _load_pack(pack_path)
    nodes: Iterable[Dict[str, Any]] = pack["nodes"]
    if not any(n.get("id") == seed for n in nodes):
        raise ValueError(f"Seed '{seed}' not found in pack")

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Write graph data
    (out_dir / "graph.json").write_text(json.dumps(pack, indent=2))

    # Basic HTML shell
    html = """<!DOCTYPE html>
<html lang='en'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>SensibLaw Mirror</title>
<link rel='stylesheet' href='assets/style.css'>
</head>
<body>
<header class='site-header'>
  <div class='header-inner'>
    <h1 class='site-title'>SensibLaw Mirror</h1>
    <p class='site-tagline'>Explore knowledge graph issues side by side.</p>
  </div>
</header>
<main class='site-main'>
  <div class='view-shell'>
    <section id='view-controls' class='view-controls' aria-label='View modes'></section>
    <section id='view-container' class='view-container' aria-live='polite'></section>
    <noscript>
      <p class='empty-state'>Enable JavaScript to view the graph visualisations.</p>
    </noscript>
  </div>
</main>
<script src='assets/main.js'></script>
</body>
</html>
"""
    (out_dir / "index.html").write_text(html)

    _write_assets(out_dir / "assets")
    _write_verify_script(out_dir)
    _write_docker_files(out_dir)

__all__ = ["generate_site"]
