from src.sources.austlii_sino import SinoQuery, build_sino_url


def test_build_sino_url_basic():
    url = build_sino_url(
        "https://www.austlii.edu.au/cgi-bin/sinosrch.cgi",
        SinoQuery(meta="/au", method="any", query="native title", results=50, offset=0),
    )
    assert "meta=%2Fau" in url
    assert "method=any" in url
    assert "query=native+title" in url
    assert "results=50" in url
    assert "offset=0" in url


def test_build_sino_url_mask_path_repeats():
    url = build_sino_url(
        "https://www.austlii.edu.au/cgi-bin/sinosrch.cgi",
        SinoQuery(meta="/au", query="mabo", mask_path=["au/cases/cth/high_ct", "au/legis/cth/consol_act"]),
    )
    assert "mask_path=au%2Fcases%2Fcth%2Fhigh_ct" in url
    assert "mask_path=au%2Flegis%2Fcth%2Fconsol_act" in url


def test_build_sino_url_mask_by_phc():
    url = build_sino_url(
        "https://www.austlii.edu.au/cgi-bin/sinosrch.cgi",
        SinoQuery(
            meta="/austlii",
            query="native title",
            mask_by_phc={"au": ["au/cases/cth/high_ct"], "nz": ["nz/cases/NZCA"]},
        ),
    )
    assert "mask_au=au%2Fcases%2Fcth%2Fhigh_ct" in url
    assert "mask_nz=nz%2Fcases%2FNZCA" in url
