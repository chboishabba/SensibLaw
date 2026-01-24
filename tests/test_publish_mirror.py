import json
import os
import subprocess
from pathlib import Path
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import threading
import urllib.request
import pytest


def test_publish_static_site(tmp_path: Path):
    pack = Path("tests/fixtures/publish_pack.json")
    out_dir = tmp_path / "site"
    env = os.environ.copy()
    env["SENSIBLAW_PACK"] = str(pack)
    subprocess.run(
        ["python", "-m", "src.cli", "publish", "--seed", "caseA", "--out", str(out_dir)],
        check=True,
        env=env,
    )

    # Verify expected files exist
    assert (out_dir / "index.html").exists()
    assert (out_dir / "graph.json").exists()
    assert (out_dir / "verify.sh").exists()
    assert (out_dir / "Dockerfile").exists()
    assert (out_dir / "docker-compose.yml").exists()

    # Run verify.sh to ensure no external references
    subprocess.run(["bash", "verify.sh"], cwd=out_dir, check=True)

    # Serve the site locally and fetch resources
    handler = partial(SimpleHTTPRequestHandler, directory=str(out_dir))
    try:
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    except PermissionError:
        pytest.skip("Local sockets are not permitted in this environment")
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    with urllib.request.urlopen(base + "/index.html") as f:
        content = f.read().decode()
    assert "http://" not in content and "https://" not in content
    with urllib.request.urlopen(base + "/graph.json") as f:
        data = json.load(f)
    server.shutdown()
    thread.join()
    assert any(n["id"] == "caseA" for n in data["nodes"])
