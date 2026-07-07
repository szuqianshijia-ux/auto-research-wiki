"""
arxiv.py — arXiv 元数据获取与 PDF 解析。
不需要 API key，使用官方 Atom API。
"""
from __future__ import annotations

import re
import urllib.request
import urllib.error
from .base import PaperMeta


_ARXIV_ID_RE = re.compile(
    r"(?:arxiv[:\s/]*|abs/|pdf/)?(\d{4}\.\d{4,5}(?:v\d+)?)", re.IGNORECASE
)


def parse_arxiv_id(text: str) -> str | None:
    """从任意字符串提取 arXiv ID（如 2303.04137、arxiv:2303.04137、URL）。"""
    m = _ARXIV_ID_RE.search(text)
    return m.group(1).split("v")[0] if m else None  # 去掉版本号


def fetch(arxiv_id: str) -> PaperMeta:
    """从 arXiv API 获取论文元数据，填充 PaperMeta。"""
    meta = PaperMeta(input_id=arxiv_id, arxiv_id=arxiv_id)
    url = f"https://export.arxiv.org/api/query?id_list={arxiv_id}&max_results=1"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            xml = resp.read().decode("utf-8")
    except urllib.error.URLError as e:
        print(f"  [arXiv] API 请求失败: {e}")
        meta.pdf_urls = [
            f"https://arxiv.org/pdf/{arxiv_id}",
            f"https://arxiv.org/pdf/{arxiv_id}.pdf",
        ]
        meta.resolved_by = "arxiv-fallback"
        return meta

    entry_m = re.search(r"<entry>(.*?)</entry>", xml, re.DOTALL)
    if not entry_m:
        meta.pdf_urls = [f"https://arxiv.org/pdf/{arxiv_id}"]
        meta.resolved_by = "arxiv-fallback"
        return meta

    entry = entry_m.group(1)

    def _text(tag: str, dotall: bool = False) -> str:
        flags = re.DOTALL if dotall else 0
        m = re.search(rf"<{tag}>(.*?)</{tag}>", entry, flags)
        return m.group(1).strip() if m else ""

    meta.title = _text("title")
    meta.authors = re.findall(r"<name>(.*?)</name>", entry)
    meta.year = _text("published")[:4]
    meta.abstract = re.sub(r"\s+", " ", _text("summary", dotall=True))[:600]

    # DOI link (may or may not be present)
    doi_m = re.search(r'title="doi"[^>]*href="([^"]+)"', entry)
    if doi_m:
        meta.doi = doi_m.group(1)

    meta.pdf_urls = [
        f"https://arxiv.org/pdf/{arxiv_id}",
        f"https://arxiv.org/pdf/{arxiv_id}.pdf",
    ]
    meta.resolved_by = "arxiv"
    return meta
