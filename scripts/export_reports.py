#!/usr/bin/env python3
"""批量导出报告为 Markdown 文档(REQ-OUT-001)。

用法:
    python scripts/export_reports.py [base_url] [out_dir]
    默认 base_url=http://127.0.0.1:8000,out_dir=exports/
可重复执行,增量覆盖同名文件;未完成的报告自然跳过(仅导出已有版本)。
"""
import json
import sys
import urllib.request
from pathlib import Path

base = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
out = Path(sys.argv[2] if len(sys.argv) > 2 else "exports")
out.mkdir(parents=True, exist_ok=True)

repos = json.load(urllib.request.urlopen(f"{base}/api/repos?filter=all"))
count = 0
for r in repos:
    versions = json.load(urllib.request.urlopen(f"{base}/api/repos/{r['id']}/reports"))
    for v in versions:
        md = urllib.request.urlopen(f"{base}/api/reports/{v['id']}/export").read()
        name = f"{r['full_name'].replace('/', '__')}-v{v['version_no']}.md"
        (out / name).write_bytes(md)
        count += 1
print(f"exported {count} files -> {out.resolve()}")
