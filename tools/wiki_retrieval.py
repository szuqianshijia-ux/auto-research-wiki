#!/usr/bin/env python3
"""
wiki_retrieval.py — Multi-hop retrieval tool for LLM Wiki knowledge base.

Usage:
  python3 wiki_retrieval.py "query string"                  # depth=1 multi-hop search
  python3 wiki_retrieval.py "query" --depth 2               # 2-hop expansion
  python3 wiki_retrieval.py "query" --depth 0               # single-hop (plain search)
  python3 wiki_retrieval.py "query" --community             # include community context
  python3 wiki_retrieval.py "query" --topk 8 --max-related 15
  python3 wiki_retrieval.py --build-index                   # rebuild graph-index.json
  python3 wiki_retrieval.py --build-community               # rebuild community-index.json (calls LLM)
"""

import argparse
import json
import os
import re
import sys
import urllib.request
import urllib.error

# ── Config ────────────────────────────────────────────────────────────────────
# 所有配置均通过环境变量注入，无硬编码项目路径。
# 用法：WIKI_PROJECT_ID=<your-project-id> \
#       WIKI_KB_PATH=<path-to-your-kb> \
#       python3 wiki_retrieval.py "query"

BASE_URL   = os.environ.get("LLM_WIKI_BASE_URL", "http://localhost:19828/api/v1")
TOKEN      = os.environ.get("LLM_WIKI_API_TOKEN", "")
PROJECT_ID = os.environ.get("WIKI_PROJECT_ID", "") or os.environ.get("EMBODIED_PROJECT_ID", "")
KB_PATH    = os.environ.get("WIKI_KB_PATH", "")
GRAPH_INDEX_PATH    = os.path.join(KB_PATH, ".llm-wiki", "graph-index.json") if KB_PATH else ""
COMMUNITY_INDEX_PATH = os.path.join(KB_PATH, ".llm-wiki", "community-index.json") if KB_PATH else ""

LLM_API_URL  = os.environ.get("LLM_API_ENDPOINT", "")
LLM_API_KEY  = None
LLM_MODEL    = os.environ.get("LLM_MODEL", "claude-sonnet-4-20250514")

# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _headers():
    return {"X-LLM-Wiki-Token": TOKEN, "Content-Type": "application/json"}


def _check_config():
    if not TOKEN:
        print("[ERROR] LLM_WIKI_API_TOKEN not set. Add it to .env or export it.", file=sys.stderr)
        sys.exit(1)
    if not PROJECT_ID:
        print("[ERROR] WIKI_PROJECT_ID not set. Add it to .env or export it.", file=sys.stderr)
        sys.exit(1)


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"[ERROR] HTTP {e.code}: {e.reason} — URL: {url}", file=sys.stderr)
        if e.code == 401:
            print("Check LLM_WIKI_API_TOKEN is correct.", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"[ERROR] Cannot connect to LLM Wiki: {e.reason}", file=sys.stderr)
        print(f"Ensure LLM Wiki is running at {BASE_URL}", file=sys.stderr)
        sys.exit(1)


