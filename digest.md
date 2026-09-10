# radar digest - 2026-09-10 10:06

`193 new` · `75 AI infra` · `100 AI applied` · `75 no AI`

<details open>
<summary><b>Worth a look</b></summary>

### New this run
*highest-scoring things that were not here last time*

- **[HBFSim: Fast and Faithful Simulation of High-Bandwidth Flash Under Real GPU Execution](http://arxiv.org/abs/2609.09800v1)** `2.86` — new this run · cs.AR
  <br>Serving a large language model (LLM) is limited by memory capacity. High-Bandwidth Flash (HBF) stacks NAND flash inside the accelerator package, one t
- **[Nehanth/swarmllm](https://github.com/Nehanth/swarmllm)** `2.74` — new this run · 20.6/day · 194 stars
  <br>Every device brings a slice. Together they run the whole model. Peer-to-peer LLM inference across browser tabs: a from-scratch WebGPU engine and a Web
- **[Benchmarking Agentic HLS Design Tasks With HLS-Eval](http://arxiv.org/abs/2609.09526v1)** `2.26` — new this run · cs.AR
  <br>Large language models (LLMs) and AI agents are increasingly explored for hardware design, including high-level digital design. While most work targets
- **[Epoch: Compiling Diffusion Blocks for Sparse MoE Serving](http://arxiv.org/abs/2609.09748v1)** `2.25` — new this run · cs.DC
  <br>Diffusion language models generate text by refining a fixed-size block of token positions through many forward passes, a loop that does not match the 

### Moving fastest
*star velocity against the rest of the corpus*

- **[deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness)** `1.93` — 7821.66/day · 218,408 stars · starred by ggerganov
  <br>DeepSeek Harness: Everything is a Plugin.
- **[firecrawl/anydoc](https://github.com/firecrawl/anydoc)** `3.27` — 557.15/day · 21,021 stars · starred by simonw
  <br>Convert Word, PowerPoint, Excel, OpenDocument, RTF, EPUB, CSV, and PDF to clean Markdown. Built in Rust, with Node.js and Python bindings.
- **[xai-org/grok-build](https://github.com/xai-org/grok-build)** `3.16` — 462.64/day · 26,641 stars · starred by simonw
  <br>SpaceXAI's coding agent harness and TUI. Fullscreen, mouse interactive, extensible.
- **[JustVugg/colibri](https://github.com/JustVugg/colibri)** `3.92` — 384.59/day · 27,268 stars · starred by geohot · 2 sources agree
  <br>Run frontier MoE models on hardware you already own — pure C, zero deps, experts streamed from disk. Tiny engine, immense model. 🐦

### Several sources agree
*independent corroboration is the strongest signal here*

- **[ddalcu/mlx-serve](https://github.com/ddalcu/mlx-serve)** `3.75` — 5.92/day · 1,215 stars · starred by simonw · 3 sources agree
  <br>Native LLM inference server for Apple Silicon. OpenAI + Anthropic API compatible. No Python. Includes MLX Core macOS app with chat, agent mode, and to
- **[mixelpixx/Konnect](https://github.com/mixelpixx/Konnect)** `2.79` — 9.05/day · 602 stars · 2 sources agree
  <br>AI-assisted PCB design for KiCAD 10. Native KiCAD plugin — a single Rust binary exposing 217 schematic, layout, routing, placement, design-review, and
- **[t8y2/dbx](https://github.com/t8y2/dbx)** `2.69` — 140.1/day · 18,815 stars · 2 sources agree
  <br>20 MB lightweight cross-platform database client for 90+ databases, including MySQL, PostgreSQL, SQLite, Redis, MongoDB, DuckDB, SQL Server, and Damen
- **[How to build a printer](https://nishantjosh.dev/blogs/how-to-build-a-fking-printer/)** `2.57` — 435 HN points · 2 sources agree

### From your watchlist
*engineers whose taste you chose to borrow*

- **[sqliteai/warp](https://github.com/sqliteai/warp)** `3.43` — 54.61/day · 2,378 stars · starred by karpathy
  <br>Run the full 2.78-trillion-parameter Kimi K3 model or GLM-5.3-Flash beyond available RAM by streaming activated weights directly from NVMe. A dependen
- **[handy-computer/transcribe.cpp](https://github.com/handy-computer/transcribe.cpp)** `3.34` — 12.21/day · 1,904 stars · starred by ggerganov, simonw
  <br>ggml speech-to-text inference for 16+ model families
- **[rivet-dev/agentos](https://github.com/rivet-dev/agentos)** `3.06` — 4.87/day · 4,613 stars · starred by simonw
  <br>Give agents an operating system as a library. Runs in your existing backend – no sandboxes, VMs, or SaaS. Powered by WebAssembly & V8 isolates.
- **[nasa/spacewasm](https://github.com/nasa/spacewasm)** `2.93` — 19.96/day · 1,553 stars · starred by simonw
  <br>A flight-compliant WebAssembly interpreter.

### Papers, usually with no implementation
*where the gap is the project*

- **[Unified AI Gateway: A Framework for Joint Model Routing and KV Cache Management](http://arxiv.org/abs/2609.06940v1)** `2.33` — cs.DC
  <br>Large language model (LLM) inference increasingly spans models that differ in size, capability, price, and provider. This shift creates two costs for 
- **[ForgeStencil: Automating Per-Case Stencil Specialization from Kernels to 100+ Real Applications](http://arxiv.org/abs/2609.06694v1)** `2.27` — cs.DC
  <br>On modern GPUs the fastest stencil kernel depends on the stencil's shape, precision, and host application, and a kernel tuned for one case is rarely f
- **[TrajectoryDB: A New Database for Agent Trajectories](http://arxiv.org/abs/2609.07782v1)** `2.26` — cs.DB
  <br>AI agents generate rich execution trajectories that capture their interactions with large language models, tools, and external environments. These tra
- **[DataKernelBench: Can LLMs Optimize Database Queries on GPUs?](http://arxiv.org/abs/2608.25061v2)** `2.25` — cs.PL
  <br>GPUs increasingly accelerate database systems, but query-specific peak performance still often relies on hand-written kernels. Existing LLM kernel ben

</details>

---

## Ranked signal

### llm-inference  (20)

- **3.92** [JustVugg/colibri](https://github.com/JustVugg/colibri) — velocity +0.99, watchlist +0.81, fit +0.80  |  seen_before -0.15
- **3.75** [ddalcu/mlx-serve](https://github.com/ddalcu/mlx-serve) — corroboration +1.05, velocity +0.85, watchlist +0.81  |  seen_before -0.15
- **3.43** [sqliteai/warp](https://github.com/sqliteai/warp) — fit +1.00, velocity +0.94, watchlist +0.81  |  seen_before -0.15
- **3.34** [handy-computer/transcribe.cpp](https://github.com/handy-computer/transcribe.cpp) — watchlist +1.26, fit +0.85, velocity +0.79  |  seen_before -0.15
- **2.94** [FareedKhan-dev/kimi-k3-in-c](https://github.com/FareedKhan-dev/kimi-k3-in-c) — velocity +0.98, depth +0.90, fit +0.83  |  seen_before -0.15
- **2.86** [HBFSim: Fast and Faithful Simulation of High-Bandwidth Flash Under Real GPU Execution](http://arxiv.org/abs/2609.09800v1) — fit +1.36, depth +0.81, freshness +0.69
- **2.81** [pegainfer-project/pegainfer](https://github.com/pegainfer-project/pegainfer) — fit +1.56, depth +0.90, velocity +0.48  |  seen_before -0.15
- **2.57** [Blaizzy/nativ](https://github.com/Blaizzy/nativ) — velocity +0.90, watchlist +0.81, fit +0.44  |  seen_before -0.15
- **2.33** [Unified AI Gateway: A Framework for Joint Model Routing and KV Cache Management](http://arxiv.org/abs/2609.06940v1) — fit +0.95, depth +0.72, freshness +0.67
- **2.25** [Epoch: Compiling Diffusion Blocks for Sparse MoE Serving](http://arxiv.org/abs/2609.09748v1) — depth +0.81, fit +0.75, freshness +0.69
- **2.25** [MeanField Surrogate Modeling for Scalable Runtime Scheduling of Concurrent Heterogeneous AI Inference on Shared GPUs](http://arxiv.org/abs/2609.02109v1) — fit +0.97, depth +0.81, freshness +0.62  |  seen_before -0.15
- **2.24** [Shift-Accumulate Attention: Multiplier-Free Query--Key Products for Transformer Decoding](http://arxiv.org/abs/2609.09208v1) — depth +0.81, fit +0.78, freshness +0.65
- **2.21** [jmerelnyc/Talos](https://github.com/jmerelnyc/Talos) — fit +0.83, velocity +0.77, depth +0.53  |  seen_before -0.15
- **2.18** [Analytical Resource Management for Fine-grained MoE Computation-Communication Overlap](http://arxiv.org/abs/2609.07536v1) — fit +0.85, depth +0.81, freshness +0.67  |  seen_before -0.15
- **2.12** [HDA-MoE: Hybrid Parallelism and Dynamic, Adaptive Scheduling for Mixture-of-Experts with 3D Near-Memory Processing](http://arxiv.org/abs/2609.08682v1) — fit +0.83, depth +0.77, freshness +0.68  |  seen_before -0.15
- **2.07** [A Measurement Study of LLM Inference Trade-offs Across Edge Continuum Hardware](http://arxiv.org/abs/2609.08307v1) — fit +0.83, depth +0.72, freshness +0.68  |  seen_before -0.15
- **2.06** [text2ql: Multi-Target Natural Language Querying via a Language-Agnostic Intermediate Representation](http://arxiv.org/abs/2609.02115v1) — fit +0.83, depth +0.77, freshness +0.62  |  seen_before -0.15
- **2.05** [LLM Inference on IMC-NoC Architecture with Balanced Dataflow and Fine-Grained Parallelism](http://arxiv.org/abs/2609.00857v1) — fit +0.83, depth +0.77, freshness +0.61  |  seen_before -0.15
- **2.04** [Every Kernel Is a Join: Automatic Multi-GPU Parallelism for AI Computations in Einsummable](http://arxiv.org/abs/2609.03905v1) — depth +0.81, fit +0.75, freshness +0.63  |  seen_before -0.15
- **2.03** [Scaling Inference Prefill with High-Radix Photonic Interconnects](http://arxiv.org/abs/2609.01821v1) — fit +0.80, depth +0.77, freshness +0.61  |  seen_before -0.15

### data-eng  (1)

- **3.27** [firecrawl/anydoc](https://github.com/firecrawl/anydoc) — velocity +1.00, watchlist +0.81, fit +0.70  |  seen_before -0.15

### devtools  (2)

- **3.16** [xai-org/grok-build](https://github.com/xai-org/grok-build) — velocity +1.00, watchlist +0.81, fit +0.70  |  seen_before -0.15
- **2.39** [fallow-rs/fallow](https://github.com/fallow-rs/fallow) — velocity +0.90, fit +0.80, depth +0.79  |  seen_before -0.15

### gpu-hpc  (9)

- **3.08** [xuzhougeng/wisp-science](https://github.com/xuzhougeng/wisp-science) — fit +1.48, velocity +0.84, depth +0.68  |  seen_before -0.15
- **2.75** [openlake-project/openlake](https://github.com/openlake-project/openlake) — fit +1.17, velocity +0.86, depth +0.79  |  seen_before -0.15
- **2.29** [orhun/ratty](https://github.com/orhun/ratty) — velocity +0.89, depth +0.79, fit +0.68  |  seen_before -0.15
- **2.27** [ForgeStencil: Automating Per-Case Stencil Specialization from Kernels to 100+ Real Applications](http://arxiv.org/abs/2609.06694v1) — depth +0.81, fit +0.80, freshness +0.66
- **2.25** [DataKernelBench: Can LLMs Optimize Database Queries on GPUs?](http://arxiv.org/abs/2608.25061v2) — fit +1.00, depth +0.85, freshness +0.55  |  seen_before -0.15
- **2.21** [Latency-Aware Orchestration for Multi-Agent LLM Workflows on Heterogeneous GPUs](http://arxiv.org/abs/2609.03335v1) — fit +0.92, depth +0.81, freshness +0.63  |  seen_before -0.15
- **2.10** [Python in the front, party in the Backline: compiling quantum workloads across CPUs, GPUs, and FPGAs](http://arxiv.org/abs/2609.09270v1) — depth +0.81, freshness +0.68, fit +0.61
- **2.09** [AutoUVM: Automated Prefetching Framework for LLMs under UVM Oversubscription](http://arxiv.org/abs/2609.06172v1) — depth +0.81, fit +0.78, freshness +0.65  |  seen_before -0.15
- **2.05** [Tuning Collective Patterns to Alleviate Congestion in Shared AI Clusters](http://arxiv.org/abs/2609.04417v1) — depth +0.81, fit +0.75, freshness +0.63  |  seen_before -0.15

### virtualization  (2)

- **3.06** [elliothux/open-compute](https://github.com/elliothux/open-compute) — velocity +0.90, depth +0.90, fit +0.88  |  seen_before -0.15
- **2.69** [t8y2/dbx](https://github.com/t8y2/dbx) — velocity +0.97, corroboration +0.70, depth +0.68  |  seen_before -0.15

### os-kernel  (5)

- **3.06** [rivet-dev/agentos](https://github.com/rivet-dev/agentos) — fit +0.90, depth +0.90, watchlist +0.81  |  seen_before -0.15
- **2.81** [astrid-runtime/astrid](https://github.com/astrid-runtime/astrid) — fit +1.09, velocity +0.94, depth +0.90  |  seen_before -0.15
- **2.23** [databufflabs/databuff](https://github.com/databufflabs/databuff) — depth +0.75, fit +0.73, velocity +0.71  |  seen_before -0.15
- **2.12** [SchedBlame: Who Ran While You Waited? Culprit-Attributed CPU Contention for Containers on Stock Kernels](http://arxiv.org/abs/2609.02052v1) — depth +0.85, fit +0.80, freshness +0.62  |  seen_before -0.15
- **2.06** [RightNow-AI/openfang](https://github.com/RightNow-AI/openfang) — velocity +0.96, depth +0.68, fit +0.54  |  seen_before -0.15

### compilers-pl  (12)

- **2.94** [NVlabs/cuda-oxide](https://github.com/NVlabs/cuda-oxide) — fit +1.22, depth +0.90, velocity +0.89  |  seen_before -0.15
- **2.93** [nasa/spacewasm](https://github.com/nasa/spacewasm) — velocity +0.87, depth +0.85, watchlist +0.81  |  seen_before -0.15
- **2.63** [BoundaryML/baml](https://github.com/BoundaryML/baml) — watchlist +0.81, velocity +0.73, fit +0.73  |  seen_before -0.15
- **2.43** [Helvesec/rmux](https://github.com/Helvesec/rmux) — velocity +0.88, watchlist +0.81, depth +0.41  |  seen_before -0.15
- **2.38** [l0ng-ai/tty7](https://github.com/l0ng-ai/tty7) — velocity +0.81, depth +0.74, fit +0.73  |  seen_before -0.15
- **2.36** [rhaiscript/rhai](https://github.com/rhaiscript/rhai) — depth +0.90, watchlist +0.81, fit +0.58  |  seen_before -0.15
- **2.35** [Zaneham/Booth](https://github.com/Zaneham/Booth) — depth +0.90, fit +0.85, velocity +0.72  |  seen_before -0.15
- **2.31** [can1357/pon](https://github.com/can1357/pon) — depth +0.90, velocity +0.71, fit +0.61  |  seen_before -0.15
- **2.26** [Benchmarking Agentic HLS Design Tasks With HLS-Eval](http://arxiv.org/abs/2609.09526v1) — fit +0.85, depth +0.72, freshness +0.68
- **2.16** [NVlabs/cutile-rs](https://github.com/NVlabs/cutile-rs) — depth +0.90, fit +0.78, velocity +0.58  |  seen_before -0.15
- **2.10** [UnsafeChecker: Finding Soundness Bugs in Rust Safe Abstractions](http://arxiv.org/abs/2609.09641v1) — depth +0.81, freshness +0.69, fit +0.61
- **2.05** [MaxKernel: Agentic Kernel Generation for TPUs](http://arxiv.org/abs/2609.04523v1) — fit +0.80, depth +0.77, freshness +0.63  |  seen_before -0.15

### ai-agents  (3)

- **2.81** [redhat-et/ripwire](https://github.com/redhat-et/ripwire) — fit +0.97, velocity +0.93, depth +0.70  |  seen_before -0.15
- **2.79** [mixelpixx/Konnect](https://github.com/mixelpixx/Konnect) — velocity +0.85, corroboration +0.70, fit +0.68  |  seen_before -0.15
- **2.71** [Human-Agent-Society/reef](https://github.com/Human-Agent-Society/reef) — fit +1.00, velocity +0.96, freshness +0.60  |  seen_before -0.15

### wasm  (3)

- **2.80** [open-ribbi/velocut](https://github.com/open-ribbi/velocut) — fit +1.22, depth +0.79, velocity +0.69  |  seen_before -0.15
- **2.77** [ruvnet/RuVector](https://github.com/ruvnet/RuVector) — fit +1.34, velocity +0.84, depth +0.74  |  seen_before -0.15
- **2.04** [nearai/ironclaw](https://github.com/nearai/ironclaw) — velocity +0.95, depth +0.68, fit +0.54  |  seen_before -0.15

### security  (3)

- **2.79** [sunblaze-ucb/exploitgym](https://github.com/sunblaze-ucb/exploitgym) — watchlist +0.81, velocity +0.76, fit +0.75  |  seen_before -0.15
- **2.70** [duty1g/x64dbg-mcp-server](https://github.com/duty1g/x64dbg-mcp-server) — velocity +0.96, fit +0.85, freshness +0.52  |  seen_before -0.15
- **2.26** [2akouwu/reverify](https://github.com/2akouwu/reverify) — velocity +0.97, fit +0.70, freshness +0.60  |  seen_before -0.15

### distributed  (2)

- **2.74** [Nehanth/swarmllm](https://github.com/Nehanth/swarmllm) — fit +1.02, velocity +0.87, freshness +0.60
- **2.41** [Mesh-LLM/mesh-llm](https://github.com/Mesh-LLM/mesh-llm) — fit +0.95, velocity +0.84, depth +0.74  |  seen_before -0.15

### discussion  (2)

- **2.57** [How to build a printer](https://nishantjosh.dev/blogs/how-to-build-a-fking-printer/) — velocity +0.93, corroboration +0.70, freshness +0.68  |  chatter -0.00, seen_before -0.15
- **2.08** [A decade of rustls](https://rustls.dev/blog/2026-09-08-a-decade-of-rustls/) — velocity +0.82, freshness +0.69, depth +0.40  |  chatter -0.00

### ui-desktop  (3)

- **2.40** [vercel-labs/native](https://github.com/vercel-labs/native) — velocity +0.95, corroboration +0.70, depth +0.46  |  seen_before -0.15
- **2.04** [Pinvou/pinvou-agent](https://github.com/Pinvou/pinvou-agent) — velocity +0.92, fit +0.54, depth +0.41  |  seen_before -0.15
- **2.03** [fy-agent/fyagent](https://github.com/fy-agent/fyagent) — velocity +0.89, fit +0.54, depth +0.41  |  seen_before -0.15

### databases  (6)

- **2.39** [pgrundev/pgbot](https://github.com/pgrundev/pgbot) — velocity +0.92, depth +0.62, fit +0.56  |  seen_before -0.15
- **2.34** [deeplethe/utopia](https://github.com/deeplethe/utopia) — velocity +0.99, fit +0.68, freshness +0.42  |  seen_before -0.15
- **2.30** [nubskr/walrus](https://github.com/nubskr/walrus) — fit +0.92, depth +0.90, velocity +0.63  |  seen_before -0.15
- **2.30** [alibaba/open-code-review](https://github.com/alibaba/open-code-review) — velocity +0.98, corroboration +0.70, fit +0.36  |  seen_before -0.15
- **2.26** [TrajectoryDB: A New Database for Agent Trajectories](http://arxiv.org/abs/2609.07782v1) — fit +0.92, depth +0.81, freshness +0.67  |  seen_before -0.15
- **2.20** [Bonded Recourse for Smart-Contract Settlement of Compensable Agent Side Effects](http://arxiv.org/abs/2609.01939v1) — fit +0.92, depth +0.81, freshness +0.61  |  seen_before -0.15

### emulation  (1)

- **2.18** [KytyPS5/KytyPS5](https://github.com/KytyPS5/KytyPS5) — depth +0.90, velocity +0.90, fit +0.36  |  seen_before -0.15

### embedded-hw  (1)

- **2.04** [AutoTrans: AI-Assisted Automatic Translation of Security Assertions for RISC-V Processors](http://arxiv.org/abs/2609.10057v1) — depth +0.72, freshness +0.69, fit +0.63

### graphics-media  (1)

- **2.02** [pascalorg/editor](https://github.com/pascalorg/editor) — velocity +0.95, corroboration +0.70, fit +0.34  |  seen_before -0.15

### concurrency  (1)

- **2.02** [Show HN: We built open OpenRouter that turns usage into a better model](https://github.com/experientiallabs/experiential) — fit +0.92, freshness +0.57, velocity +0.50  |  seen_before -0.15

### other  (3)

- **2.38** [iczelia/bzip3](https://github.com/iczelia/bzip3) — velocity +0.79, corroboration +0.70, freshness +0.67  |  seen_before -0.15
- **2.21** [Kernel-Managed Shared Memory for System-Wide Personalization](http://arxiv.org/abs/2609.10144v1) — fit +0.80, depth +0.72, freshness +0.69
- **2.10** [LLMs as a Cognitive Virus](https://arxiv.org/abs/2609.03344) — velocity +0.76, depth +0.68, freshness +0.65  |  seen_before -0.15

