# 笔记 

##  任务： 实时搜索综合类型 

### LIVERESEARCHBENCH

100道题目左右 ， 规模

主打卖点为实时live检索， GT需要agent联网实时更新获取，避免test set污染

跑一次千万token左右

take away : 

长报告不等于好报告

multi-agent 平均表现更强，但不是全面更强 , single-agent web search 在一致性上反而更强

coverage、citation、consistency、depth 之间存在明显 trade-off

Citation Association 是最核心问题。 论文总结说，模型最常见的问题不是语言不流畅，而是 citation correctness 和 formatting：正文 citation 和 reference 对不上、URL 缺失、引用格式不一致、reference 没被正文引用、编号乱序、表格破损等。

### Mind2Web 2: Evaluating Agentic Search with Agent-as-a-Judge 

130个任务 

每个任务都有一个树状评分标准，叶子节点是二元判断，比如“这个商品是不是白色”“价格是否正确”“链接是否真的支持该说法”。内部节点按 critical / non-critical / sequential 逻辑聚合，最后得到两个核心指标：

Partial Completion：任务完成了多少比例。

Success Rate：是否满分完成整个任务。

为每个任务构建一个专门的 judge agent ， 正确率约 99.03%

千万token左右 

OpenAI Deep Research 的 Partial Completion 是 0.54，Success Rate 是 0.28；人类是 0.79 和 0.54

浏览器操作能力不是充分条件 ， Partial Completion 只有 0.26，Success Rate 0.10

time-varying task 是硬伤

citation grounding 仍然很差


第一，人类完整成功率高很多。Human Success Rate 0.54，OpenAI Deep Research 0.28。这个差距说明：agent 经常能做到“部分正确”，但要完整满足所有约束、所有链接都对、所有信息都齐，仍然很难。

第二，agent 速度明显更快。Human 平均 18.4 分钟，OpenAI Deep Research 8.4 分钟，Grok DeeperSearch 5.72 分钟。论文的判断是：agent 已经有明显 cognitive offloading 价值，尤其适合自动化繁琐搜索劳动。

第三，人类也不是满分。Human Success Rate 也只有 0.54，不是 0.9 或 1.0。原因是 Mind2Web 2 的任务非常琐碎，容易因为疲劳、漏看约束、复制错误、看错网页而失败。论文的人类实验显示，任务平均要访问 8 个网站、110 个网页，最多 31 个网站、375 个网页，本来就很容易出错。

第四，agent 在细节耐心上有潜力超过人类，但现在证据链和动态网页还不稳。论文错误分析里提到，人类主要错误常常是 criteria violation，也就是粗心违反约束；而 agent 常见问题更多是信息没找全、引用缺失/伪造、链接不支持正文、检索到了但综合错。


## 多模态浏览器操作类型任务 

### MMInA: Benchmarking Multihop Multimodal Internet Agents

人类 task success rate 是 96.25%，而最强模型整体也只有二十几个百分点。

## 任务 ： 什么时候启动 agent，什么时候继续搜，什么时候停止或弃答。

### To Search or Not to Search: Aligning the Decision Boundary of  Deep Search Agents via Causal Intervention

什么时候应该停止搜索 ？

提出一种 诊断 + 训练对齐框架

在每一个 回答 或者 继续搜索的 boundary

做测试 ， 确定模型在哪个boundary 出错误

然后把错误决策链 样本 和 正确决策链样本 做对比学习 DPO训练

EM 大约 +1.1 到 +1.4 点；推理时间约降 5%–7%；ASQ 降约 3.5%–3.7%

### Search Wisely: Mitigating Sub-optimal Agentic Searches By Reducing Uncertainty

Over-search：模型明明靠已有上下文或参数知识就能回答，却还去搜。例如“美国第一任总统是谁”，模型其实知道是 George Washington，但为了保险仍然调用 search。

Under-search：模型其实不知道，应该搜索，却直接凭感觉回答，导致幻觉。例如一个冷门足球俱乐部在哪个国家，模型根据名字猜测，结果答错。

方法是 β-GRPO：只有当答案正确，而且 search query token 的最小生成概率超过阈值 β 时，才给 reward。也就是说，它把“高置信搜索决策”塞进 RL reward 里。

Average	0.309	0.344	+0.035

