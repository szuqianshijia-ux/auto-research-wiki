#!/usr/bin/env python3
"""
download.py — 多源论文下载器，集成到 LLM Wiki 工作流。

支持输入格式：
  arXiv ID     2509.18644
  DOI          10.1109/ICRA.2023.xxxxxx
  DOI URL      https://doi.org/10.xxxx/...
  arXiv URL    https://arxiv.org/abs/2509.18644
  GitHub URL   https://github.com/owner/repo
  S2 ID        40 位十六进制（Semantic Scholar paper ID）
  标题         "Diffusion Policy"（模糊匹配，结果不保证准确）

数据源解析顺序：
  arXiv → arXiv API + OpenAlex 补充 PDF URL
  DOI   → OpenAlex → Unpaywall（需配置 email）→ Semantic Scholar
  其他  → Semantic Scholar → OpenAlex 标题搜索

用法：
  python3 download.py <ID或URL> [<ID> ...] --dir <目录> [选项]

示例：
  python3 download.py 2509.18644 --dir training
  python3 download.py 10.1109/TRO.2023.123 --dir vla --topic 机器人操作
  python3 download.py https://github.com/Physical-Intelligence/openpi --dir refs
  python3 download.py 2509.18644 2303.18080 --dir training --topic 视觉预训练
  python3 download.py "Diffusion Policy robot" --dir action   # 标题搜索

  # MinerU 转换（需 GPU 且已安装 magic-pdf）
  python3 download.py 2509.18644 --dir training --convert
  python3 download.py 2509.18644 --dir training --convert --markdown-dir /data/md
  python3 download.py 2509.18644 --dir training --convert --add-to-sources
"""

import argparse
import shutil
import sys
from pathlib import Path

# 确保 wiki_paper_downloader 作为包导入
_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE.parent))

from wiki_paper_downloader import config as cfg
from wiki_paper_downloader import resolver, downloader, output, wiki_sync, pdf_converter
from wiki_paper_downloader.sources import github


def _resolve_markdown_dir(args_markdown_dir: str) -> Path:
    """Determine the Markdown output directory from CLI arg / env / default."""
    if args_markdown_dir:
        return Path(args_markdown_dir)
    if cfg.WIKI_MARKDOWN_DIR:
        return cfg.WIKI_MARKDOWN_DIR
    # Default: sibling of raw/sources/ → raw/markdown/
    return cfg.WIKI_PAPERS_BASE.parent.parent / "markdown"


