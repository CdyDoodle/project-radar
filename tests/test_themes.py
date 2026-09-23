"""Regression corpus for the theme and axis classifiers.

Each case is a mistake the patterns made at some point (see README, "Themes"
and "Balance"). If a pattern edit breaks one of these, the edit is wrong.
"""
import pytest

from radar import axis, themes
from tests.conftest import link, repo

PRIMARY = [
    # (repo, description, topics, expected primary theme)
    ("ggml-org/llama.cpp", "LLM inference in C/C++", ["ggml"], "llm-inference"),
    ("vllm-project/vllm", "A high-throughput and memory-efficient inference and "
     "serving engine for LLMs", [], "llm-inference"),
    ("x/cuda-kernels", "Hand-tuned CUDA kernels for attention", ["cuda"], "gpu-hpc"),
    ("x/nes-rs", "NES emulator written in Rust", ["emulator"], "emulation"),
    # A terminal emulator is not emulation, and a multiplexer has no lexer.
    ("wez/wezterm", "A GPU-accelerated cross-platform terminal emulator and "
     "multiplexer", [], "gpu-hpc"),
    ("coder/boo", "A GNU screen style terminal multiplexer", [], "devtools"),
    ("tursodatabase/turso", "SQLite rewrite in Rust", ["database"], "databases"),
    ("x/raftkv", "A distributed key-value store built on Raft", ["raft"], "databases"),
    ("x/ebpf-trace", "eBPF based tracing for Linux", ["ebpf"], "os-kernel"),
    ("x/wasmtime-lite", "A small WebAssembly runtime", ["wasm"], "wasm"),
    ("x/fuzzr", "Coverage-guided fuzzing for Rust", ["fuzzing"], "security"),
    ("x/anydoc", "Convert Word, PowerPoint, PDF to clean Markdown", [], "data-eng"),
    ("x/ros-nav", "Motion planning for ROS2 robots", ["robotics"], "robotics"),
    ("x/protfold", "Protein structure prediction toolkit", ["bioinformatics"],
     "science-compute"),
    ("x/neovim", "Vim-fork focused on extensibility and usability", ["vim", "neovim"],
     "ui-desktop"),
    ("x/verilog-cpu", "A RISC-V CPU in Verilog", ["risc-v"], "embedded-hw"),
    ("x/otel-lite", "OpenTelemetry collector for small deployments", ["observability"],
     "observability"),
    ("x/jj", "A Git-compatible version control system", [], "version-control"),
    ("x/quic-rs", "QUIC protocol implementation", [], "networking"),
    ("x/mcp-gdb", "MCP server that lets Claude drive gdb", ["mcp-server"], "ai-agents"),
    # The README story: its README said "operating system".
    ("audacity/audacity", "Audio Editor", ["audio"], "graphics-media"),
    # googletest was once filed as industry news for the word "google".
    ("google/googletest", "GoogleTest - Google Testing and Mocking Framework", [], "other"),
]


@pytest.mark.parametrize("name,desc,topics,want", PRIMARY, ids=[c[0] for c in PRIMARY])
def test_primary_theme(name, desc, topics, want):
    assert themes.primary(themes.of_item(repo(name, desc, topics=topics))) == want


@pytest.mark.parametrize("title,want", [
    ("Restroom Archive", "discussion"),
    ("Europe's summer drought is so extreme", "discussion"),
    ("Commodore 64 released September 1, 1982", "emulation"),
    ("Apple sued over App Store pricing", "industry"),
])
def test_bare_links(title, want):
    it = link("https://example.com/" + title.replace(" ", "-"), title)
    assert themes.primary(themes.of_item(it)) == want


def test_readme_is_not_read_for_themes():
    it = repo("audacity/audacity", "Audio Editor", topics=["audio"])
    it.readme = "Runs on every operating system. Ships a docker container. Linux kernel 5+."
    assert themes.of_item(it) == {"graphics-media"}


AXIS = [
    ("ggml-org/llama.cpp", "LLM inference in C/C++", ["ggml"], axis.INFRA),
    ("x/agentos", "Give your AI agents an operating system", [], axis.INFRA),
    ("x/mcp-gateway", "An MCP gateway that routes tool calls across servers", [], axis.INFRA),
    # A bare MCP server bridges a domain tool to a model: an application.
    ("x/mcp-gdb", "MCP server that lets Claude drive gdb", ["mcp-server"], axis.APPLICATION),
    ("x/re-agent", "An LLM agent that decompiles binaries", ["reverse-engineering"],
     axis.APPLICATION),
    ("tursodatabase/turso", "SQLite rewrite in Rust", ["database"], axis.NON_AI),
    ("x/anydoc", "Convert Word, PowerPoint, PDF to clean Markdown", [], axis.NON_AI),
]


@pytest.mark.parametrize("name,desc,topics,want", AXIS, ids=[c[0] for c in AXIS])
def test_axis(name, desc, topics, want):
    assert axis.of_item(repo(name, desc, topics=topics)) == want


def test_no_pattern_matches_empty_string():
    assert not themes.classify("")


def test_every_theme_is_in_priority():
    assert set(themes.THEME_PATTERNS) | {themes.DISCUSSION} == set(themes.PRIORITY)
