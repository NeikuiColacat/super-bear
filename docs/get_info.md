第一批必接：
1. SEC EDGAR
2. 公司 IR / press release / earnings release 抓取
3. YFinance 或 OpenBB-yfinance
4. Tavily
5. Brave Search（暂缓默认接入）
6. Stock Sentiment API

当前第一批接入配置：
- 默认运行配置：`configs/ingestion_run.yaml`
- 第一批 smoke 配置：`configs/ingestion_first_batch.sample.yaml`
- 无 API key 来源：`company_ir`、`yfinance`
- 需要 API key 来源：`tavily`、`stock_sentiment`
- 暂缓默认接入：`brave_search`，adapter 保留，默认运行配置不启用

示例：

```bash
uv run python -m packages.ingestion.runner --config configs/ingestion_first_batch.sample.yaml --source company_ir --limit 2
uv run python -m packages.ingestion.runner --config configs/ingestion_first_batch.sample.yaml --source yfinance --limit 2
```

第二批再接：
7. Longbridge 或 TickFlow
8. Bocha
9. SerpAPI

暂时不接：
AKShare
Tushare
Pytdx
Baostock
Anspire
MiniMax
SearXNG

---

## 附录 A：第一批 API 用法与当前接入审查（2026-06-30）

> 目标：检查第一批数据源“官方怎么用、支持哪些关键参数、我们现在是否用对”。
> 结论先行：SEC EDGAR、Company IR/RSS、YFinance、Tavily、Brave 的当前最小接入方向基本正确；Stock Sentiment API 的 endpoint、鉴权 header 和时间参数已按官方 OpenAPI 修正，并已完成 `reddit + AAPL + days=1` 小额度 smoke test。

### 总览

| 来源 | 当前状态 | 当前是否用对 | 下一步 |
|---|---|---|---|
| SEC EDGAR | 已接入 submissions + primary filing HTML + 请求节流 | 小规模用对 | companyfacts 暂未接；历史分片暂不追 |
| 公司 IR / RSS / Atom | 已接入 RSS/Atom feed catalog | XML RSS/Atom 用对 | 继续标注 verified feeds；JSON feed 另接 parser |
| YFinance | 已接入 OHLCV market context | 用对 | 保持为行情 context，不当因果证据 |
| Tavily | 已接入 search leads | 最小参数用对 | 后续可扩 domain/time/topic 参数 |
| Brave Search | adapter 已接入，但默认运行配置暂不启用 | 尚未真实跑通本地样本 | 后续需要时再配 key 做小额度实测 |
| Stock Sentiment / Adanos | `reddit + AAPL + days=1` 已真实跑通 | 最小参数已按官方修正 | 继续小额度验证其它 source coverage |

每次 `RunManifestWriter` 写出 `manifest.json` 时，也会在同目录写出 `source_health.json`，用于快速查看每个 source 的 `success / failed / skipped / no_records / warning_codes / error_code`。

### 1. SEC EDGAR

官方参考：
- SEC EDGAR APIs: <https://www.sec.gov/search-filings/edgar-application-programming-interfaces>
- SEC accessing EDGAR data / fair access: <https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data>
- SEC developer resources: <https://www.sec.gov/about/developer-resources>
- SEC webmaster FAQ / Archives: <https://www.sec.gov/about/webmaster-frequently-asked-questions>

官方用法：
- submissions:
  - `GET https://data.sec.gov/submissions/CIK##########.json`
  - CIK 必须补齐 10 位，例如 Apple 是 `CIK0000320193.json`
- companyfacts:
  - `GET https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json`
  - 返回公司 XBRL facts；我们当前还没有真正接入这个采集路径
- filing primary document:
  - `GET https://www.sec.gov/Archives/edgar/data/{cik_no_leading_zeros}/{accession_no_dashes}/{primaryDocument}`
  - `primaryDocument` 来自 submissions JSON
- header:
  - 必须设置描述性 `User-Agent`，包含项目/组织和联系邮箱
- 访问限制：
  - SEC fair access 当前明确要求不要超过 `10 requests/second`

