"""The Hugging Face source, driven by canned API answers. No network."""
from radar import rank, themes
from radar.sources import huggingface as hf

CARD = """---
license: apache-2.0
tags: [decision-model]
---
# Kev 0.8B

[![badge](https://img.shields.io/x)](https://x)

Kev is a small decision model you can fine-tune and run on a laptop. It answers
typed questions with calibrated probabilities instead of generating text.

## Usage
"""

TINY = {"id": "alice/tiny-tts", "author": "alice", "likes": 300, "trendingScore": 90,
        "downloads": 5000, "pipeline_tag": "text-to-speech", "tags": ["onnx", "license:mit",
        "region:us", "base_model:finetune:x/y"], "safetensors": {"total": 4_500_000},
        "createdAt": "2026-11-10T00:00:00.000Z"}
KEV = {"id": "jaredpalmer/kev-0.8b", "author": "jaredpalmer", "likes": 180, "trendingScore": 40,
       "downloads": 10_000, "pipeline_tag": "text-classification", "library_name": "peft",
       "tags": ["decision-model"], "safetensors": {"total": 800_000_000}}
BIG = {"id": "BigLab/Huge-70B", "author": "BigLab", "likes": 900, "trendingScore": 600,
       "pipeline_tag": "text-generation", "safetensors": {"total": 70_000_000_000}}
SHELL = {"id": "farm/h3", "author": "farm", "likes": 450, "trendingScore": 370, "tags": ["region:us"]}
QUIET = {"id": "bob/meh", "author": "bob", "likes": 3, "pipeline_tag": "text-generation"}
SPACE = {"id": "alice/voice-demo", "author": "alice", "likes": 120, "trendingScore": 30,
         "sdk": "gradio", "cardData": {"title": "Voice Demo",
                                       "short_description": "Clone a voice in your browser"}}


class Http:
    def __init__(self):
        self.calls = []

    def json(self, url, params=None, **kw):
        self.calls.append((url, params))
        if url.endswith("/spaces"):
            return [SPACE]
        if "num_parameters" in (params or {}):
            return [TINY, KEV]
        return [BIG, SHELL, QUIET, KEV]

    def get(self, url, **kw):
        class R:
            text = CARD
        if url.endswith("kev-0.8b/raw/main/README.md"):
            return R()
        if "/api/users/" in url:               # people have a user overview
            return R() if any(n in url for n in ("alice", "jaredpalmer")) else None
        return None


def fetch(cfg):
    cfg.raw["sources"] = {"hf_models": {"trending": 4, "small": 2, "spaces": 1}}
    http = Http()
    return {i.title: i for i in hf.HFModels().fetch(cfg, http)}, http


def test_listings_are_merged_and_filtered(cfg):
    items, http = fetch(cfg)
    assert set(items) == {"BigLab/Huge-70B", "alice/tiny-tts", "jaredpalmer/kev-0.8b",
                          "Voice Demo (alice/voice-demo)"}             # no shell, no 3-like model
    small = next(p for u, p in http.calls if "num_parameters" in (p or {}))
    assert small["num_parameters"] == "min:0,max:3B"


def test_model_items_carry_size_card_and_owner(cfg):
    items, _ = fetch(cfg)
    kev = items["jaredpalmer/kev-0.8b"]
    assert kev.key == "url:huggingface.co/jaredpalmer/kev-0.8b"
    assert kev.summary.startswith("800M-parameter text classification model. Kev is a small")
    assert "badge" not in kev.summary and kev.readme.startswith("---")
    assert kev.metrics["params"] == 800_000_000 and kev.metrics["owner_type"] == "User"
    assert items["BigLab/Huge-70B"].metrics["owner_type"] == "Organization"
    tiny = items["alice/tiny-tts"]
    assert tiny.topics == ["text-to-speech", "onnx"]                   # licence, region, base dropped
    assert tiny.summary == "4.5M-parameter text to speech model."      # no card: size and task


def test_models_are_things_not_discussion(cfg):
    items, _ = fetch(cfg)
    tiny = items["alice/tiny-tts"]
    assert "small-models" in themes.of_item(tiny)                      # "4.5M-parameter"
    assert "small-models" not in themes.of_item(items["BigLab/Huge-70B"])
    assert "chatter" not in rank.penalties(tiny, cfg)
    assert rank.indie(tiny) == 1.0 and rank.velocity(tiny) > 0


def test_space_item(cfg):
    items, _ = fetch(cfg)
    sp = items["Voice Demo (alice/voice-demo)"]
    assert sp.url == "https://huggingface.co/spaces/alice/voice-demo"
    assert sp.summary == "Clone a voice in your browser" and sp.metrics["hf_kind"] == "space"


def test_size_helpers():
    assert hf.parse_size("3B") == 3_000_000_000 and hf.parse_size("500M") == 500_000_000
    assert hf.size_label(4_500_000) == "4.5M" and hf.size_label(1_700_000_000) == "1.7B"
    assert hf.size_label(3_000_000_000) == "3B"
    assert hf.card_description("---\na: b\n---\n# T\n\nshort\n") == ""


def test_a_model_with_its_own_repo_merges_onto_it(cfg):
    card = CARD + "\nCode: https://github.com/jaredpalmer/kev-0.8b\n"
    item = hf.HFModels()._model_item(KEV, card)
    assert item.key == "gh:jaredpalmer/kev-0.8b"
    assert item.metrics["hf_url"] == "https://huggingface.co/jaredpalmer/kev-0.8b"
    other = hf.HFModels()._model_item(KEV, CARD + "\nSee https://github.com/jaredpalmer/kev-0.8b-old\n")
    assert other.key.startswith("url:huggingface.co/")              # a different repo


def test_a_big_model_is_not_small_whatever_its_card_says():
    big = hf.HFModels()._model_item(BIG, "A small model for everyone. " * 3)
    assert "small-models" not in themes.of_item(big)
    assert hf.card_description("Official site&nbsp;| Docs | Discord\n\n" + "Real words here. " * 5)\
        .startswith("Real words here.")
