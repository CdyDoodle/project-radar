"""Concept taxonomy.

Text similarity fails at the thing we actually need. Two projects can describe
the same idea with almost no shared vocabulary -- "trillion-parameter model on
one CPU in 8GB" and "frontier MoE on hardware you already own" are the same
project and score ~0.1 cosine. What makes them redundant is the concept.

So classify into coarse themes and let the redundancy check work on those. The
patterns are deliberately broad; this is a bucketing aid for diversification and
faceting, not a claim to precision.
"""
from __future__ import annotations

import re

THEME_PATTERNS: dict[str, str] = {
    "llm-inference": r"inference|quantiz|\bgguf\b|\bggml\b|\bmoe\b|mixture.of.experts|"
                     r"kv.?cache|decoding|llama\.cpp|\bvllm\b|\bollama\b|token/s|"
                     r"tokens per second|prefill|speculative decod|serving (llm|model)|"
                     r"local (llm|model|ai)|on.?device (ai|model|inference)|"
                     r"run .{0,20}(model|llm) (on|locally)|serve .{0,15}model",
    "ai-agents":     r"\bagent\b|\bagents\b|\bmcp\b|tool.?call|tool.?use|autonomous|"
                     r"copilot|coding assistant|workflow orchestr|\bprompt\b",
    "ml-research":   r"transformer|diffusion|reinforcement learning|\brl\b|fine.?tun|"
                     r"pretrain|post.?train|\bsft\b|\brlhf\b|foundation model|embedding|"
                     r"neural network|attention mechanism|\bbenchmark\b|dataset|"
                     r"model (training|weights)",
    "compilers-pl":  r"compiler|parser|\bjit\b|interpreter|type system|type.?check|"
                     r"lexer|\blsp\b|language server|bytecode|codegen|\bast\b|transpil|"
                     r"\bmojo\b|programming language|\bdsl\b|linker|\babi\b|cosmopolitan|"
                     r"binary format",
    "databases":     r"database|\bsql\b|query engine|storage engine|\boltp\b|\bolap\b|"
                     r"\bindex(ing)?\b|key.?value store|transaction|write.?ahead|columnar|"
                     r"graph ?db|\bdbms\b|datastore|vector (db|database|store)",
    "distributed":   r"distributed|consensus|\braft\b|paxos|replicat|cluster|kubernetes|"
                     r"fault.?toler|sharding|gossip|service mesh",
    "os-kernel":     r"\bkernel\b|operating system|\bebpf\b|syscall|hypervisor|unikernel|"
                     r"device driver|bootloader|microkernel|capability.?secure|\bvmm\b|"
                     r"\bmacos\b|\blinux\b|\bwindows\b .{0,12}(driver|native)|firmware",
    "gpu-hpc":       r"\bcuda\b|\bgpu\b|\bsimd\b|\bhpc\b|tensor core|\bptx\b|metal shader|"
                     r"\brocm\b|vectoriz|\bavx|parallel comput|kernel fusion",
    "security":      r"cryptograph|zero.?knowledge|\bzk\b|\btls\b|sandbox|fuzz|exploit|"
                     r"formal verif|vulnerab|malware|reverse engineer|attestation",
    "networking":    r"\bprotocol\b|\bquic\b|peer.?to.?peer|\bp2p\b|\bdns\b|proxy|"
                     r"\brpc\b|packet|load balanc|\bhttp/[23]\b",
    "graphics-media": r"\brender(er|ing)?\b|\bvideo\b|\baudio\b|\bcodec\b|\b3d\b|"
                      r"game engine|shader|raytrac|image processing|\bgraphics\b|"
                      r"\bwgpu\b|\bvulkan\b|\bopengl\b|\bwebgpu\b|\bfont\b|typograph",
    "devtools":      r"\bcli\b|text editor|\bterminal\b|debugger|build system|"
                     r"package manager|linter|formatter|\btui\b|\bide\b|toolchain|"
                     r"\bcargo\b|packaging",
    "web":           r"\breact\b|\bcss\b|browser engine|frontend|\bdom\b|web framework",
    "wasm":          r"webassembly|\bwasm\b|\bwasi\b",
    "data-eng":      r"\betl\b|stream processing|\bkafka\b|dataframe|data lake|\bspark\b|"
                     r"document (conversion|parsing)|\bocr\b|scraper|crawler",
}

_COMPILED = {k: re.compile(v, re.I) for k, v in THEME_PATTERNS.items()}
ALL_THEMES = sorted(THEME_PATTERNS)


def classify(text: str) -> set[str]:
    return {name for name, rx in _COMPILED.items() if rx.search(text or "")}


def of_item(item) -> set[str]:
    """Themes for an Item. README is included but truncated -- long docs
    mention everything and would make every project match every theme."""
    text = " ".join([
        item.title or "", item.summary or "", " ".join(item.topics),
        item.lang or "", (item.readme or "")[:1500],
    ])
    return classify(text)


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


UNCLASSIFIED = "other"

# Order for choosing an item's single filing theme, most specific first.
#
# An explicit list beats anything clever. Picking the *rarest* matching theme
# sounds principled and files an LLM inference server under "graphics-media"
# because its README happens to mention rendering. The generic buckets sit at
# the end so they only win when nothing sharper matched -- half the corpus
# matches "ai-agents", so grouping by it would say nothing.
PRIORITY = [
    "llm-inference", "compilers-pl", "os-kernel", "databases", "distributed",
    "gpu-hpc", "wasm", "security", "networking", "data-eng", "graphics-media",
    "ml-research", "web", "devtools", "ai-agents",
]


def primary(theme_set: set[str]) -> str:
    """The single theme to file an item under when grouping."""
    if not theme_set:
        return UNCLASSIFIED
    for name in PRIORITY:
        if name in theme_set:
            return name
    return sorted(theme_set)[0]
