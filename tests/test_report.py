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