def main():
    parser = argparse.ArgumentParser(
        description="多源论文下载器，输出到 LLM Wiki raw/sources/papers/",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("ids", nargs="+", metavar="ID/URL", help="arXiv ID、DOI、URL 或标题")
    parser.add_argument("--dir", required=True, metavar="子目录",
                        help="目标子目录别名或全名（vla/action/data/deploy/training/refs）")
    parser.add_argument("--name", default="", metavar="短名",
                        help="覆盖自动短名（仅单 ID 时有效）")
    parser.add_argument("--topic", default="", metavar="主题",
                        help="清单文件主题后缀，如 视觉预训练")
    parser.add_argument("--dry-run", action="store_true",
                        help="仅解析和显示，不实际下载")
    parser.add_argument("--no-checklist", action="store_true",
                        help="跳过清单文件更新")
    parser.add_argument("--no-rescan", action="store_true",
                        help="跳过下载后自动触发 Wiki Rescan")

    # MinerU 转换选项
    convert_group = parser.add_argument_group("MinerU PDF 转换（需 GPU + magic-pdf）")
    convert_group.add_argument(
        "--convert", action="store_true",
        default=cfg.MINERU_ENABLED,
        help="下载后用 MinerU 将 PDF 转为 Markdown（默认关闭；可用 MINERU_ENABLED=1 全局开启）",
    )
    convert_group.add_argument(
        "--markdown-dir", default="", metavar="目录",
        help=(
            "Markdown 输出目录（默认：<project_root>/markdown/）。"
            "可用 WIKI_MARKDOWN_DIR 环境变量设置全局默认值。"
        ),
    )
    convert_group.add_argument(
        "--add-to-sources", action="store_true",
        default=cfg.MINERU_ADD_TO_SOURCES,
        help=(
            "将转换后的 Markdown 复制到 raw/sources/markdown/ 供 LLM Wiki 索引。"
            "可用 MINERU_ADD_TO_SOURCES=1 全局开启。"
        ),
    )

    args = parser.parse_args()

    subdir_name = output.resolve_subdir(args.dir)
    target_dir = cfg.WIKI_PAPERS_BASE / subdir_name
    if not args.dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)

    md_out_dir = _resolve_markdown_dir(args.markdown_dir)
    checklist_entries = []
    converted_md_paths: list[Path] = []   # track for --add-to-sources

    for i, raw_id in enumerate(args.ids):
        raw_id = raw_id.strip()
        print(f"\n[{i+1}/{len(args.ids)}] {raw_id}")

        # --- 元数据解析 ---
        meta = resolver.resolve(
            raw_id,
            unpaywall_email=cfg.UNPAYWALL_EMAIL,
            s2_api_key=cfg.SEMANTIC_SCHOLAR_API_KEY,
        )

        # --- GitHub 特殊处理 ---
        if meta.resolved_by == "github" and "github.com" in raw_id:
            repo = github.parse_repo(raw_id)
            if args.dry_run:
                print(f"  [dry-run] 将保存 GitHub README: github_{repo.replace('/', '_')}.md")
                continue
            refs_dir = cfg.WIKI_PAPERS_BASE / "references"
            refs_dir.mkdir(parents=True, exist_ok=True)
            out_path = github.save_as_markdown(repo, refs_dir)
            if out_path:
                size = out_path.stat().st_size
                print(f"  ✓ {out_path.name} ({size/1024:.0f} KB)")
                checklist_entries.append({
                    "id": f"github:{repo}",
                    "filename": out_path.name,
                    "title": meta.title,
                    "subdir": "references",
                    "size": size,
                    "source": "github",
                })
            continue

        # --- PDF 下载 ---
        if not meta.pdf_urls and not meta.title:
            print(f"  [失败] 无法解析 — 未找到任何信息")
            checklist_entries.append({
                "id": raw_id, "filename": "—", "title": "解析失败",
                "subdir": subdir_name, "size": 0, "source": meta.resolved_by or "unknown",
            })
            continue

        # 确定文件名
        short_name = args.name if (i == 0 and args.name) else ""
        filename = output.make_filename(meta, short_name)
        target_path = target_dir / filename

        # 检查已存在（同 arXiv ID 不论短名）
        existing = output.find_existing(meta.arxiv_id, target_dir) if meta.arxiv_id else None
        if existing or (not meta.arxiv_id and target_path.exists()):
            existing = existing or target_path
            size = existing.stat().st_size
            print(f"  [跳过] 已存在: {existing.name} ({size/1024/1024:.1f} MB)")
            checklist_entries.append({
                "id": meta.arxiv_id or raw_id,
                "filename": existing.name,
                "title": meta.title,
                "subdir": subdir_name,
                "size": size,
                "source": "cached",
            })
            # Still try to convert if --convert is set (idempotent)
            if args.convert and not args.dry_run:
                md = pdf_converter.convert_pdf(
                    existing, md_out_dir, min_vram_mib=cfg.MINERU_MIN_VRAM_MIB
                )
                if md:
                    converted_md_paths.append(md)
            continue

        if not meta.pdf_urls:
            print(f"  [警告] 元数据已获取但无可用 PDF URL")
            print(f"  标题: {meta.title or '未知'}")
            checklist_entries.append({
                "id": meta.arxiv_id or raw_id,
                "filename": "—",
                "title": meta.title,
                "subdir": subdir_name,
                "size": 0,
                "source": meta.resolved_by,
            })
            continue

        if args.dry_run:
            print(f"  [dry-run] 标题: {meta.title}")
            print(f"  [dry-run] 将下载: {target_path}")
            print(f"  [dry-run] PDF URL: {meta.pdf_urls[0]}")
            if args.convert:
                expected = pdf_converter.expected_md(md_out_dir, target_path)
                print(f"  [dry-run] 将转换: {expected}")
            continue

        print(f"  标题: {meta.title}")
        print(f"  来源: {meta.resolved_by} | PDF 候选: {len(meta.pdf_urls)} 个")
        ok = downloader.download_pdf(meta.pdf_urls, target_path, timeout=cfg.DOWNLOAD_TIMEOUT)

        if ok:
            size = target_path.stat().st_size
            print(f"  ✓ {filename}  ({size/1024/1024:.1f} MB)")
            checklist_entries.append({
                "id": meta.arxiv_id or raw_id,
                "filename": filename,
                "title": meta.title,
                "subdir": subdir_name,
                "size": size,
                "source": meta.resolved_by,
            })

            # --- MinerU 转换（opt-in）---
            if args.convert:
                md = pdf_converter.convert_pdf(
                    target_path, md_out_dir, min_vram_mib=cfg.MINERU_MIN_VRAM_MIB
                )
                if md:
                    converted_md_paths.append(md)
        else:
            print(f"  ✗ 所有 PDF URL 均失败")
            print(f"  手动下载: wget -O '{target_path}' '{meta.pdf_urls[0]}'")
            checklist_entries.append({
                "id": meta.arxiv_id or raw_id,
                "filename": filename,
                "title": meta.title,
                "subdir": subdir_name,
                "size": 0,
                "source": f"{meta.resolved_by}-failed",
            })

    # --- 将转换后的 Markdown 复制到 raw/sources/markdown/ ---
    if converted_md_paths and args.add_to_sources:
        sources_md_dir = cfg.WIKI_PAPERS_BASE.parent / "markdown"
        sources_md_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n[MinerU] 复制 {len(converted_md_paths)} 个 Markdown 到 sources...")
        for md in converted_md_paths:
            dest = sources_md_dir / md.name
            shutil.copy2(md, dest)
            print(f"  → {dest.name}")

    # --- 清单 ---
    if checklist_entries and not args.dry_run and not args.no_checklist:
        checklist_path = output.append_checklist(checklist_entries, args.topic, cfg.WIKI_PAPERS_BASE)
        print(f"\n清单已更新: {checklist_path.name}")

    # --- 汇总 ---
    new_count = sum(1 for e in checklist_entries if e["source"] not in ("cached", "github") and e["filename"] != "—" and "failed" not in e["source"])
    ok_count = sum(1 for e in checklist_entries if e["filename"] != "—" and "failed" not in e["source"])
    fail_count = sum(1 for e in checklist_entries if "failed" in e["source"] or e["filename"] == "—")
    skip_count = ok_count - new_count
    print(f"\n完成: {new_count} 新下载 / {skip_count} 已存在跳过 / {fail_count} 失败")
    if converted_md_paths:
        print(f"MinerU:  {len(converted_md_paths)} 个 Markdown 已生成")

    # --- Wiki Rescan（仅有新文件或新 Markdown 进 sources 时触发）---
    sources_updated = bool(converted_md_paths and args.add_to_sources)
    do_rescan = (
        cfg.AUTO_RESCAN
        and not args.dry_run
        and not args.no_rescan
        and (new_count > 0 or sources_updated)
    )
    if do_rescan:
        wiki_sync.rescan(verbose=True, project_id=cfg.WIKI_PROJECT_ID)
    elif (new_count or sources_updated) and not args.dry_run:
        print("下一步: 在 LLM Wiki 中点击 File Sync → Rescan")

    if fail_count:
        sys.exit(1)


if __name__ == "__main__":
    main()
