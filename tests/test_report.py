from radar import rank, report
from tests.conftest import link, repo


def seed(store, cfg, run_id="r1"):
    items = [
        repo("a/infer", "LLM inference server with kv cache", stars=5000, stars_per_day=90),
        repo("b/db", "A columnar database engine", stars=800, stars_per_day=12),
        repo("c/agent-re", "An AI agent that reverse engineers binaries", stars=300,
             stars_per_day=8, starred_by=["alice"], source="github_starred"),
        repo("d/huge", "Everything app", stars=250_000, stars_per_day=4000),
        link("https://arxiv.org/abs/2609.00001", "A new attention kernel", source="arxiv"),
        link("https://example.com/news", "Restroom Archive", hn_points=300),
    ]
    store.start_run(run_id)
    with store.tx():
        for it in items:
            store.upsert(it)
    rank.rank_all(store, cfg)


def test_build_writes_html_and_markdown(store, cfg):
    seed(store, cfg)
    html, md = report.build(cfg, store, run_id="r1", feed_limit=50)
    page = html.read_text(encoding="utf-8")
    assert "a/infer" in page and "b/db" in page
    assert "Worth a look" in page
    assert md.read_text(encoding="utf-8").startswith("# radar digest")


def test_html_escapes_titles(store, cfg):
    with store.tx():
        store.upsert(repo("x/xss", "<script>alert(1)</script>", stars=10))
    rank.rank_all(store, cfg)
    html, _ = report.build(cfg, store, feed_limit=10)
    assert "<script>alert(1)</script>" not in html.read_text(encoding="utf-8")


def test_page_carries_both_languages_and_row_keys(store, cfg):
    seed(store, cfg)
    html, md = report.build(cfg, store, run_id="r1")
    page = html.read_text(encoding="utf-8")
    assert 'data-zh="排名信号"' in page and 'data-en="Ranked signal"' in page
    assert 'data-key="gh:a/infer"' in page and 'data-cmd="dismiss"' in page
    assert 'data-zh="LLM 推理"' in page                      # theme label
    assert '<html lang="en">' in page


def test_chinese_default_language(store, cfg):
    cfg.raw["report"] = {"language": "zh-CN"}
    seed(store, cfg)
    html, md = report.build(cfg, store, run_id="r1")
    assert '<html lang="zh-CN">' in html.read_text(encoding="utf-8")
    text = md.read_text(encoding="utf-8")
    assert text.startswith("# radar 摘要") and "## 排名信号" in text and "### LLM 推理" in text


def test_saved_lane_and_famous_repos_kept_out_of_fastest(store, cfg):
    seed(store, cfg)
    store.set_status("gh:b/db", "saved")
    lanes = {l["key"]: l for l in report._highlights(store, cfg, since=None)}
    assert [i["title"] for i in lanes["saved"]["items"]] == ["b/db"]
    fastest = [i["title"] for i in lanes["fastest"]["items"]]
    assert "d/huge" not in fastest and "a/infer" in fastest   # 250k stars is mega


def test_earlier_briefs_are_listed(store, cfg):
    seed(store, cfg)
    brief = {"title": "Old idea", "one_liner": "o", "difficulty": 3, "novelty": 2,
             "effort_weeks": 4, "pitch": "", "why_now": "", "hard_parts": [],
             "you_will_learn": [], "milestones": [], "prior_art": [], "kill_criteria": "",
             "ai_leverage": "", "source_urls": []}
    store.add_brief("20260901-000000-00", "20260901-000000", brief)
    store.add_brief("r1-00", "r1", {**brief, "title": "Current idea"})
    past = report._past_briefs(store, "r1")
    assert [p["date"] for p in past] == ["2026-09-01"]
    assert past[0]["briefs"][0]["title"] == "Old idea"
    page = report.build(cfg, store, run_id="r1")[0].read_text(encoding="utf-8")
    assert 'id="past"' in page and "Old idea" in page


def test_briefs_keep_their_order_when_the_latest_run_has_none(store, cfg):
    seed(store, cfg)
    base = {"one_liner": "o", "difficulty": 3, "novelty": 2, "effort_weeks": 4, "pitch": "",
            "why_now": "", "hard_parts": [], "you_will_learn": [], "milestones": [],
            "prior_art": [], "kill_criteria": "", "ai_leverage": "", "source_urls": []}
    for i in range(3):
        store.add_brief(f"r1-{i:02d}", "r1", {**base, "title": f"Brief {i + 1}"})
    store.start_run("r2")                                   # a later run with no briefs
    page = report.build(cfg, store)[0].read_text(encoding="utf-8")
    assert page.index("Brief 1") < page.index("Brief 2") < page.index("Brief 3")
