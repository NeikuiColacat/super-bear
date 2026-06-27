下面是一版面向你们项目的 **技术架构与技术选型计划 v0.1**。我按“能快速做出 MVP，同时为后续事件证据链和 Agent 深搜预留空间”的原则设计。

结论先放前面：

> **不要把系统做成一个纯 Agent。应该做成“数据挖掘筛选 + 事件/证据图结构化 + Agent 深搜验证 + 每日低负担推送”的混合架构。**

`daily_stock_analysis` 和 `OpenBB` 都值得复用，但角色不同：

```text
daily_stock_analysis = 应用层参考 / 可复用外壳
OpenBB = 金融结构化数据 adapter
RSSHub / changedetection.io = 信息源传感器
pgvector / sentence-transformers / spaCy = 低成本数据挖掘和结构化抽取
LangGraph / open_deep_research = Agent 深搜流程参考
你们自己实现 = 事件图、证据链、归因判断、个性化排序
```

## 一、目标系统定位

你们要做的不是普通股票日报，也不是普通舆情监控，而是：

> **面向 watchlist 的金融事件情报系统：每天从大量新闻、公告、监管文件和市场数据中筛出 3–5 条最值得看的事件，并给出可追溯证据链和简短影响解释。**

用户最终看到的不是“长报告”，而是类似：

```text
事件：
A 公司与 B 公司签订供货协议。

为什么重要：
B 是大型存储公司，该协议可能提高市场对 A 后续订单的预期。

市场反应：
A 在公告后两个交易日相对行业上涨 7.1%，成交量为 30 日均值 2.4 倍。

证据：
1. A 公司 IR 公告
2. Newswire 新闻稿
3. B 公司背景资料

归因强度：
Plausible。同期还有分析师上调评级，因此不能写成强因果。
```

这类任务的技术关键不是“让 Agent 多搜”，而是：

```text
海量信息 → 候选事件 → 证据包 → Agent 验证 → 每日推送
```

## 二、总体架构

推荐采用 8 层架构：

```text
1. Source Adapter Layer
   SEC / IR / Newswire / RSS / 政府源 / OpenBB / FRED / 搜索 API

2. Data Gateway Layer
   统一 provider 接口、限流、缓存、字段标准化、原始数据留存

3. Raw Item Store
   保存原始 RSS item、HTML、PDF、JSON、filing、搜索结果

4. Mining & Extraction Layer
   去重、ticker 匹配、实体识别、事件类型抽取、embedding 聚类、价格异动检测

5. Event & Evidence Graph Layer
   event、entity、document、claim、evidence、price_move 结构化

6. Agent Investigation Layer
   只对 top-N 候选事件做深搜、补证据、反证检查、归因判断

7. Digest & Feedback Layer
   每日 3–5 条事件卡片，Telegram/Email/Slack 推送，用户反馈回流

8. Observability & Governance Layer
   token 成本、source 健康、agent 失败率、证据覆盖率、用户反馈、日志和 trace
```

核心设计原则：

```text
便宜层先筛选
结构化层先压缩
Agent 只处理少量高价值事件
所有 claim 都要能回溯到 source
```

## 三、GitHub 高 star 项目复用规划

### 1. daily_stock_analysis：作为应用层外壳和参考，不作为核心事件引擎

`daily_stock_analysis` 是非常值得拆的项目。它的定位是多市场股票智能分析系统：每日分析自选股，生成决策仪表盘，并推送到企业微信、飞书、Telegram、Discord、Slack 或邮箱。它支持多源行情、新闻舆情、LLM 决策报告和自动推送。项目本身是 MIT License。([GitHub][1]) ([GitHub][2])

建议复用：

```text
watchlist 配置
定时任务
通知渠道
LLM provider 配置
搜索 provider 设计
历史报告存储
WebUI / dashboard 思路
token usage dashboard 思路
```

不建议直接复用为核心：

```text
事件抽取
证据链
因果归因
source authority
agent 搜索停止策略
```

原因是它的主线是“股票分析报告”，不是“事件证据链”。它可以成为 MVP 外壳，但你们要重写事件层。

### 2. OpenBB：作为金融结构化数据 adapter，必须隔离使用

