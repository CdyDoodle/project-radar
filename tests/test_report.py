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


def test_no_project_briefs_on_the_page(store, cfg):
    seed(store, cfg)
    page = report.build(cfg, store, run_id="r1")[0].read_text(encoding="utf-8")
    assert "view-briefs" not in page and "项目简报" not in page
    assert 'data-zh="多来源印证"' in page


def test_topic_lane_from_config(store, cfg):
    cfg.raw["report"] = {"topic_lanes": [{
        "key": "ai-security", "en": "AI security", "zh": "AI 安全",
        "terms": ["prompt injection", "jailbreak", "security"]}]}
    items = [
        repo("a/shield", "Detects prompt injection against LLM agents", stars=300),
        repo("b/ios", "iPhone jailbreak toolkit", stars=300),                # no AI
        repo("c/chat", "An LLM chat app", stars=300),
    ]
    items[2].readme = "## Security\nReport issues by email."             # README only
    store.start_run("r1")
    with store.tx():
        for it in items:
            store.upsert(it)
    rank.rank_all(store, cfg)
    lanes = {l["key"]: l for l in report._highlights(store, cfg, since=None)}
    lane = lanes["topic:ai-security"]
    assert [i["title"] for i in lane["items"]] == ["a/shield"]
    assert lane["title"] == {"en": "AI security", "zh": "AI 安全"}
    page = report.build(cfg, store, run_id="r1")[0].read_text(encoding="utf-8")
    assert 'data-zh="AI 安全"' in page


def test_feed_quick_views_and_badges(store, cfg):
    cfg.raw["report"] = {"topic_lanes": [{"key": "ai-security", "en": "AI security",
                                          "zh": "AI 安全", "terms": ["prompt injection"]}]}
    store.start_run("r1")
    with store.tx():
        store.upsert(repo("alice/shield", "Stops prompt injection in LLM agents",
                          owner_type="User", stars=300))
        store.upsert(repo("bigco/db", "A columnar database engine",
                          owner_type="Organization", stars=300))
    rank.rank_all(store, cfg)
    rows = {r["key"]: r for r in report._rows(store, cfg, 50, since="2000")}
    shield = rows["gh:alice/shield"]
    assert set(shield["quick"].split()) == {"indie", "new", "topic:ai-security"}
    assert [b["zh"] for b in shield["badges"]] == ["新", "个人作品", "AI 安全"]
    assert "indie" not in rows["gh:bigco/db"]["quick"]
    views = {v["key"]: v["n"] for v in report._quick_views(list(rows.values()), cfg)}
    assert views == {"": 2, "indie": 1, "topic:ai-security": 1, "new": 2}   # no saved: left out
    page = report.build(cfg, store, run_id="r1")[0].read_text(encoding="utf-8")
    assert 'data-quick="indie"' in page and 'class="bdg indie"' in page