我们当前支持的参数：
- `ciks`: 要抓取的 CIK 列表
- `include_forms`: 表单过滤，例如 `8-K`、`10-Q`、`10-K`
- `published_after`: 只保留这个时间之后的 filing
- `max_filings_per_cik`: 每个 CIK 最多保留几条 filing
- `fetch_primary_documents`: 是否抓 primary filing HTML
- `primary_document_limit`: 本次最多抓几篇 primary document
- `text_excerpt_chars`: 从 primary document 抽取多少字符预览
- `user_agent` / `SEC_USER_AGENT`: SEC User-Agent
- `request_timeout_seconds`: 请求超时

审查结论：
- URL 形态正确。
- CIK 补零和 Archives 去前导零逻辑正确。
- 没有 `SEC_USER_AGENT` 时拒绝请求是正确的。
- `rate_limit_per_second: 8` 配置低于 SEC 10 rps，且 SEC adapter 已在连续请求之间执行 sleep/throttle。
- 问题：当前 parser 只读 `filings.recent`，不追 submissions 里的 `files` 历史分片；每日近况够用，历史回填不够。
- 问题：`companyfacts` 只有 URL builder，还没有 fetch/parser，不应宣称已经接入 XBRL facts。

### 2. 公司 IR / press release / earnings release（RSS / Atom）

官方/标准参考：
- RSS 2.0 specification: <https://www.rssboard.org/rss-specification>
- Atom RFC 4287: <https://www.rfc-editor.org/rfc/rfc4287>

标准字段：
- RSS item:
  - `title`
  - `link`
  - `description`
  - `pubDate`
  - 可选 `guid`
- Atom entry:
  - `title`
  - `link href="..."`
  - `published`
  - `updated`
  - `summary`
  - `content`

我们当前支持的参数：
- `catalog_path`: 公司 feed catalog，例如 `configs/company_ir_sources.yaml`
- `issuers`: 直接传入 issuer 列表
- `published_after`: 只保留某个时间之后的 feed item
- `continue_on_feed_error`: 某个 feed 失败时是否继续跑其他 feed
- `fetch_item_pages`: 是否抓取 feed item 对应的正文页并写入 RawStore
- `request_timeout_seconds`: 请求超时

审查结论：
- 对标准 RSS/Atom XML feed 的接法是正确的。
- `published_after` 日常增量抓取逻辑正确。
- 已增加 `feed_no_records` warning：raw feed 有 item 但被日期过滤为 0 时，会记录 raw item 数、过滤数、最新发布时间。
- 问题：当前 parser 只支持 XML RSS/Atom，不支持 JSON feed；catalog 里如果有 `.json` feed，会进入 parse warning，不应当作已覆盖。
- 问题：很多公司没有 RSS/Atom，需要人工 verified feed，不建议现在做网页 fallback。

### 3. YFinance / OpenBB-yfinance

参考：
- yfinance docs: <https://ranaroussi.github.io/yfinance/>
- yfinance `PriceHistory.history`: <https://ranaroussi.github.io/yfinance/reference/yfinance.price_history.html>

常用参数：
- `period`: 时间窗口，例如 `5d`、`1mo`、`1y`
- `interval`: K 线粒度，例如 `1d`、`1h`、`1m`
- `start` / `end`: 显式时间范围
- `actions`: 是否包含 dividends / stock splits
- `auto_adjust`: 是否复权调整
- `timeout`: 请求超时

我们当前支持的参数：
- `tickers`
- `period`
- `interval`
- `currency`

审查结论：
- 当前 `Ticker(ticker).history(period=..., interval=..., actions=True)` 用法正确。
- `period: 5d`、`interval: 1d` 适合作为每日 attention/context。
- 但 yfinance 是非官方 Yahoo Finance 封装，不应作为强审计级数据源。
- 当前项目实际用的是 `yfinance` adapter，不是 OpenBB-yfinance；如果后续换 OpenBB，也应输出同一个 `MarketContext` schema。
- 行情数据只能作为 context / confirmation，不能单独作为事件原因或主证据。

### 4. Tavily Search

官方参考：
- Tavily Search API: <https://docs.tavily.com/documentation/api-reference/endpoint/search>
- Tavily API introduction: <https://docs.tavily.com/documentation/api-reference/introduction>

官方用法：
- `POST https://api.tavily.com/search`
- header:
  - `Authorization: Bearer <TAVILY_API_KEY>`
  - `Content-Type: application/json`
