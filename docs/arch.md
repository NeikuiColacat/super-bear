# Super Bear 技术架构与技术选型 v0.2

## 0. 设计目标

Super Bear 是一个面向 Nasdaq-100 / 美国科技股普通投资者的事件情报系统。

它不是交易终端，不是买卖信号引擎，也不是投资顾问。它要做的是：

```text
从多源材料中发现事件
把事件拆成可验证声明
把声明绑定到原文证据片段
判断证据是否充分、冲突或过期
每天给用户 3-5 条低压力、可追溯的事件简报
```

这版架构的目标是 **model-resilient**：未来 GPT-6 / GPT-7 或更便宜、更强的模型发布时，我们只替换模型路由、prompt 和抽取策略，不重写来源、证据、时间、预算和合规骨架。

一句话原则：

```text
LLM 负责理解和提出候选；
系统负责验证、记账、追溯、约束和发布。
```

## 1. 总体架构

采用 11 层架构：

```text
1. Source Registry
2. Deterministic Ingestion
3. RawStore + RunManifest
4. Document / Chunk / Span
5. LLM-Assisted Extraction
6. Deterministic Validation
7. Claim-Evidence Ledger
8. Sufficiency / Conflict / Temporal Validity Checks
9. Super Bear Tool/API Surface + External Investigator Harness + Result Validation
10. Ranking + Diversity Control
11. EventCard / Daily Brief
```

中文解释：

| 层 | 名字 | 作用 | 是否依赖 LLM |
|---|---|---|---|
| 1 | 来源注册表 | 管理 SEC、IR、新闻、搜索、行情等来源和合规策略 | 否 |
| 2 | 确定性数据接入 | 用 API/RSS/允许的抓取方式获取数据 | 否 |
| 3 | 原始数据存储 + 运行记录 | 保存 raw payload、hash、运行结果、错误 | 否 |
| 4 | 文档 / 文档块 / 证据片段 | 把原始材料切成可引用的单位 | 否 |
| 5 | LLM 辅助信息抽取 | 抽实体、事件候选、claim 候选、evidence span 候选 | 是，低成本模型 |
| 6 | 确定性校验 | 校验 schema、char offset、source、time、family | 否 |
| 7 | 声明-证据账本 | 记录 event、claim、evidence 的可审计关系 | 否 |
| 8 | 充分性 / 冲突 / 时间检查 | 判断证据够不够、是否冲突、是否过期 | 规则为主，强模型辅助 |
| 9 | 工具/API + 外部调查器 + 结果校验 | 把底层能力暴露给 Claude Code、Copilot CLI、OpenCode 等 harness，并校验返回结果 | 外部 harness 可用 LLM，但 Super Bear 做最终校验 |
| 10 | 排序 + 多样性控制 | 从候选事件中选出最值得看的少数事件 | 规则为主，LLM 可 rerank |
| 11 | 事件卡片 / 每日简报 | 输出用户可读的 3-5 条事件卡片 | LLM 可润色，但必须引用 ledger |

## 2. 核心对象模型

核心对象链路：

```text
Document -> Chunk / Span -> Event -> Claim -> EvidenceSpan -> EventCard -> Briefing
```

### Document

一篇标准化文档。可以来自 SEC filing、公司 IR、新闻稿、搜索结果、行情上下文等。

最低字段：

```text
doc_id
source_id
source_type
source_tier
source_family_id
title
url
published_at
retrieved_at
raw_object_uri
content_hash
parser_version
language
entities
```

### Chunk / Span

文档里的可引用文本单位。

```text
chunk_id or span_id
doc_id
text
char_start
char_end
section_label
content_hash
```

`Chunk` 可以稍长，用于读取和检索；`Span` 要更精确，用于证据引用。

### Event

稳定事件对象，不等于单篇文章。

```text
event_id
canonical_title
event_type
entities
event_time
status: new | developing | corrected | refuted | resolved
related_doc_ids
claim_ids
evidence_status: sufficient | insufficient | conflicting | abstained
```

### Claim

一个可以被支持、反驳、更新或弃答的事实声明。

