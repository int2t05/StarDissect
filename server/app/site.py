# 报告阅读站(server/app/site.py):report_versions → reports-site/src 整树导出 + npm 重建
# 阅读面从 SPA 的 DOM 手术迁到 VitePress 静态站(ADR-0009):渲染加工由站点自己的
# markdown-it 插件承担(证据块/mermaid/章节锚点,与 render/pipeline.py 同源移植),
# 服务端只做两件事——摆 Markdown 源、拉构建。SPA 保留为管理面,reports-site 是阅读面。
import json
import logging
import os
import shutil
import subprocess
import threading
from pathlib import Path

from app import config
from app.db import connect
from app.render import pipeline

logger = logging.getLogger("stardissect.site")

SITE_DIR = config.repo_root() / "reports-site"
BUILD_TIMEOUT_SEC = 300

# 单工人收口:_lock 只被工人持有;_dirty 由任意触发者立、工人清
_lock = threading.Lock()
_dirty = threading.Event()


def repo_slug(full_name: str) -> str:
    """仓库 → URL 片段:与导出文件名同一规则(routes.py export_report),`/` 换 `__`。"""
    return full_name.replace("/", "__")


def export_site(conn) -> None:
    """未归档报告 → reports-site/src/<repo-slug>/<vid>/index.md,整树重摆。

    frontmatter 给工具条与源码链接(VID/REPO/COMMIT,复用 /reports/{vid}/export 的
    meta 形态);正文经 _normalize_fences 预整形——与 SPA 阅读时同一道入口整形,围栏
    粘连/未闭合在渲染前修好,锚点/证据块/mermaid 全部交给站点的 markdown-it 插件。
    整树重摆:先删后写,已删报告/已归档报告的旧目录自然消失。
    """
    rows = conn.execute(
        """SELECT v.id, v.version_no, v.commit_anchor, v.created_at, v.markdown, r.full_name
           FROM report_versions v JOIN repos r ON r.id=v.repo_id
           WHERE v.archived=0 AND r.archived=0 ORDER BY v.id DESC"""
    ).fetchall()
    src = SITE_DIR / "src"
    # 整树重摆:先删后写——孤儿可能藏在 slug 目录内层(报告删除后),按层清理反而漏
    shutil.rmtree(src, ignore_errors=True)
    src.mkdir(parents=True, exist_ok=True)
    for row in rows:
        slug = repo_slug(row["full_name"])
        target = src / slug / str(row["id"]) / "index.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_frontmatter(row) + pipeline._normalize_fences(row["markdown"]), encoding="utf-8")
    _write_home(src, rows)
    logger.info("报告站导出完成:%d 份报告", len(rows))


def _frontmatter(row) -> str:
    """YAML frontmatter:字符串值一律 JSON 序列化(合法 YAML),full_name 里的斜杠引号不炸。"""
    fields = {
        "title": f"{row['full_name']} v{row['version_no']}",
        "repo": row["full_name"],
        "version": row["version_no"],
        "commit": row["commit_anchor"],
        "generated_at": row["created_at"],
        "vid": row["id"],
    }
    lines = [f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in fields.items()]
    return "---\n" + "\n".join(lines) + "\n---\n\n"


def _write_home(src: Path, rows) -> None:
    """首页:未归档报告按月分组的清单,新的在前——阅读站的开门页。"""
    parts = ['---\ntitle: StarDissect 报告\n---\n\n# StarDissect 报告\n\n']
    if not rows:
        parts.append("还没有报告:跑一轮分析后,这里会按月列出全部报告。\n")
    else:
        parts.append("GitHub star 仓库的深度分析报告,新的在前。\n")
        groups: dict[str, list] = {}
        for row in rows:
            month = str(row["created_at"])[:7] or "无日期"
            groups.setdefault(month, []).append(row)
        for month, items in groups.items():
            parts.append(f"\n## {month}\n\n")
            parts.extend(
                f"- [{row['full_name']} v{row['version_no']}](/{repo_slug(row['full_name'])}/{row['id']}/)\n"
                for row in items
            )
            parts.append("\n")
    (src / "index.md").write_text("".join(parts), encoding="utf-8")


def schedule_rebuild_for(full_name: str, version_id: int) -> None:
    """报告删除后的定向触发:对应导出目录在才排程(站点未建过时天然 no-op)。

    导出布局的知识归本模块(src/<repo-slug>/<vid>/),调用方只给仓库名与版本 id。
    """
    if (SITE_DIR / "src" / repo_slug(full_name) / str(version_id)).exists():
        schedule_rebuild()


def schedule_rebuild() -> None:
    """异步重建:守卫不过即跳过;过了就立 dirty,没有工人在做就派一个 daemon 线程。

    守卫(全过才动):site 脚手架在位(package.json)、npm 可用、环境未显式关停
    (STARDISSECT_SITE_REBUILD=0,测试缝)。构建在后台做,日志进 data/logs/site-build.log。
    """
    if not _guards_ok():
        return
    _dirty.set()
    if _lock.acquire(blocking=False):
        threading.Thread(target=_worker, daemon=True).start()


def _guards_ok() -> bool:
    if os.environ.get("STARDISSECT_SITE_REBUILD") == "0":
        return False
    if not (SITE_DIR / "package.json").is_file():
        logger.warning("跳过报告站重建:reports-site/package.json 不存在")
        return False
    if shutil.which("npm") is None:
        logger.warning("跳过报告站重建:npm 不在 PATH")
        return False
    if not (SITE_DIR / "node_modules").is_dir():
        logger.warning("跳过报告站重建:reports-site 未执行 npm install")
        return False
    return True


def _worker() -> None:
    """唯一的重建工人:dirty 立着就一直做;每轮先清 dirty 再干活,期间的触发算下一轮。"""
    try:
        while _dirty.is_set():
            _dirty.clear()
            try:
                # 工人线程自建自管连接(sqlite 严格同线程)
                export_site(connect(config.db_path()))
                _run_npm_build()
            except Exception:
                logger.exception("报告站重建失败(不致命,下次触发再试)")
    finally:
        _lock.release()


def rebuild_now() -> None:
    """同步重建(CLI/调试用):导出 + 构建,做完才返回;失败抛异常。"""
    if not _guards_ok():
        raise RuntimeError("报告站重建守卫未过:检查 package.json/node_modules/npm 与 STARDISSECT_SITE_REBUILD")
    export_site(connect(config.db_path()))
    _run_npm_build()


def _run_npm_build() -> None:
    """跑一次 npm run build;失败把输出尾巴带回来。构建前先删 dist:旧产物上原地覆盖
    时(大量文件先删后写)会触发 node fail-fast 崩溃,清空重来既避开也符合整树重建语义。"""
    config.logs_dir().mkdir(parents=True, exist_ok=True)
    shutil.rmtree(config.reports_site_dist(), ignore_errors=True)
    proc = subprocess.run(
        ["npm", "run", "build"],
        cwd=SITE_DIR,
        timeout=BUILD_TIMEOUT_SEC,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    log = config.logs_dir() / "site-build.log"
    with open(log, "a", encoding="utf-8") as f:
        f.write(f"--- build exit={proc.returncode} ---\n{(proc.stdout or '')[-2000:]}\n{(proc.stderr or '')[-2000:]}\n")
    if proc.returncode != 0:
        raise RuntimeError(f"报告站 npm build 失败(exit {proc.returncode}),详见 {log}")
    logger.info("报告站构建完成:%s", config.reports_site_dist())
