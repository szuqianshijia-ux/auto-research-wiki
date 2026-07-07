"""
unpaywall.py — Unpaywall API，通过 DOI 查找开放获取 PDF。
需要在 config.py 中配置 UNPAYWALL_EMAIL（使用真实 email）。

文档: https://unpaywall.org/products/api
"""
from __future__ import annotations

import json
import urllib.request
import urllib.error
from .base import PaperMeta


def fetch_by_doi(doi: str, email: str) -> PaperMeta | None:
    """通过 DOI 查询 Unpaywall。email 必须是真实地址。"""
    if not email or "@" not in email:
        return None
    if not doi:
        return None

    clean_doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "")
    url = f"https://api.unpaywall.org/v2/{clean_doi}?email={email}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code in (404, 422):
            return None
        print(f"  [Unpaywall] HTTP {e.code}")
        return None
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        print(f"  [Unpaywall] 请求失败: {e}")
        return None

    return _parse(data, doi)


def _parse(data: dict, input_id: str) -> PaperMeta | None:
    if not data or not data.get("title"):
        return None

    meta = PaperMeta(input_id=input_id)
    meta.title = data.get("title") or ""
    meta.year = str(data.get("year") or "")
    meta.doi = data.get("doi") or ""
    meta.resolved_by = "unpaywall"

    meta.authors = [
        f"{a.get('given', '')} {a.get('family', '')}".strip()
        for a in (data.get("z_authors") or [])
    ]

    # best_oa_location PDF
    best = data.get("best_oa_location") or {}
    pdf_url = best.get("url_for_pdf") or best.get("url") or ""
    if pdf_url:
        meta.pdf_urls.append(pdf_url)

    # all oa_locations as fallback
    for loc in data.get("oa_locations") or []:
        u = loc.get("url_for_pdf") or loc.get("url") or ""
        if u and u not in meta.pdf_urls:
            meta.pdf_urls.append(u)

    return meta
