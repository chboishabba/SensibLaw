from __future__ import annotations

import json
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from sensiblaw.ribbon.compute import compute_segments, compute_total_mass


def _load_lens_pack(name: str) -> dict:
    root = Path(__file__).resolve().parents[3]
    pack_path = root / "itir-ribbon" / "lens_packs" / f"{name}.json"
    return json.loads(pack_path.read_text())


def _build_demo_data() -> dict:
    # Create a small aligned signal domain.
    signal_len = 40
    signals = {
        "citation_rate": [1.0 if i < 20 else 2.0 for i in range(signal_len)],
        "exhibit_rate": [0.5 if i % 2 == 0 else 1.5 for i in range(signal_len)],
        "contradiction_rate": [0.2 if i % 5 == 0 else 0.1 for i in range(signal_len)],
        "placeholder": [1.0] * signal_len,
    }
    boundaries = [0, 10, 20, 30, 40]

    time_lens = _load_lens_pack("time")
    evidence_lens = _load_lens_pack("evidence_density")

    time_segments = compute_segments(time_lens, signals, boundaries)
    evidence_segments = compute_segments(evidence_lens, signals, boundaries)

    return {
        "time": {
            "segments": [seg.__dict__ for seg in time_segments],
            "total_mass": compute_total_mass(time_segments),
        },
        "evidence": {
            "segments": [seg.__dict__ for seg in evidence_segments],
            "total_mass": compute_total_mass(evidence_segments),
        },
    }


def render() -> None:
    st.subheader("Ribbon Demo (Conserved Allocation)")
    st.caption(
        "This demo exposes the selector contract for Playwright conservation tests."
    )

    lens_data = _build_demo_data()
    payload = json.dumps(lens_data)

    html = f"""
    <div>
      <div data-testid="conservation-badge" data-total-mass="{lens_data['time']['total_mass']}" data-lens-id="time">
        Lens: <span data-testid="lens-label">time</span>
      </div>
      <div style="margin: 8px 0;">
        <button data-testid="lens-switcher" type="button">Switch lens</button>
        <button data-testid="lens-item:time" type="button">time</button>
        <button data-testid="lens-item:evidence" type="button">evidence</button>
        <button data-testid="compare-overlay-toggle" type="button">compare</button>
      </div>
      <div data-testid="ribbon-viewport" style="display:flex;width:100%;border:1px solid #ccc;height:24px;">
        <div data-testid="segment" data-seg-id="seg-1" style="background:#7aa6c2"></div>
        <div data-testid="segment" data-seg-id="seg-2" style="background:#8fb3c8"></div>
        <div data-testid="segment" data-seg-id="seg-3" style="background:#a4c0cf"></div>
        <div data-testid="segment" data-seg-id="seg-4" style="background:#b9cdd6"></div>
      </div>
      <div data-testid="compare-overlay" style="display:none;height:10px;margin-top:4px;background:#eee"></div>
    </div>
    <script>
      const lensData = {payload};
      const badge = document.querySelector('[data-testid="conservation-badge"]');
      const lensLabel = document.querySelector('[data-testid="lens-label"]');
      const compare = document.querySelector('[data-testid="compare-overlay"]');
      let compareOn = false;

      function renderLens(lensId) {{
        const lens = lensData[lensId];
        if (!lens) return;
        badge.dataset.totalMass = lens.total_mass;
        badge.dataset.lensId = lensId;
        lensLabel.textContent = lensId;

        lens.segments.forEach((seg) => {{
          const el = document.querySelector(`[data-seg-id="${{seg.seg_id}}"]`);
          if (!el) return;
          el.style.width = (seg.width_norm * 100).toFixed(3) + '%';
          el.dataset.widthNorm = seg.width_norm.toFixed(6);
          el.dataset.mass = seg.mass.toFixed(6);
        }});
      }}

      document.querySelector('[data-testid="lens-item:time"]').addEventListener('click', () => renderLens('time'));
      document.querySelector('[data-testid="lens-item:evidence"]').addEventListener('click', () => renderLens('evidence'));
      document.querySelector('[data-testid="compare-overlay-toggle"]').addEventListener('click', () => {{
        compareOn = !compareOn;
        compare.style.display = compareOn ? 'block' : 'none';
      }});

      renderLens('time');
    </script>
    """

    components.html(html, height=140)
