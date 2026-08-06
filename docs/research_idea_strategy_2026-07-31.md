# 海量信息流中的高价值事件发现：单人研究路线评估

> 调研截止：2026-07-31
>
> 研究对象：Super Bear / `ns100_agent`
>
> 约束：单人、无长期金融专家合作、有限算力、需要可复现和可审计

## 0. 结论

第一篇论文最稳妥的定位不是纯 Method，也不是“金融事件投资价值”大 Benchmark，而是：

> **New Problem/Setting + Benchmark 主贡献 + 轻量可解释 Controller**

推荐主题暂称：

> **BEES-Stream: Budgeted Event-Evidence Sufficiency in Evolving Information Streams**

一句话故事：

> 现有 Search Agent benchmark 通常从一个 query 出发，评价最后是否答对；BEES-Stream 评价 agent 能否在持续变化的事件流中，把有限的 query/read/token/latency 预算分配给真正改变事件状态的信息，形成当前、独立、可追溯的 Claim-Evidence Ledger，并正确选择 `CONTINUE / STOP / ABSTAIN`。

这里的“高价值”必须限界为：

```text
对事件知识状态有增量价值
!= 对股票有投资价值
!= 会导致价格上涨或下跌
```

第一篇论文不应把主观的“值得投资者关注”当作 gold label。它应先研究可客观评测的 `event-state information gain`：新 claim、补充支持、独立确认、更新、纠正、反驳、过期，以及重复和同源噪声。

最终建议为 **Accept with Revisions，worth pursuing pending the pilot experiment**。

## 1. 冻结的研究问题

### RQ1

2024-2026 年的工作，哪些已经覆盖事件聚类、证据检索、时间有效性、搜索停止和成本控制？哪些组合能力仍没有被统一评测？

### RQ2

在没有金融专家长期合作时，哪些标签可以通过 SEC 元数据、原文 offset、时间、来源家族和受控 evidence pack 程序化构造？哪些标签不能声称是客观真值？

### RQ3

对当前仓库和单人资源而言，应选择 Benchmark、Method，还是 Benchmark + 轻量 Method？什么实验结果应触发转向？

## 2. 文献地形

### 2.1 信息流压缩与事件形成

