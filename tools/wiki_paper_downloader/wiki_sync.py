"""
wiki_sync.py — LLM Wiki API 集成。

功能：
  rescan()      — 触发 File Sync Rescan
  search()      — 搜索知识库（关键词+向量混合）
  get_context() — 多跳智能检索，返回结构化上下文（供 Claude 直接使用）

Token 从 ~/.local/share/com.llmwiki.app/app-state.json 自动读取，
也可以通过环境变量 LLM_WIKI_TOKEN 覆盖。
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

WIKI_API_BASE = "http://127.0.0.1:19828/api/v1"
_APPSTATE = Path.home() / ".local/share/com.llmwiki.app/app-state.json"
_CONNECT_TIMEOUT = 5
_RESCAN_TIMEOUT = 60
_SEARCH_TIMEOUT = 15


def _read_token() -> str:
    token = os.environ.get("LLM_WIKI_TOKEN", "")
    if token:
        return token
    try:
        data = json.loads(_APPSTATE.read_text(encoding="utf-8"))
        return data.get("apiConfig", {}).get("token", "")
    except Exception:
        return ""


def _json_get(url: str, token: str, timeout: int) -> dict:
    req = urllib.request.Request(url, headers={"X-LLM-Wiki-Token": token})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _json_post(url: str, token: str, timeout: int) -> dict:
    req = urllib.request.Request(
        url,
        method="POST",
        headers={"X-LLM-Wiki-Token": token, "Content-Length": "0"},
        data=b"",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def rescan(verbose: bool = True, project_id: str = "") -> bool:
    """
    触发 LLM Wiki 指定项目的 File Sync → Rescan。

    Args:
        verbose: 是否输出详细日志
        project_id: 目标项目 ID。若为空，自动从 API 获取当前项目；
                    若指定，直接操作该项目（支持多项目并行）

    Returns True on success, False if wiki is not running or call fails.
    Silently skips if no token is configured.
    """
    token = _read_token()
    if not token:
        if verbose:
            print("  [Wiki] 未找到 token，跳过 Rescan")
        return False

    # 如果未指定 project_id，自动从 API 获取当前项目
    if not project_id:
        try:
            data = _json_get(f"{WIKI_API_BASE}/projects", token, _CONNECT_TIMEOUT)
        except urllib.error.URLError:
            if verbose:
                print("  [Wiki] 服务未运行，跳过 Rescan")
            return False
        except Exception as e:
            if verbose:
                print(f"  [Wiki] 获取项目失败: {e}")
            return False

        project_id = data.get("currentProject", {}).get("id", "")

    if not project_id:
        if verbose:
            print("  [Wiki] 未找到当前项目，跳过 Rescan")
        return False

    try:
        result = _json_post(
            f"{WIKI_API_BASE}/projects/{project_id}/sources/rescan",
            token,
            _RESCAN_TIMEOUT,
        )
    except urllib.error.URLError as e:
        if verbose:
            print(f"  [Wiki] Rescan 请求失败: {e}")
        return False
    except Exception as e:
        if verbose:
            print(f"  [Wiki] Rescan 异常: {e}")
        return False

    changed = len(result.get("result", {}).get("changedTasks", []))
    if verbose:
        print(f"  [Wiki] Rescan 完成 — {changed} 个文件已加入处理队列")
    return True


def search(
    query: str,
    project_id: str = "",
    topK: int = 10,
    include_content: bool = True,
    verbose: bool = False,
) -> list[dict]:
    """
    搜索 wiki 知识库，返回匹配结果列表。

    每条结果包含: path, title, score, snippet, content（当include_content=True时）

    Args:
        query: 搜索查询文本
        project_id: 项目ID，默认自动从wiki服务获取当前项目
        topK: 返回结果数量上限
        include_content: 是否包含完整页面内容
    """
    token = _read_token()
    if not token:
        if verbose:
            print("  [Wiki] 未找到 token")
        return []

    if not project_id:
        try:
            data = _json_get(f"{WIKI_API_BASE}/projects", token, _CONNECT_TIMEOUT)
            project_id = data.get("currentProject", {}).get("id", "")
        except Exception as e:
            if verbose:
                print(f"  [Wiki] 获取项目失败: {e}")
            return []

    if not project_id:
        if verbose:
            print("  [Wiki] 未找到当前项目")
        return []

    body = json.dumps({
        "query": query,
        "topK": topK,
        "includeContent": include_content,
    }).encode()

    req = urllib.request.Request(
        f"{WIKI_API_BASE}/projects/{project_id}/search",
        data=body,
        headers={"X-LLM-Wiki-Token": token, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_SEARCH_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
            results = data.get("results", [])
            if verbose:
                print(f"  [Wiki] 搜索 '{query}' → {len(results)} 条结果")
            return results
    except Exception as e:
        if verbose:
            print(f"  [Wiki] 搜索失败: {e}")
        return []


def get_context(
    query: str,
    depth: int = 1,
    topK: int = 5,
    include_community: bool = False,
    project_id: str = "",
) -> str:
    """
    多跳智能检索，返回结构化上下文字符串，可直接放入 Claude 提示词。

    Args:
        query: 检索查询
        depth: 跳数 (0=仅搜索, 1=1跳关联展开, 2=2跳深度展开)
        topK: 初始搜索返回数量
        include_community: 是否附加知识社区摘要
        project_id: 覆盖项目ID（默认自动获取）

    Returns:
        格式化的上下文字符串，包含核心结果、关联页面、（可选）社区摘要
    """
    # Dynamically import wiki_retrieval from tools dir
    tools_dir = str(Path(__file__).parent.parent)
    if tools_dir not in sys.path:
        sys.path.insert(0, tools_dir)

    try:
        from wiki_retrieval import smart_search, pack_context
    except ImportError as e:
        return f"[Wiki] wiki_retrieval 未找到: {e}"

    # Override project_id in wiki_retrieval if specified
    if project_id:
        import wiki_retrieval
        original_id = wiki_retrieval.PROJECT_ID
        wiki_retrieval.PROJECT_ID = project_id

    try:
        results = smart_search(
            query,
            depth=depth,
            topK=topK,
            include_community=include_community,
        )
        return pack_context(results)
    finally:
        if project_id:
            wiki_retrieval.PROJECT_ID = original_id
