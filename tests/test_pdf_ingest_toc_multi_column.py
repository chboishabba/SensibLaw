from pathlib import Path

from src.pdf_ingest import extract_pdf_text, parse_table_of_contents


def test_parse_table_of_contents_handles_multi_column_layout():
    pages = extract_pdf_text(Path("act-2005-004.pdf"))
    toc_pages = pages[2:6]

    entries = parse_table_of_contents(toc_pages)

    assert entries, "Expected TOC entries to be parsed"

    part1 = entries[0]
    assert part1.node_type == "part"
    assert part1.identifier == "1"
    assert part1.title == "Preliminary"
    assert part1.page_number in {None, 5}

    part1_section_ids = [child.identifier for child in part1.children[:4]]
    assert part1_section_ids == ["1", "2", "3", "4"]

    part1_section_titles = [child.title for child in part1.children[:4]]
    assert part1_section_titles == [
        "Short title",
        "Commencement",
        "Definitions",
        "Notes",
    ]

    part1_section_pages = [child.page_number for child in part1.children[:4]]
    assert part1_section_pages == [5, 5, 5, 5]

    part2 = entries[1]
    assert part2.identifier == "2"
    assert part2.title == "Offences"

    division1 = part2.children[0]
    assert division1.identifier == "1"
    assert division1.title == "Offences about quality of community use of public places"

    section5 = division1.children[0]
    assert section5.identifier == "5"
    assert section5.title == "Object of div 1"
    assert section5.page_number == 6

    section6 = division1.children[1]
    assert section6.identifier == "6"
    assert section6.title == "Public nuisance"
    assert section6.page_number == 6