OpenBB 的定位是开放金融数据平台，用来把 proprietary、licensed、public data sources 接入 Python、REST API、MCP、Excel、OpenBB Workspace 和 AI agent。它强调 “connect once, consume everywhere”。([GitHub][3])

建议用途：

```text
历史行情
公司 profile
财务指标
部分基本面
宏观或 provider 数据
Agent 金融数据工具层
```

但 OpenBB 本身采用 AGPL-3.0，商业闭源产品要谨慎。OpenBB 仓库 license 明确写主仓库文件使用 GNU Affero GPL v3.0。([GitHub][4])

建议做法：

```text
内部 MVP：可以直接用
商业化：作为独立 adapter service 隔离部署，必要时购买商业许可或替换 provider
长期：不要让核心数据模型依赖 OpenBB
```

### 3. RSSHub：作为外围 RSS 适配器，不合入核心闭源代码

RSSHub 的价值是“Everything is RSSible”，可以把大量网站转换成 RSS。它适合做长尾信息源接入，尤其是没有标准 RSS 的网站。RSSHub 是 AGPL-3.0。([GitHub][5])

建议用途：

```text
新闻源适配
公司页面的 feed 化
中文互联网信息源接入
长尾 RSS route
```

建议部署方式：

```text
Sidecar service
不要复制 route 代码进核心闭源后端
所有进入主系统的数据都重新标准化和留存来源
```

### 4. changedetection.io：作为公司 IR / 监管网页变化检测 sidecar

changedetection.io 专门做网页变化监控和告警，适合没有 RSS 的公司 IR 页面、监管页面、交易所公告页面。官方仓库定位是 website change detection、web page monitoring 和 website change alerts。([GitHub][6])

建议用途：

```text
公司 IR 页面变化
Investor events 页面变化
presentation / webcast 页面变化
监管机构页面变化
交易所公告页面变化
```

它不负责解释变化，只负责把变化转成 webhook event。

### 5. TrendRadar：舆情/热点监控参考，不建议直接作为核心

TrendRadar 是高 star 的 AI 舆情与趋势监控项目，支持多平台热点聚合、AI 筛选、翻译、分析简报、MCP 分析能力和多渠道推送。它是 GPL-3.0。([GitHub][7])

建议用途：

```text
参考热点聚合逻辑
参考 AI 简报体验
参考通知渠道和用户配置
```

不建议：

```text
直接合入商业闭源核心
把它作为金融事件证据链系统
```

### 6. Huginn / n8n：仅作为工作流参考或外围集成

Huginn 是老牌自托管自动化系统，官方说它能让 agents read the web、watch for events、take actions，并沿 directed graph 创建和消费 events。([GitHub][8])

n8n 是工作流自动化平台，支持 400+ integrations 和 native AI capabilities，但采用 Sustainable Use License / Enterprise License。([GitHub][9]) ([GitHub][10])

建议：

```text
Huginn：参考 event graph / trigger 设计
n8n：可用于外围通知、Notion、邮件、Slack 等 glue workflow
```

不建议：

```text
把核心事件聚类、证据链和 Agent 触发策略写进 n8n
把 Huginn 当作核心后端
```

### 7. LangGraph / open_deep_research：作为 Agent 深搜流程参考

LangGraph 是面向 long-running、stateful agents 的低层编排框架。([GitHub][11])

open_deep_research 是 LangChain 开源的 deep research agent，支持多模型、搜索工具和 MCP servers。([GitHub][12])

建议用途：

```text
Agent 状态机
搜索 / 阅读 / 归纳 / 验证流程
深搜任务可恢复
tool-calling 约束
多步骤 evidence collection
```

不建议：

```text
直接让 open_deep_research 处理所有新闻
直接生成长报告
```

你们应该把它改成“事件证据验证器”，而不是通用研究报告机。

## 四、推荐技术选型

### 1. 后端和任务系统

