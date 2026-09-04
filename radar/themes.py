"""Concept taxonomy.

Text similarity fails at the thing we actually need. Two projects can describe
the same idea with almost no shared vocabulary -- "trillion-parameter model on
one CPU in 8GB" and "frontier MoE on hardware you already own" are the same
project and score ~0.1 cosine. What makes them redundant is the concept.

So classify into coarse themes and let the redundancy check work on those. The
patterns are deliberately broad; this is a bucketing aid for diversification and
faceting, not a claim to precision.

Two rules learned the hard way:

- Match what a thing *is*, not what it mentions. A bare `\\bllm\\b` files agent
  frameworks and a video editor as inference engines, because everything
  mentions LLMs now. Patterns here should name the artifact, not the buzzword.

- Some items have no theme because they aren't projects. A third of the corpus
  arrives from HN/Lobsters as a bare headline -- "Restroom Archive", "Europe's
  summer drought" -- and no regex will ever bucket those. They're caught
  structurally instead, by shape rather than text.
"""
from __future__ import annotations

import re

THEME_PATTERNS: dict[str, str] = {
    # Deliberately NOT a bare "llm" -- that matches everything built this year.
    "llm-inference": r"\bgguf\b|\bggml\b|\bmoe\b|mixture.of.experts|kv.?cache|"
                     r"llama\.cpp|\bvllm\b|\bollama\b|\bllamafile\b|token/s|"
                     r"tokens per second|prefill|speculative decod|quantiz|"
                     r"(llm|model|inference) (server|engine|runtime|serving)|"
                     r"serving (llm|model)|local (llm|model)\b|"
                     r"on.?device (ai|model|inference)|inference (on|for|at)|"
                     r"run(s|ning)? .{0,25}(model|llm)s? (on|locally|in)",
    "ai-agents":     r"\bagent\b|\bagents\b|\bmcp\b|tool.?call|tool.?use|autonomous|"
                     r"copilot|coding assistant|pair programmer|workflow orchestr|"
                     r"\bprompt\b|\bllm\b|\bai-native\b|\bai-powered\b|\bai-enabled\b",
    "ml-research":   r"transformer|diffusion|reinforcement learning|\brl\b|fine.?tun|"
                     r"pretrain|post.?train|\bsft\b|\brlhf\b|foundation model|embedding|"
                     r"neural (network|operator)|attention mechanism|\bbenchmark\b|"
                     r"dataset|model (training|weights)|\binference\b",
    "compilers-pl":  r"compiler|parser|\bjit\b|interpreter|type system|type.?check|"
                     r"lexer|\blsp\b|language server|bytecode|codegen|\bast\b|transpil|"
                     r"\bmojo\b|(programming|functional|systems|scripting) language|"
                     r"\bdsl\b|linker|\babi\b|cosmopolitan|binary format|\bbun\b|"
                     r"formatting library|\bmacro[s]?\b",
    "databases":     r"database|\bsql\b|query engine|storage engine|\boltp\b|\bolap\b|"
                     r"\bindex(ing)?\b|key.?value store|transaction|write.?ahead|columnar|"
                     r"graph ?db|\bdbms\b|datastore|vector (db|database|store)|"
                     r"\bredis\b|memcached|cache server|\bsqlite\b|\bpostgres",
    "distributed":   r"distributed|consensus|\braft\b|paxos|replicat|cluster|kubernetes|"
                     r"fault.?toler|sharding|gossip|service mesh|message queue",
    "concurrency":   r"goroutine|coroutine|async runtime|free.?threaded|\bgil\b|"
                     r"thread pool|lock.?free|\bmutex\b|\batomics?\b|data race|"
                     r"concurren|parallelism|\bio_uring\b|event loop|green thread",
    "os-kernel":     r"\bkernel\b|operating system|\bebpf\b|syscall|hypervisor|unikernel|"
                     r"device driver|bootloader|microkernel|capability.?secure|\bvmm\b|"
                     r"\bmacos\b|\blinux\b|\bwindows\b .{0,12}(driver|native)|"
                     r"privilege escalat|\bposix\b",
    "embedded-hw":   r"embedded|firmware|microcontroller|\bfpga\b|risc-?v|arduino|"
                     r"raspberry pi|hardware (design|accelerat)|\bsilicon\b|\basic\b|"
                     r"verilog|\bvhdl\b|systolic|finfet|\bcircuit\b|\brtos\b|bare.?metal|"
                     r"\bsoc\b|transistor|instruction set|\biot\b|esp32|espressif|"
                     r"\bradio\b|\bsdr\b|\bism band|\bmatter\b protocol|smart home",
    # "orchestrat" alone appears in half the agent-framework blurbs.
    "virtualization": r"\bcontainer\b|\bdocker\b|micro.?vm|container orchestrat|"
                      r"serverless|podman|"
                      r"\boci\b|\bcgroup|namespace isolation|\bkata\b|virtual machine|"
                      r"containerd|\bruntime\b .{0,15}(container|isolation)",
    "gpu-hpc":       r"\bcuda\b|\bgpu\b|\bsimd\b|\bhpc\b|tensor core|\bptx\b|metal shader|"
                     r"\brocm\b|vectoriz|\bavx|parallel comput|kernel fusion",
    "security":      r"cryptograph|zero.?knowledge|\bzk\b|\btls\b|sandbox|fuzz|exploit|"
                     r"formal verif|vulnerab|malware|reverse engineer|attestation|"
                     r"\bhacked?\b|\bbackdoor|encryption|\bcve\b|penetration test",
    "networking":    r"\bprotocol\b|\bquic\b|peer.?to.?peer|\bp2p\b|\bdns\b|proxy|"
                     r"\brpc\b|packet|load balanc|\bhttp/[23]\b|"
                     r"network (traffic|diagnostic|monitor)|sniffer|cell site|"
                     r"traceroute|\bvpn\b|\bfirewall\b|\bsocket[s]?\b",
    "observability": r"observability|telemetry|\btracing\b|opentelemetry|\bprofiler\b|"
                     r"structured (log|event)|\bmetrics\b|distributed trace|"
                     r"\bmonitoring\b|wide events",
    # Never a bare "emulator": every terminal emulator in the feed matched it.
    "emulation":     r"(console|game|system|hardware|cpu|chip|x86|arm|legacy) emulat|"
                     r"emulator for|\bemulation\b|recompil|\bretro\b|game console|"
                     r"playstation|nintendo|game ?boy|\bqemu\b|binary translation|"
                     r"\bdosbox\b|\bnes\b|\bsnes\b|\bn64\b|\bxbox\b|commodore|\bamiga\b",
    "version-control": r"version control|\bvcs\b|git-compatible|\bmonorepo\b|"
                       r"merge conflict|\bdiff\b|\bgit\b .{0,20}(tool|hook|history|workflow)|"
                       r"pull request|\bcommit[s]? \b",
    "science-compute": r"genomic|metagenomic|bioinformatic|molecular|\bprotein\b|"
                       r"chemistry|\bphysics\b|climate|astronom|finite element|"
                       r"monte carlo|\bpolymer\b|numerical (method|solver)|"
                       r"scientific comput|\bsimulation\b|\bdrought\b|\benergy\b",
    "theory":        r"\btheorem\b|\bproof\b|lower bound|upper bound|\bnp-hard\b|"
                     r"combinatori|\btopolog|\balgebra|convex|approximation ratio|"
                     r"complexity (class|bound)|gradient descent|semigroup|"
                     r"probabilistic (programming|semantics)|\blattice\b",
    "data-eng":      r"\betl\b|stream processing|\bkafka\b|dataframe|data lake|\bspark\b|"
                     r"document (conversion|parsing)|\bocr\b|scraper|crawler|"
                     r"convert .{0,40}(pdf|markdown|docx|csv)|\bpdf\b|spreadsheet|"
                     r"structured (extraction|output)|compression|\bzstd\b|\bcodec\b|"
                     r"\barchive\b|\bencoding\b",
    "graphics-media": r"\brender(er|ing)?\b|\bvideo\b|\baudio\b|\b3d\b|game engine|"
                      r"shader|raytrac|image (processing|editing|manipulation)|"
                      r"\bgraphics\b|\bwgpu\b|\bvulkan\b|\bopengl\b|\bwebgpu\b|\bfont\b|"
                      r"typograph|upscal|frame ?gen|\bdlss\b|\bfsr\b|\bxess\b|"
                      r"\bcompositor\b|media player|\bimagemagick\b|screen (capture|mirror)",
    "ui-desktop":    r"\bgui\b|desktop app|native app|immediate mode|window manager|"
                     r"\btauri\b|\belectron\b|menu ?bar|system tray|\bwidget[s]?\b|"
                     r"\bui toolkit\b|\bwayland\b|\bx11\b|keyboard remap|\bvim\b|"
                     r"\bneovim\b|text editor|\beditor\b",
    "wasm":          r"webassembly|\bwasm\b|\bwasi\b",
    "web":           r"\breact\b|\bcss\b|browser( engine)?|frontend|\bdom\b|web framework|"
                     r"headless browser|\bchrome\b|\bfirefox\b|\bextension[s]?\b|"
                     r"static site|\bhtml\b|http server|web app",
    "devtools":      r"\bcli\b|\bterminal\b|debugger|build system|package manager|"
                     r"linter|formatter|\btui\b|\bide\b|toolchain|task runner|"
                     r"\bpager\b|\bshell\b|env var|dotfile|syntax.?high|\bcd command\b|"
                     r"\bcargo\b|packaging|developer (tool|experience)",
    # Not project themes. Industry news, policy and community argument arrive
    # constantly from HN and would otherwise own "other" forever.
    "industry":      r"\bacquisition\b|\bfunding\b|\bstartup\b|\bipo\b|layoff|lawsuit|"
                     r"antitrust|regulat|\bgdpr\b|privacy polic|legislat|lawmaker|"
                     r"\bcourt\b|licens(e|ing) change|\bceo\b|app store|play store|"
                     r"\bban(ned|ning)\b|surveillance|\bpolicy\b|donation|nonprofit|"
                     r"\bpricing\b|subscription|shuts? down|\bunemploy|\bfraud\b|"
                     r"\bfbi\b|(google|apple|meta|amazon) .{0,14}(sued|fined|blocks?|removes?)",
}

