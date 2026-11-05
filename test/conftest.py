# 测试根:把 server/ 加入导入路径,使 test/ 可直接导入 app 包
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "server"))

# 测试进程一律不真跑报告站构建(npm 慢且碰文件系统);触发逻辑由 test_site 用缝验收
os.environ.setdefault("STARDISSECT_SITE_REBUILD", "0")
