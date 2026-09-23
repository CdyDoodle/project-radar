"""The Claude Code path, driven by a fake CLI. Nothing here spends usage."""
import json
import re
from datetime import timedelta

import pytest

from radar import ideate, rank
from radar.models import now
from tests.test_report import seed

CARD = {"what_it_is": "An inference server.", "technical_depth": 4,
        "depth_reason": "custom kv cache", "frontier": "multi-node",
        "adjacent_ideas": ["a", "b"], "low_substance": False}

BRIEF = {"title": "T", "one_liner": "o", "pitch": "p", "why_now": "w",
         "hard_parts": ["h"], "you_will_learn": ["l"], "milestones": ["Week 1-2: x"],
         "prior_art": ["none"], "kill_criteria": "k", "effort_weeks": 4,
         "difficulty": 3, "novelty": 4, "ai_leverage": "tool",
         "source_urls": ["https://github.com/a/infer"]}


class FakeClaude:
    """Stands in for `_invoke`: answers auth checks and structured calls."""

    def __init__(self, logged_in=True, shallow=(), bad_first=False):
        self.logged_in = logged_in
        self.shallow = set(shallow)
        self.bad_first = bad_first
        self.calls = []

    def __call__(self, args, stdin, timeout):
        self.calls.append((args, stdin))
        if args[1:3] == ["auth", "status"]:
            return json.dumps({"loggedIn": self.logged_in, "authMethod": "claude.ai"})
        if not self.logged_in:
            return json.dumps({"is_error": True, "result": "Not logged in · Please run /login"})
        schema = json.loads(args[args.index("--json-schema") + 1])
        if self.bad_first:
            self.bad_first = False
            return json.dumps({"is_error": False, "structured_output": {"nope": 1}})
        if "cards" in schema["properties"]:
            ids = re.findall(r"ITEM ID: (\w+)", stdin)
            cards = [{**CARD, "id": i,
                      "technical_depth": 1 if i in self.shallow else 4,
                      "low_substance": i in self.shallow} for i in ids]
            return json.dumps({"is_error": False, "structured_output": {"cards": cards}})
        return json.dumps({"is_error": False, "result": "```json\n" + json.dumps(
            {"briefs": [BRIEF, {**BRIEF, "title": "T2"}], "board_summary": "s"}) + "\n```"})


@pytest.fixture
def fake(monkeypatch, cfg):
    f = FakeClaude()
    monkeypatch.setattr(ideate, "_invoke", f)
    monkeypatch.setattr(ideate, "find_claude", lambda cfg: "claude")
    return f


def test_cards_then_briefs(store, cfg, fake):
    seed(store, cfg)
    assert ideate.make_cards(cfg, store) == 3        # brief.cards = 3 in the test config
    carded = [r for r in store.items() if r["card"]]
    assert len(carded) == 3
    assert all(json.loads(r["card"])["carded_at"] for r in carded)
    briefs = ideate.make_briefs(cfg, store, "r1")
    assert [b["title"] for b in briefs] == ["T", "T2"]
    assert store.briefs(run_id="r1")[0]["board_summary"] == "s"


def test_fresh_cards_are_not_redone(store, cfg, fake):
    seed(store, cfg)
    ideate.make_cards(cfg, store)
    first = {r["id"] for r in store.items() if r["card"]}
    n_calls = len(fake.calls)
    ideate.make_cards(cfg, store)                      # tops up from the uncarded rest
    resent = set()
    for args, stdin in fake.calls[n_calls:]:
        resent |= set(re.findall(r"ITEM ID: (\w+)", stdin))
    assert resent and not (resent & first)


def test_expired_cards_are_redone(store, cfg, fake):
    seed(store, cfg)
    ideate.make_cards(cfg, store)
    old = (now() - timedelta(days=90)).isoformat()
    for r in store.items():
        if r["card"]:
            store.set_card(r["id"], {**json.loads(r["card"]), "carded_at": old})
    assert ideate.make_cards(cfg, store) == 3


def test_invalid_answer_is_retried(store, cfg, monkeypatch):
    f = FakeClaude(bad_first=True)
    monkeypatch.setattr(ideate, "_invoke", f)
    monkeypatch.setattr(ideate, "find_claude", lambda cfg: "claude")
    seed(store, cfg)
    assert ideate.make_cards(cfg, store, limit=2) == 2


def test_not_logged_in_is_a_clear_error(store, cfg, monkeypatch):
    monkeypatch.setattr(ideate, "_invoke", FakeClaude(logged_in=False))
    monkeypatch.setattr(ideate, "find_claude", lambda cfg: "claude")
    with pytest.raises(SystemExit, match="/login"):
        ideate.make_cards(cfg, store)


def test_no_tools_and_schema_are_passed(store, cfg, fake):
    seed(store, cfg)
    ideate.make_cards(cfg, store, limit=1)
    args = next(a for a, _ in fake.calls if "-p" in a)
    assert args[args.index("--tools") + 1] == ""
    schema = json.loads(args[args.index("--json-schema") + 1])
    assert "$defs" not in json.dumps(schema) and "$ref" not in json.dumps(schema)
    assert schema["additionalProperties"] is False


def test_chinese_language_rule_reaches_the_prompt(store, cfg, fake):
    cfg.raw["brief"]["language"] = "zh-CN"
    seed(store, cfg)
    ideate.make_cards(cfg, store, limit=1)
    args = next(a for a, _ in fake.calls if "-p" in a)
    assert "简体中文" in args[args.index("--system-prompt") + 1]


def test_finds_the_desktop_apps_packaged_copy(tmp_path, monkeypatch, cfg):
    # A normal terminal sees the MSIX package folder, not the redirected APPDATA.
    pkg = tmp_path / "Local" / "Packages" / "Claude_abc123" / "LocalCache" / "Roaming"
    for ver in ("2.1.9", "2.1.280"):
        exe = pkg / "Claude" / "claude-code" / ver / "claude.exe"
        exe.parent.mkdir(parents=True)
        exe.write_bytes(b"")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming-empty"))
    monkeypatch.setattr(ideate.shutil, "which", lambda name: None)
    assert ideate.find_claude(cfg).endswith("2.1.280" + __import__("os").sep + "claude.exe")


def test_api_key_is_withheld(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("CLAUDECODE", "1")
    env = ideate._child_env()
    assert "ANTHROPIC_API_KEY" not in env and "CLAUDECODE" not in env


def test_card_penalties_reach_the_score(store, cfg, monkeypatch):
    seed(store, cfg)
    thin = store.get("gh:b/db")["id"]
    f = FakeClaude(shallow={thin})
    monkeypatch.setattr(ideate, "_invoke", f)
    monkeypatch.setattr(ideate, "find_claude", lambda cfg: "claude")
    ideate.make_cards(cfg, store, limit=6)
    rank.rank_all(store, cfg)
    pens = json.loads(store.get("gh:b/db")["breakdown"])["penalties"]
    assert pens["low_substance"] == -2.0 and pens["shallow"] == -0.8
    ok = json.loads(store.get("gh:a/infer")["breakdown"])["penalties"]
    assert "low_substance" not in ok and "shallow" not in ok
