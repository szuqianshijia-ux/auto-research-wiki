"""
base.py — 论文元数据结构和源处理器基类。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PaperMeta:
    """统一的论文元数据，由各 source 填充。"""
    # 输入标识符（原始用户输入，如 arXiv ID / DOI / URL）
    input_id: str = ""

    title: str = ""
    authors: list[str] = field(default_factory=list)
    year: str = ""
    venue: str = ""
    abstract: str = ""
    doi: str = ""
    arxiv_id: str = ""
    s2_id: str = ""             # Semantic Scholar paper ID
    github_url: str = ""

    # 解析出的可用 PDF URL（按优先级排序）
    pdf_urls: list[str] = field(default_factory=list)

    # 来源标识，如 "arxiv" / "openalex" / "semantic_scholar"
    resolved_by: str = ""

    @property
    def short_title(self) -> str:
        """从标题生成短文件名（前3个显著词）。"""
        stopwords = {
            "a", "an", "the", "of", "for", "in", "on", "at", "to", "via",
            "and", "or", "with", "from", "by", "is", "are", "using", "its",
        }
        words = re.sub(r"[^\w\s]", "", self.title).split()
        significant = [w for w in words if w.lower() not in stopwords][:3]
        return "".join(w.capitalize() for w in significant)[:30] if significant else "Paper"

    @property
    def best_id(self) -> str:
        """用于文件命名的最佳 ID（arXiv > DOI 前缀 > input_id）。"""
        if self.arxiv_id:
            return self.arxiv_id
        if self.doi:
            # 取 DOI 最后一段，去掉特殊字符
            tail = self.doi.rstrip("/").split("/")[-1]
            return re.sub(r"[^\w.-]", "_", tail)[:20]
        return re.sub(r"[^\w.-]", "_", self.input_id)[:20]