- [Using LLM for Improving Key Event Discovery](https://aclanthology.org/2023.findings-emnlp.274/) 从新闻流中发现受媒体关注的 key events，但“媒体关注”不等于证据充分或投资价值。
- [From Moments to Milestones](https://aclanthology.org/2024.acl-long.390/) 研究 incremental event clustering 和 timeline generation，解决“信息属于哪个事件”，但不解决“是否值得继续调查”。
- [GlobeSumm](https://aclanthology.org/2024.emnlp-main.603/) 显式处理多来源事件摘要中的冲突、冗余和遗漏，但不包含主动搜索与预算停止。
- [Enhancing Event-centric News Cluster Summarization](https://aclanthology.org/2025.acl-long.801/) 结合动态聚类、event attribution 和 data sharpening，说明先形成事件簇再交给 LLM 是有效路线。
- [Synergizing Unsupervised Episode Detection with LLMs](https://aclanthology.org/2025.acl-long.1433/) 先用无监督结构发现 episode，再用 LLM 精炼，支持“确定性漏斗优先，agent 后置”的工程方向。
- [NEWSCOPE](https://aclanthology.org/2025.emnlp-main.1722/) 用 sentence-level clustering 和 diversity-aware reranking 提高互补信息覆盖，但 diversity 仍不等价于 claim sufficiency。
- [Agent Newsroom](https://aclanthology.org/2026.acl-long.1149/) 已在 token/time budget 下联合考虑 coverage、diversity、temporal grounding 和去重，是事件流侧的强最近邻。
- [TingIS](https://aclanthology.org/2026.acl-industry.147/) 报告了每日约 30 万条企业事件描述的级联处理架构，进一步说明海量数据不能逐条喂给 agent。

### 2.2 搜索、证据充分性与停止

- [FIRE](https://aclanthology.org/2025.findings-naacl.158/) 交替执行 claim verification 与 retrieval，并用当前判断置信度控制继续检索。
- [Search Wisely](https://aclanthology.org/2025.emnlp-main.998/) 将 over-search 和 under-search 与模型的知识边界不确定性联系起来。
- [Over-Searching in Search-Augmented LLMs](https://aclanthology.org/2026.eacl-long.361/) 说明噪声检索会放大 over-search，搜索还可能损害不可回答问题上的 abstention。
- [S2G-RAG](https://aclanthology.org/2026.acl-long.1185/) 已使用 structured sufficiency 和 gap items 驱动下一轮检索，是纯“结构化 gap judge”方法的直接最近邻。
- [Don't Stop Early](https://aclanthology.org/2026.acl-industry.116/) 使用显式 evidence sufficiency criteria 减少 deep research 的过早停止。
- [AutoSearch](https://aclanthology.org/2026.findings-acl.1399/) 研究 minimal sufficient search depth，进一步压缩了通用 QA stopping method 的新颖空间。
- [User-Centric Evidence Ranking](https://aclanthology.org/2026.eacl-long.340/) 优先呈现互补且充分的证据，减少用户阅读量，但默认候选证据已经存在。
- [To Search or Not to Search / DAS](https://arxiv.org/abs/2602.03304) 用反事实轨迹校准 search/answer decision boundary；截至本报告日期应按预印本处理。
- [MPW-Bench](https://arxiv.org/abs/2603.04751) 用平行世界和 1,608 个实例控制参数记忆、动态网页与搜索环境漂移，并直接指出 evidence sufficiency 和 when-to-stop 是瓶颈；截至本报告日期应按预印本处理。

### 2.3 时间与金融事件证据

- [Time Matters](https://aclanthology.org/2024.emnlp-industry.48/) 表明 evidence retrieval 和 verification 需要显式时间信息，不能只依赖语义相似。
- [Fin-RATE](https://arxiv.org/abs/2602.07294) 覆盖 SEC 跨文档、跨时期、跨公司的分析，暴露 time/entity mismatch，但任务仍是分析问答。
- [Grounded Event Extraction from SEC 8-K](https://arxiv.org/abs/2607.08346) 在 292,984 份 8-K 上生成 119 类、带原文 quote 的 event tags，证明大规模可审计抽取可行；它不评价搜索动作、来源独立性或停止决策。
- [Frontier Financial Judgement](https://arxiv.org/abs/2607.20645) 直接评价 stale、immaterial、misleading 和 valuation-relevant 新闻，但依赖专业股票分析师标签，说明“金融高价值”并不是适合单人自动构造的 gold。

## 3. 组件化空白

当前工作已经分别覆盖：

```text
event clustering
event timeline
diverse retrieval
claim verification
search/stop decision
temporal retrieval
cost-quality trade-off
```

本轮没有检索到同时统一以下维度的 benchmark 或 method：

```text
Event object
+ multiple mandatory claims
+ claim-evidence provenance
+ source-family independence
+ conflict and supersession
+ temporal validity
+ CONTINUE / STOP / ABSTAIN
+ query/read/token/latency budgets
+ downstream attention-limited shortlist
```

这只能支持“存在组件化空白”，不能单凭没有搜到就声称已经证明 novelty。

## 4. 三个候选 Idea

| Idea | 论文定位 | 专家依赖 | 预计人月 | 最大风险 | 结论 |
|---|---|---:|---:|---|---|
| BEES-Stream | New Problem/Setting + Benchmark | 低到中 | 4-6 | sufficiency 定义的 construct validity | 第一选择 |
| Ledger-VoI Controller | Method + 小型 replay suite | 低 | 4-5 | 与 S2G-RAG、DAS、AutoSearch 的差异不足 | 有条件的第二选择 |
| Progressive Disclosure | Temporal Benchmark / hard track | 低 | 2.5-4 | 过窄，可能被简单 latest-document 规则解决 | 作为 BEES-Stream hard track |

不推荐第一篇做：

```text
“从全部财经新闻中选出最有投资价值的 5 条”
```

它需要专家排序或真实用户研究；用价格波动、搜索热度或媒体数量替代 gold，会把 attention proxy 错写成真实价值。

## 5. 推荐方案：BEES-Stream

### 5.1 Paper Type

- 类型：**New Problem/Setting Paper，按 Benchmark/Evaluation 叙事**
- 主贡献：新的评测对象与协议
- 轻量 Controller：companion baseline，不在立项阶段声称 Novel Method

### 5.2 Benchmark 五支柱

| 支柱 | 设计 |
|---|---|
| Research Gap | 现有 Search Agent 从 query 出发；本任务从 evolving event state 出发，评价跨事件预算分配和 evidence sufficiency |
| Construction Pipeline | 从可回放 SEC/IR 文档、确定性元数据和原文 span 构造 event packs；受控注入 missing、duplicate、same-family、stale、update、refute 和 unanswerable 状态 |
| Evaluation Framework | 分离 retrieval、evidence-state judgment、stopping、abstention 和 budget compliance，避免单一 end-to-end 分数掩盖错误来源 |
| Empirical Findings | 比较不同 agent 在噪声、更新、来源独立性和预算压力下的能力边界；结果必须由实验产生，不能预写 |
| Companion Method | 一个 finite-state Coverage Controller 或 training-light Marginal Evidence Gain Controller |

### 5.3 三个 Track

#### Track A: Oracle Evidence Pack

给定完整候选文档池，只评价：

```text
claim coverage
evidence relation
source independence
temporal validity
STOP / ABSTAIN
```

这个 Track 用来回答：如果 retrieval 不再是瓶颈，agent 是否仍会错误判断“证据够了”。

#### Track B: Budgeted Retrieval Replay

给定 event lead、冻结索引和有限 action：

```text
SEARCH_PRIMARY_SOURCE
SEARCH_INDEPENDENT_CONFIRMATION
SEARCH_UPDATE_OR_CORRECTION
READ_DOCUMENT
VERIFY_EVIDENCE
CHECK_SOURCE_INDEPENDENCE
CHECK_TEMPORAL_VALIDITY
STOP
ABSTAIN
```

评价 agent 在不同预算下能否恢复正确 event evidence state。

#### Track C: Progressive Disclosure

按时间依次释放 initial filing、exhibit、amendment 和后续披露，评价：

```text
premature stop
obsolete citation
claim-level update
monitor versus stop
update delay
```

第一版不做 live web。先做 frozen snapshot + chronological replay，保证可复现。

### 5.4 Gold Label 分层

#### Gold-A：确定性标签

无需金融专家：

```text
accession / issuer / form / item / filing time
document hash and exact duplicate
source URL and source family
verbatim span and char offset
XBRL value, unit, period and filing
query/read/token/latency usage
withheld evidence and budget exhaustion
```

#### Gold-B：程序化或弱监督标签

必须单独报告质量：

```text
same-event relation
mandatory semantic claim
support / refute / update
valid_to / superseded_by
synthetic contradiction
optimal STOP / ABSTAIN
```

#### 不应作为第一版 Gold

```text
对普通投资者的真实重要性
长期商业影响
事件导致价格变化
买卖或收益判断
```

如果找不到专家合作者，仍建议请 2 名普通标注者独立核对一小批“claim 是否被原文明确支持”。这不是金融判断，不要求专家共同研究；如果连独立复核也做不到，第一版只保留 Gold-A 和极窄的表单规则任务。

### 5.5 评价指标

主指标建议：

```text
Success@Budget
```

只有在以下条件同时满足时算成功：

```text
mandatory claim state correct
evidence span valid
source-family accounting correct
temporal state correct
STOP or ABSTAIN correct
no budget violation
```

诊断指标：

```text
Mandatory-Claim Coverage at Stop
Evidence Span Precision / Recall
Source-Independence Accuracy
Temporal-Validity Accuracy
Conflict / Update F1
Unsupported-Stop Rate
Under-search Rate
Over-search Cost
Abstain Calibration
Budget Violation Rate
Utility-Budget Curve
```

不要把 query、read、token、latency 合成一个无法解释的总成本后只报一个数字。应分别报告固定预算曲线，再提供一个预先声明的归一化 utility。

### 5.6 强基线

最小 baseline matrix：

```text
no-search
random action
always-search
fixed-depth
primary-first deterministic policy
LLM prompt-only self-stop
S2G-style structured gap judge
confidence-based stop
finite-state ledger controller
hindsight oracle
```

模型不需要铺满几十种。第一版应优先覆盖：

```text
1-2 个开源小模型
1 个开源强模型
2 个闭源 frontier model
```

## 6. 轻量 Companion Controller

事件 `e` 的 deficit 可以定义为：

```text
Deficit(e) =
    mandatory_claim_gap
  + conflict_penalty
  + stale_evidence_penalty
  + source_independence_gap
```

动作 `a` 的 Marginal Evidence Gain：

```text
MEG(e, a) =
    P(valid_new_evidence | state, action)
  * expected_deficit_reduction
  / normalized_action_cost
  - redundancy_penalty
```

决策规则：

```text
if all mandatory claims are current and sufficiently supported:
    STOP
elif all feasible actions have non-positive MEG:
    ABSTAIN
elif budget cannot cover any valid action:
    ABSTAIN
else:
    execute argmax_a MEG(e, a)
```

第一版可使用 Logistic Regression、LightGBM 或小型 contextual bandit 预测 evidence yield，不需要训练 LLM。

只有当它在 held-out 时间、公司和 event type 上稳定优于透明规则，才把论文升级为 Method-led。否则它就是 benchmark 的 companion baseline。

## 7. Idea-Evaluator 审稿

### 7.1 First Impression

- Paper type：New Problem/Setting + Benchmark
- One-sentence story：评价 agent 能否在 evolving event streams 中，用有限预算形成当前、独立、充分的事件证据状态，并正确停止或弃答。

### 7.2 Fatal-Flaws Audit

| Flaw | Severity | Defense |
|---|---|---|
| F1：通用 stopping 和 sufficiency 方法在 2026 年已经拥挤 | MAJOR | 把贡献限定在 event-conditioned ledger state、source family、temporal validity 和 multi-budget protocol，不声称首次研究 search stopping |
| F6/F7：mandatory claims 和 high-value gold 可能不可验证 | MAJOR | 核心集仅使用表单、XBRL、时间、offset 和受控 pack 的客观标签；主观金融价值移出 benchmark |

不存在已确认的 CRITICAL flaw，但两个 MAJOR 必须通过 pilot 和数据审计消除。

### 7.3 Lifecycle and Capability Match

以下判断假设单人每周可投入 15-25 个有效小时，已有 Python 工程能力和有限 API 预算。

| Aspect | Assessment |
|---|---|
| Idea category | Data-Intensive New Setting / Benchmark |
| Lifecycle | 4-6 个月完成可投稿版本，8-9 个月完成更完整版本 |
| Engineering fit | Green，当前 repo 已有 ledger、validator 和 investigator contract |
| Data fit | Yellow，需冻结数据、定义 split、验证许可和做质量抽检 |
| Research fit | Yellow，必须持续跟踪 2026 新工作并严格限界 novelty |

### 7.4 Five-Dimension Radar

分数均为 mechanism-based，尚未由实验确认。

| Dimension | Score | Evidence | 提升方式 |
|---|---:|---|---|
| Higher | 7 | 结构化 claim/evidence state 比仅看最终答案更可诊断 | 用 Oracle Pack 与 Open Retrieval 分离错误来源 |
| Faster | 8 | 四类预算和 stopping 是主任务 | 报告完整 utility-budget frontier |
| Stronger | 9 | 显式覆盖 conflict、stale、source independence 和 abstain | 构造困难 slice 和 counterfactual consistency test |
| Cheaper | 8 | 大量 Gold-A 可程序化构造，controller 不训练大模型 | 限制语义标签规模，进行分层审计 |
| Broader | 7 | event-evidence protocol 可迁移到企业情报、公共事件和安全告警 | 第一版先 SEC-only，第二版再做跨域验证 |

### 7.5 Paradigm-Shift Probe

| Probe | 判断 | 理由 |
|---|---|---|
| First Principles | Yes | 不再默认每个 query 都值得完整搜索，而是从有限 attention budget 出发 |
| Elephant in the Room | Yes | agent 最终答对并不代表搜索过程经济、证据独立或时间有效 |
| Technology Cycle | Yes | LLM agent 已可执行搜索，但缺少可审计的 stopping 和 abstention protocol |
| Hamming's Rule | Partial | 能推动可靠 search agent evaluation，但第一版不会改变全部事件智能研究 |

Disruptive potential：**possible**，不是已证明。

### 7.6 Feasibility

| Risk | Level | Mitigation |
|---|---|---|
| Compute | Low-Medium | training-light controller；冻结 source pool；限制 frontier model matrix |
| Data | Medium-High | SEC-only 起步；发布 ID、URL、hash、offset 和重建脚本，避免分发受限全文 |
| Engineering | Medium | 先补 benchmark runner、evaluator、trajectory store，不先做 web SaaS |
| Timeline | Medium | 先完成 100-200 个 pilot tasks，通过 gate 后再扩到 1,200+ |

### 7.7 Verdict

**Accept with Revisions，worth pursuing pending the validation experiment。**

## 8. Benchmark 还是 Method

### 默认选择

按 **Benchmark/Evaluation** 立项，附轻量 controller。

理由：

1. 当前 repo 的独特资产是 Claim-Evidence Ledger、确定性 validation、时间字段和 bounded investigator contract，而不是可直接声称新颖的模型算法。
2. 2025-2026 年通用 stopping 方法已经出现 FIRE、Search Wisely、DAS、S2G-RAG、AutoSearch 和 evidence-aware termination；纯 Method 更容易被认为是已有方法的事件领域组合。
3. “金融高价值” Benchmark 需要专家，但“事件证据充分性”可以用大量客观、程序化标签构造。
4. 一个好的 benchmark 可以成为后续 learned controller、ranking 和 brief-change triage 的共同实验基础。

### 转为 Method-led 的 Gate

只有 pilot 同时满足以下条件才转：

```text
1. fixed-depth、primary-first 和 prompt-only stop 明显落后
2. learned MEG controller 在多个预算档位同时降低 under-search 和 over-search
3. 增益在 held-out company、time 和 event type 上保持
4. 去掉 source independence 或 temporal validity 后性能显著下降
5. 简单规则与 learned controller 的置信区间不重叠
```

如果这些条件不成立，保留 Benchmark 叙事，不为了 Method 故事更换指标或扩大模型。

## 9. 决定性 Pilot

### 数据

```text
10-20 家 Nasdaq-100 公司
3-6 个月 SEC 8-K / exhibit / amendment
100-200 个 replayable event packs
每个 pack 3-8 个 mandatory atomic claims
```

### Slice

```text
complete
missing evidence
same-family duplicates
stale or superseded
conflicting or negative evidence
unanswerable after budget exhaustion
```

### Baseline

```text
fixed-depth
primary-first
prompt-only self-stop
finite-state ledger controller
MEG controller
oracle
```

### Kill Criteria

出现任一情况就缩题或转向：

```text
Oracle Pack 上强模型接近饱和，无法区分系统
primary-first 规则在所有 slice 上与 learned controller 持平
mandatory claims 无法通过客观规则稳定定义
自然 update/refute 样本数量过少且受控注入不能通过质量审计
数据许可不允许可复现发布
```

## 10. 3 / 6 / 9 个月路线

### 0-3 个月：验证题目是否成立

```text
冻结 SEC-only corpus
实现 benchmark schema 和 chronological replay
实现 Gold-A 标签与 6 个 diagnostic slices
跑 5-6 个 baseline
完成 kill-criteria review
```

### 4-6 个月：形成可投稿版本

```text
扩到 1,200-2,000 instances
完成 time/company/event-family split
加入 Progressive Disclosure hard track
完成普通标注者小样本独立复核
实现 finite-state 或 MEG companion controller
完成主要 ablation 和 error taxonomy
```

### 7-9 个月：增强论文而不扩散范围

```text
增加跨模型和跨预算曲线
完成 contamination 和 duplicate audit
发布 data card、rebuild scripts、trajectory schema
可选增加一个非金融公开事件域验证 protocol transfer
```

## 11. 与当前仓库的映射

- 架构对象与 11 层目标见 [`docs/arch.md`](arch.md)。
- 当前 evidence checker 已能输出 missing、conflicting 和 stale，但还没有 mandatory claim、source tier 与 source-family sufficiency，见 [`packages/evidence/checker.py`](../packages/evidence/checker.py)。
- bounded actions 和 query/read/token/latency budgets 已进入 contract，见 [`packages/harness/contracts.py`](../packages/harness/contracts.py)。
- 当前 event assembler 还不是跨来源、可版本化的稳定 event identity，见 [`packages/events/assembler.py`](../packages/events/assembler.py)。
- 当前 briefing 直接渲染 cards，尚未实现 ranking、MMR 或 top-k attention budget，见 [`packages/briefing/markdown.py`](../packages/briefing/markdown.py)。

这些资产足以支持 benchmark pilot，但不足以把现有 `sufficient` 状态直接当作论文 gold。

## 12. 首先不要做的事

```text
不要把全部每日文档逐条交给 agent
不要把股价变化当作事件价值或因果 gold
不要在第一篇同时声称 benchmark、强新方法、完整产品和用户研究
不要先做 live web benchmark
不要用同一事件的转载跨 train/test
不要把 SEC、SEC-hosted exhibit 和公司 IR 自动算成三个独立来源
不要用 LLM-as-a-judge 作为全部核心 gold
```

## 13. 最先执行的三个动作

1. 写出 `event pack`、`mandatory claim slot`、`evidence state` 和 `STOP/ABSTAIN` 的正式 benchmark schema。
2. 手工加程序化构造 30 个高质量 pilot packs，先检查任务是否真的能区分 `fixed-depth`、`primary-first` 和 `prompt-only`。
3. 只有 pilot 通过 kill criteria 后，再批量扩数据和实现 MEG controller。
