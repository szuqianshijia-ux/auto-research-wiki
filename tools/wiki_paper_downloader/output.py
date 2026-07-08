"""
output.py — 将下载结果写到 Wiki raw/sources/papers/ 并更新清单。
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from .sources.base import PaperMeta


# 目录别名（供 CLI 使用）
DIR_ALIASES = {
    "vla": "vla_foundation",
    "action": "action_chunking_latency",
    "data": "data_imitation",
    "deploy": "efficient_deployment",
    "training": "training_theory",
    "refs": "references",
}


def resolve_subdir(alias_or_name: str) -> str:
    return DIR_ALIASES.get(alias_or_name, alias_or_name)


def find_existing(arxiv_id: str, target_dir: Path) -> Path | None:
    """检查是否已有同 arXiv ID 的文件（不论短名）。"""
    if not arxiv_id:
        return None
    matches = list(target_dir.glob(f"{arxiv_id}_*.pdf"))
    return matches[0] if matches else None


def make_filename(meta: PaperMeta, short_name: str = "") -> str:
    """生成 arXivID_短名.pdf 格式的文件名。"""
    base_id = meta.best_id
    name = short_name or meta.short_title or "Paper"
    return f"{base_id}_{name}.pdf"


def append_checklist(entries: list[dict], topic: str, papers_base: Path) -> Path:
    """将结果追加到今日清单文件。"""
    today = date.today().strftime("%Y%m%d")
    slug = re.sub(r"[\s/\\]", "_", topic) if topic else "下载"
    path = papers_base / f"_补充论文清单_{today}_{slug}.md"

    if path.exists():
        lines = path.read_text(encoding="utf-8").rstrip().splitlines()
    else:
        lines = [
            "---",
            "type: paper-index",
            f"title: 补充论文清单：{topic or '自动下载'}",
            f"created: {today[:4]}-{today[4:6]}-{today[6:]}",
            "tags: [papers, auto-download]",
            "---",
            "",
            f"# 补充论文清单（{today[:4]}-{today[4:6]}-{today[6:]}）",
            "",
            "| arXiv/ID | 文件 | 标题 | 目录 | 大小 | 来源 |",
            "| --- | --- | --- | --- | --- | --- |",
        ]

    for e in entries:
        size_str = f"{e['size']/1024/1024:.1f} MB" if e.get("size") else "—"
        lines.append(
            f"| {e['id']} | {e['filename']} | {e['title'] or '(未获取)'} "
            f"| {e['subdir']} | {size_str} | {e['source']} |"
        )

    lines += [
        "",
        "---",
        "",
        "**后续步骤**: Rescan 已由 download.py 自动触发。"
        " 若未自动触发，可在 LLM Wiki 应用中手动点击 **File Sync → Rescan**，"
        " 或运行 `python3 -c \"from wiki_paper_downloader import wiki_sync; wiki_sync.rescan()\"`。",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
