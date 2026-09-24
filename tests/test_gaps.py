"""`radar gaps`: checking papers for existing code, with fake HTTP."""
import json

import requests

from radar import gaps as gp
from radar import report
from tests.conftest import link


class Resp:
    def __init__(self, items, cached=False):
        rows = [n if isinstance(n, dict) else {"full_name": n, "language": "Python"} for n in items]
        self.content = json.dumps({"items": rows}).encode()
        self.headers = requests.structures.CaseInsensitiveDict(
            {"X-Radar-Cache": "hit"} if cached else {})


class FakeHttp:
    token = None

    def __init__(self, answers):
        self.answers, self.queries = answers, []

    def get(self, url, **kw):
        q = kw["params"]["q"]
        self.queries.append(q)
        return self.answers.get(q)


def paper(n, **metrics):
    return link(f"https://arxiv.org/abs/2609.{n:05d}", f"paper {n}", source="arxiv", **metrics)


def test_check_marks_papers_with_and_without_code(store, cfg, monkeypatch):
    slept = []
    monkeypatch.setattr(gp, "_sleep", slept.append)
    with store.tx():
        store.upsert(paper(1))                                            # no code anywhere
        store.upsert(paper(2))                                            # a repo cites it
        store.upsert(paper(3, hf_github_repo="https://github.com/lab/code"))  # linked on HF
    http = FakeHttp({'"2609.00001" in:readme,description': Resp([]),
                     '"2609.00002" in:readme,description': Resp(["someone/impl"])})
    stats = gp.check(cfg, store, http)
    assert stats == {"checked": 3, "with_code": 2, "no_code": 1, "failed": 0}
    assert len(http.queries) == 2                                         # HF link needs no search
    assert len(slept) == 1                                                # paced between searches
    m2 = json.loads(store.get("arxiv:2609.00002")["metrics"])
    assert m2["impl_count"] == 1 and m2["impl_repos"] == ["someone/impl"]
    assert [r["key"] for r in gp.gaps(store)] == ["arxiv:2609.00001"]


def test_recent_checks_are_not_repeated(store, cfg, monkeypatch):
    monkeypatch.setattr(gp, "_sleep", lambda s: None)
    with store.tx():
        store.upsert(paper(1))
    http = FakeHttp({'"2609.00001" in:readme,description': Resp([])})
    gp.check(cfg, store, http)
    gp.check(cfg, store, http)
    assert len(http.queries) == 1
    gp.check(cfg, store, http, recheck=True)
    assert len(http.queries) == 2


def test_a_failed_search_is_not_recorded_as_no_code(store, cfg, monkeypatch):
    monkeypatch.setattr(gp, "_sleep", lambda s: None)
    with store.tx():
        store.upsert(paper(1))
    stats = gp.check(cfg, store, FakeHttp({}))                            # search returns None
    assert stats["failed"] == 1 and gp.gaps(store) == []
    assert "impl_checked_at" not in json.loads(store.get("arxiv:2609.00001")["metrics"])


def test_a_fresh_fetch_keeps_the_check(store, cfg, monkeypatch):
    monkeypatch.setattr(gp, "_sleep", lambda s: None)
    with store.tx():
        store.upsert(paper(1))
    gp.check(cfg, store, FakeHttp({'"2609.00001" in:readme,description': Resp([])}))
    store.upsert(paper(1))                                                # seen again next run
    assert json.loads(store.get("arxiv:2609.00001")["metrics"])["impl_checked_at"]


def test_dashboard_lane_uses_checked_papers(store, cfg, monkeypatch):
    monkeypatch.setattr(gp, "_sleep", lambda s: None)
    with store.tx():
        store.upsert(paper(1)); store.upsert(paper(2))
    lanes = {l["key"] for l in report._highlights(store, cfg, since=None)}
    assert "papers_unchecked" in lanes                                    # nothing checked yet
    gp.check(cfg, store, FakeHttp({'"2609.00001" in:readme,description': Resp([]),
                                   '"2609.00002" in:readme,description': Resp(["x/y"])}))
    lanes = {l["key"]: l for l in report._highlights(store, cfg, since=None)}
    assert [i["title"] for i in lanes["papers"]["items"]] == ["paper 1"]
    assert "no code found" in lanes["papers"]["items"][0]["reason"]["en"]


def test_paper_lists_and_digests_are_not_implementations(store, cfg, monkeypatch):
    monkeypatch.setattr(gp, "_sleep", lambda s: None)
    with store.tx():
        store.upsert(paper(1))
    noise = [{"full_name": "sukoji/awesome-self-evolving-agents", "language": None},
             {"full_name": "Aaron617/agent-arXiv-daily", "language": "Python"},
             {"full_name": "me/me.github.io", "language": "JavaScript"},
             {"full_name": "x/notes", "description": "my paper reading notes", "language": "Python"},
             {"full_name": "x/slides", "language": "TeX"}]
    gp.check(cfg, store, FakeHttp({'"2609.00001" in:readme,description': Resp(noise)}))
    assert [r["key"] for r in gp.gaps(store)] == ["arxiv:2609.00001"]   # still no real code
    assert gp.is_implementation({"full_name": "lab/flash-thing", "language": "Cuda"})