- 常用 body 参数：
  - `query`: 必填
  - `max_results`
  - `search_depth`
  - `include_raw_content`
  - `include_answer`
  - `include_images`
  - `include_domains`
  - `exclude_domains`
  - 时间/主题相关参数按 Tavily 当前文档选择

我们当前支持的参数：
- `queries`
- `max_results`
- `search_depth`
- `include_raw_content`
- `include_domains`
- `exclude_domains`
- `request_timeout_seconds`

审查结论：
- endpoint、Bearer auth、JSON body 都正确。
- 当前配置 `max_results: 5`、`search_depth: basic` 合理，适合作为低成本 search lead。
- Tavily 结果只能作为 lead，不作为 primary evidence。
- 已支持 `include_domains` / `exclude_domains`，可把搜索限制到 SEC、IR、Newswire、公司域名，减少噪声。
- 后续可扩时间窗口参数；现在 sample 里 `published_at` 经常为空，不能直接当时间证据。

### 5. Brave Search

官方参考：
- Brave Web Search API: <https://api-dashboard.search.brave.com/api-reference/web/search/get>
- Brave auth guide: <https://api-dashboard.search.brave.com/documentation/guides/authentication>

官方用法：
- `GET https://api.search.brave.com/res/v1/web/search`
- header:
  - `X-Subscription-Token: <BRAVE_SEARCH_API_KEY>`
  - `Accept: application/json`
- 常用 query 参数：
  - `q`: 必填
  - `count`: 结果数量，常用 1-20
  - `offset`: 分页
  - `freshness`: `pd` / `pw` / `pm` / `py` 或日期范围
  - `country`
  - `search_lang`
  - `ui_lang`
  - `safesearch`
  - `text_decorations`
  - `spellcheck`

我们当前支持的参数：
- `queries`
- `count`
- `freshness`
- `text_decorations`
- `request_timeout_seconds`

审查结论：
- endpoint、`X-Subscription-Token`、`q/count/freshness` 设计正确。
- 当前还没有本地真实成功样本，不能算“已验证跑通”。
- 默认已加 `text_decorations=false`，避免 snippet 混入高亮标记。
- 和 Tavily 功能重叠，MVP 阶段不需要两者都高频调用；可以优先 Tavily，Brave 作为 fallback 或对照。

### 6. Stock Sentiment API / Adanos

官方参考：
- Adanos API docs: <https://api.adanos.org/docs>
- Adanos OpenAPI: <https://api.adanos.org/openapi.json>
- Reddit Stock Sentiment: <https://adanos.org/reddit-stock-sentiment>

官方用法：
- auth:
  - 受保护 endpoint 使用 `X-API-Key`
  - 不是 `Authorization: Bearer`
- stock detail endpoint 当前形态：
  - `GET https://api.adanos.org/reddit/stocks/v1/stock/{ticker}`
  - `GET https://api.adanos.org/x/stocks/v1/stock/{ticker}`
  - `GET https://api.adanos.org/news/stocks/v1/stock/{ticker}`
  - `GET https://api.adanos.org/polymarket/stocks/v1/stock/{ticker}`
- trending endpoint 示例：
  - `GET https://api.adanos.org/reddit/stocks/v1/trending?limit=3`
- 时间参数：
  - 推荐 `from=YYYY-MM-DD&to=YYYY-MM-DD`
  - OpenAPI 也保留 `days=1..365`
  - 当前没有 `lookback=24h`
- 常见字段：
  - `buzz_score`
  - `trend`
  - `sentiment_score`
  - `bullish_pct`
  - `bearish_pct`
  - `mentions`
  - `unique_posts`
  - `subreddit_count`
  - `total_upvotes`
  - `trend_history`
  - `found`

我们当前支持的参数：
- `tickers`
- `sources`
- `days`
- `from`
- `to`
- `endpoint_template`
- `request_timeout_seconds`

审查结论：
- 当前实现已改为 `X-API-Key`。
- 当前默认 endpoint 已改为 `/{source}/stocks/v1/stock/{ticker}`。
- 当前配置已从 `lookback: 24h` 改为 `days: 1`，也支持 `from/to`。
- 解析时已避免把 boolean `found` 当 numeric metric。
- `sample_size` 缺失时，会用 `mentions` 作为样本量近似。

