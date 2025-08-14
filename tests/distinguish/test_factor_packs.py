from src.distinguish.factor_packs import factor_pack_for_case


def test_glj_factor_packs_paragraphs():
    packs = factor_pack_for_case("[2002] HCA 14")
    assert packs["delay"] == [1]
    assert packs["lost evidence"] == [2]
