#!/usr/bin/env python3
"""
Wiki 检索优化工具：
  detect-dups    检测近重复文件，输出分组报告
  merge-dups     LLM 合并重复组（先运行 detect-dups）
  trim           LLM 压缩超长文件

用法：
  python3 tools/wiki_optimizer.py detect-dups [--type concept|entity|source]
  python3 tools/wiki_optimizer.py merge-dups  [--dry-run]
  python3 tools/wiki_optimizer.py trim --type concept --max-lines 80 [--dry-run] [--limit N]
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
import urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# ─── 配置 ────────────────────────────────────────────────────────────────────
_auto_research_dir = os.environ.get("AUTO_RESEARCH_DIR", "")
_kb_subpath = os.environ.get("WIKI_KB_SUBPATH", "")
KB_ROOT = Path(os.path.join(_auto_research_dir, _kb_subpath)) if _auto_research_dir else Path(".")
WIKI_DIR = KB_ROOT / "wiki"
BACKUP_DIR = KB_ROOT / ".wiki-backup"
DUPS_REPORT = KB_ROOT / ".wiki-backup/dups-report.json"

LLM_ENDPOINT = os.environ.get("LLM_API_ENDPOINT", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "claude-haiku-4-5-20251001")

TYPE_DIRS = {
    "concept": WIKI_DIR / "concepts",
    "entity": WIKI_DIR / "entities",
    "source": WIKI_DIR / "sources",
}


def get_api_key() -> str:
    key = os.environ.get("LLM_API_KEY", "")
    if key:
        return key
    state_path = Path.home() / ".local/share/com.llmwiki.app/app-state.json"
    try:
        with open(state_path) as f:
            state = json.load(f)
        return state["llmConfig"]["apiKey"]
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        print(f"[ERROR] Cannot read API key: {e}", file=sys.stderr)
        print("Set LLM_API_KEY env var or install LLM Wiki app.", file=sys.stderr)
        sys.exit(1)


def call_llm(messages: list, system: str = "", max_tokens: int = 4096) -> str:
    api_key = get_api_key()
    payload = {"model": LLM_MODEL, "max_tokens": max_tokens, "messages": messages}
    if system:
        payload["system"] = system
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{LLM_ENDPOINT}/v1/messages",
        data=data,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read())
    text = result["content"][0]["text"]
    # 去除 LLM 有时加的 ```markdown 包装
    if text.startswith("```markdown\n"):
        text = text[len("```markdown\n"):]
    if text.endswith("\n```"):
        text = text[:-4]
    return text.strip()


def backup_file(path: Path):
    """备份文件到 .wiki-backup/，保留相对路径结构"""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    rel = path.relative_to(WIKI_DIR)
    dest = BACKUP_DIR / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dest)


def read_frontmatter(path: Path) -> dict:
    """解析 YAML frontmatter（简单解析，不依赖 pyyaml）"""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    fm_text = text[3:end]
    result = {}
    for line in fm_text.splitlines():
        if ":" in line and not line.startswith(" ") and not line.startswith("-"):
            k, _, v = line.partition(":")
            result[k.strip()] = v.strip()
    return result


# ─── DETECT-DUPS ─────────────────────────────────────────────────────────────

def slug_prefix(slug: str, n: int = 3) -> str:
    """取 slug 前 n 段作为前缀"""
    parts = slug.split("-")
    return "-".join(parts[:n])


def detect_dups(file_type: str) -> dict:
    """
    检测近重复：
    1. 文件名前缀分组（≥3 个文件共享前 3 段前缀）
    2. 标题相似分组（去停用词后完全相同）
    返回 {group_key: [slug1, slug2, ...]} 的字典
    """
    d = TYPE_DIRS.get(file_type)
    if not d or not d.exists():
        print(f"目录不存在: {d}")
        return {}

    files = sorted(d.glob("*.md"))
    slugs = [f.stem for f in files]

    groups = defaultdict(list)

    # 方法 1：前缀分组
    prefix_groups = defaultdict(list)
    for slug in slugs:
        prefix_groups[slug_prefix(slug, 3)].append(slug)
    for prefix, members in prefix_groups.items():
        if len(members) >= 2:
            key = f"prefix:{prefix}"
            groups[key] = members

    # 方法 2：标题归一化分组（去连字符、去序号前缀）
    title_groups = defaultdict(list)
    for slug in slugs:
        # 去除序号前缀（如 "02-", "15hz-"）
        normalized = re.sub(r"^\d+[-_]", "", slug)
        # 将 plural 统一：trailing "s" 去掉
        normalized = re.sub(r"s$", "", normalized)
        title_groups[normalized].append(slug)
    for title, members in title_groups.items():
        if len(members) >= 2 and len(title) > 4:
            key = f"title:{title}"
            # 避免与前缀分组重复
            existing = {frozenset(v) for v in groups.values()}
            if frozenset(members) not in existing:
                groups[key] = members

    # 过滤掉明显不相关的（组内文件名差距太大）
    filtered = {}
    for key, members in groups.items():
        filtered[key] = sorted(members)

    return filtered


def cmd_detect_dups(args):
    types = [args.type] if args.type else ["concept", "entity"]
    all_groups = {}
    for t in types:
        print(f"\n── {t} ──────────────────────────────────")
        groups = detect_dups(t)
        for key, members in sorted(groups.items(), key=lambda x: -len(x[1])):
            print(f"  [{len(members)}] {key}")
            for m in members:
                print(f"      {m}")
        all_groups[t] = groups
        print(f"  共 {len(groups)} 组近重复")

    # 保存报告
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    with open(DUPS_REPORT, "w") as f:
        json.dump(all_groups, f, ensure_ascii=False, indent=2)
    print(f"\n报告已保存: {DUPS_REPORT}")


# ─── MERGE-DUPS ──────────────────────────────────────────────────────────────

def merge_group(file_type: str, members: list[str], dry_run: bool):
    """将一组重复文件合并为一个"""
    d = TYPE_DIRS[file_type]
    paths = [d / f"{m}.md" for m in members if (d / f"{m}.md").exists()]
    if len(paths) < 2:
        return

    # 选最长文件名（通常最具代表性）作为目标 slug
    target_slug = min(members, key=len)
    target_path = d / f"{target_slug}.md"

    print(f"  合并 {len(paths)} 个文件 → {target_slug}.md")
    if dry_run:
        for p in paths:
            print(f"    (dry) {p.name}")
        return

    # 读取所有内容
    contents = []
    for p in paths:
        backup_file(p)
        contents.append(f"=== {p.stem} ===\n{p.read_text(encoding='utf-8')}")

    combined = "\n\n".join(contents)

    today = datetime.now().strftime("%Y-%m-%d")
    system = f"""你是知识库整理助手。将多个高度相似的 wiki/{file_type} 文件合并为一个高质量的文件。