### 当前优先修复顺序

1. Stock Sentiment adapter：
   - 已用小额度真实请求复测 `reddit + AAPL + days=1`
   - 如需可复现窗口，把默认 `days` 切成显式 `from/to`
2. SEC adapter：
   - 已执行真实 `rate_limit_per_second` 限流
3. Company IR：
   - 标记 catalog 里哪些 feed 是 XML RSS/Atom verified
   - JSON feed 暂不宣称支持
4. Search API：
   - Tavily / Brave 先作为 lead source，不进入主证据链
   - 后续加 domain/time filters，降低噪声

---

## 附录 B：DeepSeek API 用法与本项目接入建议（2026-07-01）

官方参考：
- DeepSeek quick start: <https://api-docs.deepseek.com/>
- Models & Pricing: <https://api-docs.deepseek.com/quick_start/pricing>
- Chat Completion API: <https://api-docs.deepseek.com/api/create-chat-completion>
- JSON Output: <https://api-docs.deepseek.com/guides/json_mode>
- Tool Calls: <https://api-docs.deepseek.com/guides/tool_calls>
- Thinking Mode: <https://api-docs.deepseek.com/guides/thinking_mode>
- Rate Limit & Isolation: <https://api-docs.deepseek.com/quick_start/rate_limit>
- Error Codes: <https://api-docs.deepseek.com/quick_start/error_codes>
- Get User Balance: <https://api-docs.deepseek.com/api/get-user-balance>

### 基本接入

OpenAI-compatible:

```text
base_url: https://api.deepseek.com
endpoint: POST /chat/completions
auth: Authorization: Bearer ${DEEPSEEK_API_KEY}
```

Anthropic-compatible:

```text
base_url: https://api.deepseek.com/anthropic
auth: x-api-key
```

本项目第一版优先使用 OpenAI-compatible client，因为 Python SDK、JSON Output、tool calls 和现有 `ModelRun` 记录更容易统一。

### 当前官方模型

| 模型 | 适合用途 | 本项目建议 |
|---|---|---|
| `deepseek-v4-flash` | 低成本批量抽取、分类、初步 event/claim/evidence candidate | 默认模型 |
| `deepseek-v4-pro` | 冲突判断、证据充分性判断、复杂事件归因审阅 | 只用于 top-N 高价值样本 |

兼容旧名：
- `deepseek-chat` 会在 2026-07-24 15:59 UTC 废弃；当前兼容到 `deepseek-v4-flash` 的 non-thinking mode。
- `deepseek-reasoner` 会在 2026-07-24 15:59 UTC 废弃；当前兼容到 `deepseek-v4-flash` 的 thinking mode。

### 价格和容量

官方价格单位是每 1M token，人民币计价：

| 模型 | cache hit input | cache miss input | output | context | max output | 并发 |
|---|---:|---:|---:|---:|---:|---:|
| `deepseek-v4-flash` | 0.02 元 | 1 元 | 2 元 | 1M | 384K | 2500 |
| `deepseek-v4-pro` | 0.025 元 | 3 元 | 6 元 | 1M | 384K | 500 |

本项目第一轮 goal 建议预算：
- `deepseek-v4-flash`: 最多 300k input tokens / 80k output tokens。
- `deepseek-v4-pro`: 最多 50k input tokens / 20k output tokens。
- 优先复用本地 raw/chunk；只有对高质量 document chunk 做模型抽取。

### Chat Completion 常用参数

| 参数 | 说明 | 本项目默认 |
|---|---|---|
| `model` | `deepseek-v4-flash` 或 `deepseek-v4-pro` | flash |
| `messages` | system/user/assistant/tool 消息 | 必填 |
| `max_tokens` | 最大输出 token；防止 JSON 被截断 | schema 任务按需设置 |
| `response_format` | `{ "type": "json_object" }` 开启 JSON Output | 抽取任务默认开启 |
| `stream` | SSE 流式输出 | pipeline 默认 false |
| `stream_options.include_usage` | stream 时返回 usage | 仅调试 |
| `temperature` | 0-2；thinking mode 下无效 | non-thinking 抽取用 0 或 0.2 |
| `top_p` | nucleus sampling；不要和 temperature 同时调 | 默认不设 |
| `thinking` | `{ "type": "enabled" }` 或 `{ "type": "disabled" }` | 抽取 disabled，审阅 enabled |
| `reasoning_effort` | `high` 或 `max` | pro 审阅 high |
| `tools` | function tool schema，最多 128 个 | 暂不用于第一轮抽取 |
| `tool_choice` | `none` / `auto` / `required` / 指定工具 | 第一轮不用 |
| `user_id` | 业务侧隔离，不能含隐私 | 可设为 `super_bear_dev` |

