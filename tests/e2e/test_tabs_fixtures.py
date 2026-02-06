import os
import pytest


pytestmark = [pytest.mark.e2e]


def _should_run():
    return os.environ.get("RUN_PLAYWRIGHT") == "1"


def test_tabs_render_fixtures():
    if not _should_run():
        pytest.skip("Set RUN_PLAYWRIGHT=1 to run UI e2e checks.")

    playwright = pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import expect

    base_url = os.environ.get("STREAMLIT_URL", "http://localhost:8501/")
    url = (
        f"{base_url}?graph_fixture=knowledge_graph_minimal.json"
        "&case_fixture=case_comparison_minimal.json"
        "&concepts_fixture=concepts_minimal.json"
        "&obligations_fixture=obligations_minimal.json"
    )

    with playwright.sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")

        # Text & Concepts (fixture mode)
        page.get_by_role("tab", name="Text & Concepts").click()
        expect(page.get_by_text("Fixture mode", exact=False)).to_be_visible()
        expect(page.get_by_text("Concept matches")).to_be_visible()

        # Obligations (fixture mode)
        page.get_by_role("tab", name="Obligations").click()
        expect(page.get_by_text("Fixture mode", exact=False)).to_be_visible()
        expect(page.get_by_text("Obligations (read-only)", exact=False)).to_be_visible()

        # Knowledge Graph (fixture mode)
        page.get_by_role("tab", name="Knowledge Graph").click()
        expect(page.get_by_text("Fixture mode", exact=False)).to_be_visible()
        expect(page.get_by_text("Nodes")).to_be_visible()
        expect(page.get_by_text("Edges")).to_be_visible()

        # Case Comparison (fixture mode)
        page.get_by_role("tab", name="Case Comparison").click()
        expect(page.get_by_text("Added")).to_be_visible()
        expect(page.get_by_text("Removed")).to_be_visible()
        expect(page.get_by_text("Unchanged")).to_be_visible()

        # Quick forbidden language sweep
        banned = [
            "compliance",
            "breach",
            "prevails",
            "valid",
            "invalid",
            "stronger",
            "weaker",
            "satisfies",
            "violates",
            "binding",
            "override",
        ]
        body = page.content().lower()
        assert all(term not in body for term in banned)

        # No generic mutation controls visible in these tabs
        for label in ["Save", "Apply", "Approve", "Edit", "Resolve"]:
            assert page.get_by_role("button", name=label).count() == 0

        browser.close()
