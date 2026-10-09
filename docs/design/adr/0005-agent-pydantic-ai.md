# ADR-0005 分析 agent:pydantic-ai 工具循环(轮次+时限)

状态:草案 · 2026-10-09

## 背景

用户决策 DEC-03:成本控制=「agent 轮次上限 + 任务总时限」,不做预算上限;分析器是实现 agent(NFR-01)。产出须结构化:报告章节、五类证据、知识点、分类修正(REQ-CLS-004、RPT-002、KP-001)。

## 决策

pydantic-ai 构建两个 agent:

1. **classifier**(轻):输入 README+元数据+文件树 → 输出 类型/理由/置信(REQ-CLS-001)。
2. **analyzer**(重):工具循环深读源码 → 输出 ReportDraft(章节正文+证据标注+知识点+可选分类修正)。

约束执行:`UsageLimits(request_limit=轮次上限)`(pydantic_ai_slim/pydantic_ai/usage.py:471-549,超限抛 UsageLimitExceeded)+ `asyncio.timeout(任务时限)` 双约束;两者在运行层强制,与应用层 REQ-TASK-003 对应。模型供应商经 pydantic-ai 模型字符串切换(OPN-03 保持开放)。

## 理由与落选

- dspy:面向提示词优化流水线,与「工具循环+类型化产出」的形态不匹配。落选。
- instructor:仅做结构化抽取,工具循环需自建。落选。
- 手写 OpenAI SDK 循环:重造工具调用解析与类型校验。落选。
- pydantic-ai:「typed agent loop,every model a string swap away」(reference/pydantic-ai/README.md,查阅 2026-10-09);原生 UsageLimits 直接对应 DEC-03,这是决定性证据。

## 影响

工具集(read_file/search_code/list_dir/fetch_github/web_fetch)作用域=仓库浅克隆 @ 固定 commit(源码事实可锚定,REQ-RPT-002);分类修正字段在应用层校验「人工锁定」后落库(REQ-CLS-003);超限异常→REQ-TASK-003 的受限完成/失败归档。

## 参考

- reference/pydantic-ai/README.md(查阅 2026-10-09):agent 循环与模型可切换定位。
- reference/pydantic-ai/pydantic_ai_slim/pydantic_ai/usage.py:471-549(查阅 2026-10-09):UsageLimits.request_limit 强制语义。
