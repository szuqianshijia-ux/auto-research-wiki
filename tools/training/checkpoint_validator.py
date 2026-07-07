#!/usr/bin/env python3
"""
Checkpoint 结构验证工具

验证训练 checkpoint 目录的完整性：
  - 必需文件和目录是否存在
  - 目录层级是否正确（如 params/ 和 assets/ 平级）
  - 是否有残留临时文件（下载未完成）
  - norm_stats 是否存在

用法：
  python tools/training/checkpoint_validator.py --checkpoint-dir /path/to/ckpt
  python tools/training/checkpoint_validator.py --checkpoint-dir /path/to/ckpt --config schema.yaml
  python tools/training/checkpoint_validator.py --checkpoint-dir /path/to/ckpt --fix
"""

import argparse
import fnmatch
import json
import os
import shutil
import sys
from pathlib import Path

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


DEFAULT_SCHEMA = {
    "required_dirs": ["params"],
    "required_files": ["params/_METADATA"],
    "optional_dirs": ["assets", "train_state"],
    "asset_check": {"enabled": True, "norm_stats_file": "norm_stats.json"},
    "sibling_check": [["params", "assets"]],
    "temp_file_patterns": ["*.gstmp", "*.tmp", "*.partial", "*.downloading"],
    "min_file_size": 1,
}


def load_schema(config_path: str | None) -> dict:
    if not config_path:
        return DEFAULT_SCHEMA.copy()

    path = Path(config_path)
    if not path.exists():
        print(f"[WARN] Config not found: {config_path}, using defaults")
        return DEFAULT_SCHEMA.copy()

    text = path.read_text(encoding="utf-8")

    if HAS_YAML:
        return yaml.safe_load(text)

    print("[WARN] PyYAML not installed, using default schema")
    print("       Install with: pip install pyyaml")
    return DEFAULT_SCHEMA.copy()


def find_temp_files(ckpt_dir: Path, patterns: list[str]) -> list[Path]:
    found = []
    for root, _, files in os.walk(ckpt_dir):
        for f in files:
            for pat in patterns:
                if fnmatch.fnmatch(f, pat):
                    found.append(Path(root) / f)
                    break
    return found


def find_empty_files(ckpt_dir: Path, min_size: int) -> list[Path]:
    found = []
    for root, _, files in os.walk(ckpt_dir):
        for f in files:
            p = Path(root) / f
            try:
                if p.stat().st_size < min_size:
                    found.append(p)
            except OSError:
                found.append(p)
    return found


def find_asset_ids(assets_dir: Path) -> list[str]:
    if not assets_dir.exists():
        return []
    return [d.name for d in assets_dir.iterdir() if d.is_dir()]


