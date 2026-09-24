"""`radar track`: watching a chosen project's space, with fake HTTP."""
import json
from datetime import timedelta

import requests

from radar import report
from radar import track as tk
from radar.models import now
from tests.conftest import link, repo


class Resp:
    def __init__(self, content: bytes):
        self.content = content
        self.headers = requests.structures.CaseInsensitiveDict()


class FakeHttp:
    token = None

    def __init__(self, gh=None, arxiv=None):
        self.gh_items = gh or {}
        self.arxiv = arxiv or {}
        self.calls = []

    def get(self, url, **kw):
        q = kw["params"].get("q") or kw["params"].get("search_query")
        self.calls.append((url, q))
        if "github" in url:
            return Resp(json.dumps({"items": self.gh_items.get(q, [])}).encode())
        return Resp(self.arxiv.get(q, b"<feed xmlns='http://www.w3.org/2005/Atom'/>"))


def atom(entries):
    body = "".join(
        f"<entry><id>http://arxiv.org/abs/{i}v1</id><title>{t}</title><published>{p}</published></entry>"
        for i, t, p in entries)
    return f"<feed xmlns='http://www.w3.org/2005/Atom'>{body}</feed>".encode()


def iso(days):
    return (now() + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_add_list_stop(store):
    tk.add(store, "expert prefetch", ["expert prefetching", "moe offload"])
    assert [t["name"] for t in tk.tracks(store)] == ["expert prefetch"]
    assert tk.stop(store, "EXPERT PREFETCH")
    assert tk.tracks(store) == [] and tk.find(store, "expert prefetch")


def test_corpus_matches_need_two_phrases_or_every_word_of_one(store):
    with store.tx():
        store.upsert(repo("a/both", "moe offload with expert prefetching"))
        store.upsert(repo("b/one", "some moe offload tool"))              # every word of one
        store.upsert(repo("c/moe-offload", "a thing"))                     # in the name
        store.upsert(repo("d/half", "an moe model"))                       # half a phrase: no
    tk.add(store, "p", ["expert prefetching", "moe offload"])
    t = tk.tracks(store)[0]
    assert tk.match_corpus(store, t) == 3
    keys = {h["key"] for h in tk.tracks(store)[0]["hits"]}
    assert keys == {"gh:a/both", "gh:b/one", "gh:c/moe-offload"}
    assert tk.match_corpus(store, tk.tracks(store)[0]) == 0               # stored once


def test_github_and_arxiv_only_report_new_things(store, cfg, monkeypatch):
    monkeypatch.setattr(tk, "_sleep", lambda s: None)
    tk.add(store, "p", ["expert prefetching"])
    q = "expert prefetching created:>=" + now().strftime("%Y-%m-%d")
    gh = {q: [{"full_name": "x/prefetcher", "html_url": "https://github.com/x/prefetcher",
               "created_at": iso(0), "stargazers_count": 12, "description": "fast"},
              {"full_name": "y/fork", "fork": True}]}
    arxiv = {"all:expert AND all:prefetching": atom([("2609.11111", "New  Prefetching", iso(1)),
                                                 ("2501.00001", "Old paper", iso(-300))])}
    http = FakeHttp(gh, arxiv)
    found = tk.check_all(cfg, store, http)
    assert found == {"p": 2}
    hits = {h["key"]: h for h in tk.tracks(store)[0]["hits"]}
    assert set(hits) == {"gh:x/prefetcher", "arxiv:2609.11111"}
    assert "12 stars" in hits["gh:x/prefetcher"]["reason"]
    assert hits["arxiv:2609.11111"]["title"] == "New Prefetching"


def test_dashboard_shows_tracks(store, cfg):
    s = store.begin_fetch()
    store.upsert(repo("a/moe-offload", "x"), s)
    store.start_run("r1")
    tk.add(store, "My project", ["moe offload"])
    tk.match_corpus(store, tk.tracks(store)[0])
    page = report.build(cfg, store, run_id="r1")[0].read_text(encoding="utf-8")
    assert 'id="tracks"' in page and "My project" in page and "a/moe-offload" in page


def test_long_dive_phrases_match_on_most_of_their_words(store):
    with store.tx():
        store.upsert(repo("a/bench", "benchmark of call graph precision with a SCIP oracle"))
        store.upsert(repo("b/other", "a call to action"))
    tk.add(store, "p", ["SCIP oracle tree-sitter call graph precision recall"])
    assert tk.match_corpus(store, tk.tracks(store)[0]) == 0     # 5 of 7 words, one phrase
    tk.add(store, "q", ["SCIP oracle call graph precision"])
    assert tk.match_corpus(store, tk.find(store, "q")) == 1     # every word of one phrase
    assert {h["key"] for h in tk.find(store, "q")["hits"]} == {"gh:a/bench"}


def test_searches_are_paced(store, cfg, monkeypatch):
    slept = []
    monkeypatch.setattr(tk, "_sleep", slept.append)
    tk.add(store, "p", ["alpha beta", "gamma delta", "epsilon zeta"])
    tk.check_all(cfg, store, FakeHttp())
    assert len(slept) >= 4                                      # between GitHub and arXiv calls
