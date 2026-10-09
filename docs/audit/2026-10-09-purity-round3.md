# 纯净审计 round3 — 稳定性专项 + 全量一致性

<!-- 四路子代理(A+E / B+C / D 一致性 / F 稳定性);触发=部署实测 clone 网络抖动失败 -->

| 日期   | 2026-10-09                     | 方式   | 四路子代理 → 甄别 → 修复 → 56 tests + build 全绿 |
| ------ | ------------------------------ | ------ | ------------------------------------------------ |
| 结论   | 21 项发现:20 修复,1 记录(批量重试入口,不强推) | 前置修复 | clone 退避重试 + 残留目录清理(触发项) |

## 稳定性(F 组)

| # | 问题 | 修复 |
| - | ---- | ---- |
| 1 | clone/sleep 同步阻塞协程循环,终止 watcher 失效 | prepare_clone 整体移入 to_thread;subprocess 加 timeout(600s/30s) |
| 2 | **锁定分类可被 manual_scope 影子覆盖**(upsert 先删后插绕过锁) | upsert_classification 锁定校验(非 manual_lock 拒绝),路由 409 |
| 3 | uvicorn.access 每请求一行冲刷轮转日志 | access 降噪至 WARNING,error 仍全量入 app.log |
| 4 | 分类与自动标签两次 commit 崩溃留半态 | 同事务提交;auto_tags 入检索域 |
| 5 | 批量失败重试入口 | 记录(低优先,手动重试够用) |
| 6 | 迁移机制不支持列变更 | tech.md §2 标注边界 |

## 一致性(D 组 9 项)与 A/B/C/E(10 项)摘要

- 「受限完成」清根后残余:FIG-02 补「中断」态与恢复边;tech §3「排队/进行均拒」
- classifier 输出补 tags;§6 补 restore 端点;§2 tags 补 UNIQUE、迁移边界注记;§8 改台账追踪
- UIUX 编号归位:UX-60/61 移至 §11 尾(顺序编号),新增 UX-62 标签双轨展示;UX-27/10 去修订叙事;UX-31 档位核对;UX-22 目录 200px 对齐
- 强对比修复(data-contrast 选择器,此前永不生效);auto_tags 补索引与库列表 LIKE 双源;根 package.json.bak 移除;硬编码阴影色记录(tokens 化留待 UI 批次)
- .env.example 降级链顺序纠正;「唯一陈述」措辞;index.html 补 32px png 接线

## 复检

- pytest 56 passed + build 通过;grep 无批次 ID/修订叙事残留(台账除外)
- 交叉引用全闭合;DDL 含 auto_tags;编号序列连续
