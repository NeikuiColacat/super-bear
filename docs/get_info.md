第一批必接：
1. SEC EDGAR
2. 公司 IR / press release / earnings release 抓取
3. YFinance 或 OpenBB-yfinance
4. Tavily
5. Brave Search
6. Stock Sentiment API

当前第一批接入配置：
- 默认运行配置：`configs/ingestion_run.yaml`
- 第一批 smoke 配置：`configs/ingestion_first_batch.sample.yaml`
- 无 API key 来源：`company_ir`、`yfinance`
- 需要 API key 来源：`tavily`、`brave_search`、`stock_sentiment`

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
