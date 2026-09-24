"""`radar dive` with a fake Claude Code and fake HTTP. Nothing spends usage."""
import json

import pytest

from radar import dive as dv
from radar import ideate, report
from tests.test_ideate import BRIEF
from tests.test_report import seed

DIVE = {
    "verdict": "pivot", "verdict_reason": "Close work exists.",
    "novelty_revised": 2, "novelty_reason": "Two projects already do most of it.",
    "prior_art": [
        {"name": "real", "url": "https://github.com/a/infer", "closeness": "overlapping", "note": "n"},
        {"name": "invented", "url": "https://github.com/nobody/made-up", "closeness": "same", "note": "n"},
    ],
    "feasibility": "yes", "risks": ["r1", "r2"], "needs": ["a GPU"],
    "two_week_experiment": {"goal": "g", "steps": ["s1", "s2", "s3"], "success_metric": "m",
                            "kill_threshold": "k", "time_needed": "2 weeks"},
    "pivot_ideas": ["p"], "search_terms": ["kv cache offload", "expert streaming"],
    "searched": ["github: expert streaming"],
}


class FakeHttp:
    def gh(self, path, **kw):
        return {"full_name": "a/infer", "stargazers_count": 1234} if path == "/repos/a/infer" else None

    def get(self, url, **kw):
        return None


@pytest.fixture
def seeded(store, cfg, monkeypatch):
    calls = []

    def invoke(args, stdin, timeout):
        calls.append(args)
        if args[1:3] == ["auth", "status"]:
            return json.dumps({"loggedIn": True, "authMethod": "claude.ai"})
        return json.dumps({"is_error": False, "structured_output": DIVE})

    monkeypatch.setattr(ideate, "_invoke", invoke)
    monkeypatch.setattr(ideate, "find_claude", lambda cfg: "claude")
    seed(store, cfg)
    store.add_brief("r1-00", "r1", {**BRIEF, "title": "First"})
    store.add_brief("r1-01", "r1", {**BRIEF, "title": "Second"})
    return calls


def test_dive_uses_web_tools_and_verifies_links(store, cfg, seeded):
    brief = dv.resolve_brief(store, "2")
    assert brief["title"] == "Second"
    rep = dv.dive(cfg, store, brief, http=FakeHttp())
    args = next(a for a in seeded if "-p" in a)
    assert args[args.index("--tools") + 1] == "WebSearch,WebFetch"
    assert args[args.index("--allowedTools") + 1: args.index("--allowedTools") + 3] == ["WebSearch", "WebFetch"]
    real, invented = rep["prior_art"]
    assert real["verified"] and real["stars"] == 1234
    assert not invented["verified"]                  # a made-up link is caught
    assert rep["links_unverified"] == 1
    assert store.dives_for(["r1-01"])["r1-01"]["verdict"] == "pivot"


def test_card_and_brief_passes_still_get_no_tools(store, cfg, seeded):
    ideate.make_cards(cfg, store, limit=1)
    args = next(a for a in seeded if "-p" in a)
    assert args[args.index("--tools") + 1] == "" and "--allowedTools" not in args


def test_dive_shows_under_its_brief(store, cfg, seeded):
    dv.dive(cfg, store, dv.resolve_brief(store, "1"), http=FakeHttp())
    page = report.build(cfg, store, run_id="r1")[0].read_text(encoding="utf-8")
    assert 'class="verdict v-pivot"' in page and "nobody/made-up" in page
    assert 'data-zh="链接失效"' in page
    assert "radar dive 2" in page                    # the unchecked one says how to check it


def test_unknown_brief(store, cfg, seeded):
    assert dv.resolve_brief(store, "9") is None and dv.resolve_brief(store, "nope") is None


# -- feedback log ----------------------------------------------------------------
def test_verdicts_are_logged_with_the_score_they_had(store, cfg):
    seed(store, cfg)
    before = store.get("gh:b/db")["score"]
    store.set_status("gh:b/db", "saved")
    store.set_status("gh:a/infer", "dismissed")
    store.set_status("gh:a/infer", "new")            # undo
    fb = store.feedback()
    assert [(r["key"], r["action"]) for r in fb] == [("gh:b/db", "saved")]
    assert fb[0]["score"] == before and json.loads(fb[0]["breakdown"])["components"]