```text
claim_id
event_id
claim_text
claim_type: fact | forecast | opinion | rumor
mandatory: bool
status: supported | refuted | missing | conflicting | obsolete
```

### EvidenceSpan

核心证据单位。用户看到的事实句必须能追到这里。

```text
span_id
doc_id
claim_id
relation: support | refute | update | uncertain
text
char_start
char_end
source_type
source_tier
source_family_id
published_at
valid_from
valid_to
confidence
```

### ModelRun

每一次 LLM 调用的审计记录。

```text
model
prompt_version
input_tokens
output_tokens
cache_hit_tokens
cache_miss_tokens
cost_estimate
latency_ms
schema_validation_status
source_doc_ids
output_object_ids
```

`RunManifest` 记录数据管道怎么跑；`ModelRun` 记录模型理解怎么跑。

### InvestigatorRun

每一次外部 agent harness 调用的审计记录。

```text
investigator_run_id
harness_name
harness_version
adapter_version
model_name
prompt_version
allowed_actions
query_budget
read_budget
token_budget
latency_budget_ms
input_event_ids
input_claim_ids
input_evidence_span_ids
tool_calls
output_object_ids
stop_reason
abstained
validation_status
```

`ModelRun` 记录单次模型调用；`InvestigatorRun` 记录一次完整外部调查流程。

## 3. 数据接入层

第一批必接来源来自 `docs/get_info.md`：

```text
1. SEC EDGAR
2. 公司 IR / press release / earnings release
3. YFinance 或 OpenBB-yfinance
4. Tavily
5. Brave Search
6. Stock Sentiment API
```

### Source Registry

Source Registry 不是简单的 URL 列表，而是来源政策表。

最低字段：

```text
source_id
source_name
source_type
source_tier
source_family_id
license_type
storage_allowed
redistribution_allowed
full_text_allowed
derived_only
rate_limit_policy
default_output_kind
```

### 6 类来源的角色

| 来源 | 主要产物 | 在系统里的角色 |
|---|---|---|
| SEC EDGAR | Document | 一手监管披露，最高优先级证据 |
| 公司 IR / press release | Document | 公司一手声明和财报材料 |
| YFinance / OpenBB-yfinance | MarketContext | 行情和基本市场上下文，不作为事实事件证据 |
| Tavily | SearchLead | Agent/调查器的搜索线索 |
| Brave Search | SearchLead | 独立搜索线索和补证据入口 |
| Stock Sentiment API | AttentionSignal | 弱信号，只能触发关注，不能独立证明事实 |

### 接入原则

```text
优先 API / RSS / SEC / 公司 IR
受限新闻默认不镜像全文
搜索结果先存 metadata、URL、snippet、hash
社交舆情只能作为 weak signal
所有来源都必须记录 retrieved_at 和 content_hash
```

## 4. LLM-Assisted Extraction

低成本长上下文模型改变了第 4 层设计：不再优先堆传统 NLP 和 embedding 工具，而是让便宜模型批量做 schema-bound extraction。

### 低成本模型适合做

```text
实体候选抽取
事件候选抽取
claim 候选拆解
evidence span 候选定位
SEC / IR section 标注
新闻和公告的语义去重候选
事件卡片草稿
```

### 低成本模型不适合做

```text
source license 判断
stable ID 生成
char offset 最终校验
ticker / CIK 硬匹配
价格和成交量计算
事实最终裁决
投资建议
```

### 推荐模型分工

| 任务 | 推荐模型层 |
|---|---|
| 大规模文档结构化抽取 | cheap / flash model |
| section、entity、claim、span 候选 | cheap / flash model |
| 事件合并候选判断 | cheap model，困难样本再 strong model |
| sufficiency / conflict / stale 判断 | strong / pro model + rule |
| 复杂证据包裁决 | strong / pro model |
| 最终 brief 合规审阅 | strong / pro model 或规则检查 |

### Prompt 和输出要求

所有 LLM 输出必须：

```text
使用固定 JSON schema
记录 prompt_version
记录 ModelRun
通过 Pydantic validation
引用 source_doc_ids
引用原文 char_start / char_end 或 span_id
失败可重跑
```