要求：
1. 保留 YAML frontmatter（type/title/updated/tags/related/sources）
2. 合并所有 tags 和 related（去重）
3. 正文中文，技术术语保留英文
4. 消除重复内容，保留最完整的信息
5. 目标长度：{file_type == 'concept' and '50-80 行' or '80-150 行'}
6. 今天日期：{today}
7. 直接输出合并后的 markdown，不要说明文字"""

    messages = [{"role": "user", "content": f"请合并以下 {len(paths)} 个重复文件：\n\n{combined[:6000]}"}]

    try:
        merged = call_llm(messages, system=system, max_tokens=3000)
    except Exception as e:
        print(f"    LLM 调用失败: {e}")
        return

    # 写入目标文件
    target_path.write_text(merged + "\n", encoding="utf-8")
    print(f"    ✓ 写入 {target_path.name}（{len(merged.splitlines())} 行）")

    # 删除其他文件
    for p in paths:
        if p != target_path:
            p.unlink()
            print(f"    ✗ 删除 {p.name}")


def cmd_merge_dups(args):
    if not DUPS_REPORT.exists():
        print("请先运行 detect-dups")
        sys.exit(1)

    with open(DUPS_REPORT) as f:
        all_groups = json.load(f)

    total_merged = 0
    for file_type, groups in all_groups.items():
        print(f"\n── {file_type} ──")
        for key, members in groups.items():
            d = TYPE_DIRS[file_type]
            existing = [m for m in members if (d / f"{m}.md").exists()]
            if len(existing) < 2:
                continue
            merge_group(file_type, existing, args.dry_run)
            total_merged += 1
            time.sleep(0.5)  # 避免 API rate limit

    print(f"\n合并完成，处理了 {total_merged} 组")


# ─── TRIM ────────────────────────────────────────────────────────────────────

def trim_file(path: Path, max_lines: int, dry_run: bool) -> bool:
    """将超长文件压缩到 max_lines 以内"""
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()
    if len(lines) <= max_lines:
        return False

    file_type = path.parent.name.rstrip("s")  # concepts→concept
    today = datetime.now().strftime("%Y-%m-%d")

    print(f"  压缩 {path.name}（{len(lines)} 行 → {max_lines} 行）")
    if dry_run:
        return True

    backup_file(path)

    system = f"""你是知识库整理助手。将以下 wiki/{file_type} 文件压缩为不超过 {max_lines} 行的精炼版本。
