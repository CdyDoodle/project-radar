# radar 摘要 - 2026-09-23 21:53

`149 本次新增` · `75 AI 基础设施` · `100 AI 应用` · `75 非 AI`

<details open>
<summary><b>值得一看</b></summary>

### 已保存
*你标记为值得保留的条目*

- **[NVlabs/cuda-oxide](https://github.com/NVlabs/cuda-oxide)** `3.36` — 每天 23.23 星 · 3,575 星 · 2 个来源共同提到
  <br>cuda-oxide 是一个 Rust 到 CUDA 的编译器，让你用 safe(ish)、地道的 Rust 编写（SIMT）GPU kernel。它将标准 Rust 代码直接编译为

### 本次新增
*上次没有、这次得分最高的条目*

- **[DeepSeek-V4.1-Flash：将 KV cache 压缩推向极限](https://arxiv.org/abs/2609.19969)** `2.57` — 本次新增 · Hugging Face 172 赞 · 未找到代码
  <br>长程 agent 的广泛采用使模型负载越来越偏重输入。尽管已有工作大幅降低了
- **[VC-Attention：面向低比特注意力的值平滑与 Softmax 转换](https://arxiv.org/abs/2609.15810)** `2.53` — 本次新增 · Hugging Face 50 赞 · 未找到代码
  <br>Diffusion Transformer 在视频生成上达到了 state-of-the-art 水平，但其超长的时空序列使 attention 成为部署成本的主要来源，
- **[Flash-dLLM：IO 感知的 KV 缓存与并行解码，实现快速、省内存的扩散 LLM](https://arxiv.org/abs/2609.26796)** `2.50` — 本次新增 · Hugging Face 12 赞 · 已有代码：VILA-Lab/Flash-dLLM
  <br>扩散大语言模型（dLLM）通过支持非自回归文本生
- **[文档检索感知分块（D-RAC）：通过 PDF 规范化与多模态 Markdown 转换实现企业文档的通用检索感知摄取](https://arxiv.org/abs/2609.24220)** `2.47` — 本次新增 · Hugging Face 52 赞 · 未找到代码
  <br>面向企业知识库的检索增强生成（RAG）系统必须摄入异构文档格式——PDF、Word 文档、演示

### 增长最快
*相对整个语料库的星增速，不含已成名的仓库*

- **[mizorewww/laya-mlx](https://github.com/mizorewww/laya-mlx)** `2.22` — 每天 1437.7 星 · 5,813 星
  <br>面向 Laya 类型化决策模型的原生 MLX 运行时——在 M3 Max 上短决策耗时 7–14 ms。无文本生成、无 PyTorch、无云 API。
- **[jaredpalmer/kev](https://github.com/jaredpalmer/kev/tree/main)** `1.63` — 每天 865.99 星 · 4,621 星 · HN 458 分
  <br>基于 Qwen3.5 构建的类 Jev 小型决策模型系列，可自行训练和运行
- **[JustVugg/colibri](https://github.com/JustVugg/colibri)** `3.69` — 每天 443.27 星 · 37,279 星 · geohot 已 star · 2 个来源共同提到
  <br>在你已有的硬件上运行前沿 MoE 模型——纯 C、零依赖，专家从磁盘流式加载。引擎小巧，模型庞大。🐦
- **[firecrawl/anydoc](https://github.com/firecrawl/anydoc)** `3.01` — 每天 431.2 星 · 21,960 星 · simonw 已 star
  <br>将 Word、PowerPoint、Excel、OpenDocument、RTF、EPUB、CSV 和 PDF 转换为干净的 Markdown。使用 Rust 构建，提供 Node.js 和 Python 绑定。

### 多个来源共同提到
*多个来源独立印证是这里最强的信号*

- **[antirez/ds4](https://github.com/antirez/ds4)** `3.76` — 每天 161.99 星 · 22,662 星 · antirez 正在开发 · 2 个来源共同提到
  <br>支持 Metal、CUDA 和 ROCm 的 DeepSeek 4 Flash 与 PRO 本地推理引擎
- **[ddalcu/mlx-serve](https://github.com/ddalcu/mlx-serve)** `3.56` — 每天 6.9 星 · 1,507 星 · simonw 已 star · 3 个来源共同提到
  <br>面向 Apple Silicon 的原生 LLM 推理服务器。兼容 OpenAI + Anthropic API。无需 Python。附带 MLX Core macOS 应用，支持聊天、agent 模式和
- **[RRSI：Agent harness 的正则化递归自我改进](https://arxiv.org/abs/2609.24972)** `3.26` — Hugging Face 174 赞 · 2 个来源共同提到 · cs.LG · 已有代码：google-research/rrsi
  <br>LLM agent 的能力在很大程度上被其 harness 放大，即围绕 t
- **[EvoOntology：面向数据 agent 的自演化本体层](http://arxiv.org/abs/2609.15779v1)** `3.24` — Hugging Face 139 赞 · 2 个来源共同提到 · cs.DB · 已有代码：ruc-datalab/EvoOntology
  <br>数据 agent 旨在基于表格、文件和数据库等异构数据完成自然语言指令。然而，数据 agent 面临一

### 来自你的关注列表
*你选择借鉴其眼光的工程师*

- **[sqliteai/warp](https://github.com/sqliteai/warp)** `3.13` — 每天 43.0 星 · 2,440 星 · karpathy 已 star
  <br>通过直接流式加载激活权重，在可用 RAM 之外运行完整的 2.78 万亿参数 Kimi K3 模型、DeepSeek V4.1 Flash 或 GLM-5.3-Flash
- **[handy-computer/transcribe.cpp](https://github.com/handy-computer/transcribe.cpp)** `3.06` — 每天 11.54 星 · 1,953 星 · ggerganov, simonw 已 star
  <br>基于 ggml 的语音转文字推理，支持 16+ 个模型系列
- **[xai-org/grok-build](https://github.com/xai-org/grok-build)** `2.92` — 每天 382.09 星 · 27,046 星 · simonw 已 star
  <br>SpaceXAI 的编码智能体 harness 与 TUI。全屏、鼠标交互、可扩展。
- **[rivet-dev/agentos](https://github.com/rivet-dev/agentos)** `2.78` — 每天 4.86 星 · 4,659 星 · simonw 已 star
  <br>以库的形式为 agent 提供一个操作系统。直接运行在你现有的后端中——无需沙箱、虚拟机或 SaaS。基于 WebAssembly 和 V8 isolate。

### 尚无人实现的论文
*已核实：Hugging Face 和 GitHub 上都没有代码。空白本身就是项目*

- **[AI 研究智能体的递归自我改进](http://arxiv.org/abs/2609.26457v1)** `2.60` — Hugging Face 6 赞 · 2 个来源共同提到 · cs.LG · 未找到代码
  <br>AI agent 正开始在整个 AI 技术栈中自动化研发工作，从提升训练效率到优化推理。一个自然
- **[DeepSeek Elastic Compute（DSec）：用于大规模高效 Agentic 训练的沙箱基础设施](http://arxiv.org/abs/2609.22978v1)** `2.59` — cs.DC · 未找到代码
  <br>基于大语言模型（LLM）的大规模智能体训练与评估依赖于隔离的、有状态的执行环境，模型在其中检
- **[将逻辑 mask 与 GPU 执行解耦，实现动态块稀疏注意力](http://arxiv.org/abs/2609.25869v1)** `2.48` — cs.AR · 未找到代码
  <br>在通过迭代去噪生成视频的视频扩散 Transformer（vDiT）中，注意力计算使推理代价高昂。Block-spar
- **[AKTS：面向语言模型 agent 的亚微秒级内核策略切换](http://arxiv.org/abs/2609.12276v1)** `2.44` — cs.OS · 未找到代码
  <br>基于 GPU 的 LLM 服务器常在同一组 CPU 上混合处理交互式请求与后台批处理任务。在请求突发期间，调度器应

</details>

---

## 排名信号

### LLM 推理  (17)

- **3.76** [antirez/ds4](https://github.com/antirez/ds4) — 兴趣匹配 +0.98, 热度 +0.96, 关注列表 +0.81  |  已出现过 -0.30
- **3.69** [JustVugg/colibri](https://github.com/JustVugg/colibri) — 热度 +0.99, 关注列表 +0.81, 兴趣匹配 +0.77  |  已出现过 -0.30
- **3.56** [ddalcu/mlx-serve](https://github.com/ddalcu/mlx-serve) — 多源印证 +1.05, 热度 +0.85, 关注列表 +0.81  |  已出现过 -0.30
- **3.13** [sqliteai/warp](https://github.com/sqliteai/warp) — 兴趣匹配 +0.96, 热度 +0.89, 关注列表 +0.81  |  已出现过 -0.30
- **3.06** [handy-computer/transcribe.cpp](https://github.com/handy-computer/transcribe.cpp) — 关注列表 +1.26, 兴趣匹配 +0.82, 热度 +0.71  |  已出现过 -0.30
- **2.83** [AlexsJones/llmfit](https://github.com/AlexsJones/llmfit) — 热度 +0.96, 兴趣匹配 +0.93, 多源印证 +0.70  |  已出现过 -0.30
- **2.78** [onPanda：通过 token 级修正高效标注 LLM 与 Agent 的 On-Policy 对齐数据](https://arxiv.org/abs/2609.24983) — 多源印证 +0.70, 技术深度 +0.68, 新鲜度 +0.67  |  已出现过 -0.06
- **2.66** [FareedKhan-dev/kimi-k3-in-c](https://github.com/FareedKhan-dev/kimi-k3-in-c) — 热度 +0.96, 技术深度 +0.90, 兴趣匹配 +0.79  |  已出现过 -0.30
- **2.57** [DeepSeek-V4.1-Flash：将 KV cache 压缩推向极限](https://arxiv.org/abs/2609.19969) — 热度 +0.73, 技术深度 +0.68, 新鲜度 +0.63
- **2.53** [VC-Attention：面向低比特注意力的值平滑与 Softmax 转换](https://arxiv.org/abs/2609.15810) — 技术深度 +0.77, 新鲜度 +0.60, 兴趣匹配 +0.58
- **2.51** [pegainfer-project/pegainfer](https://github.com/pegainfer-project/pegainfer) — 兴趣匹配 +1.49, 技术深度 +0.90, 热度 +0.40  |  已出现过 -0.30
- **2.50** [Flash-dLLM：IO 感知的 KV 缓存与并行解码，实现快速、省内存的扩散 LLM](https://arxiv.org/abs/2609.26796) — 兴趣匹配 +0.77, 技术深度 +0.77, 新鲜度 +0.68
- **2.44** [AKTS：面向语言模型 agent 的亚微秒级内核策略切换](http://arxiv.org/abs/2609.12276v1) — 兴趣匹配 +1.26, 技术深度 +0.90, 新鲜度 +0.58  |  已出现过 -0.30
- **2.42** [Weave：在 MoE megakernel 中进行细粒度动态 SM 调度以实现计算-通信重叠](http://arxiv.org/abs/2609.21483v1) — 兴趣匹配 +0.98, 技术深度 +0.85, 新鲜度 +0.65  |  已出现过 -0.06
- **2.33** [迈向面向 LLM 的全流程 FP8 强化学习](https://arxiv.org/abs/2609.22870) — 兴趣匹配 +0.79, 技术深度 +0.68, 新鲜度 +0.65
- **2.26** [Blaizzy/nativ](https://github.com/Blaizzy/nativ) — 热度 +0.82, 关注列表 +0.81, 兴趣匹配 +0.42  |  已出现过 -0.30
- **2.15** [实测焦耳，学习路由：面向高能效 LLM 服务的路由学习](http://arxiv.org/abs/2609.23085v1) — 兴趣匹配 +0.77, 技术深度 +0.72, 新鲜度 +0.66

### 编译器与语言  (10)

- **3.36** [NVlabs/cuda-oxide](https://github.com/NVlabs/cuda-oxide) — 兴趣匹配 +1.17, 技术深度 +0.90, 热度 +0.82  |  已出现过 -0.30
- **2.59** [nasa/spacewasm](https://github.com/nasa/spacewasm) — 关注列表 +0.81, 技术深度 +0.79, 热度 +0.79  |  已出现过 -0.30
- **2.39** [CodeMidas：从代码本身扩展 Agentic 编码 RL 环境](https://arxiv.org/abs/2609.22068) — 热度 +0.70, 技术深度 +0.68, 新鲜度 +0.64
- **2.37** [Tiga：大规模编译图消息传递](http://arxiv.org/abs/2609.24802v1) — 兴趣匹配 +0.96, 技术深度 +0.85, 新鲜度 +0.68  |  已出现过 -0.12
- **2.37** [BoundaryML/baml](https://github.com/BoundaryML/baml) — 关注列表 +0.81, 兴趣匹配 +0.70, 热度 +0.65  |  已出现过 -0.30
- **2.35** [弥合厂商鸿沟：面向 HL-LHC 时代，通过 ROCm/HIP 为 Awkward Array 提供 AMD GPU 支持](http://arxiv.org/abs/2609.24628v1) — 兴趣匹配 +0.93, 技术深度 +0.85, 新鲜度 +0.68  |  已出现过 -0.12
- **2.33** [基于 VLM 智能体的上下文内机器人学习](https://arxiv.org/abs/2609.19138) — 技术深度 +0.72, 新鲜度 +0.62, 兴趣匹配 +0.61
- **2.18** [GPU-CFR：通过将博弈编译为静态数据流并使用 CUDA Graph 重放，让反事实遗憾最小化提速 80 倍](http://arxiv.org/abs/2609.11923v1) — 兴趣匹配 +1.00, 技术深度 +0.90, 新鲜度 +0.57  |  已出现过 -0.30
- **2.15** [rhaiscript/rhai](https://github.com/rhaiscript/rhai) — 技术深度 +0.90, 关注列表 +0.81, 兴趣匹配 +0.56  |  已出现过 -0.30
- **2.15** [hypit-ai/hypit](https://github.com/hypit-ai/hypit) — 热度 +0.98, 兴趣匹配 +0.77, 技术深度 +0.40  |  已出现过 -0.30

### 机器学习研究  (4)

- **3.26** [RRSI：Agent harness 的正则化递归自我改进](https://arxiv.org/abs/2609.24972) — 热度 +0.73, 多源印证 +0.70, 技术深度 +0.68  |  已出现过 -0.06
- **2.53** [BI-Agent 与 BI-Bench：迈向端到端商业智能自动化](http://arxiv.org/abs/2609.20886v1) — 多源印证 +0.70, 技术深度 +0.68, 新鲜度 +0.63  |  已出现过 -0.18
- **2.38** [The Tasteful Agent：衡量并提升长程任务中的品味](https://arxiv.org/abs/2609.25804) — 新鲜度 +0.68, 热度 +0.68, 技术深度 +0.68
- **2.14** [ScienceIDE：将世界科学代码库转化为智能体可学习的环境](https://arxiv.org/abs/2609.19134) — 技术深度 +0.68, 热度 +0.66, 新鲜度 +0.62

### 数据库  (2)

- **3.24** [EvoOntology：面向数据 agent 的自演化本体层](http://arxiv.org/abs/2609.15779v1) — 技术深度 +0.77, 兴趣匹配 +0.75, 热度 +0.72  |  已出现过 -0.30
- **2.54** [naw103/foremerge](https://github.com/naw103/foremerge) — 热度 +0.77, 兴趣匹配 +0.70, 新鲜度 +0.68  |  已出现过 -0.12

### 数据工程  (1)

- **3.01** [firecrawl/anydoc](https://github.com/firecrawl/anydoc) — 热度 +0.99, 关注列表 +0.81, 兴趣匹配 +0.68  |  已出现过 -0.30

### 开发工具  (3)

- **2.92** [xai-org/grok-build](https://github.com/xai-org/grok-build) — 热度 +0.99, 关注列表 +0.81, 兴趣匹配 +0.68  |  已出现过 -0.30
- **2.71** [编码 agent 的 harness 设计实证研究](https://arxiv.org/abs/2609.20804) — 多源印证 +0.70, 技术深度 +0.68, 热度 +0.66  |  已出现过 -0.30
- **2.13** [fallow-rs/fallow](https://github.com/fallow-rs/fallow) — 热度 +0.83, 技术深度 +0.79, 兴趣匹配 +0.77  |  已出现过 -0.30

### 操作系统内核  (3)

- **2.78** [rivet-dev/agentos](https://github.com/rivet-dev/agentos) — 技术深度 +0.90, 兴趣匹配 +0.86, 关注列表 +0.81  |  已出现过 -0.30
- **2.58** [astrid-runtime/astrid](https://github.com/astrid-runtime/astrid) — 兴趣匹配 +1.05, 热度 +0.91, 技术深度 +0.90  |  已出现过 -0.30
- **2.11** [立场：是时候用自演化的操作系统层来虚拟化基础模型了](http://arxiv.org/abs/2609.19203v1) — 兴趣匹配 +0.93, 技术深度 +0.85, 新鲜度 +0.63  |  已出现过 -0.30

### AI 智能体  (4)

- **2.76** [redhat-et/ripwire](https://github.com/redhat-et/ripwire) — 兴趣匹配 +1.12, 热度 +0.89, 技术深度 +0.75  |  已出现过 -0.30
- **2.60** [justrach/codegraff](https://github.com/justrach/codegraff) — 兴趣匹配 +0.84, 热度 +0.70, 多源印证 +0.70  |  已出现过 -0.30
- **2.20** [SoL-Pi：递归扩展自动研究循环以打造高效的 Agent Harness](https://arxiv.org/abs/2609.20519) — 热度 +0.71, 技术深度 +0.68, 新鲜度 +0.63
- **2.12** [EvolveTrade：面向自演化 LLM 交易 agent 的经验驱动策略优化](https://arxiv.org/abs/2609.17632) — 技术深度 +0.68, 新鲜度 +0.61, 热度 +0.49

### 虚拟化  (2)

- **2.75** [elliothux/open-compute](https://github.com/elliothux/open-compute) — 技术深度 +0.90, 热度 +0.88, 兴趣匹配 +0.84  |  已出现过 -0.30
- **2.49** [t8y2/dbx](https://github.com/t8y2/dbx) — 热度 +0.96, 多源印证 +0.70, 技术深度 +0.68  |  已出现过 -0.30

### 科学计算  (2)

- **2.60** [AI 研究智能体的递归自我改进](http://arxiv.org/abs/2609.26457v1) — 多源印证 +0.70, 新鲜度 +0.69, 技术深度 +0.68  |  已出现过 -0.06
- **2.40** [面向 LLM 助手的可验证社会推理](https://arxiv.org/abs/2609.17496) — 技术深度 +0.68, 热度 +0.62, 新鲜度 +0.61

### GPU 与高性能计算  (11)

- **2.59** [DeepSeek Elastic Compute（DSec）：用于大规模高效 Agentic 训练的沙箱基础设施](http://arxiv.org/abs/2609.22978v1) — 兴趣匹配 +1.12, 技术深度 +0.81, 新鲜度 +0.66
- **2.53** [openlake-project/openlake](https://github.com/openlake-project/openlake) — 兴趣匹配 +1.12, 技术深度 +0.85, 热度 +0.79  |  已出现过 -0.30
- **2.48** [将逻辑 mask 与 GPU 执行解耦，实现动态块稀疏注意力](http://arxiv.org/abs/2609.25869v1) — 兴趣匹配 +1.00, 技术深度 +0.85, 新鲜度 +0.69  |  已出现过 -0.06
- **2.40** [仅有采样数量还不够：候选生成策略塑造了 LLM 测试时扩展的能耗与性能](https://arxiv.org/abs/2609.19499) — 技术深度 +0.72, 新鲜度 +0.62, 兴趣匹配 +0.58
- **2.39** [KerColle：释放视觉-语言-动作模型中的细粒度 GPU 并发](http://arxiv.org/abs/2609.22335v1) — 兴趣匹配 +0.91, 技术深度 +0.85, 新鲜度 +0.63
- **2.34** [xuzhougeng/wisp-science](https://github.com/xuzhougeng/wisp-science) — 兴趣匹配 +1.42, 热度 +0.75, 技术深度 +0.68  |  已出现过 -0.30, 技术浅 -0.40
- **2.29** [检验检查器：面向 GPU kernel benchmark oracle 的变异分析](https://arxiv.org/abs/2609.22220) — 兴趣匹配 +0.89, 技术深度 +0.85, 新鲜度 +0.50
- **2.16** [加速缓解跨 GPU 架构的 LLM 推理不确定性](http://arxiv.org/abs/2609.25624v1) — 兴趣匹配 +0.77, 技术深度 +0.77, 新鲜度 +0.68  |  已出现过 -0.06
- **2.12** [Video DeltaNet：面向直播视频生成的视频原生混合注意力](https://arxiv.org/abs/2609.20744) — 技术深度 +0.72, 新鲜度 +0.63, 热度 +0.58
- **2.11** [Conduit：面向分布式强化学习的经验数据平面](http://arxiv.org/abs/2609.24456v1) — 技术深度 +0.81, 兴趣匹配 +0.75, 新鲜度 +0.68  |  已出现过 -0.12
- **2.10** [l0ng-ai/tty7](https://github.com/l0ng-ai/tty7) — 热度 +0.75, 技术深度 +0.74, 兴趣匹配 +0.70  |  已出现过 -0.30

### 安全  (4)

- **2.57** [duty1g/x64dbg-mcp-server](https://github.com/duty1g/x64dbg-mcp-server) — 兴趣匹配 +1.00, 热度 +0.93, 技术深度 +0.51  |  已出现过 -0.30
- **2.50** [sunblaze-ucb/exploitgym](https://github.com/sunblaze-ucb/exploitgym) — 关注列表 +0.81, 兴趣匹配 +0.72, 热度 +0.67  |  已出现过 -0.30
- **2.47** [文档检索感知分块（D-RAC）：通过 PDF 规范化与多模态 Markdown 转换实现企业文档的通用检索感知摄取](https://arxiv.org/abs/2609.24220) — 技术深度 +0.72, 新鲜度 +0.67, 热度 +0.59
- **2.22** [RiskChainBench：一个面向混淆平台消息还原与证据支撑网络调查的 Benchmark](https://arxiv.org/abs/2609.16900) — 技术深度 +0.72, 新鲜度 +0.61, 热度 +0.56

### 嵌入式与硬件  (2)

- **2.46** [tursodatabase/turso](https://github.com/tursodatabase/turso) — 技术深度 +0.90, 热度 +0.82, 兴趣匹配 +0.75
- **2.42** [面向 agentic 智能的大规模基于代码的 grounded 技能合成](https://arxiv.org/abs/2609.05571) — 技术深度 +0.72, 热度 +0.67, 新鲜度 +0.52

### 分布式系统  (2)

- **2.46** [Nehanth/swarmllm](https://github.com/Nehanth/swarmllm) — 兴趣匹配 +1.17, 热度 +0.80, 新鲜度 +0.49  |  已出现过 -0.30
- **2.14** [Mesh-LLM/mesh-llm](https://github.com/Mesh-LLM/mesh-llm) — 兴趣匹配 +0.91, 热度 +0.77, 技术深度 +0.74  |  已出现过 -0.30

### WebAssembly  (1)

- **2.32** [ruvnet/RuVector](https://github.com/ruvnet/RuVector) — 兴趣匹配 +1.12, 热度 +0.76, 技术深度 +0.74  |  已出现过 -0.30

### 可观测性  (3)

- **2.23** [Realtime-Venus：支持异步委派的全双工交互系统](https://arxiv.org/abs/2609.13814) — 热度 +0.74, 技术深度 +0.72, 新鲜度 +0.58
- **2.20** [Asymptote-Labs/agent-beacon](https://github.com/Asymptote-Labs/agent-beacon) — 热度 +0.70, 多源印证 +0.70, 技术深度 +0.56  |  已出现过 -0.18
- **2.14** [PACT：企业 AI 助手在压力下是否值得信赖？](https://arxiv.org/abs/2609.18605) — 技术深度 +0.68, 新鲜度 +0.62, 热度 +0.49

### 图形与媒体  (2)

- **2.21** [VideoGen-Agent：强化视频生成 agent](https://arxiv.org/abs/2609.24997) — 技术深度 +0.68, 新鲜度 +0.67, 热度 +0.49
- **2.13** [Complex KDA：理解并增强 Kimi Delta Attention 的表达能力](https://arxiv.org/abs/2609.24797) — 多源印证 +0.70, 技术深度 +0.68, 新鲜度 +0.67  |  已出现过 -0.06

### 机器人  (1)

- **2.18** [将 VLM 的智能迁移到机器人控制](https://arxiv.org/abs/2609.22966) — 技术深度 +0.68, 热度 +0.67, 新鲜度 +0.65

### 桌面与界面  (2)

- **2.14** [RecreationWorld：面向混合式 Computer-Use Agent 的可扩展、可验证环境](https://arxiv.org/abs/2609.22000) — 技术深度 +0.68, 新鲜度 +0.64, 热度 +0.64
- **2.12** [tinyhumansai/openhuman](https://github.com/tinyhumansai/openhuman) — 热度 +0.97, 多源印证 +0.70, 兴趣匹配 +0.51  |  已成名 -0.19, 已出现过 -0.30

### 其他  (4)

- **2.46** [simonw/llm-typesafe](https://github.com/simonw/llm-typesafe) — 关注列表 +0.81, 新鲜度 +0.69, 热度 +0.66
- **2.34** [信心源于经验：从推理到 agent 的经验式置信度估计](https://arxiv.org/abs/2609.17708) — 技术深度 +0.68, 热度 +0.63, 新鲜度 +0.61
- **2.22** [mizorewww/laya-mlx](https://github.com/mizorewww/laya-mlx) — 热度 +1.00, 新鲜度 +0.66, 兴趣匹配 +0.61  |  已出现过 -0.24
- **2.21** [simonw/llm-keys-ui](https://github.com/simonw/llm-keys-ui) — 关注列表 +0.81, 新鲜度 +0.67, 热度 +0.42