| 模块      | 推荐             | 原因                                                                                                      |
| ------- | -------------- | ------------------------------------------------------------------------------------------------------- |
| API 服务  | FastAPI        | Python 生态好，适合数据和 LLM 工程；FastAPI 是基于 Python type hints 的高性能 API 框架。([GitHub][13])                        |
| 任务队列    | Celery + Redis | 适合 daily batch、抓取、解析、agent job；Celery 是成熟分布式任务队列，BSD License。([GitHub][14])                             |
| 长流程编排   | 暂不上 Temporal   | 只有当 agent 任务需要跨小时恢复、人工确认、复杂重试时再上；Temporal 强在 durable execution 和自动恢复。([GitHub][15])                     |
| 批处理 DAG | 暂不上 Airflow    | Airflow 适合复杂 DAG 和生产数据平台；MVP 阶段 Celery 足够。Airflow 本身用于 author、schedule、monitor workflows。([GitHub][16]) |

第一阶段不要上 Kafka、Temporal、Airflow。否则会被平台工程拖慢。

### 2. 存储和检索

| 模块   | 推荐                    | 原因                                                                          |
| ---- | --------------------- | --------------------------------------------------------------------------- |
| 主数据库 | PostgreSQL            | 事件、source、claim、用户反馈、任务状态都适合关系模型                                            |
| 向量检索 | pgvector              | pgvector 是 PostgreSQL 的开源向量相似度搜索扩展，可直接用 Postgres client 查询向量。([GitHub][17]) |
| 原文快照 | S3 / MinIO            | 保存 HTML、PDF、TXT、JSON、RSS raw payload                                        |
| 全文检索 | MVP 先用 PostgreSQL FTS | 后续数据量大再上 OpenSearch                                                         |
| 图数据库 | 暂不上 Neo4j             | MVP 用关系表表达 event graph / evidence graph 即可                                  |

推荐的数据表中心不是 `article`，而是：

```text
source
raw_item
document
entity
event
claim
evidence_link
price_move
event_attribution
digest_item
user_feedback
```

### 3. 数据挖掘和信息抽取

| 模块               | 推荐                       | 用途                                                                                  |
| ---------------- | ------------------------ | ----------------------------------------------------------------------------------- |
| Embedding / 语义相似 | sentence-transformers    | 新闻去重、事件聚类、用户 thesis 匹配；该框架用于计算 embeddings、similarity scores、reranker。([GitHub][18]) |
| NER / 规则 NLP     | spaCy                    | 公司、人名、产品、监管机构、时间和数字抽取；spaCy 是生产级 NLP 库，MIT License。([GitHub][19]) ([GitHub][20])    |
| 异常检测             | PyOD                     | 新闻量异常、成交量异常、价格异动候选；PyOD 覆盖 tabular、time series、graph、text 等异常检测。([GitHub][21])      |
| 主题建模             | BERTopic 可选              | 周报/月报主题趋势；BERTopic 用 transformers + c-TF-IDF 做可解释主题聚类。([GitHub][22])                |
| 结构化事件抽取          | 规则 + LLM JSON extraction | 供货协议、合作、并购、监管、诉讼、财报等事件抽取                                                            |

不要一开始训练模型。MVP 用规则、embedding、LLM structured extraction 足够。

### 4. 金融数据和事件源

优先级如下。

| 优先级 | 数据源                                | 作用                                                                                                                  |
| --- | ---------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| P0  | SEC EDGAR                          | filing、8-K、10-Q、10-K、Form 4、13D/G，一手证据。SEC 当前 fair access 速率为 10 requests/second。([证券交易委员会][23])                    |
| P0  | SEC RSS                            | 最新 filing 增量发现；SEC RSS 用于跟踪 EDGAR filings 等最新材料。([证券交易委员会][24])                                                     |
| P0  | Newswire RSS                       | GlobeNewswire、PR Newswire、Business Wire，用作事件触发器                                                                     |
| P0  | 公司 IR 页面/RSS                       | 财报、presentation、webcast、投资者活动、一手公司材料                                                                                |
| P0  | Federal Register / FTC / DOJ / BIS | 监管、反垄断、出口管制、政策变化                                                                                                    |
| P1  | FRED / ALFRED                      | 宏观背景；FRED API 用于程序化获取经济数据。([联邦储备经济数据][25])                                                                          |
| P1  | OpenBB                             | 结构化金融数据 adapter                                                                                                     |
| P1  | Tavily / Brave Search              | Agent 搜索补证据；Tavily 面向 AI agents/RAG，Brave Search API 基于独立 Web index 并用于 agentic search。([Tavily][26]) ([Brave][27]) |
| P2  | GDELT                              | 外部新闻、地缘、供应链、跨语言发现                                                                                                   |
| P2  | 付费行情 / 新闻源                         | 商业化后再接                                                                                                              |

