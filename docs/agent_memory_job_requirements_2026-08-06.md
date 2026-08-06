# 大厂 Agent Memory 岗位需求与 Super Bear 应聘定位调研

> 调研日期：2026-08-06
>
> 目标：归纳腾讯、字节跳动、百度、阿里等公司的 Agent Memory 相关招聘要求，并判断 Super Bear 项目应如何补强、包装和用于求职。

## 1. 结论摘要

Super Bear 可以作为 Agent 方向的核心应聘项目，但目前最匹配的岗位不是“纯基础模型 Memory 研究员”，而是以下方向：

1. Search Agent / Deep Research Agent 算法工程师；
2. Agent Evaluation、Agent 可靠性与事实性评测；
3. RAG 应用算法、知识工程与上下文工程；
4. Agent Harness、Runtime、Tool Use 与 Agent Infra；
5. 大模型应用算法工程师。

项目当前最大的竞争力，是将 Agent 设计成一个具有来源、时间、证据、冲突状态和预算约束的可审计系统，而不是一个只会调用工具或把历史对话写入向量数据库的 Demo。

但目前不能把项目描述为已经完成的“通用 Agent Memory 系统”。仓库尚缺少：

- 跨会话用户/Agent 长期记忆；
- 通用 Memory 写入、合并、更新、替代和遗忘生命周期；
- BM25、向量、混合检索、重排和上下文构建；
- LongMemEval、LoCoMo 等公开 Memory Benchmark 的结果；
- 与 No Memory、Full Context、Vector-only 等基线的消融实验；
- SFT、DPO、PPO、GRPO 或 Agentic RL 等模型训练能力。

因此，当前最诚实且有辨识度的项目定位是：

> **Super Bear：面向动态事件流的可审计 Search Agent 与时序 Claim-Evidence Ledger**

完成 Memory 扩展和评测后，可升级为：

> **Super Bear：面向长程 Search Agent 的可追溯分层记忆与预算化检索系统**

## 2. 调研范围与证据边界

本次调研围绕以下关键词展开：

- Agent Memory、长期记忆、短期记忆；
- RAG、混合检索、重排、上下文工程；
- Agent Harness、Runtime、Agent Infra；
- Agent Evaluation、Agentic RL；
- Long Context、Knowledge Base、Deep Research Agent。

证据使用规则：

- 优先使用公司官方招聘页、官方研究页和官方产品文档；
- 官方动态招聘页无法稳定读取时，使用带有原始职位信息的招聘镜像补全职责与要求；
- 已结束职位只用于观察能力要求，不代表当前仍可投递；
- 产品文档用于确认企业正在建设的技术能力，不把产品能力直接等同于招聘条件；
- 二手招聘平台的信息需要在正式投递前回到企业官网再次确认。

## 3. 代表性岗位样本

### 3.1 腾讯：微信大模型算法研究员——Agent

来源：