LLM 输出默认是 `candidate`，只有通过 deterministic validation 才能进入 ledger。

## 5. Deterministic Validation

这层负责把模型的“候选理解”变成可落账对象。

必须检查：

```text
JSON schema 是否通过
doc_id 是否存在
char_start / char_end 是否真的对应原文
source_type / source_tier / source_family_id 是否来自 Source Registry
published_at / retrieved_at / event_time 是否为 timezone-aware datetime
ticker / CIK / issuer 是否能匹配 registry
claim_type 是否为允许枚举
evidence relation 是否为允许枚举
```

没有通过校验的候选不能进入 Claim-Evidence Ledger。

## 6. Claim-Evidence Ledger

这是项目的核心资产。

它要回答：

```text
这个事件是什么？
这个事件有哪些必须 claim？
每个 claim 是否被支持？
支持它的证据是哪一段原文？
证据来自哪个 source family？
证据是否过期或被更新？
有没有反证或冲突证据？
```

早期 MVP 可以先用 JSONL：

```text
data/events/events.jsonl
data/ledger/claims.jsonl
data/ledger/evidence_spans.jsonl
data/cards/event_cards.jsonl
data/briefs/YYYY-MM-DD.md
```

产品期再迁移到 PostgreSQL：

```text
documents
chunks
events
claims
evidence_spans
model_runs
ingestion_runs
source_registry
event_cards
briefings
user_feedback
```

不用一开始上 Neo4j。关系表已经足够表达 event graph / evidence graph。

## 7. Sufficiency / Conflict / Temporal Validity

这一层判断系统应不应该继续查、停止、还是弃答。

### Evidence status

```text
sufficient
insufficient
conflicting
stale
abstained
```

### 基础规则

```text
mandatory claims 必须被覆盖
关键事实必须有 source_tier 足够高的 evidence span
同一 source_family 的多条转载不能当成独立确认
存在 refute/update relation 时必须标记 conflict 或 stale
超过预算仍缺关键 claim 时必须 abstain
```

强模型可以参与判断，但输出必须引用 claim_id 和 evidence_span_id。

## 8. Super Bear Tool/API Surface and External Investigator Harness

Super Bear 不自研通用 Agent 框架。它提供证据系统、数据工具、校验器和审计记录；Claude Code、GitHub Copilot CLI、OpenCode、Kilo Code、nanobot、Langcli 或未来 GPT-6/7 agent 这类外部 harness 负责调用工具并返回结构化调查结果。

核心原则：

```text
harness proposes
Super Bear validates
Super Bear commits
```

外部 harness 不是事实来源，也不能直接写入 Claim-Evidence Ledger。

### 8.1 启动条件

外部调查器不是默认开启的深搜器，只在这些情况启动：

```text
证据不足
证据冲突
证据可能过期
事件重要但缺一手来源
需要独立来源确认
```

### 8.2 允许动作

允许动作固定为：

```text
SEARCH_PRIMARY_SOURCE
SEARCH_INDEPENDENT_CONFIRMATION
SEARCH_UPDATE_OR_CORRECTION
READ_DOCUMENT
EXTRACT_CLAIMS
VERIFY_EVIDENCE
CHECK_SOURCE_INDEPENDENCE
CHECK_TEMPORAL_VALIDITY
STOP
ABSTAIN
```

### 8.3 预算

每次运行必须带预算：

```text
query_budget
read_budget
token_budget
latency_budget_ms
```

### 8.4 Super Bear Tools

第一版工具层优先做成 Python API，然后包一层 CLI。

推荐工具：

```text
read_document(doc_id)
list_chunks(doc_id)
get_span(doc_id, char_start, char_end)
search_documents(query, source_type, time_range)
get_event(event_id)
get_claim(claim_id)
get_evidence_span(span_id)
check_source_independence(evidence_span_ids)
check_temporal_validity(evidence_span_ids)
validate_evidence_span(doc_id, text, char_start, char_end)
propose_claim(event_id, text, evidence_span_ids)
```

工具分两类：