要求：
1. 保留完整的 YAML frontmatter（只更新 updated 为 {today}）
2. 删除重复段落、过度展开的说明、举例过多的部分
3. 保留核心定义、关键机制、重要数据（数字、命令、文件路径等不可删）
4. 正文用中文，技术术语保留英文
5. 直接输出压缩后的 markdown，不要说明文字"""

    messages = [{"role": "user", "content": f"请压缩以下文件到不超过 {max_lines} 行：\n\n{content[:5000]}"}]

    try:
        trimmed = call_llm(messages, system=system, max_tokens=2500)
    except Exception as e:
        print(f"    LLM 调用失败: {e}")
        return False

    new_lines = len(trimmed.splitlines())
    path.write_text(trimmed + "\n", encoding="utf-8")
    print(f"    ✓ {len(lines)} → {new_lines} 行")
    return True


def cmd_trim(args):
    d = TYPE_DIRS.get(args.type)
    if not d:
        print(f"未知类型: {args.type}")
        sys.exit(1)

    files = sorted(d.glob("*.md"), key=lambda p: -p.stat().st_size)
    long_files = [f for f in files if len(f.read_text(encoding="utf-8").splitlines()) > args.max_lines]

    print(f"找到 {len(long_files)} 个超过 {args.max_lines} 行的 {args.type} 文件")

    if args.limit:
        long_files = long_files[:args.limit]
        print(f"（限制处理前 {args.limit} 个）")

    trimmed_count = 0
    for i, path in enumerate(long_files, 1):
        print(f"[{i}/{len(long_files)}] {path.name}")
        if trim_file(path, args.max_lines, args.dry_run):
            trimmed_count += 1
        if not args.dry_run:
            time.sleep(0.3)

    print(f"\n完成，压缩了 {trimmed_count} 个文件")


# ─── 主入口 ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Wiki 检索优化工具")
    sub = parser.add_subparsers(dest="cmd")

    # detect-dups
    p1 = sub.add_parser("detect-dups", help="检测近重复文件")
    p1.add_argument("--type", choices=["concept", "entity", "source"], default=None)

    # merge-dups
    p2 = sub.add_parser("merge-dups", help="LLM 合并重复组")
    p2.add_argument("--dry-run", action="store_true")

    # trim
    p3 = sub.add_parser("trim", help="LLM 压缩超长文件")
    p3.add_argument("--type", choices=["concept", "entity", "source"], required=True)
    p3.add_argument("--max-lines", type=int, default=80)
    p3.add_argument("--dry-run", action="store_true")
    p3.add_argument("--limit", type=int, default=None, help="最多处理 N 个文件")

    args = parser.parse_args()

    if args.cmd == "detect-dups":
        cmd_detect_dups(args)
    elif args.cmd == "merge-dups":
        cmd_merge_dups(args)
    elif args.cmd == "trim":
        cmd_trim(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