def validate(ckpt_dir: Path, schema: dict) -> dict:
    results = {
        "checkpoint_dir": str(ckpt_dir),
        "errors": [],
        "warnings": [],
        "info": [],
    }

    if not ckpt_dir.exists():
        results["errors"].append(f"Checkpoint directory does not exist: {ckpt_dir}")
        return results

    for d in schema.get("required_dirs", []):
        dp = ckpt_dir / d
        if not dp.is_dir():
            results["errors"].append(f"Required directory missing: {d}/")
        else:
            results["info"].append(f"Required directory exists: {d}/")

    for f in schema.get("required_files", []):
        fp = ckpt_dir / f
        if not fp.is_file():
            results["errors"].append(f"Required file missing: {f}")
        else:
            results["info"].append(f"Required file exists: {f}")

    for d in schema.get("optional_dirs", []):
        dp = ckpt_dir / d
        if dp.is_dir():
            results["info"].append(f"Optional directory exists: {d}/")
        else:
            results["info"].append(f"Optional directory absent: {d}/ (OK)")

    for pair in schema.get("sibling_check", []):
        if len(pair) < 2:
            continue
        dir_a, dir_b = pair[0], pair[1]
        a_at_root = (ckpt_dir / dir_a).is_dir()
        b_at_root = (ckpt_dir / dir_b).is_dir()
        b_nested = (ckpt_dir / dir_a / dir_b).is_dir()

        if b_nested and not b_at_root:
            results["errors"].append(
                f"Directory '{dir_b}/' is nested inside '{dir_a}/' instead of being a sibling. "
                f"Fix: mv {ckpt_dir / dir_a / dir_b} {ckpt_dir / dir_b}"
            )
        elif a_at_root and b_at_root:
            results["info"].append(f"Sibling check OK: {dir_a}/ and {dir_b}/ are at the same level")

    ac = schema.get("asset_check", {})
    if ac.get("enabled"):
        assets_dir = ckpt_dir / "assets"
        if assets_dir.is_dir():
            asset_ids = find_asset_ids(assets_dir)
            if not asset_ids:
                results["warnings"].append("assets/ directory exists but contains no subdirectories")
            else:
                norm_file = ac.get("norm_stats_file", "norm_stats.json")
                for aid in asset_ids:
                    ns_path = assets_dir / aid / norm_file
                    if ns_path.is_file():
                        results["info"].append(f"norm_stats found: assets/{aid}/{norm_file}")
                    else:
                        results["errors"].append(f"norm_stats missing: assets/{aid}/{norm_file}")

    temp_files = find_temp_files(ckpt_dir, schema.get("temp_file_patterns", []))
    if temp_files:
        for tf in temp_files:
            results["warnings"].append(f"Temp file found (download incomplete?): {tf.relative_to(ckpt_dir)}")

    min_size = schema.get("min_file_size", 1)
    empty_files = find_empty_files(ckpt_dir, min_size)
    if empty_files:
        for ef in empty_files[:10]:
            try:
                size = ef.stat().st_size
                results["warnings"].append(f"Empty/tiny file: {ef.relative_to(ckpt_dir)} ({size} bytes)")
            except OSError:
                results["warnings"].append(f"Inaccessible file: {ef.relative_to(ckpt_dir)}")
        if len(empty_files) > 10:
            results["warnings"].append(f"... and {len(empty_files) - 10} more empty files")

    total_size = sum(f.stat().st_size for f in ckpt_dir.rglob("*") if f.is_file())
    file_count = sum(1 for _ in ckpt_dir.rglob("*") if _.is_file())
    results["info"].append(f"Total files: {file_count}")
    results["info"].append(f"Total size: {total_size / (1024**3):.2f} GB")

    return results


def auto_fix(ckpt_dir: Path, schema: dict) -> list[str]:
    fixes = []

    for pair in schema.get("sibling_check", []):
        if len(pair) < 2:
            continue
        dir_a, dir_b = pair[0], pair[1]
        nested = ckpt_dir / dir_a / dir_b
        target = ckpt_dir / dir_b

        if nested.is_dir() and not target.is_dir():
            shutil.move(str(nested), str(target))
            fixes.append(f"Moved {nested} -> {target}")

    return fixes


def print_report(results: dict):
    print(f"\n{'=' * 60}")
    print(f"  Checkpoint Validation Report")
    print(f"  {results['checkpoint_dir']}")
    print(f"{'=' * 60}")

    errors = results["errors"]
    warnings = results["warnings"]
    info = results["info"]

    if errors:
        print(f"\n  ERRORS ({len(errors)}):")
        for e in errors:
            print(f"    [x] {e}")

    if warnings:
        print(f"\n  WARNINGS ({len(warnings)}):")
        for w in warnings:
            print(f"    [!] {w}")

    if info:
        print(f"\n  INFO:")
        for i in info:
            print(f"    [i] {i}")

    print()
    if not errors and not warnings:
        print("  RESULT: PASS")
    elif errors:
        print("  RESULT: FAIL")
    else:
        print("  RESULT: PASS (with warnings)")
    print()


def main():
    parser = argparse.ArgumentParser(description="Validate checkpoint directory structure")
    parser.add_argument("--checkpoint-dir", required=True, help="Path to checkpoint directory")
    parser.add_argument("--config", default=None, help="Path to checkpoint schema YAML (optional)")
    parser.add_argument("--fix", action="store_true", help="Auto-fix common issues (e.g., nested directories)")
    parser.add_argument("--json", action="store_true", help="Output as JSON instead of formatted report")
    args = parser.parse_args()

    ckpt_dir = Path(args.checkpoint_dir).resolve()
    schema = load_schema(args.config)

    if args.fix:
        fixes = auto_fix(ckpt_dir, schema)
        for f in fixes:
            print(f"  [FIX] {f}")
        if not fixes:
            print("  No auto-fixable issues found.")

    results = validate(ckpt_dir, schema)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print_report(results)

    sys.exit(1 if results["errors"] else 0)


if __name__ == "__main__":
    main()