第一版重点不要放在“行情平台多接几个”，而是先把 **SEC + Newswire + IR + 政府监管源** 做好。

### 5. 反馈和可观测性

| 模块                       | 推荐                                                                                                    |
| ------------------------ | ----------------------------------------------------------------------------------------------------- |
| 推送与反馈                    | Telegram first，Email fallback，后续 Slack/飞书                                                             |
| 用户反馈                     | Telegram Inline Keyboard，Bot API 支持 callback query。([Telegram  API][28])                              |
| Tracing / metrics / logs | OpenTelemetry；它是 vendor-neutral observability framework，可导出 traces、metrics、logs。([OpenTelemetry][29]) |
| Metrics / alert          | Prometheus + Alertmanager；Prometheus 支持时序数据、PromQL 和 alerting。([Prometheus][30])                      |
| Error tracking           | Sentry；Sentry 用于错误追踪和性能问题定位。([GitHub][31])                                                            |

要从第一天记录：

```text
source_poll_success_rate
parse_failure_rate
raw_items_ingested
duplicate_ratio
event_cluster_count
agent_trigger_count
agent_token_cost
digest_delivery_success
user_feedback_rate
citation_check_pass_rate
```

## 五、核心数据流设计

### Daily batch 主流程

MVP 不做强实时，先做 daily batch：

```text
每天固定时间启动
    ↓
抓取过去 24h SEC / Newswire / IR / 政府源 / 搜索结果 / 行情
    ↓
raw_items 入库
    ↓
URL/hash 去重
    ↓
ticker/entity 匹配
    ↓
embedding 聚类成 event_candidates
    ↓
价格异动和成交量 join
    ↓
source authority + watchlist relevance + novelty 打分
    ↓
选 top 10–20 个候选事件
    ↓
Agent 对每个候选做低 token 证据验证
    ↓
选出 3–5 条 digest cards
    ↓
推送并收集反馈
```

### 后续轻量增量监控

第二阶段加轻量 sentinel：

```text
SEC：30–60 分钟一次
Newswire：30–120 分钟一次
核心 IR：2–6 小时一次
政府源：2–6 小时一次
普通新闻搜索：日报前集中跑
```

注意：轻量 sentinel 只做抓取、入库、初筛，不默认启动大模型。

## 六、事件图 / 证据图设计

不要一开始上大型知识图谱。先用 PostgreSQL 做轻量 Evidence Graph。

### 核心表

```text
entities
- id
- type: company/person/product/agency/industry
- canonical_name
- aliases
- tickers
- identifiers: cik, lei, exchange, etc.

events
- id
- event_type
- canonical_title
- event_time
- first_seen_at
- affected_tickers
- importance_score
- status

documents
- id
- source_id
- source_type
- url
- title
- published_at
- retrieved_at
- raw_snapshot_ref
- content_hash

claims
- id
- event_id
- claim_text
- claim_type
- confidence
- generated_by

evidence_links
- claim_id
- document_id
- excerpt
- relation: supports / contradicts / neutral
- evidence_score

price_moves
- ticker
- window_start
- window_end
- return
- sector_return
- index_return
- abnormal_return
- volume_ratio

event_attributions
- event_id
- price_move_id
- attribution_strength: supported / plausible / weak / unsupported
- rationale
- uncertainty
```

这套结构足够支持你们的核心链路：

```text
股价异动
  ← possibly_explained_by
事件
  ← supported_by
文档 / source
  → mentions
公司 / 产品 / 交易对手
```

## 七、Agent 设计：不要让它从零开始搜

Agent 只处理结构化 evidence pack。

### 输入格式

