import pytest

from src.pdf_ingest import _clean_toc_title_segment


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("No. 1 Introduction 2022", "No. 1 Introduction 2022"),
        ("Clause 2.4 Overview 2021", "Clause 2.4 Overview 2021"),
        ("Introduction ........ 23", "Introduction"),
        ("Summary ······ 4", "Summary"),
        ("Background Page 12", "Background"),
        ("Appendix page12", "Appendix"),
    ],
)
def test_clean_toc_title_segment_preserves_legitimate_numbers(raw, expected):
    assert _clean_toc_title_segment(raw) == expected
