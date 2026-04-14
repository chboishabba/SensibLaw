from __future__ import annotations

from src.policy.gwb_legal_follow_graph import build_gwb_legal_follow_graph, build_gwb_legal_follow_operator_view
from src.sources.uk_legislation import (
    load_uk_legislation_api_sample,
    load_uk_legislation_follow_candidates,
    normalize_legislation_receipts,
    parse_legislation_xml,
)


def test_uk_legislation_follow_candidates_produce_follow_queue() -> None:
    candidates = load_uk_legislation_follow_candidates()
    if not candidates["review_item_rows"] or not candidates["source_review_rows"]:
        raise AssertionError("uk_legislation fixture is missing")
    graph = build_gwb_legal_follow_graph(
        review_item_rows=candidates["review_item_rows"],
        source_review_rows=candidates["source_review_rows"],
    )
    view = build_gwb_legal_follow_operator_view(graph)

    summary = view["summary"]
    assert summary["queue_count"] >= 1
    assert summary["route_target_counts"].get("uk_legislation_follow", 0) >= 1
    assert summary["priority_band_counts"]["high"] >= 0
    assert view["queue"][0]["authority_yield"] == "high"
    control = view["control_plane"]
    assert "uk_legislation_follow" in control["route_targets"]


def test_uk_legislation_receipt_normalization() -> None:
    receipts = normalize_legislation_receipts()
    assert receipts
    assert all("value" in receipt for receipt in receipts)
    assert all("metadata" in receipt for receipt in receipts)
    normalized = receipts[0]["metadata"].get("normalized_source_unit")
    assert normalized
    assert normalized["source_family"] == "uk_legislation"


LEGISLATION_SAMPLE_XML = """<?xml version='1.0' encoding='utf-8'?>
<Legislation xmlns="http://www.legislation.gov.uk/namespaces/legislation"
             xmlns:ukm="http://www.legislation.gov.uk/namespaces/metadata"
             xmlns:dc="http://purl.org/dc/elements/1.1/"
             xmlns:dct="http://purl.org/dc/terms/">
  <ukm:Metadata>
    <dc:title>Example Act</dc:title>
    <dct:valid>2024-01-01</dct:valid>
  </ukm:Metadata>
  <Primary>
    <Body>
      <Pblock>
        <P1group>
          <P1 DocumentURI="http://www.legislation.gov.uk/ukpga/2018/16/section/1">
            <Pnumber />
          </P1>
          <P1 DocumentURI="http://www.legislation.gov.uk/ukpga/2018/16/section/2">
            <Pnumber />
          </P1>
        </P1group>
      </Pblock>
    </Body>
  </Primary>
</Legislation>
"""


def test_parse_legislation_xml_extracts_sections() -> None:
    payload = parse_legislation_xml(
        LEGISLATION_SAMPLE_XML.encode("utf-8"),
        max_sections=1,
        version_suffix="enacted",
    )
    assert payload["title"] == "Example Act"
    assert payload["documentDate"] == "2024-01-01"
    assert len(payload["sections"]) == 1
    section = payload["sections"][0]
    assert section["sectionNumber"] == "1"
    assert section["url"].endswith("/section/1/enacted")
    assert section["sectionLabel"] == "1"


def test_parse_legislation_xml_deduplicates_sections() -> None:
    duplicate_sample = """<?xml version='1.0' encoding='utf-8'?>
<Legislation xmlns="http://www.legislation.gov.uk/namespaces/legislation"
             xmlns:ukm="http://www.legislation.gov.uk/namespaces/metadata"
             xmlns:dc="http://purl.org/dc/elements/1.1/"
             xmlns:dct="http://purl.org/dc/terms/">
  <ukm:Metadata>
    <dc:title>Example Act</dc:title>
    <dct:valid>2024-01-01</dct:valid>
  </ukm:Metadata>
  <Primary>
    <Body>
      <Pblock>
        <P1group>
          <P1 DocumentURI="http://www.legislation.gov.uk/ukpga/2020/1/section/1" />
          <P1 DocumentURI="http://www.legislation.gov.uk/ukpga/2020/1/section/1" />
        </P1group>
      </Pblock>
    </Body>
  </Primary>
</Legislation>
"""
    payload = parse_legislation_xml(duplicate_sample.encode("utf-8"))
    assert len(payload["sections"]) == 1
    assert payload["sections"][0]["sectionNumber"] == "1"


def test_normalize_receipts_include_labels() -> None:
    receipts = normalize_legislation_receipts(max_sections=1)
    assert receipts
    metadata = receipts[0]["metadata"]
    assert metadata["section_label"]
    assert metadata["version"] == "enacted"


def test_uk_legislation_receipt_normalization_fallback(monkeypatch) -> None:
    import src.sources.uk_legislation as uk_legislation_src

    monkeypatch.setattr(uk_legislation_src, "fetch_legislation_act_payload", lambda **kwargs: {})
    receipts = normalize_legislation_receipts()
    sample = load_uk_legislation_api_sample()
    assert receipts[0]["value"] == sample["sections"][0]["url"]