```json
{
  "candidate_event": {
    "type": "supply_agreement",
    "subject": "A",
    "counterparty": "B",
    "event_time": "2026-06-01"
  },
  "price_move": {
    "ticker": "A",
    "abnormal_return": "+7.1%",
    "volume_ratio": "2.4x",
    "window": "2026-06-01 to 2026-06-03"
  },
  "evidence": [
    {
      "source_type": "company_ir",
      "published_at": "2026-06-01 08:30",
      "excerpt": "A announced a supply agreement with B...",
      "url": "..."
    }
  ],
  "open_questions": [
    "B 是否为重要客户？",
    "是否存在同期更强解释？",
    "是否有官方确认？"
  ]
}
```

### 输出格式

```json
{
  "attribution_strength": "plausible",
  "causal_chain": "A 股价上涨可能与其和 B 签订供货协议有关，因为 B 是重要客户，该协议提高了订单预期。",
  "supporting_claims": [
    {
      "claim": "A 与 B 签订供货协议",
      "evidence_ids": ["..."]
    }
  ],
  "alternative_explanations": [
    "同期存在分析师上调评级"
  ],
  "uncertainty": "协议金额未披露，不能证明收入影响规模"
}
```

这样每个候选事件的 token 成本可以控制在较低水平。Agent 不是读几十篇文章，而是验证一个压缩证据包。

## 八、token 消耗策略

目标是：

```text
每天处理 1000–5000 条 raw item
Agent 只看 top 10–20 个候选事件
最终推送 3–5 条
```

### 分层 token 策略

| 层             | 是否用 LLM                    | token 策略      |
| ------------- | -------------------------- | ------------- |
| RSS/SEC/IR 抓取 | 否                          | 0 token       |
| URL/hash 去重   | 否                          | 0 token       |
| embedding 聚类  | 否或本地模型                     | 不用大模型 token   |
| 简单事件类型识别      | 规则优先                       | 0 token       |
| 复杂事件抽取        | 小模型 / 便宜模型 JSON extraction | 低 token       |
| Top-N 证据验证    | 强模型 / GPT-5.5 级 Agent      | 只处理 10–20 个候选 |
| 最终 digest     | 强模型                        | 只生成 3–5 条     |

不要做：

```text
每条新闻都调用大模型
每条候选都做深搜
让 Agent 自由浏览全网
让模型读完整网页全文
```

推荐初始预算：

```text
每日候选事件验证：10–20 个
每个 evidence pack：800–1500 prompt tokens
每个输出：200–500 tokens
每日总量：约 1–4 万 tokens，加上少量搜索补证据
```

这个级别适合 MVP 成本控制。

## 九、阶段性计划

### Phase 0：架构 POC，1–2 周

目标：跑通最小闭环。

范围：

```text
FastAPI + PostgreSQL + Celery
SEC latest filings adapter
Newswire RSS adapter
OpenBB / yfinance 简单行情 adapter
daily_stock_analysis 通知方式参考
Telegram 推送
最简单事件卡片
```

输出：

```text
每天从 10–30 只 watchlist 股票生成 3 条事件简报
每条附 source_url
```

不做：

```text
复杂 agent
完整 IR
复杂证据图
实时监控
```

### Phase 1：免费 MVP 数据层，4–6 周

目标：建立可用数据接入层和 raw item store。

范围：

```text
SEC EDGAR submissions / RSS / filing HTML
GlobeNewswire / PR Newswire / Business Wire RSS
30–50 家核心公司 IR 页面/RSS
FTC / DOJ / Federal Register / BIS
FRED
Source Registry
raw snapshot 保存
去重和 source health
基础查询 API
```

输出：

```text
能按 ticker / time / source_type 查询过去 24h 原始材料
能稳定生成候选事件池
```

### Phase 2：事件挖掘和证据图，4–8 周

目标：从“新闻条目”升级成“事件”。

范围：

```text
实体识别和 ticker matching
embedding 去重和事件聚类
event schema
claim / evidence schema
价格异动检测
source authority scoring
候选事件排序
```

输出：

```text
每天 1000+ raw item → 20 个候选事件
每个事件有 source、time、entities、evidence excerpt
```

### Phase 3：低 token Agent 调查，4–6 周

目标：Agent 只处理 top-N 事件并输出归因判断。

范围：

