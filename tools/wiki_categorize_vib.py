#!/usr/bin/env python3
"""
振动 wiki/sources 分类标记脚本
1. 给所有 sources 文件的 YAML frontmatter 添加 category 字段
2. 修复 emoji 文件名 → ASCII 前缀
3. 更新 ingest-cache.json

category 取值：
  paper          — 研究论文（arXiv ID / Year-Author / Author_Year / Elsevier 等）
  thesis-chapter — 论文章节稿
  experiment     — 实验记录与数据报告
  report         — 综合研究报告、文献矩阵、深度研究
  management     — 管理文档（清单、计划、协议、说明）
"""

import json
import os
import re
import unicodedata
from datetime import datetime
from pathlib import Path

_auto_research_dir = os.environ.get("AUTO_RESEARCH_DIR", "")
_vib_subpath = os.environ.get("WIKI_VIB_SUBPATH", "research_project")
VIB_ROOT = Path(os.path.join(_auto_research_dir, _vib_subpath)) if _auto_research_dir else Path(".")
SOURCES = VIB_ROOT / "wiki/sources"
CACHE_PATH = VIB_ROOT / ".llm-wiki/ingest-cache.json"
TODAY = datetime.now().strftime("%Y-%m-%d")

# ─── 分类规则 ─────────────────────────────────────────────────────────────────

def detect_category(filename: str) -> str:
    name = filename.removesuffix(".md")

    # ── 论文类 ──────────────────────────────────────────────────────────────
    # arXiv ID: 1307.1188, 2605.21914
    if re.match(r"^\d{4}\.\d{4,5}", name):
        return "paper"
    # Year-Author: 2017-Yang-Full-Field, 1981-Horn-OpticalFlow
    if re.match(r"^1[89]\d{2}-[A-Z]", name) or re.match(r"^200[0-9]-[A-Z]", name):
        return "paper"
    if re.match(r"^201[0-9]-[A-Z]", name) or re.match(r"^202[0-5]-[A-Z]", name):
        return "paper"
    # 2026-Author (新发布论文): 2026-Becerril-UAV
    if re.match(r"^2026-[A-Z][a-z]", name):
        return "paper"
    # Author_Year: Chen_2015_Modal, Collier_Dare_2022
    if re.match(r"^[A-Z][a-z]+_[0-9]{4}", name):
        return "paper"
    # 特殊 Author_Year: Fleet_Jepson_1990, Peeters_1999
    if re.match(r"^[A-Z][a-z]+_[A-Za-z]+_[0-9]{4}", name):
        return "paper"
    # Elsevier DOI 格式: 1-s2.0-SXXX
    if re.match(r"^1-s2\.0-", name):
        return "paper"
    # 2109/2406 系列 arXiv
    if re.match(r"^2[01][0-9]{2}\.[0-9]{4,5}", name):
        return "paper"

    # ── 论文章节 ─────────────────────────────────────────────────────────
    # 01绪论, 01_OUTLINE, 02理论基础, 03S1静态场景
    if re.match(r"^0[1-9][一-鿿_A-Z]", name):
        return "thesis-chapter"
    if re.match(r"^0[1-9]$", name):
        return "thesis-chapter"
    if "臧宗迪" in name or "thesis_e2e" in name:
        return "thesis-chapter"
    # 论文提纲/大纲
    if name in ["论文大纲", "论文提纲", "项目总入口", "写作材料包"]:
        return "thesis-chapter"

    # ── 实验记录 ─────────────────────────────────────────────────────────────
    # 日期实验报告: 2026-05-31_xxx, 2026-07-04_xxx
    if re.match(r"^2026-0[5-7]-[0-9]", name):
        return "experiment"
    # 2026年第N周
    if re.match(r"^2026年第", name):
        return "experiment"
    # 样本/sample 相关
    if re.search(r"sample|样本[0-9]|triplet|SNR|s[12]静态|s[12]相机", name, re.IGNORECASE):
        return "experiment"
    # 实验对齐说明
    if "full2000" in name or "对齐说明" in name:
        return "experiment"
    # STATUS/m2def
    if re.match(r"^(STATUS|m2def)", name):
        return "experiment"

    # ── 研究报告 ─────────────────────────────────────────────────────────────
    if re.search(r"深度研究报告|文献矩阵|文献背景|deep-research-report|PHASE_METHOD", name):
        return "report"
    if re.search(r"基准|BASELINE|证据[口地图]|图表|EVIDENCE|CURRENT_BASELINES", name):
        return "report"
    if re.search(r"论文图表|论文证据|审阅记录|论文图表与证据", name):
        return "report"
    # Google AI 研究报告
    if re.search(r"Google_AI|精读|研究咨询|方案验证", name):
        return "report"

    # ── 管理文档 ─────────────────────────────────────────────────────────────
    return "management"


# ─── 工具函数 ─────────────────────────────────────────────────────────────────

def load_cache():
    if not CACHE_PATH.exists():
        return {}, {}
    with open(CACHE_PATH) as f:
        raw = json.load(f)
    if "entries" in raw:
        return raw["entries"], raw
    return raw, raw

def save_cache(entries, raw):
    if "entries" in raw:
        raw["entries"] = entries
    else:
        raw = entries
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump(raw, f, ensure_ascii=False, indent=2)

