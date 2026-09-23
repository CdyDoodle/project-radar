"""Data correctness: accumulation across runs, trending hydration, whole-word fit."""
import pytest

from radar import rank
from radar.sources.github import GitHubTrending, hydrate
from tests.conftest import link, repo


# -- corroboration survives across runs -------------------------------------
def test_sources_accumulate_across_runs(store):
    store.upsert(repo("x/y", source="hackernews", hn_points=300))
    store.upsert(repo("x/y", source="github_trending", trending_windows=["daily"]))
    it = store.to_item(store.get("gh:x/y"))
    assert it.sources == {"hackernews", "github_trending"}
    assert it.metrics["hn_points"] == 300
    assert it.metrics["trending_windows"] == ["daily"]
    assert rank.corroboration(it) == 0.5


def test_watchers_and_windows_union_across_runs(store):
    store.upsert(repo("x/y", source="github_starred", starred_by=["alice"],
                      trending_windows=["weekly"]))
    store.upsert(repo("x/y", source="github_starred", starred_by=["bob"],
                      trending_windows=["daily"]))
    m = store.to_item(store.get("gh:x/y")).metrics
    assert m["starred_by"] == ["alice", "bob"]
    assert m["trending_windows"] == ["daily", "weekly"]


def test_point_in_time_metrics_take_the_fresh_reading(store):
    store.upsert(repo("x/y", stars=100, days_since_push=200, archived=True))
    store.upsert(repo("x/y", stars=90, days_since_push=1, archived=False))
    m = store.to_item(store.get("gh:x/y")).metrics
    # max-merging would keep 200 days and archived=True forever.
    assert m == {**m, "stars": 90, "days_since_push": 1, "archived": False}


def test_snapshot_metric_missing_from_fresh_sighting_is_kept(store):
    store.upsert(repo("x/y", stars=500))
    store.upsert(repo("x/y", source="hackernews", hn_points=50))
    assert store.to_item(store.get("gh:x/y")).metrics["stars"] == 500


def test_repo_title_survives_an_hn_only_run(store):
    store.upsert(repo("x/y", source="github_search"))
    hn = repo("x/y", source="hackernews")
    hn.title = "Show HN: My cool thing"
    store.upsert(hn)
    assert store.get("gh:x/y")["title"] == "x/y"


def test_evidence_is_deduplicated_and_capped(store):
    for day in range(30):
        it = repo("x/y", source="github_trending")
        it.evidence = [f"trending day {day}", "starred by alice"]
        store.upsert(it)
    ev = store.to_item(store.get("gh:x/y")).evidence
    assert len(ev) == 12 and ev[0] == "trending day 29"
    assert ev.count("starred by alice") == 1


def test_first_seen_and_status_are_preserved(store):
    store.upsert(repo("x/y"))
    first = store.get("gh:x/y")["first_seen"]
    store.set_status("gh:x/y", "saved")
    store.upsert(repo("x/y"))
    row = store.get("gh:x/y")
    assert row["first_seen"] == first and row["status"] == "saved"


# -- trending --------------------------------------------------------------
TRENDING_HTML = """
<article class="Box-row">
  <h2><a href="/Owner/Tool">Owner / Tool</a></h2>
  <p>A fast thing</p>
  <span itemprop="programmingLanguage">Rust</span>
  <span class="d-inline-block float-sm-right">1,234 stars today</span>
</article>
<article class="Box-row">
  <h2><a href="/other/gone">other / gone</a></h2>
  <span class="d-inline-block float-sm-right">12 stars this week</span>
</article>
"""


class FakeHttp:
    def __init__(self, repos):
        self.repos = repos
        self.calls = []

    def gh(self, path, **kw):
        self.calls.append(path)
        return self.repos.get(path)


def test_trending_parse_extracts_period_stars():
    items = GitHubTrending().parse(TRENDING_HTML, "daily")
    assert [i.key for i in items] == ["gh:owner/tool", "gh:other/gone"]
    assert items[0].metrics["stars_today"] == 1234
    assert items[1].metrics["stars_this_week"] == 12


def test_hydrate_fills_metadata_and_keeps_trending_signal():
    api = {"/repos/owner/tool": {
        "full_name": "Owner/Tool", "html_url": "https://github.com/Owner/Tool",
        "description": "A fast thing, per the API", "stargazers_count": 9000,
        "created_at": "2026-08-01T00:00:00Z", "pushed_at": "2026-09-20T00:00:00Z",
        "topics": ["compiler"], "language": "Rust",
    }}
    http = FakeHttp(api)
    items = GitHubTrending().parse(TRENDING_HTML, "daily") * 2   # duplicates across windows
    out = hydrate(http, items, workers=2)
    tool = out[0]
    assert tool.metrics["stars"] == 9000 and tool.created_at is not None
    assert tool.topics == ["compiler"]
    assert tool.metrics["stars_today"] == 1234
    assert tool.metrics["trending_windows"] == ["daily"]
    assert tool.source == "github_trending"
    assert tool.evidence[0].startswith("GitHub trending (daily)")
    # A repo the API could not resolve keeps its scraped row.
    assert out[1].key == "gh:other/gone" and "stars" not in out[1].metrics
    # One call per unique repo, not per sighting.
    assert sorted(http.calls) == ["/repos/other/gone", "/repos/owner/tool"]


# -- whole-word matching ---------------------------------------------------
@pytest.mark.parametrize("term,text,hit", [
    ("rust", "in trust we", False),
    ("rust", "written in rust", True),
    ("agent", "a reagent for", False),
    ("agent", "coding agents", True),
    ("formal verification", "topics: formal-verification", True),
    ("database", "two databases", True),
    ("c++", "modern c++ code", True),
])
def test_term_pattern(term, text, hit):
    assert bool(rank.term_pattern(term).search(text)) is hit


def test_fit_ignores_substrings():
    interests = {"rust": 1.0}
    assert rank.fit(link("https://x.com/a", "Trust and safety"), interests) == 0
    assert rank.fit(link("https://x.com/b", "Written in Rust"), interests) > 0


def test_depth_ignores_substrings():
    # "aircraft" and "jitter" used to count as the raft and jit topics.
    a = repo("x/a", "aircraft jitter draft", lang=None)
    b = repo("x/b", "raft jit", lang=None)
    assert rank.depth(a) < rank.depth(b)


# -- source health -------------------------------------------------------------
def test_source_health_flags_collapsed_sources():
    from radar.collect import source_health
    prev = {"hackernews": 180, "lobsters": 50, "arxiv": 200, "_raw": 1000}
    now_ = {"hackernews": 0, "lobsters": 6, "arxiv": 190, "_raw": 400}
    warnings = source_health(now_, prev)
    assert any("hackernews returned nothing" in w for w in warnings)
    assert any("lobsters returned 6 items, down from 50" in w for w in warnings)
    assert not any("arxiv" in w for w in warnings)
    assert source_health(now_, None) == []            # first run: nothing to compare