```text
LangGraph agent
open_deep_research 流程参考
受控 search tools: SEC / IR / Newswire / Web search
evidence pack 输入
supported / plausible / weak / unsupported 输出
citation verifier
```

输出：

```text
每日 3–5 条事件卡片
每条有证据、影响解释、不确定性、替代解释
```

### Phase 4：反馈和轻量增量监控，4–8 周

目标：从 batch demo 进入真实产品形态。

范围：

```text
Telegram inline feedback
user preference scoring
source health dashboard
轻量 hourly polling
重大事件即时 alert
token cost dashboard
observability
```

输出：

```text
用户可以反馈“有用 / 不相关 / 继续深挖 / 屏蔽此主题”
系统能根据反馈调整下一次排序
```

## 十、团队和工作量估算

如果 1 个全栈/数据工程师做：

```text
POC：1–2 周
可用 MVP：8–12 周
比较完整 beta：3–4 个月
```

如果 2 人并行：

```text
1 人做数据接入 + 事件挖掘
1 人做 agent + 推送 + Web/API

POC：1 周左右
MVP：5–8 周
beta：2–3 个月
```

最不应该一开始投入的方向：

```text
全市场实时监控
大型知识图谱
复杂多 Agent 系统
付费行情集成
完整 Web SaaS 权限系统
自动交易
```

## 十一、关键风险

### 1. 许可证风险

需要特别注意：

```text
OpenBB：AGPL-3.0，商业闭源要隔离或评估商业许可
RSSHub：AGPL-3.0，建议 sidecar 使用
TrendRadar：GPL-3.0，不建议合入核心
n8n：Sustainable Use License，不建议作为核心
daily_stock_analysis：MIT，相对适合参考和复用
```

这些结论应在商业化前做一次正式 license review。高 star 不是许可安全的保证。

### 2. 数据源合规风险

免费行情、新闻搜索和网页抓取不等于可商业再分发。第一版可以内部验证，公开产品必须区分：

```text
内部使用
摘要使用
链接跳转
全文镜像
数据再分发
衍生指标展示
```

### 3. Agent 过度归因风险

系统必须避免把“相关”写成“导致”。

所以归因标签必须分级：

```text
supported
plausible
weak
unsupported
```

并且要强制输出不确定性和替代解释。

### 4. 数据质量风险

IR 页面变动、RSS 失效、SEC 限流、搜索 API 结果波动都会影响结果。必须从第一天记录 source health 和 ingestion run。

## 十二、最终推荐方案

第一版的技术栈我建议定成：

```text
Backend:
Python + FastAPI

Task:
Celery + Redis

Storage:
PostgreSQL + pgvector
S3 / MinIO for raw snapshots

Data:
SEC EDGAR direct adapter
Newswire RSS adapter
Company IR adapter
Gov/regulatory adapter
OpenBB adapter
FRED adapter
Tavily / Brave search adapter

Mining:
sentence-transformers
spaCy
rules + LLM JSON extraction
PyOD optional

Agent:
LangGraph
open_deep_research as reference
strict evidence-pack input
structured JSON output

App / Push:
daily_stock_analysis as reference
Telegram first
Email fallback
Slack/Feishu later

Observability:
OpenTelemetry
Prometheus
Sentry
```

一句话计划：

> **用 daily_stock_analysis 学应用层，用 OpenBB 做金融数据 adapter，用 RSSHub/changedetection 做外围传感器，用 PostgreSQL+pgvector 建事件证据图，用数据挖掘做低成本筛选，用 LangGraph Agent 做 top-N 深搜和归因验证。**

这样做的好处是：

```text
MVP 快
token 可控
证据可追溯
后续能扩展到轻量 24h 监控
不会被单个 GitHub 项目锁死
```

最重要的是：你们的核心壁垒不要放在“能不能抓新闻、能不能发日报”。这些已有项目已经做得很多。你们真正要做的是：

```text
把分散新闻和公告变成事件
把事件变成证据链
把证据链变成可控的归因判断
把归因判断压缩成用户每天愿意看的 3–5 条
```