不建议继续使用：
- `presence_penalty`
- `frequency_penalty`

这些参数已标记为 deprecated / no effect。

### JSON Output 使用规则

启用方式：

```json
{
  "response_format": {"type": "json_object"}
}
```

同时 prompt 里必须明确要求输出 JSON，并给出目标 JSON 示例。否则官方文档说明模型可能输出长时间空白，直到达到 token limit。

本项目抽取任务必须要求：
- 只输出 JSON。
- 每个 candidate 必须包含 `doc_id`、`chunk_id`、`char_start`、`char_end`。
- 不允许模型发明 source provenance。
- LLM 输出只进入 candidate，不直接进入 ledger。
- Pydantic/schema validation 失败则丢弃或写 `validation_errors.jsonl`。

### Thinking Mode 使用规则

默认 thinking 是 enabled。为了省 token：
- 批量实体/event/claim/evidence candidate 抽取：使用 `deepseek-v4-flash` + `thinking.disabled`。
- 证据充分性、冲突、时序有效性审查：使用 `deepseek-v4-pro` + `thinking.enabled`。

thinking mode 注意事项：
- `temperature`、`top_p`、`presence_penalty`、`frequency_penalty` 在 thinking mode 下不生效。
- thinking 输出会包含 `reasoning_content` 和最终 `content`。
- 多轮无 tool call 时，不需要把旧的 `reasoning_content` 拼回上下文。
- 多轮有 tool call 时，需要把 `reasoning_content` 带回后续请求，否则可能 400。

### Tool Calls 使用规则

DeepSeek 支持 tool calls；`strict` mode 是 beta，需要：
- 使用 `base_url="https://api.deepseek.com/beta"`。
- 每个 function 设置 `strict: true`。
- schema 必须符合官方支持范围。

本项目第一轮不优先使用 tool calls。原因：
- 我们现在需要的是离线 chunk 抽取，不是 agent 在线调用工具。
- 更简单可靠的方式是 JSON Output + Pydantic validation。
- 等 Super Bear tool contract 稳定后，再考虑把 read-only tools 暴露给 harness。

### 错误码处理

| HTTP code | 含义 | 本项目处理 |
|---:|---|---|
| 400 | 请求格式错误 | 停机，修 payload/schema |
| 401 | API key 错误 | 停机，不打印 key |
| 402 | 余额不足 | 停机 |
| 422 | 参数错误 | 停机，修参数 |
| 429 | 请求太快 | 降并发/退避；连续 3 次停机 |
| 500 | 服务端错误 | 短暂重试 |
| 503 | 服务过载 | 短暂重试 |

### 本项目推荐调用策略

第一阶段只做 schema-bound extraction：

```text
Document / Chunk
  -> DeepSeek JSON Output candidate extraction
  -> Pydantic validation
  -> deterministic char offset validation
  -> claim/evidence candidate JSONL
```

推荐默认：

```text
model: deepseek-v4-flash
thinking: disabled
temperature: 0
response_format: json_object
max_tokens: 2000-4000
user_id: super_bear_dev
```

只在以下情况升级到 `deepseek-v4-pro`：
- event candidate 已经进入 top-N。
- 支持/反驳证据冲突。
- 必须判断 evidence sufficiency。
- 需要明确 abstain / continue-search 决策。

禁止：
- 不把 search snippet、social sentiment、price move 交给模型当主证据。
- 不让模型直接写入 Claim-Evidence Ledger。
- 不让模型生成无法追溯到 `chunk_id + char offsets` 的事实句子。
- 不在日志、文档、commit 或测试输出里打印 `DEEPSEEK_API_KEY`。
