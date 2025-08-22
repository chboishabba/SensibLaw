"""Fuzz the section parser using atheris.

This harness feeds random byte sequences to ``parse_section`` to uncover
crashes.
"""

import sys
import atheris

with atheris.instrument_imports():
    from src.ingestion.section_parser import parse_html_section as parse_section


def TestOneInput(data: bytes) -> None:
    text = data.decode("utf-8", errors="ignore")
    try:
        parse_section(text)
    except Exception:
        # Propagate the exception so Atheris can record the crash
        raise


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
