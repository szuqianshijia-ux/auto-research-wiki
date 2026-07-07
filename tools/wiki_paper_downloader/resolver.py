"""
resolver.py — 输入解析和源分发。
接受任意字符串（arXiv ID、DOI、URL、GitHub URL），
调用合适的 source 模块获取 PaperMeta 和 PDF URL 列表。
"""
from __future__ import annotations

import re
from .sources.base import PaperMeta
from .sources import arxiv, openalex, semantic_scholar, unpaywall, github

_ARXIV_RE = re.compile(r"(?:arxiv[:\s/]*|abs/|pdf/)?(\d{4}\.\d{4,5}(?:v\d+)?)", re.IGNORECASE)
_DOI_RE = re.compile(r"10\.\d{4,}/\S+")
_GITHUB_RE = re.compile(r"github\.com/[\w.-]+/[\w.-]+")
_S2_RE = re.compile(r"[0-9a-f]{40}")  # Semantic Scholar 40-char hex ID


def resolve(
    input_id: str,
    unpaywall_email: str = "",
    s2_api_key: str = "",
    verbose: bool = True,
) -> PaperMeta:
    """
    从用户输入解析论文元数据，按优先级尝试各数据源。
    返回填充好的 PaperMeta（包含 pdf_urls 列表）。
    """

    def log(msg: str):
        if verbose:
            print(f"  {msg}")

    # 1. GitHub URL / repo
    if "github.com" in input_id:
        repo = github.parse_repo(input_id)
        if repo:
            log(f"[GitHub] 检测到仓库: {repo}")
            return github.make_meta_from_repo(repo)

    # 2. DOI（必须在 arXiv 之前检测，避免 DOI 中的数字被误匹配）
    # 裸 DOI 以 "10." 开头，DOI URL 包含 "doi.org/"
    doi_match = _DOI_RE.search(input_id)
    _is_doi = doi_match and (
        input_id.strip().startswith("10.")
        or "doi.org/" in input_id
    )

    if not _is_doi:
        # 3. arXiv ID 或 arXiv URL（仅在确认不是 DOI 时才匹配）
        arxiv_id = arxiv.parse_arxiv_id(input_id)
        if arxiv_id:
            log(f"[arXiv] ID: {arxiv_id}")
            meta = arxiv.fetch(arxiv_id)
            if meta.title:
                log(f"  标题: {meta.title}")
            # 补充 OpenAlex 的 PDF URL（可能有更好的 OA 链接）
            oa_meta = openalex.fetch_by_arxiv(arxiv_id)
            if oa_meta and oa_meta.pdf_urls:
                for u in oa_meta.pdf_urls:
                    if u not in meta.pdf_urls:
                        meta.pdf_urls.insert(0, u)
            return meta

    # DOI 路径
    doi_match = _DOI_RE.search(input_id)
    if doi_match:
        doi = doi_match.group(0).rstrip(".")
        log(f"[DOI] {doi}")

        # 先 OpenAlex（免费无限制）
        meta = openalex.fetch_by_doi(doi)
        if meta and meta.title:
            log(f"  [OpenAlex] 标题: {meta.title}")
            meta.doi = doi

            # 再 Unpaywall 补充 PDF URL
            if unpaywall_email:
                up = unpaywall.fetch_by_doi(doi, unpaywall_email)
                if up:
                    for u in up.pdf_urls:
                        if u not in meta.pdf_urls:
                            meta.pdf_urls.append(u)

            # 如果有 arXiv ID 但 pdf_urls 里没有 arXiv 链接，补上
            if meta.arxiv_id and not any("arxiv.org/pdf" in u for u in meta.pdf_urls):
                meta.pdf_urls.append(f"https://arxiv.org/pdf/{meta.arxiv_id}")
            return meta

        # OpenAlex 失败，尝试 Semantic Scholar
        log("  [OpenAlex] 未找到，尝试 Semantic Scholar…")
        meta = semantic_scholar.fetch_by_doi(doi, s2_api_key)
        if meta and meta.title:
            log(f"  [S2] 标题: {meta.title}")
            return meta

        # 最后 Unpaywall
        if unpaywall_email:
            meta = unpaywall.fetch_by_doi(doi, unpaywall_email)
            if meta and meta.title:
                log(f"  [Unpaywall] 标题: {meta.title}")
                return meta

        # 返回空 meta（仅含 DOI）
        m = PaperMeta(input_id=input_id, doi=doi)
        m.resolved_by = "doi-unresolved"
        return m

    # 4. Semantic Scholar 40-char ID
    if _S2_RE.fullmatch(input_id.strip()):
        log(f"[Semantic Scholar] ID: {input_id}")
        meta = semantic_scholar.fetch_by_s2id(input_id.strip(), s2_api_key)
        if meta:
            return meta

    # 5. 未识别：当成标题搜索（OpenAlex）
    log(f"[OpenAlex] 标题搜索: {input_id[:60]}…")
    results = openalex.search_by_title(input_id, limit=3)
    if results:
        meta = results[0]
        log(f"  找到: {meta.title}")
        return meta

    # 完全无法解析
    return PaperMeta(input_id=input_id, resolved_by="unknown")