[1]: https://github.com/ZhuLinsen/daily_stock_analysis?utm_source=chatgpt.com "ZhuLinsen/daily_stock_analysis: LLM 驱动的多市场股票 ..."
[2]: https://github.com/ZhuLinsen/daily_stock_analysis/blob/main/LICENSE?utm_source=chatgpt.com "daily_stock_analysis/LICENSE at main"
[3]: https://github.com/OpenBB-finance/OpenBB?utm_source=chatgpt.com "OpenBB-finance/OpenBB: Financial data platform for ..."
[4]: https://github.com/OpenBB-finance/OpenBB/blob/develop/LICENSE?utm_source=chatgpt.com "OpenBB/LICENSE at develop"
[5]: https://github.com/diygod/rsshub?utm_source=chatgpt.com "DIYgod/RSSHub: 🧡 Everything is RSSible"
[6]: https://github.com/dgtlmoon/changedetection.io?ref=meyer-laurent.com&utm_source=chatgpt.com "dgtlmoon/changedetection.io at meyer-laurent.com"
[7]: https://github.com/SANSAN0/TRENDRADAR?utm_source=chatgpt.com "sansan0/TrendRadar: ⭐AI-driven public ..."
[8]: https://github.com/huginn/huginn?utm_source=chatgpt.com "huginn/huginn: Create agents that monitor and act on your ..."
[9]: https://github.com/n8n-io/n8n?utm_source=chatgpt.com "n8n - Secure Workflow Automation for Technical Teams"
[10]: https://github.com/n8n-io/n8n/blob/master/LICENSE.md?utm_source=chatgpt.com "n8n/LICENSE.md at master · n8n-io/n8n"
[11]: https://github.com/langchain-ai/langgraph?utm_source=chatgpt.com "langchain-ai/langgraph: Build resilient agents."
[12]: https://github.com/langchain-ai/open_deep_research?utm_source=chatgpt.com "langchain-ai/open_deep_research"
[13]: https://github.com/fastapi/fastapi?utm_source=chatgpt.com "FastAPI framework, high performance, easy to learn, fast ..."
[14]: https://github.com/celery/celery?utm_source=chatgpt.com "celery/celery: Distributed Task Queue (development branch)"
[15]: https://github.com/temporalio/temporal?utm_source=chatgpt.com "temporalio/temporal: Temporal service"
[16]: https://github.com/apache/airflow?utm_source=chatgpt.com "Apache Airflow - A platform to programmatically author ..."
[17]: https://github.com/pgvector/pgvector?utm_source=chatgpt.com "pgvector/pgvector: Open-source vector similarity search for ..."
[18]: https://github.com/huggingface/sentence-transformers?utm_source=chatgpt.com "Sentence Transformers: Embeddings, Retrieval, and ..."
[19]: https://github.com/explosion/spaCy?utm_source=chatgpt.com "spaCy: Industrial-strength NLP"
[20]: https://github.com/explosion/spaCy/blob/master/LICENSE?utm_source=chatgpt.com "MIT License - explosion/spaCy"
[21]: https://github.com/yzhao062/pyod?utm_source=chatgpt.com "Python Outlier Detection (PyOD) 3"
[22]: https://github.com/maartengr/bertopic?utm_source=chatgpt.com "MaartenGr/BERTopic: Leveraging BERT and c-TF ..."
[23]: https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data?utm_source=chatgpt.com "Accessing EDGAR Data"
[24]: https://www.sec.gov/about/rss-feeds?utm_source=chatgpt.com "RSS Feeds"
[25]: https://fred.stlouisfed.org/docs/api/fred/?utm_source=chatgpt.com "St. Louis Fed Web Services: FRED® API"
[26]: https://tavily.com/?utm_source=chatgpt.com "Tavily API"
[27]: https://brave.com/search/api/?utm_source=chatgpt.com "Brave Search API"
[28]: https://core.telegram.org/bots/api?utm_source=chatgpt.com "Telegram Bot API"
[29]: https://opentelemetry.io/docs/?utm_source=chatgpt.com "Documentation"
[30]: https://prometheus.io/?utm_source=chatgpt.com "Prometheus - Monitoring system & time series database"
[31]: https://github.com/getsentry/sentry?utm_source=chatgpt.com "getsentry/sentry: Developer-first error tracking and ..."