_COMPILED = {k: re.compile(v, re.I) for k, v in THEME_PATTERNS.items()}

# Assigned by shape, not by text -- see DISCUSSION below.
DISCUSSION = "discussion"
ALL_THEMES = sorted(list(THEME_PATTERNS) + [DISCUSSION])


def classify(text: str) -> set[str]:
    return {name for name, rx in _COMPILED.items() if rx.search(text or "")}


def of_item(item) -> set[str]:
    """Themes for an Item.

    README is included but truncated -- long docs mention everything and would
    make every project match every theme.
    """
    text = " ".join([
        item.title or "", item.summary or "", " ".join(item.topics),
        item.lang or "", (item.readme or "")[:1500],
    ])
    found = classify(text)
    if found:
        return found
    # Structural fallback. A bare link that matched nothing is a headline with
    # no repo and no paper behind it -- a thing to read, not a thing to build.
    # No pattern list will ever cover those, and calling them "other" hides a
    # third of the feed behind a label that says nothing.
    if item.key.startswith("url:"):
        return {DISCUSSION}
    return found


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
# the end so they only win when nothing sharper matched -- nearly everything
# now mentions agents or LLMs, so filing by that would say nothing.
PRIORITY = [
    # gpu-hpc precedes os-kernel deliberately: a GPU "kernel" is not an OS
    # kernel, and the bare word alone would file every CUDA project under OS.
    "llm-inference", "emulation", "compilers-pl", "gpu-hpc", "os-kernel",
    "embedded-hw", "virtualization", "databases", "distributed", "concurrency",
    "wasm", "security", "networking", "observability", "version-control",
    "science-compute", "theory", "data-eng", "graphics-media", "ui-desktop",
    "ml-research", "web", "devtools", "ai-agents", "industry", DISCUSSION,
]


def primary(theme_set: set[str]) -> str:
    """The single theme to file an item under when grouping."""
    if not theme_set:
        return UNCLASSIFIED
    for name in PRIORITY:
        if name in theme_set:
            return name
    return sorted(theme_set)[0]
