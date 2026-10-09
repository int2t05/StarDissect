# 应用配置:数据目录与路径(STARDISSECT_DATA 可注入,测试隔离用);.env 加载(密钥不入库)
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


def web_dist() -> Path:
    return repo_root() / "web" / "dist"