```text
read-only tools: 读取 document / chunk / event / claim / evidence
proposal tools: 提交 claim/evidence/event 候选，但不直接落账
```

最终写入必须走 deterministic result validation。

### 8.5 Harness 输入契约

外部 harness 的输入应是一个 evidence pack，而不是开放问题。

```json
{
  "investigator_run_id": "investigator_run_...",
  "task_type": "verify_evidence_gap",
  "budgets": {
    "query_budget": 3,
    "read_budget": 5,
    "token_budget": 50000,
    "latency_budget_ms": 120000
  },
  "event_pack": {
    "event_id": "event_...",
    "claims": [],
    "evidence_spans": [],
    "open_questions": []
  },
  "allowed_actions": [
    "SEARCH_PRIMARY_SOURCE",
    "READ_DOCUMENT",
    "VERIFY_EVIDENCE",
    "STOP",
    "ABSTAIN"
  ]
}
```

### 8.6 Harness 输出契约

输出必须是结构化 JSON。

```json
{
  "status": "stop",
  "evidence_status": "sufficient",
  "new_claim_candidates": [],
  "new_evidence_span_candidates": [],
  "conflicts": [],
  "abstain_reason": null,
  "tool_calls": [],
  "citations": [
    {
      "claim_id": "claim_...",
      "evidence_span_id": "span_..."
    }
  ]
}
```

输出通过校验后，才允许更新 ledger。

### 8.7 暴露形态演进

不要一开始就上 MCP / plugin 全家桶。推荐顺序：

```text
1. Python API
2. CLI wrapper: stdin JSON -> stdout JSON
3. MCP server, when tool contracts stabilize
4. HTTP API, when product services need it
5. harness-specific skill/plugin packages as thin adapters
```

MCP、skill、plugin 都只是适配层，不是核心系统。

### 8.8 Harness 选择原则

可以替换的：

```text
Claude Code
GitHub Copilot CLI
OpenCode
Kilo Code
nanobot
Langcli
future GPT-6/7 agents
LangGraph
custom job state machine
```

不能替换的：

```text
Source Registry
RawStore
Claim-Evidence Ledger
Deterministic Validation
RunManifest
ModelRun
InvestigatorRun
budget enforcement
no-investment-advice guardrails
```

早期先实现 CLI adapter。只有当需要长流程恢复、多分支状态、人审和复杂工具编排时，再引入 LangGraph 或其他 durable harness。

## 9. Ranking + Diversity Control

排序要分开四件事：

```text
global event importance
evidence confidence
user relevance
diversity / redundancy control
```

早期使用可解释规则：

```text
source_confidence
novelty
scope
materiality
urgency
market_confirmation
impact_channel
rumor_risk
unresolved_conflict
watchlist_overlap
topic_fatigue
```

`market_confirmation` 只能作为上下文或排序信号，不能写成交易结论。避免把“相关”写成“导致”。

LLM 可以 rerank top-N，但最终排序要保留解释字段。

## 10. EventCard / Daily Brief

Brief 必须来自结构化 EventCard，不能直接从 raw news 生成。

EventCard 应包含：

```text
what happened
companies involved
evidence sources and source tiers
why it might matter
impact mechanism tags
uncertainties / missing evidence
whether to continue monitoring
user relevance explanation
claim_ids
evidence_span_ids
```

禁止输出：

```text
buy / sell / hold
target price
guaranteed return
portfolio instruction
unverified rumor as fact
analyst opinion as system fact
unsupported causal claim about price movement
```

## 11. 技术选型

### 2-3 天 vibe coding MVP

目标：跑通 `SEC Document -> Chunk/Span -> Claim -> EvidenceSpan -> EventCard -> Brief`。

推荐：

```text
Python 3.11+
Pydantic
YAML configs
JSONL outputs
filesystem RawStore
CLI runner
pytest
versioned prompts
ModelRun JSONL
InvestigatorRun JSONL
cheap / flash model for extraction
strong / pro model for adjudication
Python API for Super Bear tools
CLI wrapper: stdin JSON -> stdout JSON
```

暂不上：

