# radar digest - 2026-09-12 09:39

`115 new` · `75 AI infra` · `100 AI applied` · `75 no AI`

<details open>
<summary><b>Worth a look</b></summary>

### New this run
*highest-scoring things that were not here last time*

- **[ai-dynamo/dynamo](https://github.com/ai-dynamo/dynamo)** `2.04` — new this run
  <br>A Datacenter Scale Distributed Inference Serving Framework
- **[hypit-ai/hypit](https://github.com/hypit-ai/hypit)** `1.96` — new this run · 4.91/day · 219 stars
  <br>Clone any viral video with AI agents. Not just a script, the whole workflow: swap the face, the words, the B-roll, ship 100 variants in one command, a
- **[FalkorDB/FalkorDB](https://github.com/FalkorDB/FalkorDB)** `1.96` — new this run
  <br>A super fast Graph Database uses GraphBLAS under the hood for its sparse adjacency matrix graph representation. Our goal is to provide the best Knowle
- **[capsulerun/runtime](https://github.com/capsulerun/runtime)** `1.93` — new this run · 1.03/day · 294 stars
  <br>Secure runtime to sandbox AI agent tasks. Run untrusted code in isolated WebAssembly environments.

### Moving fastest
*star velocity against the rest of the corpus*

- **[deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness)** `1.92` — 7392.33/day · 221,067 stars · starred by ggerganov
  <br>DeepSeek Harness: Everything is a Plugin.
- **[firecrawl/anydoc](https://github.com/firecrawl/anydoc)** `3.26` — 534.34/day · 21,219 stars · starred by simonw
  <br>Convert Word, PowerPoint, Excel, OpenDocument, RTF, EPUB, CSV, and PDF to clean Markdown. Built in Rust, with Node.js and Python bindings.
- **[xai-org/grok-build](https://github.com/xai-org/grok-build)** `3.15` — 448.06/day · 26,689 stars · starred by simonw
  <br>SpaceXAI's coding agent harness and TUI. Fullscreen, mouse interactive, extensible.
- **[JustVugg/colibri](https://github.com/JustVugg/colibri)** `3.91` — 383.49/day · 27,950 stars · starred by geohot · 2 sources agree
  <br>Run frontier MoE models on hardware you already own — pure C, zero deps, experts streamed from disk. Tiny engine, immense model. 🐦

### Several sources agree
*independent corroboration is the strongest signal here*

- **[NVlabs/cuda-oxide](https://github.com/NVlabs/cuda-oxide)** `3.64` — 23.01/day · 3,283 stars · 2 sources agree
  <br>cuda-oxide is a Rust-to-CUDA compiler that lets you write (SIMT) GPU kernels in safe(ish), idiomatic Rust. It compiles standard Rust code directly to 
- **[ddalcu/mlx-serve](https://github.com/ddalcu/mlx-serve)** `3.60` — 5.97/day · 1,238 stars · starred by simonw · 3 sources agree
  <br>Native LLM inference server for Apple Silicon. OpenAI + Anthropic API compatible. No Python. Includes MLX Core macOS app with chat, agent mode, and to
- **[Mesh-LLM/mesh-llm](https://github.com/Mesh-LLM/mesh-llm)** `3.11` — 15.89/day · 3,388 stars · 2 sources agree
  <br>Distributed AI/LLM for the people. Share compute privately or publicly to power your agents and chat.
- **[AlexsJones/llmfit](https://github.com/AlexsJones/llmfit)** `3.04` — 173.19/day · 36,150 stars · 2 sources agree
  <br>Hundreds of models & providers. One command to find what runs on your hardware.

### From your watchlist
*engineers whose taste you chose to borrow*

- **[sqliteai/warp](https://github.com/sqliteai/warp)** `3.42` — 52.4/day · 2,386 stars · starred by karpathy
  <br>Run the full 2.78-trillion-parameter Kimi K3 model or GLM-5.3-Flash beyond available RAM by streaming activated weights directly from NVMe. A dependen
- **[handy-computer/transcribe.cpp](https://github.com/handy-computer/transcribe.cpp)** `3.34` — 12.09/day · 1,910 stars · starred by ggerganov, simonw
  <br>ggml speech-to-text inference for 16+ model families
- **[rivet-dev/agentos](https://github.com/rivet-dev/agentos)** `3.06` — 4.87/day · 4,617 stars · starred by simonw
  <br>Give agents an operating system as a library. Runs in your existing backend – no sandboxes, VMs, or SaaS. Powered by WebAssembly & V8 isolates.
- **[nasa/spacewasm](https://github.com/nasa/spacewasm)** `2.92` — 19.47/day · 1,553 stars · starred by simonw
  <br>A flight-compliant WebAssembly interpreter.

### Papers, usually with no implementation
*where the gap is the project*

- **[HBFSim: Fast and Faithful Simulation of High-Bandwidth Flash Under Real GPU Execution](http://arxiv.org/abs/2609.09800v1)** `2.69` — cs.AR
  <br>Serving a large language model (LLM) is limited by memory capacity. High-Bandwidth Flash (HBF) stacks NAND flash inside the accelerator package, one t
- **[Phase-Decoupled, Model-Calibrated Power Control for Disaggregated LLM Serving](http://arxiv.org/abs/2609.11133v1)** `2.51` — cs.DC
  <br>Datacenter GPU power is the binding constraint on LLM serving capacity, and production serving has shifted to prefill/decode (PD) disaggregation. Depl
- **[GPU-CFR: 80x Faster Counterfactual Regret Minimization by Compiling the Game to Static Dataflow and CUDA Graph Replay](http://arxiv.org/abs/2609.11923v1)** `2.48` — cs.PL
  <br>Counterfactual regret minimization (CFR) is one of the few large numerical workloads that still runs faster on CPUs than on GPUs. Each iteration sweep
- **[Unified AI Gateway: A Framework for Joint Model Routing and KV Cache Management](http://arxiv.org/abs/2609.06940v1)** `2.31` — cs.DC
  <br>Large language model (LLM) inference increasingly spans models that differ in size, capability, price, and provider. This shift creates two costs for 

</details>

---

## Ranked signal

### llm-inference  (23)

- **3.91** [JustVugg/colibri](https://github.com/JustVugg/colibri) — velocity +0.99, watchlist +0.81, fit +0.80  |  seen_before -0.15
- **3.60** [ddalcu/mlx-serve](https://github.com/ddalcu/mlx-serve) — corroboration +1.05, watchlist +0.81, fit +0.75  |  seen_before -0.15
- **3.42** [sqliteai/warp](https://github.com/sqliteai/warp) — fit +1.00, velocity +0.95, watchlist +0.81  |  seen_before -0.15
- **3.34** [handy-computer/transcribe.cpp](https://github.com/handy-computer/transcribe.cpp) — watchlist +1.26, fit +0.85, velocity +0.80  |  seen_before -0.15
- **3.04** [AlexsJones/llmfit](https://github.com/AlexsJones/llmfit) — velocity +0.98, fit +0.97, corroboration +0.70  |  seen_before -0.15
- **2.92** [FareedKhan-dev/kimi-k3-in-c](https://github.com/FareedKhan-dev/kimi-k3-in-c) — velocity +0.98, depth +0.90, fit +0.83  |  seen_before -0.15
- **2.81** [pegainfer-project/pegainfer](https://github.com/pegainfer-project/pegainfer) — fit +1.56, depth +0.90, velocity +0.48  |  seen_before -0.15
- **2.69** [HBFSim: Fast and Faithful Simulation of High-Bandwidth Flash Under Real GPU Execution](http://arxiv.org/abs/2609.09800v1) — fit +1.36, depth +0.81, freshness +0.67  |  seen_before -0.15
- **2.56** [Blaizzy/nativ](https://github.com/Blaizzy/nativ) — velocity +0.90, watchlist +0.81, fit +0.44  |  seen_before -0.15
- **2.51** [Phase-Decoupled, Model-Calibrated Power Control for Disaggregated LLM Serving](http://arxiv.org/abs/2609.11133v1) — fit +1.22, depth +0.77, freshness +0.68  |  seen_before -0.15
- **2.31** [Unified AI Gateway: A Framework for Joint Model Routing and KV Cache Management](http://arxiv.org/abs/2609.06940v1) — fit +0.95, depth +0.72, freshness +0.65
- **2.23** [MeanField Surrogate Modeling for Scalable Runtime Scheduling of Concurrent Heterogeneous AI Inference on Shared GPUs](http://arxiv.org/abs/2609.02109v1) — fit +0.97, depth +0.81, freshness +0.60  |  seen_before -0.15
- **2.22** [Shift-Accumulate Attention: Multiplier-Free Query--Key Products for Transformer Decoding](http://arxiv.org/abs/2609.09208v1) — depth +0.81, fit +0.78, freshness +0.63
- **2.21** [jmerelnyc/Talos](https://github.com/jmerelnyc/Talos) — fit +0.83, velocity +0.77, depth +0.53  |  seen_before -0.15
- **2.16** [Analytical Resource Management for Fine-grained MoE Computation-Communication Overlap](http://arxiv.org/abs/2609.07536v1) — fit +0.85, depth +0.81, freshness +0.65  |  seen_before -0.15
- **2.10** [HDA-MoE: Hybrid Parallelism and Dynamic, Adaptive Scheduling for Mixture-of-Experts with 3D Near-Memory Processing](http://arxiv.org/abs/2609.08682v1) — fit +0.83, depth +0.77, freshness +0.66  |  seen_before -0.15
- **2.05** [A Measurement Study of LLM Inference Trade-offs Across Edge Continuum Hardware](http://arxiv.org/abs/2609.08307v1) — fit +0.83, depth +0.72, freshness +0.66  |  seen_before -0.15
- **2.04** [text2ql: Multi-Target Natural Language Querying via a Language-Agnostic Intermediate Representation](http://arxiv.org/abs/2609.02115v1) — fit +0.83, depth +0.77, freshness +0.60  |  seen_before -0.15
- **2.04** [ai-dynamo/dynamo](https://github.com/ai-dynamo/dynamo) — velocity +0.70, fit +0.63, depth +0.46
- **2.03** [LLM Inference on IMC-NoC Architecture with Balanced Dataflow and Fine-Grained Parallelism](http://arxiv.org/abs/2609.00857v1) — fit +0.83, depth +0.77, freshness +0.59  |  seen_before -0.15
- **2.03** [Learnware and AI Model Management System](http://arxiv.org/abs/2609.11656v1) — depth +0.77, fit +0.73, freshness +0.68  |  seen_before -0.15
- **2.03** [Every Kernel Is a Join: Automatic Multi-GPU Parallelism for AI Computations in Einsummable](http://arxiv.org/abs/2609.03905v1) — depth +0.81, fit +0.75, freshness +0.61  |  seen_before -0.15
- **2.01** [Scaling Inference Prefill with High-Radix Photonic Interconnects](http://arxiv.org/abs/2609.01821v1) — fit +0.80, depth +0.77, freshness +0.59  |  seen_before -0.15

### compilers-pl  (13)

- **3.64** [NVlabs/cuda-oxide](https://github.com/NVlabs/cuda-oxide) — fit +1.22, depth +0.90, velocity +0.89  |  seen_before -0.15
- **2.92** [nasa/spacewasm](https://github.com/nasa/spacewasm) — velocity +0.87, depth +0.85, watchlist +0.81  |  seen_before -0.15
- **2.64** [lkimuk/ReArk](https://github.com/lkimuk/ReArk) — velocity +0.70, corroboration +0.70, depth +0.64  |  seen_before -0.15
- **2.63** [BoundaryML/baml](https://github.com/BoundaryML/baml) — watchlist +0.81, velocity +0.73, fit +0.73  |  seen_before -0.15
- **2.48** [GPU-CFR: 80x Faster Counterfactual Regret Minimization by Compiling the Game to Static Dataflow and CUDA Graph Replay](http://arxiv.org/abs/2609.11923v1) — fit +1.05, depth +0.90, freshness +0.68  |  seen_before -0.15
- **2.43** [Helvesec/rmux](https://github.com/Helvesec/rmux) — velocity +0.89, watchlist +0.81, depth +0.41  |  seen_before -0.15
- **2.37** [l0ng-ai/tty7](https://github.com/l0ng-ai/tty7) — velocity +0.81, depth +0.74, fit +0.73  |  seen_before -0.15
- **2.36** [rhaiscript/rhai](https://github.com/rhaiscript/rhai) — depth +0.90, watchlist +0.81, fit +0.58  |  seen_before -0.15
- **2.35** [Zaneham/Booth](https://github.com/Zaneham/Booth) — depth +0.90, fit +0.85, velocity +0.72  |  seen_before -0.15
- **2.30** [can1357/pon](https://github.com/can1357/pon) — depth +0.90, velocity +0.71, fit +0.61  |  seen_before -0.15
- **2.14** [Taming Bitwise Behavior in GPU Kernels with Tensor Core: Black-Box Reconstruction, Compiler Enforcement, and Static Verification](http://arxiv.org/abs/2609.11356v1) — depth +0.81, fit +0.80, freshness +0.68  |  seen_before -0.15
- **2.08** [Benchmarking Agentic HLS Design Tasks With HLS-Eval](http://arxiv.org/abs/2609.09526v1) — fit +0.85, depth +0.72, freshness +0.66  |  seen_before -0.15
- **2.03** [MaxKernel: Agentic Kernel Generation for TPUs](http://arxiv.org/abs/2609.04523v1) — fit +0.80, depth +0.77, freshness +0.61  |  seen_before -0.15

### data-eng  (1)

- **3.26** [firecrawl/anydoc](https://github.com/firecrawl/anydoc) — velocity +1.00, watchlist +0.81, fit +0.70  |  seen_before -0.15

### devtools  (2)

- **3.15** [xai-org/grok-build](https://github.com/xai-org/grok-build) — velocity +1.00, watchlist +0.81, fit +0.70  |  seen_before -0.15
- **2.39** [fallow-rs/fallow](https://github.com/fallow-rs/fallow) — velocity +0.90, fit +0.80, depth +0.79  |  seen_before -0.15

### distributed  (2)

- **3.11** [Mesh-LLM/mesh-llm](https://github.com/Mesh-LLM/mesh-llm) — fit +0.95, velocity +0.85, depth +0.74  |  seen_before -0.15
- **2.89** [Nehanth/swarmllm](https://github.com/Nehanth/swarmllm) — fit +1.22, velocity +0.89, freshness +0.59  |  seen_before -0.15

### gpu-hpc  (8)

- **3.08** [xuzhougeng/wisp-science](https://github.com/xuzhougeng/wisp-science) — fit +1.48, velocity +0.84, depth +0.68  |  seen_before -0.15
- **2.76** [openlake-project/openlake](https://github.com/openlake-project/openlake) — fit +1.17, velocity +0.86, depth +0.79  |  seen_before -0.15
- **2.29** [orhun/ratty](https://github.com/orhun/ratty) — velocity +0.89, depth +0.79, fit +0.68  |  seen_before -0.15
- **2.25** [ForgeStencil: Automating Per-Case Stencil Specialization from Kernels to 100+ Real Applications](http://arxiv.org/abs/2609.06694v1) — depth +0.81, fit +0.80, freshness +0.64
- **2.24** [DataKernelBench: Can LLMs Optimize Database Queries on GPUs?](http://arxiv.org/abs/2608.25061v2) — fit +1.00, depth +0.85, freshness +0.53  |  seen_before -0.15
- **2.19** [Latency-Aware Orchestration for Multi-Agent LLM Workflows on Heterogeneous GPUs](http://arxiv.org/abs/2609.03335v1) — fit +0.92, depth +0.81, freshness +0.61  |  seen_before -0.15
- **2.07** [AutoUVM: Automated Prefetching Framework for LLMs under UVM Oversubscription](http://arxiv.org/abs/2609.06172v1) — depth +0.81, fit +0.78, freshness +0.63  |  seen_before -0.15
- **2.03** [Tuning Collective Patterns to Alleviate Congestion in Shared AI Clusters](http://arxiv.org/abs/2609.04417v1) — depth +0.81, fit +0.75, freshness +0.61  |  seen_before -0.15

### os-kernel  (5)

- **3.06** [rivet-dev/agentos](https://github.com/rivet-dev/agentos) — fit +0.90, depth +0.90, watchlist +0.81  |  seen_before -0.15
- **2.81** [astrid-runtime/astrid](https://github.com/astrid-runtime/astrid) — fit +1.09, velocity +0.94, depth +0.90  |  seen_before -0.15
- **2.23** [databufflabs/databuff](https://github.com/databufflabs/databuff) — depth +0.75, fit +0.73, velocity +0.71  |  seen_before -0.15
- **2.11** [SchedBlame: Who Ran While You Waited? Culprit-Attributed CPU Contention for Containers on Stock Kernels](http://arxiv.org/abs/2609.02052v1) — depth +0.85, fit +0.80, freshness +0.60  |  seen_before -0.15
- **2.07** [RightNow-AI/openfang](https://github.com/RightNow-AI/openfang) — velocity +0.97, depth +0.68, fit +0.54  |  seen_before -0.15

### virtualization  (2)

- **3.04** [elliothux/open-compute](https://github.com/elliothux/open-compute) — velocity +0.91, depth +0.90, fit +0.88  |  seen_before -0.15
- **2.69** [t8y2/dbx](https://github.com/t8y2/dbx) — velocity +0.98, corroboration +0.70, depth +0.68  |  seen_before -0.15

### ai-agents  (3)

- **2.80** [redhat-et/ripwire](https://github.com/redhat-et/ripwire) — fit +0.97, velocity +0.93, depth +0.70  |  seen_before -0.15
- **2.69** [Human-Agent-Society/reef](https://github.com/Human-Agent-Society/reef) — fit +1.00, velocity +0.96, freshness +0.58  |  seen_before -0.15
- **2.68** [mixelpixx/Konnect](https://github.com/mixelpixx/Konnect) — velocity +0.75, corroboration +0.70, fit +0.68  |  seen_before -0.15

### wasm  (3)

- **2.80** [open-ribbi/velocut](https://github.com/open-ribbi/velocut) — fit +1.22, depth +0.79, velocity +0.69  |  seen_before -0.15
- **2.77** [ruvnet/RuVector](https://github.com/ruvnet/RuVector) — fit +1.34, velocity +0.84, depth +0.74  |  seen_before -0.15
- **2.04** [nearai/ironclaw](https://github.com/nearai/ironclaw) — velocity +0.95, depth +0.68, fit +0.54  |  seen_before -0.15

### security  (4)

- **2.80** [sunblaze-ucb/exploitgym](https://github.com/sunblaze-ucb/exploitgym) — watchlist +0.81, velocity +0.77, fit +0.75  |  seen_before -0.15
- **2.69** [duty1g/x64dbg-mcp-server](https://github.com/duty1g/x64dbg-mcp-server) — velocity +0.97, fit +0.85, depth +0.51  |  seen_before -0.15
- **2.24** [2akouwu/reverify](https://github.com/2akouwu/reverify) — velocity +0.97, fit +0.70, freshness +0.58  |  seen_before -0.15
- **2.00** [sleep3r/mtproto.zig](https://github.com/sleep3r/mtproto.zig) — velocity +0.85, corroboration +0.70, depth +0.41  |  seen_before -0.15

### observability  (1)

- **2.66** [furkankly/zoetrope](https://github.com/furkankly/zoetrope) — velocity +0.91, depth +0.74, fit +0.68  |  seen_before -0.15

### ui-desktop  (2)

- **2.40** [vercel-labs/native](https://github.com/vercel-labs/native) — velocity +0.95, corroboration +0.70, depth +0.46  |  seen_before -0.15
- **2.04** [Pinvou/pinvou-agent](https://github.com/Pinvou/pinvou-agent) — velocity +0.92, fit +0.54, depth +0.41  |  seen_before -0.15

### databases  (5)

- **2.38** [pgrundev/pgbot](https://github.com/pgrundev/pgbot) — velocity +0.92, depth +0.62, fit +0.56  |  seen_before -0.15
- **2.33** [deeplethe/utopia](https://github.com/deeplethe/utopia) — velocity +0.99, fit +0.68, freshness +0.41  |  seen_before -0.15
- **2.31** [nubskr/walrus](https://github.com/nubskr/walrus) — fit +0.92, depth +0.90, velocity +0.63  |  stale -0.00, seen_before -0.15
- **2.24** [TrajectoryDB: A New Database for Agent Trajectories](http://arxiv.org/abs/2609.07782v1) — fit +0.92, depth +0.81, freshness +0.65  |  seen_before -0.15
- **2.18** [Bonded Recourse for Smart-Contract Settlement of Compensable Agent Side Effects](http://arxiv.org/abs/2609.01939v1) — fit +0.92, depth +0.81, freshness +0.60  |  seen_before -0.15

### emulation  (1)

- **2.17** [KytyPS5/KytyPS5](https://github.com/KytyPS5/KytyPS5) — depth +0.90, velocity +0.90, fit +0.36  |  seen_before -0.15

### discussion  (1)

- **2.08** [A decade of rustls](https://rustls.dev/blog/2026-09-08-a-decade-of-rustls/) — velocity +0.84, freshness +0.67, depth +0.40  |  chatter -0.00

### graphics-media  (1)

- **2.03** [pascalorg/editor](https://github.com/pascalorg/editor) — velocity +0.96, corroboration +0.70, fit +0.34  |  seen_before -0.15

### other  (3)

- **2.34** [iczelia/bzip3](https://github.com/iczelia/bzip3) — velocity +0.78, corroboration +0.70, freshness +0.65  |  seen_before -0.15
- **2.19** [Kernel-Managed Shared Memory for System-Wide Personalization](http://arxiv.org/abs/2609.10144v1) — fit +0.80, depth +0.72, freshness +0.67
- **2.07** [LLMs as a Cognitive Virus](https://arxiv.org/abs/2609.03344) — velocity +0.75, depth +0.68, freshness +0.63  |  seen_before -0.15

