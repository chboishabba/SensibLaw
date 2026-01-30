import os
import pytest


pytestmark = [pytest.mark.e2e]


def _should_run():
    return os.environ.get("RUN_PLAYWRIGHT") == "1"


def test_collections_tab_read_only():
    if not _should_run():
        pytest.skip("Set RUN_PLAYWRIGHT=1 to run UI e2e checks.")

    playwright = pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import expect

    base_url = os.environ.get("STREAMLIT_URL", "http://localhost:8501/")
    forbidden = {"compliance", "breach", "winner", "prevails", "binding", "override"}

    with playwright.sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.goto(base_url, wait_until="networkidle")
        page.get_by_role("tab", name="Collections").click()
        expect(page.get_by_text("Review Collections (read-only)")).to_be_visible()

        # Default collection path should be prefilled
        input_box = page.get_by_label("Collection path")
        expect(input_box).to_have_value("examples/review_collection_minimal.json")

        # Manifest rendered
        expect(page.get_by_text("Manifest")).to_be_visible()

        body_text = page.content().lower()
        assert forbidden.isdisjoint(body_text)

        # No mutation affordances
        for label in ["Save", "Approve", "Apply", "Edit", "Resolve"]:
            assert page.get_by_role("button", name=label).count() == 0

        browser.close()
