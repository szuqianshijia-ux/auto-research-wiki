"""
github.py — 从 GitHub 仓库抓取 README 和论文相关资料。
不需要 API key（匿名访问，每小时 60 次请求）。
主要用于：与论文配套的代码仓库、模型卡片、技术报告。
"""
from __future__ import annotations

import json
import re
import urllib.request
import urllib.error
from pathlib import Path
from .base import PaperMeta

_API_BASE = "https://api.github.com"
_RAW_BASE = "https://raw.githubusercontent.com"

_REPO_RE = re.compile(
    r"github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:/|$)"
)


def parse_repo(url: str) -> str | None:
    """从 GitHub URL 提取 owner/repo。"""
    m = _REPO_RE.search(url)
    return m.group(1) if m else None


def fetch_readme(repo: str) -> str:
    """下载 README（Markdown 文本），repo 格式: owner/repo。"""
    for branch in ("main", "master"):
        for fname in ("README.md", "README.rst", "README"):
            url = f"{_RAW_BASE}/{repo}/{branch}/{fname}"
            try:
                with urllib.request.urlopen(url, timeout=10) as resp:
                    return resp.read().decode("utf-8", errors="replace")
            except urllib.error.HTTPError:
                continue
            except urllib.error.URLError:
                break
    return ""


def fetch_repo_info(repo: str) -> dict:
    """通过 GitHub API 获取仓库基本信息（名称、描述、star 数等）。"""
    url = f"{_API_BASE}/repos/{repo}"
    req = urllib.request.Request(
        url, headers={"User-Agent": "wiki-paper-downloader/1.0", "Accept": "application/vnd.github.v3+json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, json.JSONDecodeError):
        return {}


def save_as_markdown(repo: str, output_dir: Path, readme: str = "") -> Path | None:
    """将 GitHub 仓库信息保存为 Markdown 文件（作为 wiki 的 reference 资料）。"""
    info = fetch_repo_info(repo)
    if not readme:
        readme = fetch_readme(repo)

    name = repo.replace("/", "_")
    out_path = output_dir / f"github_{name}.md"

    stars = info.get("stargazers_count", "?")
    description = info.get("description") or ""
    homepage = info.get("homepage") or ""
    updated = (info.get("updated_at") or "")[:10]

    header = f"""---
type: reference
title: GitHub — {repo}
source_type: github
repo: https://github.com/{repo}
stars: {stars}
updated: {updated}
---

# {repo}

> {description}

{"Homepage: " + homepage if homepage else ""}

Stars: {stars} | Updated: {updated}

---

"""
    out_path.write_text(header + (readme or "_README not found_"), encoding="utf-8")
    return out_path


def make_meta_from_repo(repo: str) -> PaperMeta:
    """为 GitHub 仓库构建一个 PaperMeta（用于 checklist）。"""
    info = fetch_repo_info(repo)
    meta = PaperMeta(input_id=f"github:{repo}")
    meta.title = info.get("full_name") or repo
    meta.abstract = info.get("description") or ""
    meta.github_url = f"https://github.com/{repo}"
    meta.resolved_by = "github"
    return meta
