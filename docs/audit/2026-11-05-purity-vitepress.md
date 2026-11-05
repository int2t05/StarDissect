# 纯净审计 · 2026-11-05 · VitePress 报告站迁移（ADR-0009）

范围：本次迁移全部已提交内容（`25104da` + `c9231e5` + `1d8cc37` 及本次审计修复）——`server/app/site.py`、routes/runner/main/config 接线、`reports-site/`（脚手架与主题）、SPA 瘦身、test_site/conftest、docs 五件、deploy.sh、.gitignore。

## 清单覆盖（A–E）

| 类 | 结论 |
|---|---|
| A 溯源残留 | 无发现（ADR/REQ 指针为仓库既有注释惯例；部署触发语义均为当前事实） |
| B 装饰与冗余 | 2 处，已修（B6/C6 复制残留） |
| C 死内容 | 3 处，已修（C9 过时引用、C10 重复导入） |
| D doc/impl 裂隙 | 2 处，已修（D11 响应性、D13 路径知识归属） |
| E 语言/平台 | 无发现 |

## 发现与处置

| 点 | 位置 | 证据 | 处置 |
|---|---|---|---|
| C10 | site.py `_guards_ok` | `import shutil as _shutil` 与顶部 `import shutil` 重复 | 统一用顶部导入 |
| B6 | site.py `_connect` | 懒导入 `app.db.connect` 无循环必要 | 顶部导入；`rebuild_now`/`_worker` 直用 |
| D13 | routes.py `delete_report` | 路由层手拼 `reports-site/src/<slug>/<vid>` 路径——导出布局知识泄漏出 site 模块 | 新增 `site.schedule_rebuild_for(full_name, version_id)` 收口，路由只给两个 id |
| C6 | ReportShell.vue `close()` | `removeEventListener('pointerup')` 重复两行（移植复制残留） | 去重；并补上缺失的 `pointercancel` 对称移除（监听/移除不对称是泄漏） |
| D11 | ReadState.vue | `const vid = frontmatter.value.vid` 非响应快照——VitePress SPA 换页后 PATCH 打到旧 vid | 改 `computed` + `watch(vid, load)` |
| C9 | UIUX.md UX-59 | 「若 ReportView 用独立滚动容器…」——ReportView 已删除 | 改为「落地于报告站 ProgressTracker（监听 window，ADR-0009）」 |
| C9 | deploy.sh | `npm ci >/dev/null 2>&1` 吞掉 stderr——ci 失败时部署中止且无因 | `npm ci >/dev/null`（stderr 可见） |

## 需人工裁决

- `reports-site` 主题对「`-vue` 后缀语言的围栏不走 v-pre」未设防（VitePress 既有行为）：此类围栏内的 `{{ }}` 仍会破坏构建。报告 agent 的提示词不产出该形态，风险敞口为空；若未来放开报告语言范围，在围栏整形处补一道强制 v-pre。
- `server/app/site.py` 与 `render/pipeline.py` 各持一份证据块/mermaid 规则（Python 服务端 + JS 站点层，ADR-0009 记录的分工）：改证据块契约须三处同步（提示词/管线/站点插件）——已在 ADR「影响」节声明。

## 复核

- grep 复扫：`_shutil`/重复 `pointerup`/`ReportView`（UIUX）/`from app.config import repo_root`（routes）→ 0 命中。
- 全量 pytest 88 passed；SPA `vite build` 与 reports-site `vitepress build` 均通过。
