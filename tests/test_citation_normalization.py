from src.citations.normalize import (
    CitationKey,
    austlii_case_url_guess,
    jade_content_ext_url,
    jade_mnc_url,
    normalize_mnc,
)


def test_normalize_mnc_bracketed():
    assert normalize_mnc("[1992] HCA 23") == CitationKey(1992, "HCA", 23)


def test_normalize_mnc_unbracketed():
    assert normalize_mnc("1992 HCA 23") == CitationKey(1992, "HCA", 23)


def test_jade_urls():
    key = CitationKey(2011, "HCA", 1)
    assert jade_mnc_url(key).endswith("/mnc/2011/HCA/1")
    assert "/content/ext/mnc/2011/hca/1" in jade_content_ext_url(key)


def test_austlii_guess_url():
    key = CitationKey(1992, "HCA", 23)
    url = austlii_case_url_guess(key)
    assert "austlii.edu.au" in url
    assert url.endswith("/1992/23.html")
