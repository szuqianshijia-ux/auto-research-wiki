#!/usr/bin/env python3
"""
振动论文批量 ingest 脚本
将 MinerU 转换的 markdown 处理为 wiki/sources 页面（振动项目）

用法：
  python3 tools/vib_batch_ingest.py                  # 处理所有缺失页面
  python3 tools/vib_batch_ingest.py --dry-run        # 预览
  python3 tools/vib_batch_ingest.py --limit 5        # 限制数量
  python3 tools/vib_batch_ingest.py path/to/file.md  # 单文件
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

# ─── 配置（振动项目）────────────────────────────────────────────────────────
VIB_ROOT = Path("${AUTO_RESEARCH_DIR}/research_project")
KB_ROOT = VIB_ROOT
WIKI_DIR = VIB_ROOT / "wiki"
INGEST_CACHE = VIB_ROOT / ".llm-wiki/ingest-cache.json"

# MinerU 转换输出目录
MARKDOWN_DIR = VIB_ROOT / "markdown"

# 需要处理的 markdown 来源目录（raw/sources/ 下）
SOURCE_DIRS = [
    VIB_ROOT / "raw/sources/papers/candidates",
    VIB_ROOT / "raw/sources/papers/6DOF相机运动补偿",
]

LLM_ENDPOINT = "https://llmapi.autel.com"
LLM_MODEL = "claude-haiku-4-5-20251001"


def get_api_key() -> str:
    state_path = Path.home() / ".local/share/com.llmwiki.app/app-state.json"
    with open(state_path) as f:
        state = json.load(f)
    return state["llmConfig"]["apiKey"]


def file_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


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
    if text.startswith("```markdown\n"):
        text = text[len("```markdown\n"):]
    if text.endswith("\n```"):
        text = text[:-4]
    return text.strip()


def get_format_example() -> str:
    sources_dir = WIKI_DIR / "sources"
    examples = sorted(sources_dir.glob("*.md"), key=os.path.getmtime, reverse=True)
    for ex in examples[:5]:
        content = ex.read_text(encoding="utf-8")
        if len(content) > 500:
            return f"示例文件名: {ex.name}\n\n{content[:2000]}"
    return ""


def generate_source_page(source_content: str, filename: str, example: str) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    system = f"""你是一个知识库构建助手，负责将原始文档转换为结构化的 wiki/sources 页面。

知识库目的：组织研究材料，帮助回答：
- 研究领域的方法与算法
- 相机运动补偿与6DOF校正技术
- 运动放大、相位估计、频率识别方法
- 抗干扰实验设计与验证

以下是一个现有 wiki/sources 页面的示例格式，你需要严格遵循这个格式：

{example}

规则：
1. 必须使用 YAML frontmatter（---），包含 type/title/created/updated/tags/related/sources 字段
2. type 固定为 source
3. tags 是小写英文标签列表，与研究领域相关
4. related 是相关 wiki 页面的 kebab-case 标识符列表（不含路径）
5. sources 列表包含原始文件名
6. 正文用中文，技术术语保留英文
7. 结构清晰，包含：研究问题/贡献、核心方法、关键结果、与本项目的关联
8. 今天日期：{today}"""

    messages = [
        {
            "role": "user",
            "content": f"""请将以下论文文档转换为 wiki/sources 页面格式。

原始文件名：{filename}

文档内容（前5000字）：
{source_content[:5000]}

请生成一个结构化的 wiki/sources 页面，提炼论文核心贡献和方法，与研究方向关联。""",
        }
    ]
    return call_llm(messages, system=system, max_tokens=3000)


def load_cache() -> dict:
    if INGEST_CACHE.exists():
        with open(INGEST_CACHE) as f:
            cache = json.load(f)
        if "entries" in cache and isinstance(cache["entries"], dict):
            return cache["entries"], cache
        elif isinstance(cache, dict):
            return cache, cache
    return {}, {}


def save_cache(entries: dict, cache: dict, filename: str, entry: dict):
    if "entries" in cache and isinstance(cache["entries"], dict):
        cache["entries"][filename] = entry
    else:
        cache[filename] = entry
    with open(INGEST_CACHE, "w") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def ingest_file(source_path: Path, dry_run: bool = False) -> bool:
    filename = source_path.name
    print(f"\n📄 处理: {filename}")

    entries, cache = load_cache()
    content_hash = file_hash(source_path)

    if filename in entries and entries[filename].get("hash") == content_hash:
        print(f"  ⏭  已处理（hash相同），跳过")
        return False

    target = WIKI_DIR / "sources" / filename
    if target.exists():
        print(f"  ⏭  wiki/sources/{filename} 已存在，跳过")
        return False

    if dry_run:
        print(f"  (dry-run) 将处理 → wiki/sources/{filename}")
        return True

    source_content = source_path.read_text(encoding="utf-8", errors="replace")
    example = get_format_example()

    print("  🤖 生成 wiki/sources 页面...")
    source_page = generate_source_page(source_content, filename, example)
    print(f"  ✓ {len(source_page)} 字符")

    (WIKI_DIR / "sources").mkdir(parents=True, exist_ok=True)
    target.write_text(source_page, encoding="utf-8")
    os.chmod(target, 0o755)

    save_cache(entries, cache, filename, {
        "hash": content_hash,
        "timestamp": int(time.time() * 1000),
        "filesWritten": [f"wiki/sources/{filename}"],
    })
    print(f"  ✅ 写入 wiki/sources/{filename}")
    return True


def find_missing_papers() -> list[Path]:
    """找出已复制到 raw/sources 但缺少 wiki/sources 页面的论文 markdown"""
    missing = []
    for src_dir in SOURCE_DIRS:
        if not src_dir.exists():
            continue
        for md_file in sorted(src_dir.glob("*.md")):
            target = WIKI_DIR / "sources" / md_file.name
            if not target.exists():
                missing.append(md_file)
    return missing


def main():
    parser = argparse.ArgumentParser(description="振动论文批量 ingest")
    parser.add_argument("files", nargs="*", help="指定文件路径（不指定则处理所有缺失）")
    parser.add_argument("--dry-run", action="store_true", help="预览，不写文件")
    parser.add_argument("--limit", type=int, default=None, help="最多处理 N 个")
    args = parser.parse_args()

    if args.files:
        targets = [Path(f) for f in args.files]
    else:
        targets = find_missing_papers()
        print(f"找到 {len(targets)} 个缺少 wiki/sources 页面的论文")

    if args.limit:
        targets = targets[:args.limit]

    success = 0
    skip = 0
    for i, path in enumerate(targets, 1):
        print(f"\n[{i}/{len(targets)}]", end="")
        try:
            processed = ingest_file(path, dry_run=args.dry_run)
            if processed:
                success += 1
            else:
                skip += 1
        except Exception as e:
            print(f"  ❌ 错误: {e}")
        if not args.dry_run and i < len(targets):
            time.sleep(0.5)

    print(f"\n\n{'(dry-run) ' if args.dry_run else ''}完成：处理 {success} 篇，跳过 {skip} 篇")


if __name__ == "__main__":
    main()
