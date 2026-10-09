# ADR-0006 中文检索:FTS5 + jieba 预分词

状态:草案 · 2026-10-09

## 背景

REQ-SRCH-001:检索范围=报告全文+知识点+仓库元信息;按「报告>章节」分组、命中片段;中文为主。

## 决策

(修订 2026-10-09:external content → 自持文本)章节/知识点/仓库元信息建 FTS5 虚表,**自持文本**:索引写入前用 jieba 分词,空格连接后入库(索引自身持有分词副本);查询串同样过 jieba;命中片段用 FTS5 `snippet()` 从索引副本产出(转义后包 `<mark>`,→UX-41),展示前按 CJK 相邻去空格还原阅读形态。

修订原因:external content 模式下 snippet() 从 content 表取原文回显,而索引文本是分词副本,token 偏移与原文错位导致片段为空或标记错位;自持副本使 snippet 语义成立,代价是文本双份存储(200 仓库规模可忽略)。

## 理由与落选

- FTS5 默认 unicode61 tokenizer:以空格/标点切分,中文整段成单 token,检索失效——这是本 ADR 存在的理由。仅排除。
- trigram tokenizer:免分词依赖,但中文短查询(2 字词)召回差、索引膨胀。落选。
- 前端搜索(VitePress minisearch 形态):数据与报告版本状态在服务端,多端一致性要求索引权威在服务端(UIUX §7 交互仅是弹层)。落选。
- jieba:Python 生态中文分词事实标准(reference/jieba/README.md,查阅 2026-10-09);替换点单一(索引/查询两个分词函数),后续可换 pkuseg 等。

## 影响

索引与业务表同事务写入(ADR-0002),报告发布即入库可检索;分词器版本变更需重建索引(记录重建命令于 v1.0/tech.md)。

## 参考

- reference/jieba/README.md(查阅 2026-10-09):中文分词能力与模式。
- SQLite FTS5 官方文档 https://www.sqlite.org/fts5.html(查阅 2026-10-09):external content、snippet()、自定义 tokenizer 接口。