| 指标                | Search-R1-GRPO | β-GRPO |                改善 |
| ----------------- | -------------: | -----: | ----------------: |
| Over-search rate  |         21.10% | 19.89% | -1.21 pct. points |
| Under-search rate |         42.04% | 34.71% | -7.33 pct. points |

### HiPRAG: Hierarchical Process Rewards for Efficient Agentic Retrieval Augmented Generation

1. 把 agent 输出格式改成可解析的 XML step 格式

2. 把解析出来的 每个step 用外部LLM模型打分生成 RL 信号 

3. 把这个 step-level 信号塞进 RL reward


## 任务 ： 在 query/read/token/source-cost 预算下，下一步查什么最值。

### When knowledge is not free 

问题 ： 当我们的RAG 外部数据访问成本是存在的，并且有多个数据库，每个成本都不一样，且每个数据库的相关性价值也不一样

每个候选 passage 有相关性分数 v_i 和访问成本 c_i

抽象成一个 背包问题 ，也可以是启发式问题 ，贪心问题 做静态决策解决 ， 但是实验结果不好用

转换策略 ： 做zero-shot prompting ， 让模型自行决定要不要花钱

效果比静态决策策略更好但是不稳定

## 任务 ： 因果推断 

### WorldReasoner: Evaluating Whether Language Model Agents Forecast Events with Valid Reasoning

能不能在一个历史时间点上，基于当时可见的信息，对未来事件做概率预测，并且给出有效证据和因果推理

任务形式是：

给 agent 一个已经在现实中 resolve 的预测问题，但把 agent 放回到一个模拟的历史预测日期。agent 只能访问这个日期之前的新闻、文章、市场信息，不能看到之后发生的事情。然后 agent 需要输出：

预测答案，例如 Yes / No；
预测概率，例如 P(No)=0.90；
引用的证据来源；
可选的 causal event graph，也就是它认为哪些事件推动了结果发生

| 设置                   | Weighted Avg Accuracy |
| -------------------- | --------------------: |
| Vanilla LLM          |                 58.7% |
| Causal Simulation    |                 56.6% |
| Search-Enabled       |                 68.8% |
| Search-Enabled Graph |                 64.4% |
| Near-Resolution      |                 74.7% |
| Real-Time            |                 88.8% |




| 阅读顺序 | Benchmark / 工作        | 发表/发布状态                              | 为什么优先                                                                                                                                                                                                               |
| ---: | --------------------- | ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|    1 | **WorldReasoner**     | 2026 arXiv                           | 最贴近我们要做的“事件归因 + 未来预测 + time-valid evidence”。它给定 resolved forecasting question 和模拟 forecast date，只允许使用该日期前的证据，并同时评价预测概率、引用证据和可选 causal event graph。数据包含 345 个 resolved tasks、14,141 篇文章、8,087 个抽取事件。                 |
|    2 | **LiveResearchBench** | 2025 arXiv                           | 最贴近“Deep Research Agent 生成带 citation 的长报告”。它有 100 个专家构造任务，覆盖 daily life、enterprise、academia，构建投入超过 1,500 小时，并用 DeepEval 评价 coverage、presentation、citation accuracy、citation association、consistency、analysis depth。 |
|    3 | **Mind2Web 2**        | 2025 arXiv                           | 最贴近“agentic search + source attribution”。它包含 130 个长程真实网页搜索任务，要求实时浏览、信息综合和 source attribution，并提出 Agent-as-a-Judge 评价框架。                                                                                             |
|    4 | **AVeriTeC**          | 2023 arXiv / fact-checking benchmark | 最贴近“开放网页 claim verification”。它有 4,568 个真实世界 claims，来自 50 个 fact-checking 组织，用 QA evidence 和 textual justification 组合判断 verdict，并专门处理 temporal leakage。                                                              |
|    5 | **GaRAGe**            | 2025 arXiv，Amazon Science 作者         | 最适合我们做“evidence sufficiency / citation grounding”子模块。它包含 2,366 个问题和 35K+ 人工标注 grounding passages，评价模型是否只使用相关证据、是否在证据不足时 deflect。                                                                                    |
|    6 | **MAVEN-ERE**         | 事件关系抽取经典强 benchmark                  | 最适合支撑“事件图谱 / 事件归因链”。它统一标注 event coreference、temporal、causal、subevent relations，规模包括 103,193 个事件共指链、1,216,217 个时间关系、57,992 个因果关系和 15,841 个子事件关系，并公开数据和代码。                                                            |
