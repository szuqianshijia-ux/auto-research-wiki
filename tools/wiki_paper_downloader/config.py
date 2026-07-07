"""
config.py — 配置加载。
从项目目录下的 .env 文件或环境变量读取 API keys / email。
"""
import os
from pathlib import Path

_HERE = Path(__file__).parent


def _load_dotenv():
    env_file = _HERE / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip())


_load_dotenv()

# Unpaywall 需要真实 email（配置后才会启用）
UNPAYWALL_EMAIL: str = os.environ.get("UNPAYWALL_EMAIL", "")

# Semantic Scholar API key（可选，无 key 时仍可用但有 rate limit）
SEMANTIC_SCHOLAR_API_KEY: str = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")

# Wiki 多项目配置
# 每个项目有唯一的 UUID 和对应的 raw/sources 基目录
PROJECTS: dict = {
    "embodied": {
        "id": "${EMBODIED_PROJECT_ID}",
        "base": Path("${AUTO_RESEARCH_DIR}/knowledge_bases/02_embodied_intelligence/raw/sources"),
    },
    "vibration": {
        "id": "${VIBRATION_PROJECT_ID}",
        "base": Path("${AUTO_RESEARCH_DIR}/video_vibration_research_complete/raw/sources"),
    },
}

# 当前激活的项目（通过 WIKI_PROJECT 环境变量可覆盖，默认为 embodied）
_ACTIVE_PROJECT: str = os.environ.get("WIKI_PROJECT", "embodied")

# Wiki 知识库根目录（向后兼容，默认指向 embodied 项目）
# 也可以通过 WIKI_PAPERS_BASE 环境变量直接覆盖
WIKI_PAPERS_BASE: Path = Path(
    os.environ.get(
        "WIKI_PAPERS_BASE",
        str(PROJECTS[_ACTIVE_PROJECT]["base"] / "papers"),
    )
)

# 当前项目 ID（用于 wiki_sync.rescan() 的 project_id 参数）
WIKI_PROJECT_ID: str = PROJECTS.get(_ACTIVE_PROJECT, {}).get("id", "")

# HTTP 请求超时（秒）
HTTP_TIMEOUT: int = int(os.environ.get("HTTP_TIMEOUT", "30"))
DOWNLOAD_TIMEOUT: int = int(os.environ.get("DOWNLOAD_TIMEOUT", "90"))

# 下载完成后是否自动触发 Wiki Rescan（默认开启，可用 --no-rescan 或环境变量关闭）
AUTO_RESCAN: bool = os.environ.get("WIKI_AUTO_RESCAN", "1").strip() not in ("0", "false", "no")
