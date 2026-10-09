# 测试根:把 server/ 加入导入路径,使 test/ 可直接导入 app 包
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "server"))