def strip_emoji_prefix(name: str) -> str:
    """去除文件名开头的 emoji 字符"""
    result = []
    stripped = False
    for ch in name:
        cat = unicodedata.category(ch)
        # emoji / symbol
        if not stripped and (cat.startswith("S") or ord(ch) > 0x2000 and cat in ("So", "Cn", "Co")):
            continue
        result.append(ch)
        stripped = True
    return "".join(result).lstrip("_").lstrip()

def add_category_to_yaml(path: Path, category: str) -> bool:
    """在 YAML frontmatter 中添加 category 字段（如已存在则跳过）"""
    content = path.read_text(encoding="utf-8")
    if "category:" in content[:500]:
        return False  # 已存在
    # 在 type: source 行之后插入
    content = re.sub(
        r"^(type: source)",
        f"\\1\ncategory: {category}",
        content,
        count=1,
        flags=re.MULTILINE
    )
    # 更新 updated 字段
    content = re.sub(
        r"^updated:.*$",
        f"updated: {TODAY}",
        content,
        count=1,
        flags=re.MULTILINE
    )
    path.write_text(content, encoding="utf-8")
    return True

def rename_with_cache(old_path: Path, new_path: Path, entries: dict):
    if new_path.exists():
        return False
    old_path.rename(new_path)
    old_key = old_path.name
    new_key = new_path.name
    if old_key in entries:
        entries[new_key] = entries.pop(old_key)
        if "filesWritten" in entries[new_key]:
            entries[new_key]["filesWritten"] = [
                f.replace(old_key, new_key) for f in entries[new_key]["filesWritten"]
            ]
        # 也更新 sources 字段
    return True


# ─── 主逻辑 ──────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  振动 wiki/sources 分类标记脚本")
    print("=" * 60)

    entries, raw = load_cache()
    print(f"ingest-cache: {len(entries)} 条记录")

    all_files = sorted(SOURCES.glob("*.md"))
    total = len(all_files)
    print(f"sources 文件总数: {total}")

    # ── Phase 2a: 修复 emoji 文件名 ──────────────────────────────────────────
    print("\n── Phase 2a: 修复 emoji 文件名 ──")
    emoji_fixes = {
        "📍_2篇论文直接下载链接.md": "待下载_2篇论文直接下载链接.md",
        "📖_参考文献_5篇论文.md":    "参考文献_5篇论文.md",
        "📥_待下载论文清单与优先级.md": "待下载_论文清单与优先级.md",
        "📚_核心论文库_写作指南.md":  "核心论文库_写作指南.md",
        "✅_论文库_最终清单.md":       "论文库_最终清单.md",
        "🔐_DOI论文机构权限下载指南.md": "DOI论文机构权限下载指南.md",
        "⚠️_Fleet_Jepson_1990_替代方案.md": "Fleet_Jepson_1990_替代方案.md",
        "📥_剩余2篇论文下载地址.md":  "待下载_剩余2篇论文下载地址.md",
    }
    renamed_count = 0
    for old_name, new_name in emoji_fixes.items():
        old_path = SOURCES / old_name
        new_path = SOURCES / new_name
        if not old_path.exists():
            print(f"  ⏭  {old_name[:30]}... 不存在")
            continue
        if rename_with_cache(old_path, new_path, entries):
            # 同步更新 sources 字段
            try:
                content = new_path.read_text(encoding="utf-8")
                content = re.sub(
                    r'^sources:.*$',
                    f'sources: ["{new_name}"]',
                    content, count=1, flags=re.MULTILINE
                )
                new_path.write_text(content, encoding="utf-8")
            except Exception:
                pass
            print(f"  ✅ {old_name[:35]} → {new_name}")
            renamed_count += 1

    print(f"  共重命名 {renamed_count} 个 emoji 文件")

    # ── Phase 2b: 给所有文件添加 category 字段 ──────────────────────────────
    print("\n── Phase 2b: 添加 category 字段 ──")

    # 重新加载（可能有重命名后的新文件）
    all_files = sorted(SOURCES.glob("*.md"))

    stats = {cat: 0 for cat in ["paper", "thesis-chapter", "experiment", "report", "management", "skip"]}

    for path in all_files:
        category = detect_category(path.name)
        added = add_category_to_yaml(path, category)
        if added:
            stats[category] += 1
        else:
            stats["skip"] += 1

    print("\n  分类统计（新增 category 的文件）：")
    for cat, count in stats.items():
        if cat == "skip":
            print(f"  ⏭  已有 category（跳过）: {count} 个")
        elif count > 0:
            icon = {"paper": "📄", "thesis-chapter": "📝", "experiment": "🔬",
                    "report": "📊", "management": "📋"}.get(cat, "•")
            print(f"  {icon} {cat}: {count} 个")

    # ── 保存 cache ──────────────────────────────────────────────────────────
    save_cache(entries, raw)
    print("\n✅ ingest-cache 已更新")

    # ── 统计验证 ─────────────────────────────────────────────────────────────
    print("\n── 验证：全量 category 分布 ──")
    cat_counts = {}
    for path in SOURCES.glob("*.md"):
        content = path.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"^category:\s*(.+)$", content[:500], re.MULTILINE)
        cat = m.group(1).strip() if m else "MISSING"
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

    for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")

    print("\n完成。建议触发 LLM Wiki rescan。")


if __name__ == "__main__":
    main()
