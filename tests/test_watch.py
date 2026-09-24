"""`radar watch --suggest` and `--add`, with fake GitHub."""
import tomllib
from datetime import timedelta

from radar import watch as wt
from radar.models import now
from tests.conftest import repo


def star(name, days_ago=3):
    return {"starred_at": (now() - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "repo": {"full_name": name}}


class FakeHttp:
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def gh(self, path, **kw):
        self.calls.append(path)
        page = (kw.get("params") or {}).get("page", 1)
        return self.routes.get((path, page), self.routes.get(path))


def test_suggests_people_the_watchlist_follows_and_whose_stars_overlap(store, cfg):
    # the corpus knows alice starred a/infer
    store.upsert(repo("a/infer", source="github_starred", starred_by=["alice"]))
    routes = {
        ("/users/alice/following", 1): [{"login": "carol", "type": "User"},
                                        {"login": "dave", "type": "User"},
                                        {"login": "bob", "type": "User"},        # already watched
                                        {"login": "someorg", "type": "Organization"}],
        ("/users/bob/following", 1): [{"login": "carol", "type": "User"},
                                      {"login": "dave", "type": "User"},
                                      {"login": "erin", "type": "User"}],      # only one watcher
        "/users/carol/starred": [star("a/infer"), star("old/thing", days_ago=400)],
        "/users/dave/starred": [star("x/unrelated")],
        "/users/carol": {"name": "Carol C", "bio": "compilers", "followers": 900},
        "/users/dave": {"name": "", "bio": "", "followers": 10},
    }
    cands = wt.suggest(cfg, store, FakeHttp(routes))
    assert [c.login for c in cands] == ["carol", "dave"]      # erin: one watcher; bob: watched
    carol = cands[0]
    assert carol.followed_by == ["alice", "bob"] and carol.overlap == ["a/infer"]
    assert carol.recent_stars == 1 and carol.bio == "compilers"   # old star outside window


def test_add_writes_to_config_and_skips_existing(cfg, home):
    changes = wt.add(cfg, ["carol", "Bob"])
    assert len(changes) == 1
    users = tomllib.loads((home / "config.toml").read_text(encoding="utf-8"))["sources"]["github_starred"]["users"]
    assert users == ["alice", "bob", "carol"]


def test_single_follows_count_only_with_real_star_overlap(store, cfg):
    for n in ("a/one", "a/two", "a/three"):
        store.upsert(repo(n, source="github_starred", starred_by=["alice"]))
    routes = {
        ("/users/alice/following", 1): [{"login": "fan", "type": "User"},
                                        {"login": "stranger", "type": "User"}],
        ("/users/bob/following", 1): [],
        "/users/fan/starred": [star("a/one"), star("a/two"), star("z/z")],
        "/users/stranger/starred": [star("a/one")],             # one overlap is not enough
    }
    cands = wt.suggest(cfg, store, FakeHttp(routes))
    assert [c.login for c in cands] == ["fan"] and cands[0].overlap == ["a/one", "a/two"]
