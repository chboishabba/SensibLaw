"""Smoke tests for the Streamlit console."""


def test_streamlit_app_imports() -> None:
    """Importing the Streamlit application should not raise."""

    import streamlit_app  # noqa: F401  - import is the test

    assert hasattr(streamlit_app, "main")
