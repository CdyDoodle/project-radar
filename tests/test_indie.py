"""The solo-builder signal: personal-account repos and Show HN launches."""
from radar import rank, report
from radar.sources.community import HackerNews
from radar.sources.github import _repo_item
from tests.conftest import link, repo


def test_indie_counts_personal_repos_and_show_hn():
    assert rank.indie(repo("alice/tool", owner_type="User")) == 1.0
    assert rank.indie(repo("bigco/tool", owner_type="Organization")) == 0.0
    assert rank.indie(repo("old/tool")) == 0.0                    # fetched before owner_type existed
    assert rank.indie(link("https://alice.dev", "Show HN: my app", show_hn=True)) == 1.0
    assert rank.indie(link("https://news.example", "Front page story", hn_points=400)) == 0.0


def test_repo_items_record_the_owner_type():
    data = {"full_name": "alice/tool", "owner": {"login": "alice", "type": "User"}}
    assert _repo_item(data, "github_search", "e").metrics["owner_type"] == "User"
    assert "owner_type" not in _repo_item({"full_name": "x/y"}, "github_search", "e").metrics


def test_show_hn_posts_are_marked(cfg):
    hit = {"title": "Show HN: a voice agent", "objectID": "1", "url": "https://alice.dev",
           "points": 50, "num_comments": 4, "created_at": "2026-10-20T00:00:00Z"}

    class Http:
        def json(self, url, params=None, **kw):
            return {"hits": [{**hit, "objectID": params["tags"]}]}

    items = {i.metrics["hn_id"]: i for i in HackerNews().fetch(cfg, Http())}
    assert items["show_hn"].metrics["show_hn"] is True
    assert "show_hn" not in items["story"].metrics


def test_indie_weight_reaches_the_score(store, cfg):
    cfg.raw["rank"]["weights"] = {"indie": 0.9}
    with store.tx():
        store.upsert(repo("alice/agent", "An AI agent", owner_type="User", stars=100))
    rank.rank_all(store, cfg)
    import json
    bd = json.loads(store.get("gh:alice/agent")["breakdown"])
    assert bd["contributions"]["indie"] == 0.9


def test_solo_built_ai_lane(store, cfg):
    items = [
        repo("alice/voice-agent", "An AI agent you talk to", owner_type="User", stars=400),
        repo("bigco/agent", "An AI agent platform", owner_type="Organization", stars=400),
        repo("bob/db", "A columnar database engine", owner_type="User", stars=400),
        repo("carol/llm-app", "LLM chat app", owner_type="User", stars=250_000),
        link("https://dave.dev", "Show HN: an LLM that writes SQL", show_hn=True, hn_points=60),
    ]
    store.start_run("r1")
    with store.tx():
        for it in items:
            store.upsert(it)
    rank.rank_all(store, cfg)
    lanes = {l["key"]: l for l in report._highlights(store, cfg, since=None)}
    solo = {i["title"] for i in lanes["indie"]["items"]}
    # bigco: an organization. bob: no AI. carol: already famous.
    assert solo == {"alice/voice-agent", "Show HN: an LLM that writes SQL"}
    assert lanes["indie"]["title"]["zh"] == "个人开发者的 AI 作品"
