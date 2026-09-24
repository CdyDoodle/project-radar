"""Chinese content through the translation layer, with a fake Claude Code."""
import json
import re

import pytest

from radar import ideate, report
from radar import translate as tl
from tests.test_report import seed

BRIEF = {"title": "Expert prefetching for MoE decode", "one_liner": "Predict experts ahead.",
         "pitch": "A small predictor hides storage latency.", "why_now": "colibri exists.",
         "hard_parts": ["Predictor recall at lookahead 3"], "you_will_learn": ["I/O scheduling"],
         "milestones": ["Week 1-2: traces"], "prior_art": ["colibri"], "kill_criteria": "No gain.",
         "effort_weeks": 8, "difficulty": 4, "novelty": 3, "ai_leverage": "subject",
         "source_urls": [], "board_summary": "The board points at memory hierarchies."}


class FakeClaude:
    def __init__(self):
        self.prompts = []

    def __call__(self, args, stdin, timeout):
        if args[1:3] == ["auth", "status"]:
            return json.dumps({"loggedIn": True, "authMethod": "claude.ai"})
        self.prompts.append(stdin)
        items = [{"id": i, "zh": "中文：" + text}
                 for i, text in re.findall(r"^\[(t\d+)\] (.*)$", stdin, re.M)]
        return json.dumps({"is_error": False, "structured_output": {"items": items}})


@pytest.fixture
def fake(monkeypatch):
    f = FakeClaude()
    monkeypatch.setattr(ideate, "_invoke", f)
    monkeypatch.setattr(ideate, "find_claude", lambda cfg: "claude")
    return f


@pytest.mark.parametrize("text,ok", [
    ("A columnar database engine", True),
    ("a/infer", False),                       # a repo name
    ("https://example.com/x", False),
    ("已经是中文的描述文字", False),
    ("ok", False),
    ("CUDA", False),                          # one word: a name, not prose
])
def test_translatable(text, ok):
    assert tl.translatable(text) is ok


def test_page_content_is_translated_once_and_kept(store, cfg, fake):
    seed(store, cfg)
    store.add_brief("r1-00", "r1", BRIEF)
    todo = tl.missing(cfg, store)
    assert "A columnar database engine" in todo            # feed description
    assert "Restroom Archive" in todo                       # headline title
    assert "a/infer" not in todo                            # repo names stay
    assert "A small predictor hides storage latency." in todo
    st = tl.translate_missing(cfg, store)
    assert st["translated"] == st["needed"] == len(todo) and st["failed"] == 0
    assert tl.missing(cfg, store) == []                     # stored: nothing left
    n = len(fake.prompts)
    tl.translate_missing(cfg, store)
    assert len(fake.prompts) == n                           # a second pass sends nothing

    cfg.raw["report"] = {"language": "zh-CN"}
    page = report.build(cfg, store, run_id="r1")[0].read_text(encoding="utf-8")
    assert 'data-zh="中文：A columnar database engine"' in page
    assert '>中文：A small predictor hides storage latency.<' in page   # shown by default
    assert 'data-en="A small predictor hides storage latency."' in page  # English kept
    assert "中文：restroom archive" in page                 # searchable in Chinese
    md = (cfg.out_dir / next(p.name for p in cfg.out_dir.glob("digest-*.md"))).read_text(encoding="utf-8")
    assert "中文：A small predictor hides storage latency." in md


def test_untranslated_content_falls_back_to_english(store, cfg):
    seed(store, cfg)
    cfg.raw["report"] = {"language": "zh-CN"}
    page = report.build(cfg, store, run_id="r1")[0].read_text(encoding="utf-8")
    assert 'data-zh="A columnar database engine"' in page   # no translation: original


def test_a_failed_batch_leaves_the_rest(store, cfg, monkeypatch):
    calls = {"n": 0}
    good = FakeClaude()

    def flaky(args, stdin, timeout):
        if args[1:3] != ["auth", "status"]:
            calls["n"] += 1
            if calls["n"] <= 2:                              # first batch fails twice
                return json.dumps({"is_error": True, "result": "boom"})
        return good(args, stdin, timeout)

    monkeypatch.setattr(ideate, "_invoke", flaky)
    monkeypatch.setattr(ideate, "find_claude", lambda cfg: "claude")
    cfg.raw["translate"] = {"per_call": 2}
    seed(store, cfg)
    st = tl.translate_missing(cfg, store)
    assert 0 < st["translated"] < st["needed"] and st["failed"] == st["needed"] - st["translated"]
    assert len(tl.missing(cfg, store)) == st["failed"]      # the rest is retried next run


def test_ids_left_out_of_an_answer_are_asked_for_again(store, cfg, monkeypatch):
    good, calls = FakeClaude(), {"n": 0}

    def drops_half(args, stdin, timeout):
        out = good(args, stdin, timeout)
        if args[1:3] == ["auth", "status"]:
            return out
        calls["n"] += 1
        data = json.loads(out)
        if calls["n"] == 1:                                  # first answer: half the ids
            items = data["structured_output"]["items"]
            data["structured_output"]["items"] = items[: len(items) // 2]
        return json.dumps(data)

    monkeypatch.setattr(ideate, "_invoke", drops_half)
    monkeypatch.setattr(ideate, "find_claude", lambda cfg: "claude")
    seed(store, cfg)
    st = tl.translate_missing(cfg, store)
    assert st["failed"] == 0 and calls["n"] == 2 and tl.missing(cfg, store) == []
