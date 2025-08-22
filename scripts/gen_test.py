"""Generate a pytest test skeleton for a given module path.

Usage:
    python scripts/gen_test.py src/path/to/module.py

This will create ``tests/path/to/test_module.py`` with basic pytest fixtures
and a skipped placeholder test. If `jinja2` is available, it will be used to
render the test file; otherwise, Python's string formatting is used.
"""

from __future__ import annotations

import argparse
from pathlib import Path

try:  # Optional template engine
    from jinja2 import Template  # type: ignore
except Exception:  # pragma: no cover - jinja2 may not be installed
    Template = None  # type: ignore


JINJA_TEMPLATE = '''
"""Tests for {{ module_import }}."""

import pytest
import {{ module_import }} as {{ module_name }}


@pytest.fixture
def example_fixture():
    """Example fixture for {{ module_import }}."""
    # TODO: replace with real fixture implementation
    return None


@pytest.mark.skip("TODO: add real tests for {{ module_import }}")
def test_example(example_fixture):
    """Example test for {{ module_import }}."""
    assert example_fixture is None
'''

FORMAT_TEMPLATE = '''
"""Tests for {module_import}."""

import pytest
import {module_import} as {module_name}


@pytest.fixture
def example_fixture():
    """Example fixture for {module_import}."""
    # TODO: replace with real fixture implementation
    return None


@pytest.mark.skip("TODO: add real tests for {module_import}")
def test_example(example_fixture):
    """Example test for {module_import}."""
    assert example_fixture is None
'''


def render_template(module_import: str, module_name: str) -> str:
    """Render the test skeleton using Jinja2 if available."""
    context = {"module_import": module_import, "module_name": module_name}
    if Template is not None:
        return Template(JINJA_TEMPLATE).render(**context)
    return FORMAT_TEMPLATE.format(**context)


def module_to_test_path(module_path: Path) -> tuple[str, Path]:
    """Compute import path and test file path for a module file."""
    if module_path.suffix != ".py":
        raise ValueError("Module path must point to a .py file")
    parts = module_path.with_suffix("").parts
    if parts[0] == "src":
        parts = parts[1:]
    module_import = ".".join(("src", *parts))
    test_dir = Path("tests", *parts[:-1])
    test_file = test_dir / f"test_{parts[-1]}.py"
    return module_import, test_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a pytest test skeleton")
    parser.add_argument("module", help="Path to the module file, e.g. src/pkg/mod.py")
    parser.add_argument(
        "--force", action="store_true", help="Overwrite existing test file if it exists"
    )
    args = parser.parse_args()

    module_path = Path(args.module)
    if not module_path.exists():
        parser.error(f"Module path {module_path} does not exist")

    module_import, test_file = module_to_test_path(module_path)
    if test_file.exists() and not args.force:
        parser.error(f"Test file {test_file} already exists. Use --force to overwrite.")

    test_file.parent.mkdir(parents=True, exist_ok=True)
    content = render_template(module_import, test_file.stem.replace("test_", ""))
    test_file.write_text(content, encoding="utf-8")
    print(f"Created {test_file}")


if __name__ == "__main__":
    main()