- [腾讯官方职位入口](https://careers.tencent.com/jobdesc.html?postId=2042508679395311616)
- [职位详情镜像，标注来源为腾讯招聘](https://jobs.niuqizp.com/job-vUl55CnzN.html)

岗位重点包括：

- Agent Harness 的调度、编排和执行上下文；
- 记忆写入、组织、检索与生命周期管理；
- 跨会话持久记忆；
- 端云协同的 Memory 架构；
- 对话状态、用户意图和上下文压缩。

典型要求包括：

- 计算机、电子、数学、机器学习等相关专业硕士及以上；
- 熟悉 PyTorch、Transformer；
- 在 Agent 编排、RAG 与记忆检索、长上下文或对话系统中至少有一项深入经验；
- 具备系统设计能力，能够平衡效果、性能、可扩展性和落地成本；
- 具备工程实现、沟通协作和快速原型能力。

加分项包括：

- NeurIPS、ICML、ICLR、ACL、EMNLP 等论文；
- Agent 或 Memory 开源项目贡献；
- MemGPT、Letta、LangGraph、mem0 等框架经验；
- 长上下文压缩、蒸馏、多 Agent 或端侧 Memory 经验。

对项目的启示：

腾讯把 Memory 视为完整生命周期，而不是单独的向量检索模块。Super Bear 的时序证据、更新关系和确定性提交机制与这一方向高度相关，但还需要补齐跨会话持久化、检索和遗忘。

### 3.2 腾讯：ima Copilot 大模型算法

来源：

- [牛客职位样本](https://www.nowcoder.com/jobs/detail/428221)

该职位样本涉及知识库问答，以及任务拆解、规划、工具使用和 Memory 优化。样本体现的门槛是硕士学历、3—5 年经验和实际产品落地能力。

该样本可能已经结束，因此只用于说明：知识库、RAG、Planning、Tool Use 和 Memory 经常被组合成同一个 Agent 岗位，而不是彼此独立招聘。

### 3.3 腾讯云：Agent Memory 产品能力

来源：

- [腾讯云 Agent Memory 产品文档](https://cloud.tencent.com/document/product/1813/132100)

该文档不是招聘信息，但可以用于观察企业实际产品中的 Memory 能力模型：

- 短期记忆与长期记忆分层；
- 上下文压缩与卸载；
- 关键词检索、向量检索和 RRF 融合；
- 记忆来源追踪、审计和纠错；
- 对任务效果、Token 和延迟的共同优化。

这说明“可追溯、可纠错、混合检索、Token 成本”已经属于工程化 Agent Memory 的核心问题。Super Bear 的 Claim-Evidence Ledger 可以自然延伸到这一方向。

### 3.4 字节跳动 Seed：通用 Agent、Code Agent 与强化学习

来源：

- [Seed 招聘主页](https://seed.bytedance.com/zh/career)
- [Top Seed 研究方向](https://seed.bytedance.com/zh/topseed)
- [Seed Early Career](https://seed.bytedance.com/zh/seedearlycareer)

官方页面展示的相关方向包括：

- 通用 Agent 算法；
- Code Agent；
- 强化学习；
- Multi-Agent；
- Test-time Scaling；
- 超长程 Agent 的奖励建模；
- Continual Agent；
- Learning to Use Memory。

Seed 更强调：

- 深入的技术洞察；
- 有代表性的研究或工程工作；
- 扎实的研究能力；
- 能把想法真正实现并验证的动手能力。

对项目的启示：

如果申请字节 Seed 的研究型岗位，仅有系统实现还不够。需要把 Super Bear 变成一个具有明确研究问题、公开 Benchmark、强基线、消融实验和可复现实验结果的项目。

### 3.5 字节跳动即梦：AI 算法工程师

来源：

- [LinkedIn 职位样本](https://cn.linkedin.com/jobs/view/ai%E7%AE%97%E6%B3%95%E5%B7%A5%E7%A8%8B%E5%B8%88-%E5%8D%B3%E6%A2%A6-at-%E5%AD%97%E8%8A%82%E8%B7%B3%E5%8A%A8-4365929887)

该职位样本已经结束，但技术要求覆盖面很有代表性：

- Agent Memory；
- Skills；
- Environment / Sandbox；
- Proactive Agent；
- 多模态 RAG；
- Agent Evaluation；
- SFT 合成数据；
- Agentic RL；
- Rubrics-based RL 和统一奖励。

常见基础要求包括：

- 本科及以上；
- 机器学习、深度学习和概率统计基础；
- 在至少一个相关方向拥有深入项目或研究经验；
- 熟悉 PyTorch；
- 训练方向需要 DeepSpeed、Megatron-LM 等经验；
- 良好的团队协作能力。

对项目的启示：

字节的算法岗位常把 Memory、环境、工具、评测和 Post-training 放在同一条 Agent 能力链中。Super Bear 当前覆盖环境约束、工具契约和评测设计，但不覆盖训练，因此应优先申请偏系统、应用算法和评测的岗位。

### 3.6 字节跳动火山方舟：豆包大模型 Agent 算法工程师

来源：

- [字节跳动官方职位入口](https://jobs.bytedance.com/experienced/position/7601811392853346613/detail)
- [职位详情镜像](https://watchjobs.net/zh/explore/job/BYTEDANCE_7601811392853346613/)

岗位关键词包括：

- Agentic RL 和 Post-training；
- Python、Linux 与生产环境开发；
- LangGraph、LlamaIndex、OpenAI Agents SDK、Google ADK；
- Context Management；
- ReAct、PlanAct、CodeAct；
- MCP、A2A、Function Calling；
- Agent 评测、检索和快速原型；
- 文档编写与跨团队协作。

对项目的启示：

框架经验是加分项，但岗位真正关心的是能否构建完整 Agent 链路、定义评测、控制上下文、接入工具，并在生产约束下稳定运行。Super Bear 应把框架适配层保持轻量，把 Claim-Evidence Ledger、预算和验证器作为核心。

### 3.7 百度：智能体算法工程师

来源：

- [百度智能体算法工程师](https://talent.baidu.com/jobs/detail/GRADUATE/cad8f67a-4118-4e26-a39d-0cc84f699f9d)

岗位职责包括：

- Agent 全链路设计；
- Planning、Reasoning 和 Tool Use；
- 长短期记忆；
- Multi-Agent；
- 同时评估效果、效率和资源成本。

典型要求包括：

- 本科及以上；
- 熟悉 ReAct、CoT、Plan-and-Execute；
- 熟悉 PyTorch、LangChain、AutoGen 等工具；
- 有早期产品、顶会论文或开源贡献者优先。

### 3.8 百度：Agent 全栈研发工程师

来源：

- [百度 Agent 全栈研发工程师](https://talent.baidu.com/jobs/detail/GRADUATE/6f9c3a86-6557-409d-8fa7-e6f4c68d6765)

岗位覆盖：

- Planning、Acting 和 Reflection；
- Tool / API 调用；
- 长短期记忆和状态管理；
- RAG + Agent；
- Multi-Agent；
- 成功率、稳定性、Token、调用成本、延迟和用户体验评测。

值得注意的是，该类岗位可以接受个人项目或课程项目，但项目必须能够运行、解释和量化验证。这类岗位与 Super Bear 的当前成熟度比较匹配。

### 3.9 百度：Agent 算法实习

来源：

- [百度 Agent 算法实习](https://talent.baidu.com/jobs/detail/INTERN/1a0bfe96-f59c-4384-9525-79fdf324c67f)

岗位关键词包括：

- Router、Plan、RAG、Tool Use 和 Deep Research；
- Pretrain、SFT、PPO、DPO、GRPO；
- 强化学习；
- Agent Evaluation 闭环。

典型要求包括：

- 硕士及以上；
- 熟悉 PyTorch、Transformer 和 Post-training；
- 顶会、竞赛和开源项目为加分项。

这类岗位比应用型 Agent 岗更偏模型算法。Super Bear 可以证明 Agent 系统和评测能力，但需要额外的训练项目或轨迹学习实验才能完全覆盖。

### 3.10 阿里：AI Agent 应用工程与算法岗位

来源：

- [阿里 Agent 应用工程职位样本](https://www.nowcoder.com/jobs/detail/440682)
- [阿里 Agent 算法职位样本](https://www.nowcoder.com/jobs/detail/440837)
- [阿里 AI Agent 校招职位样本](https://www.nowcoder.com/jobs/detail/442316)

这些二手职位样本反复出现以下要求：

- Python、Java、Go、JavaScript 或 TypeScript；
- Prompt、RAG、Function Calling；
- Agent Workflow、Context、Memory；
- MCP、Skills；
- LangChain、Dify 等框架；
- Planning、Reasoning、Tool Use、多 Agent；
- SFT、DPO、PPO、GRPO；
- 数据飞轮；
- Evaluation Metric、Rubric、LLM-as-a-Judge、离线评测和 A/B Test；
- 监控、降级和生产可用性。

学历要求通常是本科起步，算法研究倾向硕士或博士，优秀本科生可以通过开源、论文和高质量项目补偿。

由于这些链接不是阿里官方招聘页，正式投递前需要在阿里招聘官网核对职位是否仍开放以及职责是否更新。

### 3.11 蚂蚁：Agent 算法岗位样本

来源：

- [蚂蚁 Agent 算法岗位信息汇总](https://ai2.gdvzz.com/?p=recam-antgroup-recam-y26sp)

样本关键词包括：

- Agent Planning、Memory 和 Tool Use；
- 强化学习；
- SFT、RLHF；
- 模型推理优化；
- Agent Framework；
- Python。

本科通常是最低学历，开源贡献和顶会成果是重要加分项。该页面属于信息汇总页，应使用其提供的官方投递入口核验最终职位信息。

### 3.12 美团：长程 Agent 与长期记忆

来源：

- [美团算法岗位样本](https://www.nowcoder.com/jobs/detail/396132)

该职位样本涉及：

- Long-horizon Agent；
- 多模态和强化学习；
- 主动交互与不确定性处理；
- 长期记忆；
- 从经验到 Skill 的演化；
- 长文本、问答、知识图谱、推理和 Function Call。

该样本作为行业趋势补充使用，不代表职位当前开放。

## 4. 大厂 Agent Memory 岗位的共性能力模型

### 4.1 Memory 生命周期

企业所说的 Agent Memory 通常至少包括：

1. 判断什么值得记忆；
2. 从交互或轨迹中抽取事实、偏好、事件和经验；
3. 进行原子化、结构化、去重和归并；
4. 持久化并维护版本；
5. 根据当前任务检索和重排；
6. 将记忆压缩后放入有限上下文；
7. 处理更新、冲突、过期和遗忘；
8. 保留来源、时间、置信度和纠错链路。

因此，面试中不能把 Memory 简化成“把聊天记录 Embedding 后存入向量数据库”。向量数据库只是存储和召回组件，Memory 的核心是写入策略、生命周期、时间语义、冲突处理和任务效用。

### 4.2 RAG 与上下文工程

高频要求包括：

- 文档解析、Chunking 和 Embedding；
- BM25 与向量混合检索；
- RRF、Cross-encoder 或 LLM Reranker；
- 基于用户、任务、实体、时间和权限的过滤；
- Context Selection、Context Compression；
- Token Budget；
- 噪声召回、陈旧召回和同源重复证据控制。

项目展示时需要同时说明召回效果、错误类型、Token 成本和延迟，不能只展示“能够搜到结果”。

### 4.3 Agent 核心能力

常见关键词包括：

- ReAct；
- Plan-and-Execute；
- Reflection；
- Tool Use、Function Calling；
- MCP、Skills；
- Agent Runtime / Harness；
- State Management；
- Multi-Agent；
- 错误恢复和降级。

面试官通常更关心系统在工具失败、上下文超限、检索噪声和模型输出不合法时如何处理，而不仅是正常路径 Demo。

### 4.4 Agent Evaluation

Agent 岗位越来越强调量化评测。常见指标包括：

- Task Success Rate；
- Recall@k、MRR、nDCG；
- Memory 更新正确率；
- Temporal Reasoning Accuracy；
- Conflict Detection F1；
- Stale-memory Leakage；
- Abstention Accuracy；
- Token、Latency、Cost；
- 离线 Benchmark；
- CI Regression；
- A/B Test；
- Baseline 和 Ablation。

对于 Super Bear，最有辨识度的指标是：

- Success@Budget；
- 证据充分率；
- 错误提交率；
- 过期证据泄漏率；
- 冲突识别率；
- 达到相同正确率时的查询、读取、Token 和延迟成本。

### 4.5 模型算法与训练

偏算法和研究的岗位通常要求：

- Transformer 和 PyTorch；
- SFT、DPO、PPO、GRPO、RLHF；
- Agentic RL；
- Reward Model、Rubric 和统一奖励系统；
- Agent 轨迹数据构建；
- DeepSpeed、Megatron-LM、vLLM 等训练或推理栈。

如果没有真实训练经验，应明确把自己定位为 Agent 系统、检索、Memory 工程或 Evaluation，而不是声称覆盖 Foundation Model Post-training。

### 4.6 工程与生产化

高频基础要求包括：

- Python；
- Linux、Git；
- 部分岗位要求 Java、Go 或 TypeScript；
- 系统设计；
- 高并发、可扩展和生产稳定性；
- 日志、监控、审计和故障恢复；
- 文档和跨团队协作；
- 快速原型与持续迭代。

## 5. 学历与岗位分层

| 岗位类型 | 常见学历 | 真正决定竞争力的内容 |
| --- | --- | --- |
| 基础研究 / Memory Research | 硕士通常是门槛，博士更有优势 | 顶会论文、公开 Benchmark、新方法、训练和严谨实验 |
| Agent 应用算法 | 本科起步，硕士更常见 | PyTorch、RAG、Memory、Agent 全链路和量化结果 |
| Agent Evaluation / Reliability | 本科或硕士 | Benchmark、错误分类、基线、消融、自动回归评测 |
| Agent Infra / Harness / Runtime | 本科较常见 | 系统设计、工程质量、协议、状态、观测性和稳定性 |
| Agent 全栈应用 | 本科较常见 | 可运行产品、API、前后端、成本和用户体验 |
| 高级社招 | 学历之外常要求 3—5 年经验 | 生产落地、规模、团队协作和业务结果 |

学生或工作经验不足时，可以用以下内容补偿：

- 一个可一键运行的公开仓库；
- 公开 Benchmark 结果；
- 完整的 Baseline 和 Ablation；
- 清晰的架构文档；
- 真实失败案例；
- 可复现实验配置和日志；
- 有质量的开源贡献。

## 6. Super Bear 与岗位要求的对应关系

### 6.1 当前已经具备的能力

#### 类型化证据与领域模型

代码位置：

- `packages/core/schemas.py`

项目已经定义 Document、Chunk、Claim、EvidenceSpan、Event 等结构化对象，并保留来源、时间、字符偏移和状态字段。

对应岗位能力：

- Structured Memory；
- Knowledge Representation；
- Provenance；
- Temporal Context；
- Schema-bound Agent Output。

#### Claim-Evidence Ledger

代码位置：

- `packages/evidence/ledger.py`

Agent 或模型只负责提出候选事实，只有经过确定性验证的 Claim 和 EvidenceSpan 才能进入 Ledger。

对应岗位能力：

- Memory Write Gate；
- Fact Grounding；
- Auditable Agent；
- Hallucination Control；
- Deterministic Commit。

#### 证据验证与时间有效性

代码位置：

- `packages/evidence/validator.py`
- `packages/evidence/checker.py`

项目能够验证字符偏移、来源、时间和证据关系，并区分：

- sufficient；
- insufficient；
- conflicting；
- stale；
- support；
- refute；
- update。

对应岗位能力：

- Temporal Memory；
- Conflict Resolution；
- Stale Memory Detection；
- Evidence Sufficiency；
- Abstention。

#### 有预算的 Agent Harness

代码位置：

- `packages/harness/contracts.py`
- `packages/harness/validator.py`

项目为 Agent 定义有限动作，并限制：

- query budget；
- read budget；
- token budget；
- latency budget。

同时校验工具调用、引用、动作、STOP、ABSTAIN 和最终结果。

对应岗位能力：

- Agent Runtime / Harness；
- Tool Governance；
- Budgeted Search；
- Failure Containment；
- Agent Evaluation。

#### 确定性多源摄取

代码位置：

- `packages/ingestion/runner.py`

项目采用确定性摄取流程，保存 RawStore、RunManifest 和 JSONL 产物，并把 SEC、公司 IR、市场上下文、搜索线索和注意力信号区分开。

对应岗位能力：

- Data Pipeline；
- Source-aware RAG；
- Reproducibility；
- Audit Trail；
- Data Quality。

#### 只读 Agent 工具接口

代码位置：

- `packages/tools/read_api.py`

核心系统通过只读接口向外部 Agent 提供 Event、Claim、Evidence、Chunk 和 Event Pack，防止外部 Harness 直接写入核心 Ledger。

对应岗位能力：

- Tool API Design；
- Least-privilege Agent；
- Framework-neutral Core；
- MCP / CLI 适配基础。

#### 研究与评测设计

文档位置：

- `docs/arch.md`
- `docs/research_idea_strategy_2026-07-31.md`

项目已经设计冻结时间顺序回放、来源独立性、时间有效性、STOP / ABSTAIN 和 Success@Budget。

注意：其中部分内容仍是研究设计，不能在简历上写成已经获得实验结论。

### 6.2 当前明显缺口

| 岗位要求 | 当前状态 | 需要补强 |
| --- | --- | --- |
| 跨会话长期记忆 | 未实现 | 用户、任务、Agent 级持久 Memory |
| Memory 生命周期 | 部分具备 | WRITE、MERGE、UPDATE、SUPERSEDE、FORGET |
| 混合检索 | 未形成完整模块 | BM25、Dense、RRF、Reranker |
| Context Builder | 未实现 | 按任务价值和 Token 预算构建上下文 |
| 通用 Memory API | 未实现 | search、history、write decision、context |
| 公开 Memory Benchmark | 未完成 | LongMemEval、LoCoMo 子集 |
| Baseline 与 Ablation | 未完成 | No Memory、Full Context、Vector-only 等 |
| Agentic RL / Post-training | 未覆盖 | 独立训练实验或明确不作为主定位 |
| 生产数据库和服务 | MVP 阶段 | PostgreSQL、API、监控按实际需要推进 |

### 6.3 最适合投递的岗位顺序

当前版本建议按以下优先级投递：

1. Search Agent / Deep Research Agent；
2. Agent Evaluation / Agent Reliability；
3. RAG 应用算法 / 知识工程；
4. Agent Harness / Runtime / Context Engineering；
5. 大模型应用算法工程师；
6. 完成 Memory 扩展后，再重点投递 Agent Memory 工程或算法岗位；
7. 纯 Foundation Model Memory Research 岗，需要补论文、公开实验和模型训练。

## 7. 四周项目补强路线

### 第 1 周：实现 Memory 生命周期

建议新增 `packages/memory/`，定义：

- `MemoryRecord`；
- `MemoryEpisode`；
- `MemoryVersion`；
- `MemoryRelation`；
- `MemoryWriteDecision`；
- `MemoryQuery`；
- `MemoryRetrievalResult`。

定义明确动作：

- `WRITE`；
- `MERGE`；
- `UPDATE`；
- `SUPERSEDE`；
- `FORGET`；
- `ABSTAIN_WRITE`。

每条 Memory 保留：

- 来源文档和 EvidenceSpan；
- 事件时间、写入时间和有效时间；
- 置信度；
- 版本；
- 更新、冲突和替代关系；
- 写入决策理由。

### 第 2 周：实现混合检索与上下文构建

实现：

- BM25；
- Dense Retrieval；
- RRF；
- 时间、实体、任务和来源过滤；
- 可选 Reranker；
- 短期 Working Memory；
- 长期 Retrieved Memory；
- Token-budgeted Context Builder。

提供框架无关的核心 API：

- `search_memory`；
- `get_memory_history`；
- `build_context`。

在核心稳定后，再增加 LangGraph 或 MCP 薄适配层。不要让框架成为领域逻辑。

### 第 3 周：建立 Benchmark 与消融实验

至少比较以下基线：

1. No Memory；
2. Full Context；
3. Vector-only；
4. BM25-only；
5. Hybrid Retrieval；
6. Temporal Ledger Memory。

建议指标：

- Recall@k；
- MRR；
- Temporal Update Accuracy；
- Conflict Detection F1；
- Stale-memory Leakage；
- Abstention Accuracy；
- Success@Budget；
- Token、Latency、Cost。

测试数据：

- Super Bear 自建冻结金融事件流；
- LongMemEval 子集；
- LoCoMo 子集。

所有实验必须固定：

- 数据快照；
- 索引版本；
- 模型版本；
- Prompt 版本；
- 查询、读取、Token 和延迟预算。

### 第 4 周：形成可面试演示和实验报告

演示需要回答：

- Agent 过去记住了什么；
- 新证据到来后，什么结论发生了变化；
- 哪条旧记忆已经被替代；
- 为什么召回这条记忆；
- 为什么某条信息没有写入；
- 为什么系统选择 ABSTAIN；
- 相比 Full Context 节省了多少 Token；
- 为什么 Vector-only 会召回过期信息。

最终交付物：

- 一张清晰架构图；
- 一张 Benchmark 总表；
- 一张消融表；
- 3—5 个失败案例；
- 一条命令完成复现实验；
- README 中的 3 分钟快速体验。

## 8. 简历写法

### 8.1 当前版本的项目名称

> Super Bear：面向动态事件流的可审计 Search Agent 与时序 Claim-Evidence Ledger

### 8.2 当前可以使用的简历要点

- 设计并实现 `Document → Chunk → Claim → EvidenceSpan → Event` 的 Claim-Evidence Ledger，保留字符级证据偏移、来源等级、来源家族和时间有效性，实现事实结论的可追溯与可审计。
- 构建 SEC、公司 IR、市场数据、搜索线索和注意力信号的确定性多源摄取流程，区分 primary evidence、search lead 与 market context，阻止未验证 Agent 输出直接写入核心 Ledger。
- 设计预算约束的 Agent Harness，以有限动作和 query/read/token/latency budget 约束外部 Agent，并对工具调用、引用、STOP、ABSTAIN 和证据充分性执行确定性校验。
- 设计冻结时间顺序回放评测，覆盖证据更新、冲突、来源独立性、时间过期和预算化停止；混合检索与长期 Memory 实验正在补充。

最后一条必须保留“设计”或“正在补充”，除非实验已经真实运行并得到结果。

### 8.3 完成 Memory 扩展后的项目名称

> Super Bear：面向长程 Search Agent 的可追溯分层记忆与预算化检索系统

完成实验后，可按真实数据写结果：

> 在 LongMemEval 与自建事件流 Benchmark 上，相比 Vector-only Baseline，将时间更新准确率提高 X%，过期记忆泄漏降低 Y%，同时减少 Z% Context Token。

其中 X、Y、Z 必须来自可复现实验，不得预先编造。

### 8.4 30 秒面试介绍

> 我没有把 Agent Memory 简化成向量数据库。在动态事件中，我把长期记忆建模成具有来源、时间和更新关系的 Claim-Evidence Ledger。Agent 只负责提出候选内容，确定性验证器决定能否提交；检索和停止行为受查询、读取、Token 和延迟预算约束。这个设计主要解决错误记忆、过期记忆、同源重复证据和无依据输出。下一步是补齐混合检索、跨会话生命周期，并在 LongMemEval 和冻结事件流上做基线与消融。

## 9. 面试时需要能讲清楚的问题

1. Memory 和 RAG 的区别是什么？
2. 为什么 Vector-only Memory 会失败？
3. 系统如何判断一条信息值得写入？
4. 新旧事实冲突时，是覆盖、保留还是建立版本关系？
5. 如何区分“事件发生时间”“文档发布时间”“Memory 写入时间”和“有效时间”？
6. 如何防止同一家媒体的多篇转载被当成独立证据？
7. 为什么 Agent 不能直接写 Claim-Evidence Ledger？
8. STOP 和 ABSTAIN 的区别是什么？
9. 如何证明 Memory 改善了任务效果，而不是仅增加 Token？
10. 如何测量过期记忆泄漏？
11. 为什么选择 BM25 + Dense + RRF，而不是只用向量检索？
12. Reranker 应该放在哪里，如何衡量它是否值得增加延迟？
13. 如何在 Token Budget 下选择上下文？
14. 如何设计 No Memory、Full Context 和 Vector-only 基线？
15. 如果模型、Agent 框架或向量数据库更换，哪些核心模块不应变化？

## 10. 建议使用的公开 Memory 研究与 Benchmark

### LongMemEval

- 论文：[LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory](https://arxiv.org/abs/2410.10813)

评测长期交互中的信息抽取、多会话推理、时间推理、知识更新和拒答能力。可用于验证跨会话 Memory 的读取、更新和 Abstention。

### LoCoMo

- 论文：[Evaluating Very Long-Term Conversational Memory of LLM Agents](https://aclanthology.org/2024.acl-long.747/)

包含长对话、多 Session、问答、事件总结和多模态线索，适合比较 Full Context、RAG 和结构化 Memory。

### MemGPT

- 论文：[MemGPT: Towards LLMs as Operating Systems](https://arxiv.org/abs/2310.08560)

提出分层记忆和虚拟上下文管理。它适合用作系统设计参考，但项目需要进一步解决来源、时间、冲突和确定性提交。

### APEX-MEM

- 论文：[APEX-MEM](https://aclanthology.org/2026.acl-long.749/)

可关注其结构化时序表示、追加式记忆、检索时冲突处理和紧凑摘要设计。

### LongMemEval-V2

- 论文：[LongMemEval-V2](https://arxiv.org/abs/2605.12493)

把 Memory 扩展到 Web Agent 环境中的静态状态、动态状态、工作流、环境陷阱和前提感知，和 Search Agent / Deep Research Agent 的长期记忆更接近。

## 11. 最终求职策略

短期内，优先把 Super Bear 投向 Agent Evaluation、Search Agent、RAG 和 Agent Infra 岗位，因为这些方向与项目已有资产最一致。

项目补强的优先级应为：

1. Memory 生命周期；
2. 混合检索；
3. Token-budgeted Context Builder；
4. 公开 Benchmark；
5. Baseline 和 Ablation；
6. 可复现演示；
7. 根据目标岗位决定是否补 Agentic RL。

如果目标是腾讯微信类 Agent Memory 岗，应重点强调：

- 跨会话 Memory；
- 写入、组织、检索和生命周期；
- 时间更新和冲突；
- 端云或可扩展系统设计；
- Provenance 和纠错。

如果目标是字节 Seed 或偏研究岗位，应重点补：

- 明确研究问题；
- 强基线；
- 公开数据集；
- 消融实验；
- 统计可靠的结果；
- 训练或 Agentic RL 经验；
- 论文式技术报告。

如果目标是百度、阿里等应用型 Agent 岗，应重点展示：

- 一键运行的完整系统；
- RAG、Memory、Tool Use 和 Evaluation 闭环；
- Token、延迟、成本和成功率；
- 错误恢复、监控和稳定性；
- 真实失败案例和修复过程。

最终要让面试官看到的不是“我调用了某个 Agent 框架”，而是：

> 我能够定义 Agent 的事实边界、记忆生命周期、检索策略、预算约束和评测方法，并把这些设计实现成一个可运行、可审计、可复现的系统。
