# 应用配置:路径、运行参数与白名单(STARDISSECT_DATA 可注入;.env 加载不入库)
import os
from pathlib import Path

_ENV_LOADED = False

# .env 键 → settings 表键(仅在本表无值且环境有值时种子化,create_app 调用)
ENV_SEED_MAP = {
    "AI_BASE_URL": "ai_base_url",
    "AI_API_KEY": "ai_api_key",
    "AI_MODEL": "ai_model",
    "GITHUB_TOKEN": "github_token",
    "TAVILY_API_KEY": "tavily_api_key",
    "EXA_API_KEY": "exa_api_key",
}

# 运行参数(集中管理,消除魔法数)
CLASSIFIER_TIMEOUT_SEC = 120
CLASSIFIER_REQUEST_LIMIT = 3
TASK_DEFAULT_TURN_LIMIT = 60   # 部署实测校准:深读 30 轮不够(OPN-02)
TASK_DEFAULT_TIME_LIMIT_SEC = 1800
MODEL_MAX_TOKENS = 32768       # 网关默认输出上限会导致 IncompleteToolCall,显式放宽
CLONE_ATTEMPTS = 3             # 克隆网络抖动重试次数(部署实测:TLS 偶发中断)
CLONE_BACKOFF_SEC = 3          # 重试退避间隔
SEARCH_MAX_LIMIT = 50
QUEUE_INTERVAL_ACTIVE = 0.2    # 有任务时的轮询间隔(秒)
QUEUE_INTERVAL_IDLE = 2.0      # 空闲轮询间隔
QUEUE_RETRY_ON_ERROR = 5.0     # 循环异常后的重试间隔
TERMINATE_POLL_SEC = 0.5       # 终止请求轮询间隔
DAILY_SYNC_CRON = {"hour": "*/8", "minute": 17}  # 每 8 小时定时同步(REQ-SYNC-001,用户设定)

# agent 工具限制
MAX_FILE_LINES = 400
MAX_SEARCH_HITS = 50
MAX_WEB_CHARS = 8000
MAX_DEEP_PAGES = 5

# 中文排版校验白名单(产品名官方拼写所在行豁免中英/数字间距规则)
TYPOGRAPHY_WHITELIST = {"GitHub", "GitLab", "TypeScript"}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_env() -> None:
    """加载仓库根 .env(KEY=VALUE,不覆盖已有环境变量);幂等。"""
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    env_file = repo_root() / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())
    _ENV_LOADED = True


def data_dir() -> Path:
    return Path(os.environ.get("STARDISSECT_DATA", str(repo_root() / "data")))


def db_path() -> Path:
    return data_dir() / "app.db"


def logs_dir() -> Path:
    return data_dir() / "logs"


def web_dist() -> Path:
    return repo_root() / "web" / "dist"
