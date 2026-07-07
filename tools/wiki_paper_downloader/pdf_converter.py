#!/usr/bin/env python3
"""
pdf_converter.py — MinerU (magic-pdf) PDF → Markdown conversion wrapper.

Integrates into the LLM Wiki paper download workflow as an optional post-download step.

Features:
  - VRAM availability check before running (skips if GPU is occupied)
  - Idempotent: skips if Markdown already exists for this PDF
  - OOM retry: disables formula recognition on CUDA OOM, retries once
  - Config safety: always restores ~/magic-pdf.json via try/finally

Output path convention (set by magic-pdf):
  magic-pdf -p file.pdf -o OUT_DIR -m auto
  → OUT_DIR / file_stem / auto / file_stem.md
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

# Path to MinerU runtime config
_MAGIC_PDF_JSON = Path.home() / "magic-pdf.json"

# Minimum free VRAM (MiB) required to run MinerU with formula recognition.
# RTX 4090 D: formula recognition needs ~4-6 GB; training jobs consume ~21 GB,
# leaving ~3 GB → below threshold → skip.
_DEFAULT_MIN_VRAM_MIB = 6144


# ── VRAM guard ────────────────────────────────────────────────────────────────

def _check_vram(min_free_mib: int) -> tuple[bool, str]:
    """
    Query free GPU VRAM via nvidia-smi.
    Returns (ok, reason_string). ok=False → caller should skip MinerU.
    """
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.free",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        free_mib = int(result.stdout.strip().split("\n")[0])
        if free_mib < min_free_mib:
            return False, (
                f"可用显存 {free_mib} MiB < 阈值 {min_free_mib} MiB"
                f"（其他进程占用 GPU，跳过 MinerU 避免 OOM）"
            )
        return True, f"可用显存 {free_mib} MiB"
    except FileNotFoundError:
        return False, "未找到 nvidia-smi，跳过 GPU 转换"
    except (ValueError, subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
        return False, f"nvidia-smi 查询失败: {exc}，跳过 GPU 转换"


# ── Output path helper ────────────────────────────────────────────────────────

def expected_md(out_dir: Path, pdf_path: Path) -> Path:
    """
    Return the Markdown path that magic-pdf will create.

    magic-pdf always nests: OUT_DIR / stem / auto / stem.md
    Exposing this as a public helper lets callers check existence cheaply.
    """
    stem = pdf_path.stem
    return out_dir / stem / "auto" / f"{stem}.md"


# ── magic-pdf.json helpers ────────────────────────────────────────────────────

def _read_magic_cfg() -> dict:
    try:
        return json.loads(_MAGIC_PDF_JSON.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_magic_cfg(cfg: dict) -> None:
    _MAGIC_PDF_JSON.write_text(
        json.dumps(cfg, indent=4, ensure_ascii=False),
        encoding="utf-8",
    )


# ── Subprocess helpers ────────────────────────────────────────────────────────

def _run_magic_pdf(pdf_path: Path, out_dir: Path) -> tuple[bool, bool]:
    """
    Run magic-pdf in GPU mode.

    Returns:
        (success, is_oom)
        success=True  → conversion finished, caller should verify output path
        is_oom=True   → CUDA OOM detected, caller may retry without formulas
    """
    env = os.environ.copy()
    env.setdefault(
        "PYTORCH_CUDA_ALLOC_CONF",
        "expandable_segments:True,max_split_size_mb:256",
    )
    try:
        result = subprocess.run(
            ["magic-pdf", "-p", str(pdf_path), "-o", str(out_dir), "-m", "auto"],
            env=env,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        print("  [MinerU] magic-pdf 未找到，请先安装 MinerU (pip install magic-pdf[full])")
        return False, False

    if result.returncode == 0:
        return True, False

    stderr_lower = (result.stderr or "").lower()
    is_oom = (
        result.returncode == 137            # SIGKILL from OOM killer
        or "out of memory" in stderr_lower
        or "outofmemoryerror" in stderr_lower
        or "cuda error" in stderr_lower
    )

    if is_oom:
        print(f"  [MinerU] CUDA OOM 检测 (exit {result.returncode})")
    else:
        snippet = (result.stderr or "").strip()[-300:]
        print(f"  [MinerU] 失败 (exit {result.returncode}): {snippet or '(无错误输出)'}")

    return False, is_oom


def _retry_no_formula(pdf_path: Path, out_dir: Path) -> bool:
    """
    Retry magic-pdf with formula recognition disabled.

    Patches ~/magic-pdf.json before the run and restores it in a finally block,
    so the config is guaranteed to be restored even if conversion crashes.
    """
    original_cfg = _read_magic_cfg()
    if not original_cfg:
        print("  [MinerU] 无法读取 magic-pdf.json，跳过无公式重试")
        return False

    # Remove partial output from the failed first attempt
    partial = out_dir / pdf_path.stem
    if partial.exists():
        shutil.rmtree(partial)

    patched_cfg = dict(original_cfg)
    formula_cfg = dict(patched_cfg.get("formula-config", {}))
    formula_cfg["enable"] = False
    patched_cfg["formula-config"] = formula_cfg

    try:
        _write_magic_cfg(patched_cfg)
        print("  [MinerU] 已禁用公式识别，重试中...")
        success, _ = _run_magic_pdf(pdf_path, out_dir)
        return success
    finally:
        _write_magic_cfg(original_cfg)
        print("  [MinerU] 已恢复 magic-pdf.json 原配置")


# ── Public API ────────────────────────────────────────────────────────────────

def convert_pdf(
    pdf_path: Path,
    out_dir: Path,
    min_vram_mib: int = _DEFAULT_MIN_VRAM_MIB,
) -> Path | None:
    """
    Convert a PDF to Markdown using MinerU (magic-pdf).

    The function is idempotent: if the expected output Markdown already exists
    it returns the path immediately without re-running magic-pdf.

    Args:
        pdf_path:     Path to the source PDF file.
        out_dir:      Parent output directory.  magic-pdf will create
                      ``out_dir / stem / auto / stem.md`` internally.
        min_vram_mib: Minimum free GPU VRAM in MiB (default 6144 = 6 GB).
                      If another process has consumed enough GPU memory that
                      free VRAM falls below this threshold, conversion is
                      skipped and None is returned.

    Returns:
        Path to the generated ``.md`` file on success, or ``None`` if the
        conversion was skipped (insufficient VRAM, magic-pdf not found) or
        failed after the OOM retry.
    """
    md_path = expected_md(out_dir, pdf_path)

    # Fast path: already converted
    if md_path.exists():
        print(f"  [MinerU] 已存在，跳过: {md_path.name}")
        return md_path

    # VRAM guard — must check before touching GPU
    ok, reason = _check_vram(min_vram_mib)
    if not ok:
        print(f"  [MinerU] 跳过: {reason}")
        return None

    print(f"  [MinerU] 开始转换 {pdf_path.name}...")
    out_dir.mkdir(parents=True, exist_ok=True)

    # First attempt (formula recognition enabled)
    success, is_oom = _run_magic_pdf(pdf_path, out_dir)

    # OOM fallback: one retry without formula recognition
    if not success and is_oom:
        success = _retry_no_formula(pdf_path, out_dir)

    if not success:
        return None

    if not md_path.exists():
        print(f"  [MinerU] 转换完成但未找到预期输出路径: {md_path}")
        return None

    size_kb = md_path.stat().st_size / 1024
    print(f"  [MinerU] ✓ {md_path.name} ({size_kb:.0f} KB)")
    return md_path
