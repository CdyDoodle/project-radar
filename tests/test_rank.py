from radar import diversify, rank
from tests.conftest import link, repo


def test_score_breakdown_is_consistent(cfg):
    it = repo("x/infer", "fast inference compiler in rust", stars=900, stars_per_day=30)
    total, bd = rank.score_item(it, cfg)
    assert round(total, 3) == bd["total"]
    assert abs(bd["positive"] - sum(bd["contributions"].values())) < 0.01


def test_slop_is_penalised(cfg):
    good, _ = rank.score_item(repo("x/engine", "an inference engine"), cfg)
    slop, bd = rank.score_item(repo("x/awesome-llm", "awesome list of llm stuff"), cfg)
    assert "slop" in bd["penalties"] and slop < good


def test_chatter_penalises_bare_links(cfg):
    _, bd = rank.score_item(link("https://blog.example.com/p", "My thoughts on life"), cfg)
    assert "chatter" in bd["penalties"]


def test_mega_penalty(cfg):
    _, bd = rank.score_item(repo("x/famous", stars=200_000), cfg)
    assert "mega" in bd["penalties"]


def test_corroboration_curve():
    it = repo("x/y")
    assert rank.corroboration(it) == 0
    it.sources |= {"hackernews"}
    assert rank.corroboration(it) == 0.5
    it.sources |= {"lobsters"}
    assert rank.corroboration(it) == 0.75


def test_quotas_hand_back_unfillable_slots():
    q = diversify._quotas({"a": 0.3, "b": 0.4, "c": 0.3}, 10, {"a": 1, "b": 20, "c": 20})
    assert q["a"] == 1 and sum(q.values()) == 10


def test_quotas_never_exceed_supply():
    q = diversify._quotas({"a": 0.5, "b": 0.5}, 10, {"a": 2, "b": 3})
    assert q == {"a": 2, "b": 3}


def test_mmr_breaks_up_a_theme_stack():
    # A low-scoring filler anchors min-max normalisation, as the real pool does.
    cands = ["inf1", "inf2", "inf3", "db1", "filler"]
    texts = ["llama inference engine", "gguf inference server", "moe inference runtime",
             "a columnar database", "misc"]
    theme_sets = [{"llm-inference"}] * 3 + [{"databases"}, set()]
    picked = diversify.mmr(cands, texts, theme_sets, k=2, lam=0.65,
                           scores=[3.0, 2.9, 2.8, 2.7, 1.0])
    assert picked == ["inf1", "db1"]


def test_mmr_lambda_one_is_identity():
    cands = list("abcd")
    assert diversify.mmr(cands, ["x"] * 4, [set()] * 4, k=3, lam=1.0) == ["a", "b", "c"]
