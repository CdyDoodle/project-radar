"""Concept taxonomy.

Text similarity fails at the thing we actually need. Two projects can describe
the same idea with almost no shared vocabulary -- "trillion-parameter model on
one CPU in 8GB" and "frontier MoE on hardware you already own" are the same
project and score ~0.1 cosine. What makes them redundant is the concept.

So classify into coarse themes and let the redundancy check work on those. This
is a bucketing aid for diversification and faceting, not a claim to precision.

Three rules, each learned by auditing what the patterns actually caught:

- Match what a thing *is*, not what it mentions. A bare `\\bllm\\b` files agent
  frameworks and a video editor as inference engines, because everything
  mentions LLMs now. Bare `\\bsilicon\\b` catches "Apple Silicon"; bare
  `\\bprotocol\\b` catches "Model Context Protocol"; bare `\\blinux\\b` catches
  every project that merely runs on it. Prefer two-word phrases naming the
  artifact over single common words.

- Coverage is not precision, and improving the first often wrecks the second.
  Measure both: percentage unclassified AND average tags per item.

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
                     r"serving (llm|model)|local (llm|model|ai)\b|"
                     r"on.?device (ai|model|inference)|inference (on|for|at)|"
                     r"serves? .{0,20}(llm|model)|"
                     r"run(s|ning)? .{0,25}(model|llm)s? (on|locally|in)",
    # Bare \bagent\b / \bllm\b / \bprompt\b tagged a third of the corpus, because
    # everything built this year mentions them. Require the agent to be the
    # artifact rather than a passing reference.
    "ai-agents":     r"\bagentic\b|agents? (framework|harness|swarm|fleet|runtime|"
                     r"sdk|os|operating system|environment|behavio|infra|"
                     r"infrastructure|memory|orchestration)|"
                     r"(ai|llm|coding|autonomous|research|multi.?|self.?improving|"
                     r"sub|worker|browser|voice) agents?\b|"
                     r"\bautonomous ai\b|for (ai )?agents\b|agents? (that|which|to)\b|"
                     r"\bmcp\b|model context protocol|tool.?call|copilot|"
                     r"pair programmer|coding assistant|workflow orchestr|"
                     r"\bai-native\b|\bai-powered\b|\bai-enabled\b",
    "ml-research":   r"transformer|diffusion|reinforcement learning|\brl\b|fine.?tun|"
                     r"pretrain|post.?train|\bsft\b|\brlhf\b|foundation model|embedding|"
                     r"neural (network|operator)|attention mechanism|\bbenchmark\b|"
                     r"training (data|dataset)|dataset for|model (training|weights)",
    "compilers-pl":  r"compiler|parser|\bjit\b|interpreter|type system|type.?check|"
                     r"lexer|\blsp\b|language server|bytecode|codegen|\bast\b|transpil|"
                     r"\bmojo\b|(programming|functional|systems|scripting) language|"
                     r"\bdsl\b|linker|\babi\b|cosmopolitan|binary format|\bbun\b|"
                     r"formatting library|\bmacros?\b",
    "databases":     r"database|\bsql\b|query engine|storage engine|\boltp\b|\bolap\b|"
                     r"\bindexing\b|key.?value store|write.?ahead|columnar|"
                     r"graph ?db|\bdbms\b|datastore|vector (db|database|store)|"
                     r"\bredis\b|memcached|cache server|\bsqlite\b|\bpostgres",
    "distributed":   r"distributed|consensus|\braft\b|paxos|replicat|cluster|kubernetes|"
                     r"fault.?toler|sharding|gossip|service mesh|message queue",
    "concurrency":   r"goroutine|coroutine|async runtime|free.?threaded|\bgil\b|"
                     r"thread pool|lock.?free|\bmutex\b|data race|"
                     r"concurren|parallelism|\bio_uring\b|event loop|green thread",
    # A bare \bkernel\b tagged every GPU paper; a bare \blinux\b or \bmacos\b
    # tagged every project that merely runs there. Platform mentions, not OS work.
    "os-kernel":     r"linux kernel|kernel (module|space|driver|panic|bypass)|"
                     r"operating system|\bebpf\b|syscall|hypervisor|unikernel|"
                     r"device driver|bootloader|microkernel|capability.?secure|\bvmm\b|"
                     r"privilege escalat|\bposix\b",
    # NOT a bare \bsilicon\b -- that is "Apple Silicon" on half the Mac projects.
    "embedded-hw":   r"embedded|firmware|microcontroller|\bfpga\b|risc-?v|arduino|"
                     r"raspberry pi|hardware (design|accelerat)|custom silicon|"
                     r"silicon design|\basic\b|verilog|\bvhdl\b|systolic|finfet|"
                     r"\bcircuit\b|\brtos\b|bare.?metal|transistor|instruction set|"
                     r"\biot\b|esp32|espressif|\bsdr\b|\bism band|smart home",
    # "orchestrat" alone appears in half the agent-framework blurbs.
    "virtualization": r"\bcontainer\b|\bdocker\b|micro.?vm|container orchestrat|"
                      r"serverless|podman|\boci\b|\bcgroup|namespace isolation|"
                      r"\bkata\b|virtual machine|containerd",
    "gpu-hpc":       r"\bcuda\b|\bgpu\b|\bsimd\b|\bhpc\b|tensor core|\bptx\b|metal shader|"
                     r"\brocm\b|vectoriz|\bavx|parallel comput|kernel fusion",
    "security":      r"cryptograph|zero.?knowledge|\bzk\b|\btls\b|sandbox|fuzz|exploit|"
                     r"formal verif|vulnerab|malware|reverse engineer|attestation|"
                     r"\bhacked?\b|\bbackdoor|encryption|\bcve\b|penetration test",
    # NOT a bare \bprotocol\b -- that is "Model Context Protocol" on every MCP repo.
    "networking":    r"network protocol|wire protocol|"
                     r"protocol (stack|implementation|parser)|\bquic\b|peer.?to.?peer|"
                     r"\bp2p\b|\bdns\b|proxy|\brpc\b|packet|load balanc|\bhttp/[23]\b|"
                     r"network (traffic|diagnostic|monitor)|sniffer|cell site|"
                     r"traceroute|\bvpn\b|\bfirewall\b|\bsockets?\b",
    "observability": r"observability|telemetry|\btracing\b|opentelemetry|\bprofiler\b|"
                     r"structured (log|event)|\bmetrics\b|distributed trace|"
                     r"\bmonitoring\b|wide events",
    # Never a bare "emulator": every terminal emulator in the feed matched it.
    "emulation":     r"(console|game|system|hardware|cpu|chip|x86|arm|legacy) emulat|"
                     r"emulator for|\bemulation\b|recompil|\bretro\b|game console|"
                     r"playstation|nintendo|game ?boy|\bqemu\b|binary translation|"
                     r"\bdosbox\b|\bnes\b|\bsnes\b|\bn64\b|\bxbox\b|commodore|\bamiga\b",
    # NOT a bare \bdiff\b -- diffs appear in every changelog.
    "version-control": r"version control|\bvcs\b|git-compatible|\bmonorepo\b|"
                       r"merge conflict|diff (tool|viewer|algorithm|engine)|"
                       r"\bgit\b .{0,20}(tool|hook|history|workflow)|pull request|"
                       r"commit (message|history|gate|hook)",
    # NOT a bare \benergy\b -- every hardware paper measures energy efficiency.
    "science-compute": r"genomic|metagenomic|bioinformatic|molecular|\bprotein\b|"
                       r"chemistry|\bphysics\b|climate|astronom|finite element|"
                       r"monte carlo|\bpolymer\b|numerical (method|solver)|"
                       r"scientific comput|\bsimulation\b",
    # A topic:robotics query existed with no matching theme, so every robotics
    # repo fell straight into "other".
    "robotics":      r"\brobot(ic|ics|s)?\b|\bslam\b|\bros2?\b|manipulator|\bdrone\b|"
                     r"autonomous (vehicle|driving|navigation)|\blidar\b|"
                     r"motion planning|actuator|teleoperat|end.?effector",
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
    # NOT a bare \beditor\b -- everything has an editor integration.
    "ui-desktop":    r"\bgui\b|desktop app|native app|immediate mode|window manager|"
                     r"\btauri\b|\belectron\b|menu ?bar|system tray|\bwidgets?\b|"
                     r"\bui toolkit\b|\bwayland\b|\bx11\b|keyboard remap|\bvim\b|"
                     r"\bneovim\b|text editor|code editor|\bmacos app\b|"
                     r"native .{0,12}(ui|app|desktop)",
    "wasm":          r"webassembly|\bwasm\b|\bwasi\b",
    "web":           r"\breact\b|\bcss\b|browser( engine)?|frontend|\bdom\b|web framework|"
                     r"headless browser|\bchrome\b|\bfirefox\b|\bextensions?\b|"
                     r"static site|\bhtml\b|http server|web app",
    # NOT a bare \bcli\b -- every tool has one; that does not make it a devtool.
    "devtools":      r"cli tool|command.?line (tool|interface)|\bterminal\b|debugger|"
                     r"build system|package manager|linter|formatter|\btui\b|\bide\b|"
                     r"toolchain|task runner|\bpager\b|shell (script|prompt|integration)|"
                     r"env var|dotfile|syntax.?high|\bcargo\b|developer (tool|experience)",
    # Not project themes. Industry news, policy and community argument arrive
    # constantly from HN and would otherwise own "other" forever. NOT a bare
    # \bpolicy\b -- that is RL policies, scheduling policies, cache policies.
    "industry":      r"\bacquisition\b|\bfunding\b|\bstartup\b|\bipo\b|layoff|lawsuit|"
                     r"antitrust|regulat|\bgdpr\b|privacy polic|legislat|lawmaker|"
                     r"\bcourt\b|licens(e|ing) change|\bceo\b|app store|play store|"
                     r"\bbanned\b|\bbanning\b|surveillance|donation|nonprofit|"
                     r"\bpricing\b|subscription|shuts? down|\bunemploy|\bfraud\b|"
                     r"\bfbi\b|(google|apple|meta|amazon) .{0,14}(sued|fined|blocks?|removes?)",
}

_COMPILED = {k: re.compile(v, re.I) for k, v in THEME_PATTERNS.items()}

# A trailing "|" leaves an empty alternative, which matches the empty string and
# silently tags every item in the corpus. Editing these patterns is exactly the
# kind of work where that happens, and coverage metrics *improve* when it does,
# so it hides. Fail loudly at import instead.
_DEGENERATE = [name for name, rx in _COMPILED.items() if rx.search("")]
if _DEGENERATE:
    raise ValueError(
        "theme pattern(s) match the empty string and would tag everything: "
        + ", ".join(_DEGENERATE)
    )

# Assigned by shape, not by text -- see DISCUSSION below.
DISCUSSION = "discussion"
ALL_THEMES = sorted(list(THEME_PATTERNS) + [DISCUSSION])


def classify(text: str) -> set[str]:
    return {name for name, rx in _COMPILED.items() if rx.search(text or "")}


def of_item(item) -> set[str]:
    """Themes for an Item.

    The README is deliberately NOT read. A README mentions everything a project
    touches -- install steps (docker, cargo, env vars), platform support (Linux
    kernel, CUDA, Vulkan), the feature tour -- so including it flipped the
    primary theme of a third of enriched items to something wrong: Audacity
    filed under os-kernel for the words "operating system", a document
    converter under wasm, a video editor under virtualization for "container".

    It cost nothing to drop: every enriched item is a GitHub repo and already
    has a description and topics, so coverage was identical at 13.8% either
    way, while average tags on enriched items fell 4.25 -> 2.55.

    Title, description and topics are what a maintainer chose to say the
    project *is*. That is exactly the signal wanted here. (`enrich` still
    fetches READMEs -- they are valuable context for the LLM ideation pass.)
    """
    text = " ".join([
        item.title or "", item.summary or "", " ".join(item.topics),
        item.lang or "",
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
#
# gpu-hpc precedes os-kernel deliberately: a GPU "kernel" is not an OS kernel.
PRIORITY = [
    "llm-inference", "emulation", "compilers-pl", "gpu-hpc", "os-kernel",
    "embedded-hw", "robotics", "virtualization", "databases", "distributed",
    "concurrency", "wasm", "security", "networking", "observability",
    "version-control", "science-compute", "theory", "data-eng",
    "graphics-media", "ui-desktop", "ml-research", "web", "devtools",
    "ai-agents", "industry", DISCUSSION,
]


def primary(theme_set: set[str]) -> str:
    """The single theme to file an item under when grouping."""
    if not theme_set:
        return UNCLASSIFIED
    for name in PRIORITY:
        if name in theme_set:
            return name
    return sorted(theme_set)[0]