```text
FastAPI
Next.js
PostgreSQL
pgvector
MinIO
Redis / Celery
Dagster
LangGraph
MCP server
HTTP API
harness-specific skills/plugins
OpenTelemetry
Prometheus
Sentry
Neo4j
GraphRAG
multi-agent teams
```

### Product mode later

当 JSONL pipeline 证明有用后，再逐步引入：

```text
FastAPI
PostgreSQL
SQLAlchemy or SQLModel
Alembic
pgvector when retrieval scale justifies it
S3 / MinIO for object storage
Dagster for scheduled deterministic jobs
LiteLLM or equivalent model gateway
MCP server when tool contracts stabilize
HTTP API when product services need it
harness-specific skill/plugin packages as thin adapters
LangGraph for durable investigator workflows
structured observability
```

### Research mode

研究路径必须可复现：

```text
fixed corpus snapshot
fixed index version
fixed model version
fixed prompt version
fixed budgets
stored trajectories
stable evaluation scripts
```

不要把 live-web-only 行为混进主 benchmark。

## 12. 传统技术栈如何降级

| 原设计 | v0.2 处理 |
|---|---|
| sentence-transformers | later / optional；先 URL/hash/title + LLM event merge |
| spaCy | later / optional；先 LLM entity candidates + registry 校验 |
| PyOD | later；先 deterministic abnormal return / volume ratio rules |
| BERTopic | later；周报/月报趋势再考虑 |
| pgvector | product mode later |
| Celery + Redis | later；先 CLI runner |
| FastAPI | later；先文件态 pipeline |
| MCP server | later；先 CLI contract |
| harness-specific skill/plugin | later；先稳定工具 schema |
| LangGraph | later；先 job state machine |
| OpenTelemetry / Prometheus / Sentry | later；先 RunManifest + ModelRun + JSON logs |
| Neo4j / GraphRAG | 不进 MVP |

这些技术不是没用，而是不要抢在证据闭环之前出现。

## 13. MVP 路线

### Step 1：当前已经开始

```text
Source Registry
SEC EDGAR adapter
RawStore
RunManifest
Document schema
JSONL writer
CLI preview
```

### Step 2：下一步最小闭环

```text
SEC Document
  -> Chunk / Span
  -> extraction candidates
  -> deterministic validation
  -> Claim
  -> EvidenceSpan
  -> Event
  -> EventCard
  -> brief markdown/html
```

成功标准：

```text
每个 EventCard 的 factual sentence 都能追到 claim_id + evidence_span_id
没有 evidence_span_id 的事实句不能进入 brief
没有通过 schema/char offset/source/time 校验的候选不能进入 ledger
```

### Step 3：再接更多来源

顺序：

```text
1. 公司 IR / press release / earnings release
2. YFinance 或 OpenBB-yfinance
3. Tavily
4. Brave Search
5. Stock Sentiment API
```

搜索和社交先作为线索层，不作为强证据层。

### Step 4：再暴露给外部 harness

顺序：

```text
1. Python tool functions
2. CLI wrapper: stdin JSON -> stdout JSON
3. read-only tools for document/chunk/claim/evidence
4. proposal tools for claim/evidence candidates
5. deterministic result validator
6. MCP server / HTTP API / skill-plugin adapters
```

外部 harness 的第一版目标不是“自动研究一切”，而是验证一个已有 `event_pack` 的证据缺口。

## 14. 架构不变量

未来模型再强，也不要删这些：

```text
Source Registry
RawStore
RunManifest
Document / Chunk / Span
stable IDs
content_hash
published_at / retrieved_at / event_time
source_type / source_tier / source_family_id
Claim-Evidence Ledger
ModelRun
InvestigatorRun
Super Bear tool/API contracts
budgets
STOP / ABSTAIN
deterministic result validation
no-investment-advice guardrails
```

未来模型越强，越应该删减或弱化这些：

```text
手写大量 NLP 规则
重型 topic modeling
过早向量数据库
复杂多 agent framework
绑定某一个外部 harness 的 glue code
复杂 GraphRAG
成熟产品级观测平台
```

这就是 v0.2 的核心取舍：**让模型层可替换，让证据层不可绕过。**
