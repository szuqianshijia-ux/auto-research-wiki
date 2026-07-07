"""
downloader.py — 实际 PDF 下载，带重试和头验证。
"""
from __future__ import annotations

import urllib.request
import urllib.error
from pathlib import Path


def download_pdf(urls: list[str], target: Path, timeout: int = 90) -> bool:
    """
    按顺序尝试 urls 列表，下载 PDF 到 target。
    验证文件头为 %PDF，成功返回 True。
    """
    for url in urls:
        if not url:
            continue
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "wiki-paper-downloader/1.0"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
            if data[:4] == b"%PDF":
                target.write_bytes(data)
                return True
            else:
                print(f"    [下载] {url} — 返回非 PDF，跳过")
        except urllib.error.HTTPError as e:
            print(f"    [下载] HTTP {e.code}: {url}")
        except urllib.error.URLError as e:
            print(f"    [下载] 连接失败: {url} — {e.reason}")
        except Exception as e:
            print(f"    [下载] 未知错误: {e}")
    return False
