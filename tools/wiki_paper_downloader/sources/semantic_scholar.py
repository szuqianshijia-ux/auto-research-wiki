"""
semantic_scholar.py — Semantic Scholar API（可选 API key 提高 rate limit）。
支持通过 arXiv ID、DOI、S2 paper ID 查询。

文档: https://api.semanticscholar.org/graph/v1
"""
from __future__ import annotations

import json
import urllib.request
import urllib.error
import urllib.parse
from .base import PaperMeta

_BASE = "https://api.semanticscholar.org/graph/v1/paper"
_FIELDS = "title,authors,year,venue,abstract,externalIds,openAccessPdf"


def _headers(api_key: str = "") -> dict:
    h = {"User-Agent": "wiki-paper-downloader/1.0"}
    if api_key:
        h["x-api-key"] = api_key
    return h


def fetch_by_arxiv(arxiv_id: str, api_key: str = "") -> PaperMeta | None:
    return _fetch(f"arXiv:{arxiv_id}", arxiv_id, api_key)


def fetch_by_doi(doi: str, api_key: str = "") -> PaperMeta | None:
    return _fetch(doi, doi, api_key)


def fetch_by_s2id(s2_id: str, api_key: str = "") -> PaperMeta | None:
    return _fetch(s2_id, s2_id, api_key)


def _fetch(paper_id: str, input_id: str, api_key: str = "") -> PaperMeta | None:
    url = f"{_BASE}/{urllib.parse.quote(paper_id, safe=':')}?fields={_FIELDS}"
    req = urllib.request.Request(url, headers=_headers(api_key))
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code in (404, 429):
            return None
        print(f"  [S2] HTTP {e.code}")
        return None
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        print(f"  [S2] 请求失败: {e}")
        return None

    return _parse(data, input_id)


def _parse(data: dict, input_id: str) -> PaperMeta | None:
    if not data or not data.get("title"):
        return None

    meta = PaperMeta(input_id=input_id)
    meta.title = data.get("title") or ""
    meta.year = str(data.get("year") or "")
    meta.venue = data.get("venue") or ""
    meta.abstract = (data.get("abstract") or "")[:600]
    meta.s2_id = data.get("paperId") or ""
    meta.resolved_by = "semantic_scholar"

    ext = data.get("externalIds") or {}
    meta.arxiv_id = ext.get("ArXiv") or ""
    meta.doi = ext.get("DOI") or ""

    meta.authors = [
        a.get("name", "") for a in (data.get("authors") or []) if a.get("name")
    ]

    oa_pdf = (data.get("openAccessPdf") or {}).get("url") or ""
    if oa_pdf:
        meta.pdf_urls.append(oa_pdf)
    if meta.arxiv_id and not any("arxiv.org/pdf" in u for u in meta.pdf_urls):
        meta.pdf_urls.append(f"https://arxiv.org/pdf/{meta.arxiv_id}")

    return meta
