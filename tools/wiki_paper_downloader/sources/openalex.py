"""
openalex.py — OpenAlex API（免费，无需 API key）。
支持通过 DOI 或 arXiv URL 查询论文，返回元数据和开放获取 PDF URL。

文档: https://docs.openalex.org/api-entities/works
"""
from __future__ import annotations

import json
import re
import urllib.request
import urllib.error
import urllib.parse
from .base import PaperMeta

_BASE = "https://api.openalex.org/works"
_FIELDS = "title,doi,publication_year,authorships,abstract_inverted_index,open_access,primary_location,best_oa_location,ids"


def _reconstruct_abstract(inverted: dict) -> str:
    """OpenAlex 用倒排索引存摘要，还原为文本。"""
    if not inverted:
        return ""
    words: dict[int, str] = {}
    for word, positions in inverted.items():
        for pos in positions:
            words[pos] = word
    return " ".join(words[i] for i in sorted(words))[:600]


def _extract_arxiv_id(data: dict) -> str:
    """从 OpenAlex 的 ids 字段里提取 arXiv ID。"""
    ids = data.get("ids", {})
    arxiv_url = ids.get("arxiv", "")
    if arxiv_url:
        m = re.search(r"(\d{4}\.\d{4,5})", arxiv_url)
        if m:
            return m.group(1)
    return ""


def fetch_by_doi(doi: str) -> PaperMeta | None:
    """通过 DOI 查询 OpenAlex。DOI 格式: 10.xxxx/... 或完整 URL。"""
    if not doi.startswith("http"):
        doi_url = f"https://doi.org/{doi}"
    else:
        doi_url = doi
    return _fetch(f"{_BASE}/{urllib.parse.quote(doi_url, safe='')}?select={_FIELDS}", doi)


def fetch_by_arxiv(arxiv_id: str) -> PaperMeta | None:
    """通过 arXiv ID 查询 OpenAlex（内部转换为 arXiv URL）。"""
    arxiv_url = f"https://arxiv.org/abs/{arxiv_id}"
    meta = _fetch(f"{_BASE}/{urllib.parse.quote(arxiv_url, safe='')}?select={_FIELDS}", arxiv_id)
    if meta and not meta.arxiv_id:
        meta.arxiv_id = arxiv_id
    return meta


def search_by_title(title: str, limit: int = 3) -> list[PaperMeta]:
    """通过标题搜索 OpenAlex，返回前 N 个结果。"""
    q = urllib.parse.quote(title)
    url = f"{_BASE}?search={q}&select={_FIELDS}&per_page={limit}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        print(f"  [OpenAlex] 搜索失败: {e}")
        return []
    results = []
    for item in data.get("results", []):
        m = _parse(item, title)
        if m:
            results.append(m)
    return results


def _fetch(url: str, input_id: str) -> PaperMeta | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "wiki-paper-downloader/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        print(f"  [OpenAlex] HTTP {e.code}: {url}")
        return None
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        print(f"  [OpenAlex] 请求失败: {e}")
        return None
    return _parse(data, input_id)


def _parse(data: dict, input_id: str) -> PaperMeta | None:
    if not data or "title" not in data:
        return None

    meta = PaperMeta(input_id=input_id)
    meta.title = data.get("title") or ""
    meta.year = str(data.get("publication_year") or "")
    meta.doi = (data.get("doi") or "").replace("https://doi.org/", "")
    meta.arxiv_id = _extract_arxiv_id(data)
    meta.resolved_by = "openalex"

    # Authors
    authorships = data.get("authorships") or []
    meta.authors = [
        a.get("author", {}).get("display_name", "")
        for a in authorships
        if a.get("author", {}).get("display_name")
    ]

    # Abstract
    abstract_inv = data.get("abstract_inverted_index")
    if abstract_inv:
        meta.abstract = _reconstruct_abstract(abstract_inv)

    # PDF URLs (优先 open_access.oa_url，然后 best_oa_location)
    oa = data.get("open_access") or {}
    oa_url = oa.get("oa_url") or ""
    best_oa = data.get("best_oa_location") or {}
    best_pdf = best_oa.get("pdf_url") or ""

    primary = data.get("primary_location") or {}
    primary_pdf = primary.get("pdf_url") or ""

    for url in [oa_url, best_pdf, primary_pdf]:
        if url and url not in meta.pdf_urls:
            meta.pdf_urls.append(url)

    # arXiv fallback URL
    if meta.arxiv_id and not any("arxiv.org/pdf" in u for u in meta.pdf_urls):
        meta.pdf_urls.append(f"https://arxiv.org/pdf/{meta.arxiv_id}")

    return meta
