"""`radar tune` and the comment-preserving config editor."""
import json
import tomllib

from radar import configedit, tune
from radar.models import Item


def fake_feedback(store, rows):
    """rows: (key, saved?, components dict, topics, text)."""
    for key, saved, comps, topics, text in rows:
        store.upsert(Item(key=key, url="https://x/" + key, title=key, source="t",
                          summary=text, topics=topics))
        bd = {"components": comps}
        store.conn.execute("UPDATE items SET breakdown = ? WHERE key = ?", (json.dumps(bd), key))
        store.conn.commit()
        store.set_status(key, "saved" if saved else "dismissed")


def taste(store, n=8):
    """A user who loves watchlist picks and ignores raw velocity."""
    rows = []
    for i in range(n):
        rows.append((f"gh:good/{i}", True,
                     {"velocity": 0.2, "watchlist": 0.9, "fit": 0.5, "corroboration": 0,
                      "freshness": 0.5, "depth": 0.6},
                     ["compiler", "type-theory"], "a compiler with dependent types"))
        rows.append((f"gh:bad/{i}", False,
                     {"velocity": 0.95, "watchlist": 0.0, "fit": 0.6, "corroboration": 0,
                      "freshness": 0.5, "depth": 0.5},
                     ["chatbot"], "an agent chatbot wrapper"))
    fake_feedback(store, rows)


def test_not_enough_feedback(store, cfg):
    fake_feedback(store, [("gh:a/b", True, {"velocity": 1}, [], "")])
    prop = tune.propose(cfg, store)
    assert not prop.enough and prop.n_saved == 1 and not prop.proposed


def test_learns_to_trust_the_watchlist_over_velocity(store, cfg):
    taste(store)
    prop = tune.propose(cfg, store)
    assert prop.enough
    assert prop.proposed["watchlist"] > prop.current["watchlist"]
    assert prop.proposed["velocity"] < prop.current["velocity"]
    assert prop.acc_after >= prop.acc_before and prop.loo_after >= 0.9
    assert all(v >= 0.05 for v in prop.proposed.values())       # never negative


def test_prior_keeps_small_data_from_swinging_weights(store, cfg):
    taste(store, n=5)
    cautious = tune.propose(cfg, store, lam=20)
    bold = tune.propose(cfg, store, lam=0.2)
    drift = lambda p: sum(abs(p.proposed[c] - p.current[c]) for c in tune.COMPONENTS)
    assert drift(cautious) < drift(bold)


def test_interest_suggestions(store, cfg):
    taste(store)
    prop = tune.propose(cfg, store)
    assert ("compiler", 8, 0) in prop.raise_terms
    assert any(t == "agent" for t, _, _ in prop.lower_terms)
    assert ("type theory", 8) in prop.add_terms


def test_apply_edits_config_and_keeps_comments(store, cfg, home):
    path = home / "config.toml"
    path.write_text(path.read_text(encoding="utf-8").replace(
        "[rank]", "[rank.weights]\n# keep me\nvelocity = 1.0\nwatchlist = 1.8\n\n[rank]"),
        encoding="utf-8")
    from radar import config
    cfg = config.load(home)
    taste(store)
    changes = tune.apply(cfg, tune.propose(cfg, store))
    text = path.read_text(encoding="utf-8")
    assert "# keep me" in text and changes
    data = tomllib.loads(text)
    assert data["rank"]["weights"]["watchlist"] > 1.8
    assert data["interests"]["type theory"] == 0.6
    assert data["interests"]["compiler"] > 1.0


def test_configedit_array_append(home):
    path = home / "config.toml"
    added = configedit.append_to_array(path, "sources.github_starred", "users", ["carol", "alice"])
    assert added == ["[sources.github_starred] users: added carol"]
    assert tomllib.loads(path.read_text(encoding="utf-8"))["sources"]["github_starred"]["users"] \
        == ["alice", "bob", "carol"]
