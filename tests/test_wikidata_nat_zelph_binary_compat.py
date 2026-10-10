from __future__ import annotations

from pathlib import Path

import src.ontology.wikidata_nat_zelph_binary_compat as compat


def _manifest() -> dict:
    return {"manifestVersion": "zelph-hf-layout/v2", "sections": {}}


def test_probe_accepts_clean_meta_only_exit() -> None:
    receipt = compat.probe_zelph_manifest_compatibility(
        _manifest(),
        binary="/fixture/good",
        repl_runner=lambda _binary, payload, *, timeout_seconds: (
            0,
            "ok" if "meta-only" in payload and timeout_seconds == 5.0 else "",
        ),
        timeout_seconds=5.0,
    )
    assert receipt["compatible"] is True
    assert receipt["exit_code"] == 0
    assert receipt["termination_kind"] == "clean_exit"


def test_probe_rejects_sigsegv_meta_only() -> None:
    receipt = compat.probe_zelph_manifest_compatibility(
        _manifest(),
        binary="/usr/bin/zelph",
        repl_runner=lambda *_args, **_kwargs: (-11, ""),
    )
    assert receipt["compatible"] is False
    assert receipt["failure_kind"] == "manifest_meta_only_failed"
    assert receipt["exit_code"] == -11
    assert receipt["signal_number"] == 11
    assert receipt["signal_name"] == "SIGSEGV"


def test_candidate_order_prefers_explicit_then_itir_then_path(monkeypatch, tmp_path: Path) -> None:
    sensiblaw = tmp_path / "SensibLaw"
    sensiblaw.mkdir()
    itir_bin = tmp_path / "ITIR-suite" / "aur" / "zelph" / "build-local" / "bin" / "zelph"
    itir_bin.parent.mkdir(parents=True)
    itir_bin.write_text("", encoding="utf-8")
    itir_bin.chmod(0o755)

    explicit = tmp_path / "explicit-zelph"
    explicit.write_text("", encoding="utf-8")
    explicit.chmod(0o755)

    monkeypatch.setenv("ZELPH_BIN", str(explicit))
    monkeypatch.setattr(compat.shutil, "which", lambda _name: "/usr/bin/zelph")
    rows = compat.candidate_zelph_binaries(repo_root=sensiblaw)
    assert rows[0] == str(explicit.resolve())
    assert rows[1] == str(itir_bin.resolve())
    assert rows[-1] == "/usr/bin/zelph"


def test_selection_skips_crashing_binary_and_uses_next(monkeypatch) -> None:
    monkeypatch.setattr(compat, "candidate_zelph_binaries", lambda **_kwargs: ["/bad", "/good"])
    monkeypatch.setattr(compat, "_binary_banner", lambda binary: {"banner": binary, "banner_attempts": []})

    def probe(_manifest, *, binary, **_kwargs):
        if binary == "/bad":
            return {
                "compatible": False,
                "failure_kind": "manifest_meta_only_failed",
                "exit_code": -11,
                "termination_kind": "signal",
                "signal_number": 11,
                "signal_name": "SIGSEGV",
                "detail": "",
                "output_tail": "",
            }
        return {
            "compatible": True,
            "failure_kind": None,
            "exit_code": 0,
            "termination_kind": "clean_exit",
            "signal_number": None,
            "signal_name": None,
            "detail": "",
            "output_tail": "ok",
        }

    monkeypatch.setattr(compat, "probe_zelph_manifest_compatibility", probe)
    receipt = compat.select_compatible_zelph_binary(_manifest())
    assert receipt["compatible"] is True
    assert receipt["selected_binary"] == "/good"
    assert receipt["candidates"][0]["signal_name"] == "SIGSEGV"
    assert receipt["known_good_itir_reference"]["commit"] == compat.KNOWN_GOOD_ITIR_ZELPH_COMMIT
    assert receipt["source_support_paid"] is False
