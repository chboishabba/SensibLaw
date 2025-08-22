import hashlib
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from email.utils import formatdate

import importlib
import json
import logging
import sys


def _start_server(body: bytes) -> tuple[HTTPServer, str]:
    etag = hashlib.sha256(body).hexdigest()
    last_mod = formatdate(usegmt=True)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 (method name from BaseHTTPRequestHandler)
            if (
                self.headers.get("If-None-Match") == etag
                or self.headers.get("If-Modified-Since") == last_mod
            ):
                self.send_response(304)
                self.end_headers()
            else:
                self.send_response(200)
                self.send_header("ETag", etag)
                self.send_header("Last-Modified", last_mod)
                self.end_headers()
                self.wfile.write(body)

        def log_message(self, format, *args):  # pragma: no cover - silence
            pass

    server = HTTPServer(("localhost", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://localhost:{server.server_port}/"
    return server, url


def test_cache_revalidation(tmp_path, monkeypatch, caplog):
    # Use a temporary cache directory
    monkeypatch.setenv("SENSIBLAW_CACHE", str(tmp_path))
    # Ensure the repository root is on ``sys.path`` then import and reload the
    # cache module so it picks up the temporary path.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    cache = importlib.import_module("src.ingestion.cache")
    importlib.reload(cache)

    body = b"hello world"
    server, url = _start_server(body)

    with caplog.at_level(logging.INFO):
        first = cache.fetch_html(url)
        second = cache.fetch_html(url)

    server.shutdown()

    assert first == second == body.decode("utf-8")
    # Ensure the cache logged the 304 response on the second request
    assert any("304 Not Modified" in r.message for r in caplog.records)


def test_source_manifests_exist():
    base = Path("data")
    frl = json.loads((base / "frl_manifest.json").read_text())
    hca = json.loads((base / "hca_manifest.json").read_text())
    assert frl["base_url"].startswith("https://")
    assert hca["base_url"].startswith("https://")

