"""The three newer sources, driven by canned API responses. No network."""
from datetime import timedelta

from radar import rank
from radar.models import now
from radar.sources.community import Bluesky, HFPapers
from radar.sources.github import GitHubActivity


class FakeHttp:
    """Answers by URL path / endpoint; records every call."""

    def __init__(self, gh=None, json_=None):
        self._gh = gh or {}
        self._json = json_ or {}
        self.calls = []

    def gh(self, path, **kw):
        self.calls.append(("gh", path, kw.get("params")))
        return self._gh.get(path)

    def json(self, url, **kw):
        params = kw.get("params") or {}
        self.calls.append(("json", url, params))
        return self._json.get((url, params.get("date") or params.get("q")))


def stamp(days_ago: float) -> str:
    return (now() - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


REPO = {"full_name": "alice/newthing", "html_url": "https://github.com/alice/newthing",
        "description": "a new compiler", "stargazers_count": 40, "language": "Rust",
        "created_at": stamp(20), "pushed_at": stamp(1), "topics": ["compiler"], "fork": False}
FORK = {**REPO, "full_name": "alice/llm", "html_url": "https://github.com/alice/llm", "fork": True}


# -- github_activity -----------------------------------------------------------
def test_activity_collects_own_repos_hydrates_and_drops_forks(cfg):
    events = [
        {"type": "PushEvent", "created_at": stamp(1), "repo": {"name": "alice/newthing"}, "payload": {}},
        {"type": "PushEvent", "created_at": stamp(2), "repo": {"name": "alice/newthing"}, "payload": {}},
        {"type": "CreateEvent", "created_at": stamp(3), "repo": {"name": "alice/newthing"},
         "payload": {"ref_type": "repository"}},
        {"type": "CreateEvent", "created_at": stamp(3), "repo": {"name": "alice/branchy"},
         "payload": {"ref_type": "branch"}},                              # a branch, not a project
        {"type": "PushEvent", "created_at": stamp(4), "repo": {"name": "someoneelse/proj"}, "payload": {}},
        {"type": "PushEvent", "created_at": stamp(5), "repo": {"name": "alice/llm"}, "payload": {}},
        {"type": "IssuesEvent", "created_at": stamp(5), "repo": {"name": "alice/other"}, "payload": {}},
        {"type": "PushEvent", "created_at": stamp(90), "repo": {"name": "alice/ancient"}, "payload": {}},
    ]
    http = FakeHttp(gh={"/users/alice/events/public": events, "/users/bob/events/public": [],
                        "/repos/alice/newthing": REPO, "/repos/alice/llm": FORK})
    items = GitHubActivity().fetch(cfg, http)
    assert [i.key for i in items] == ["gh:alice/newthing"]
    it = items[0]
    assert it.metrics["worked_on_by"] == ["alice"] and it.metrics["activity_events"] == 3
    assert it.metrics["stars"] == 40 and it.topics == ["compiler"]       # hydrated
    assert it.evidence[0].startswith("@alice created it, pushed 2x")
    assert rank.watchlist(it) > 0                                        # counts like a star
    # forks are looked up but not returned; the old event stopped the scan
    looked_up = [c[1] for c in http.calls if c[1].startswith("/repos/")]
    assert sorted(looked_up) == ["/repos/alice/llm", "/repos/alice/newthing"]


# -- hf_papers -----------------------------------------------------------------
def test_hf_papers_merge_onto_arxiv_keys_with_upvotes(cfg):
    day = now().date().isoformat()
    listing = [{"paper": {"id": "2609.12345", "title": "A  Great\nPaper", "summary": "s",
                          "upvotes": 42, "publishedAt": "2026-09-20T00:00:00.000Z",
                          "authors": [{"name": "A"}, {"name": "B"}],
                          "githubRepo": "https://github.com/x/y"},
                "numComments": 3},
               {"paper": {"id": "", "title": "no id"}}]
    http = FakeHttp(json_={(HFPapers.URL, day): listing})
    cfg.raw["sources"] = {"hf_papers": {"days": 1}}
    items = HFPapers().fetch(cfg, http)
    assert len(items) == 1
    it = items[0]
    assert it.key == "arxiv:2609.12345" and it.title == "A Great Paper"
    assert it.metrics == {"hf_upvotes": 42, "hf_comments": 3, "hf_github_repo": "https://github.com/x/y"}
    assert it.author == "A, B" and it.created_at is not None


def test_hf_upvotes_count_as_velocity():
    from tests.conftest import link
    it = link("https://arxiv.org/abs/2609.1", "p", source="hf_papers", hf_upvotes=100)
    assert rank.velocity(it) > 0


# -- bluesky -------------------------------------------------------------------
POST = {
    "uri": "at://did:plc:abc/app.bsky.feed.post/3k2f", "likeCount": 30, "repostCount": 4,
    "indexedAt": "2026-09-21T10:00:00.000Z",
    "author": {"handle": "eng.bsky.social"},
    "record": {"text": "check this out <b>now</b>",
               "facets": [{"features": [{"$type": "app.bsky.richtext.facet#link",
                                         "uri": "https://arxiv.org/abs/2609.99999"}]}]},
    "embed": {"$type": "app.bsky.embed.external#view",
              "external": {"uri": "https://github.com/alice/newthing", "title": "newthing"}},
}


def test_bluesky_turns_linked_posts_into_repo_and_paper_items(cfg):
    cfg.raw["sources"] = {"bluesky": {"queries": ["compiler"], "domains": ["github.com"]}}
    http = FakeHttp(json_={(Bluesky.URL, "compiler"): {"posts": [POST, {**POST, "likeCount": 1}]}},
                    gh={"/repos/alice/newthing": REPO})
    items = Bluesky().fetch(cfg, http)
    assert sorted(i.key for i in items) == ["arxiv:2609.99999", "gh:alice/newthing"]
    repo = next(i for i in items if i.key.startswith("gh:"))
    assert repo.metrics["bsky_likes"] == 30 and repo.metrics["stars"] == 40   # hydrated
    assert repo.summary == "a new compiler"                # the repo's own description wins
    assert "check this out now" in repo.evidence[0]        # post text kept, html stripped
    assert "bsky.app/profile/eng.bsky.social/post/3k2f" in repo.evidence[0]
    assert repo.source == "bluesky" and repo.author == "alice"      # author = repo owner once hydrated