def _post(url: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=_headers(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"[ERROR] HTTP {e.code}: {e.reason} — URL: {url}", file=sys.stderr)
        if e.code == 401:
            print("Check LLM_WIKI_API_TOKEN is correct.", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"[ERROR] Cannot connect to LLM Wiki: {e.reason}", file=sys.stderr)
        print(f"Ensure LLM Wiki is running at {BASE_URL}", file=sys.stderr)
        sys.exit(1)


# ── Wiki API calls ────────────────────────────────────────────────────────────

def api_search(query: str, topK: int = 5, include_content: bool = True) -> list[dict]:
    _check_config()
    url = f"{BASE_URL}/projects/{PROJECT_ID}/search"
    resp = _post(url, {"query": query, "topK": topK, "includeContent": include_content})
    return resp.get("results", [])


def api_read_file(path: str) -> str | None:
    """Read a wiki file by its relative path (wiki/... or raw/sources/...)."""
    encoded = urllib.parse.quote(path, safe="")
    url = f"{BASE_URL}/projects/{PROJECT_ID}/files/content?path={encoded}"
    try:
        result = _get(url)
        return result.get("content", "")
    except urllib.error.HTTPError:
        return None


# ── Frontmatter parsing ───────────────────────────────────────────────────────

def _parse_frontmatter(content: str) -> dict:
    """Extract YAML frontmatter fields as raw strings."""
    if not content.startswith("---"):
        return {}
    end = content.find("\n---", 3)
    if end == -1:
        return {}
    fm_text = content[3:end]
    fields = {}
    for line in fm_text.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fields[k.strip()] = v.strip()
    return fields


def _extract_related_slugs(content: str) -> list[str]:
    """
    Extract related page slugs from:
      - frontmatter `related: [a, b, c]` or `related:\n  - a`
      - inline [[wikilinks]] in body
    Returns slug list (no wiki/ prefix, no .md extension).
    """
    slugs: list[str] = []

    # frontmatter related: [a, b, c]
    fm_match = re.search(r'^related:\s*\[([^\]]+)\]', content, re.MULTILINE)
    if fm_match:
        for s in fm_match.group(1).split(","):
            slug = s.strip().strip('"').strip("'")
            if slug:
                slugs.append(slug)

    # frontmatter related:\n  - a
    fm_block = re.findall(r'^related:(.*?)(?=^\w|\Z)', content, re.MULTILINE | re.DOTALL)
    if fm_block:
        for item in re.findall(r'^\s*-\s+(.+)$', fm_block[0], re.MULTILINE):
            slug = item.strip().strip('"').strip("'")
            if slug and slug not in slugs:
                slugs.append(slug)

    # [[wikilinks]] in body (after frontmatter)
    body_start = content.find("\n---\n", 3)
    body = content[body_start:] if body_start != -1 else content
    for m in re.finditer(r'\[\[([^\]|]+?)(?:\|[^\]]+?)?\]\]', body):
        slug = m.group(1).strip()
        if slug and slug not in slugs:
            slugs.append(slug)

    return slugs


def _slug_to_path(slug: str) -> str | None:
    """Try to resolve a slug like 'diffusion-policy' to its wiki path."""
    wiki_dir = os.path.join(KB_PATH, "wiki")
    for subdir in ("concepts", "entities", "sources", "queries", "synthesis", "comparisons"):
        candidate = os.path.join(wiki_dir, subdir, f"{slug}.md")
        if os.path.exists(candidate):
            return f"wiki/{subdir}/{slug}.md"
    return None


# ── Graph index ───────────────────────────────────────────────────────────────

def build_graph_index(kb_path: str = KB_PATH) -> dict:
    """
    Parse all wiki/*.md files, extract related/wikilink edges.
    Returns adjacency dict: {slug: {"path": str, "type": str, "related": [slugs]}}
    Also writes GRAPH_INDEX_PATH.
    """
    import urllib.parse  # noqa: needed for _slug_to_path
    wiki_dir = os.path.join(kb_path, "wiki")
    graph: dict = {}

    for root, _, files in os.walk(wiki_dir):
        for fname in files:
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(root, fname)
            slug = fname[:-3]
            rel_path = os.path.relpath(fpath, wiki_dir)
            node_type = rel_path.split(os.sep)[0]  # concepts/entities/...

            try:
                with open(fpath, encoding="utf-8") as f:
                    content = f.read()
            except OSError:
                continue

            related = _extract_related_slugs(content)
            graph[slug] = {
                "path": f"wiki/{rel_path.replace(os.sep, '/')}",
                "type": node_type,
                "related": related,
            }

    os.makedirs(os.path.dirname(GRAPH_INDEX_PATH), exist_ok=True)
    with open(GRAPH_INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)

    print(f"[graph-index] {len(graph)} nodes, written to {GRAPH_INDEX_PATH}", file=sys.stderr)
    return graph


def load_graph_index() -> dict:
    if os.path.exists(GRAPH_INDEX_PATH):
        with open(GRAPH_INDEX_PATH, encoding="utf-8") as f:
            return json.load(f)
    print("[graph-index] Not found, building...", file=sys.stderr)
    return build_graph_index()


# ── Community index ───────────────────────────────────────────────────────────

def build_community_index() -> list[dict]:
    """
    Louvain community detection over wiki graph, then LLM-summarize each community.
    Writes COMMUNITY_INDEX_PATH and returns list of community dicts.
    """
    try:
        import networkx as nx
        from networkx.algorithms.community import greedy_modularity_communities
    except ImportError:
        print("pip install networkx", file=sys.stderr)
        sys.exit(1)

    graph = load_graph_index()
    G = nx.Graph()
    for slug, node in graph.items():
        G.add_node(slug, type=node["type"])
    for slug, node in graph.items():
        for rel in node.get("related", []):
            if rel in graph:
                G.add_edge(slug, rel)

    print(f"[community] Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges", file=sys.stderr)

    communities = list(greedy_modularity_communities(G))
    communities.sort(key=len, reverse=True)
    print(f"[community] Detected {len(communities)} communities", file=sys.stderr)

    result = []
    for i, comm in enumerate(communities):
        if len(comm) < 3:  # skip trivial singleton/pair communities
            continue
        members = list(comm)
        # top members by degree
        top = sorted(members, key=lambda s: G.degree(s), reverse=True)[:15]
        sources = [s for s in members if graph.get(s, {}).get("type") == "sources"][:5]

        # Build a brief description for LLM
        top_titles = []
        for slug in top[:10]:
            node = graph.get(slug, {})
            top_titles.append(slug)

        summary = _llm_community_summary(i, top_titles, len(members))

        result.append({
            "id": i,
            "size": len(members),
            "top_members": top[:15],
            "sources": sources,
            "summary": summary,
        })
        print(f"  community {i}: {len(members)} members — {summary[:60]}...", file=sys.stderr)

    os.makedirs(os.path.dirname(COMMUNITY_INDEX_PATH), exist_ok=True)
    with open(COMMUNITY_INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"[community] Written to {COMMUNITY_INDEX_PATH}", file=sys.stderr)
    return result


def _llm_community_summary(community_id: int, slugs: list[str], total: int) -> str:
    """Call Autel API to generate a 2-sentence community summary."""
    key = _get_llm_key()
    if not key:
        return f"Community {community_id} ({total} pages): " + ", ".join(slugs[:5])

    prompt = (
        f"下面是一个知识图谱社区的主要概念节点列表（共{total}个页面），"
        "请用2句话概括这个社区的主题和核心研究方向（中文回答）：\n"
        + "\n".join(f"- {s}" for s in slugs)
    )
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    body = json.dumps({
        "model": LLM_MODEL,
        "max_tokens": 150,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(LLM_API_URL, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"Community {community_id} ({total} pages): " + ", ".join(slugs[:5])


def load_community_index() -> list[dict]:
    if os.path.exists(COMMUNITY_INDEX_PATH):
        with open(COMMUNITY_INDEX_PATH, encoding="utf-8") as f:
            return json.load(f)
    return []


def _find_relevant_communities(query_slugs: set[str], communities: list[dict], top_n: int = 2) -> list[dict]:
    """Find communities that overlap most with query result slugs."""
    scored = []
    for comm in communities:
        members = set(comm.get("top_members", []))
        overlap = len(members & query_slugs)
        if overlap > 0:
            scored.append((overlap, comm))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:top_n]]


# ── LLM API key ──────────────────────────────────────────────────────────────

def _get_llm_key() -> str | None:
    global LLM_API_KEY
    if LLM_API_KEY:
        return LLM_API_KEY
    LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
    if LLM_API_KEY:
        return LLM_API_KEY
    settings_path = os.path.expanduser("~/.claude/settings.json")
    try:
        with open(settings_path) as f:
            settings = json.load(f)
        LLM_API_KEY = settings.get("env", {}).get("ANTHROPIC_AUTH_TOKEN")
        return LLM_API_KEY
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return None


# ── Multi-hop smart search ────────────────────────────────────────────────────

def smart_search(
    query: str,
    depth: int = 1,
    topK: int = 5,
    max_related: int = 15,
    include_community: bool = False,
) -> dict:
    """
    Multi-hop retrieval:
      depth=0 → plain search results only
      depth=1 → search + 1-hop related expansion
      depth=2 → search + 2-hop expansion

    Returns dict with keys: core_results, related_pages, community_context
    """
    # Step 1: initial search
    core = api_search(query, topK=topK, include_content=True)

    if depth == 0 or not core:
        return {"core_results": core, "related_pages": [], "community_context": []}

    # Step 2: extract slugs from core results
    graph = load_graph_index()
    seen_paths: set[str] = set(r["path"] for r in core)
    seen_slugs: set[str] = set()
    expand_queue: list[str] = []

    for result in core:
        content = result.get("content", "")
        # slug from path: wiki/concepts/foo.md → foo
        path = result.get("path", "")
        slug = path.rsplit("/", 1)[-1].replace(".md", "")
        seen_slugs.add(slug)
        related = _extract_related_slugs(content)
        for rel in related:
            if rel not in seen_slugs:
                expand_queue.append(rel)

    # Step 3: hop expansion
    related_pages: list[dict] = []
    for hop in range(depth):
        next_queue: list[str] = []
        for slug in expand_queue[:max_related]:
            if slug in seen_slugs:
                continue
            seen_slugs.add(slug)
            # look up in graph index for path
            node = graph.get(slug)
            if not node:
                # try to find file directly
                wiki_path = _slug_to_path(slug)
            else:
                wiki_path = node["path"]
            if not wiki_path:
                continue

            content = api_read_file(wiki_path)
            if content is None:
                continue

            related_pages.append({
                "path": wiki_path,
                "slug": slug,
                "type": node["type"] if node else "unknown",
                "content": content,
                "hop": hop + 1,
                "via": "related/wikilink",
            })
            seen_paths.add(wiki_path)

            # prepare next hop
            if hop + 1 < depth:
                next_slugs = _extract_related_slugs(content)
                for ns in next_slugs:
                    if ns not in seen_slugs:
                        next_queue.append(ns)

        expand_queue = next_queue

    # Step 4: community context (optional)
    community_context: list[dict] = []
    if include_community:
        communities = load_community_index()
        if communities:
            relevant = _find_relevant_communities(seen_slugs, communities, top_n=2)
            community_context = relevant

    return {
        "core_results": core,
        "related_pages": related_pages,
        "community_context": community_context,
    }


# ── Context packing ───────────────────────────────────────────────────────────

def pack_context(results: dict, max_content_chars: int = 1500) -> str:
    """
    Format retrieval results into a structured context block for Claude.
    """
    lines: list[str] = []
    core = results.get("core_results", [])
    related = results.get("related_pages", [])
    communities = results.get("community_context", [])

    def _truncate(text: str, n: int) -> str:
        return text[:n] + "..." if len(text) > n else text

    # ── Core results ──
    if core:
        lines.append("## 核心检索结果（语义+关键词匹配）\n")
        for r in core:
            path = r.get("path", "")
            slug = path.rsplit("/", 1)[-1].replace(".md", "")
            score = r.get("score", 0)
            title = r.get("title") or slug
            node_type = path.split("/")[1] if "/" in path else ""
            content = r.get("content", r.get("snippet", ""))
            lines.append(f"### [{node_type}: {slug}] {title}  (score={score})")
            lines.append(_truncate(content, max_content_chars))
            lines.append("")

    # ── Related pages by hop ──
    by_hop: dict[int, list] = {}
    for p in related:
        by_hop.setdefault(p["hop"], []).append(p)

    for hop in sorted(by_hop.keys()):
        pages = by_hop[hop]
        label = "1跳关联" if hop == 1 else f"{hop}跳关联"
        lines.append(f"## 关联上下文（{label}展开）\n")
        for p in pages:
            slug = p["slug"]
            ptype = p.get("type", "")
            content = p.get("content", "")
            # extract title from content
            title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            title = title_match.group(1) if title_match else slug
            lines.append(f"### [{ptype}: {slug}] {title}")
            lines.append(_truncate(content, max_content_chars // 2))
            lines.append("")

    # ── Community context ──
    if communities:
        lines.append("## 知识社区上下文\n")
        for comm in communities:
            summary = comm.get("summary", "")
            members = comm.get("top_members", [])[:8]
            lines.append(f"**社区 {comm['id']}** ({comm['size']} 页面)")
            lines.append(summary)
            lines.append(f"主要成员: {', '.join(members)}")
            lines.append("")

    if not lines:
        return "（无检索结果）"

    return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────────────────────────

import urllib.parse  # ensure available for _slug_to_path


def main():
    parser = argparse.ArgumentParser(description="Wiki multi-hop retrieval tool")
    parser.add_argument("query", nargs="?", help="Search query")
    parser.add_argument("--depth", type=int, default=1, help="Hop depth (0=plain, 1=default, 2=deep)")
    parser.add_argument("--topk", type=int, default=5, help="Top-K initial results")
    parser.add_argument("--max-related", type=int, default=15, help="Max related pages per hop")
    parser.add_argument("--community", action="store_true", help="Include community context")
    parser.add_argument("--json", action="store_true", help="Output raw JSON instead of formatted text")
    parser.add_argument("--build-index", action="store_true", help="Rebuild graph-index.json from wiki files")
    parser.add_argument("--build-community", action="store_true", help="Rebuild community-index.json (calls LLM)")
    args = parser.parse_args()

    if args.build_index:
        build_graph_index()
        return

    if args.build_community:
        build_community_index()
        return

    if not args.query:
        parser.print_help()
        sys.exit(1)

    results = smart_search(
        args.query,
        depth=args.depth,
        topK=args.topk,
        max_related=args.max_related,
        include_community=args.community,
    )

    if args.json:
        # strip full content for JSON output to keep it manageable
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(pack_context(results))


if __name__ == "__main__":
    main()
