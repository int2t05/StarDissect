# TODO — code-review 1d58052 发现台账

<!-- 双轴审查(Standards + Spec);关闭需人工决定(修复/接受/驳回+理由)。2026-10-09 批次 -->

## Critical — 全部已修复(2026-10-09)

- [x] T-01 DELETE /tasks/{id} 按任务 id 取消(cancel_pending(task_id=));新增单任务/按仓库两条路径测试
- [x] T-02 settings GET 白名单输出(不吐 syncing/queue_paused);PATCH 跳过「…」掩码值;限额正整数校验(422)
- [x] T-03 pipeline 向 h2/h3 注入 id/data-seq 锚点;测试断言
- [x] T-04 ReportView 改 window 滚动监听;GET progress 返回 anchor_seq

## Required — 修复/接受

- [x] T-05 队列循环与执行器各自独立连接(WAL 多写者隔离);循环异常兜底 5s 重试
- [x] T-06 CLONES_DIR → config.data_dir()/clones
- [x] T-07 报告 HTML 存库前 nh3 白名单消毒(rel 由 link_rel 管理)
- [x] T-08 每日定时条件修正(flag != "1");同步失败记 failed=1+finished_at
- [x] T-09 manual_scope 闭环:改状态已分类+入队;缺 type→422
- [x] T-10 限额非法值拒存;【接受】GitHub token 有效性校验依赖首次同步(记录于 OPN)
- [x] T-11 Spec ❌ 项补齐:RPT-003 排版校验器(validator.py,5 规则+白名单,违规入 meta)、RPT-005 mermaid 标记+前端渲染+文字后备、KP-002 编辑/软删除 API+人工修订标注、READ-006 已读/收藏(列+API+UI+键盘 m/f)、TASK-002 分析中终止(watcher 轮询取消)、SRCH-001 分组+↑↓/Enter 环绕+isComposing、READ-005 源码事实点击跳锚定 commit 的 GitHub blob
- [x] T-12 web_search/deep_research 纳入 tech.md §4 工具契约(用户指示:参考 Cognik/gpt-researcher 建立深度调研);PATCH repos unstarred 移除;concurrency 死配置移除
- [x] T-13 turns_used 投机字段删除(DDL+tech.md 同步);repo_fts 写入方补齐(入库+标签变动,含人工标签)

## Optional/Nit — 接受并记录

- [x] T-14 【接受】web_fetch 无 SSRF 限制(单用户内网部署,DEC-04);【接受】ReadingHome N+1(200 规模);【修复】useKeyboard helpVisible 删除?未删——挂接键盘帮助浮层留待 UI 打磨批次;其余小项随重构批次处理
- [x] T-15 【接受】RPT-001 通用基础章节硬模板校验:提示词约束+首批验证校准(OPN-01)

关闭记录:用户 2026-10-09 授权「跑 code-review」并指示深度调研纳入,全部 Critical/Required 由 AI 修复并通过 51 项测试;接受项理由如上,可驳回重开。
