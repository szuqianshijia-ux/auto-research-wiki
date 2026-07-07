#!/usr/bin/env python3
"""
训练监控工具 — 监视 checkpoint 目录变化，训练完成后自动记录实验

监视指定目录下的 checkpoint 变化（新文件出现、临时文件消失），
判断训练是否完成，完成后可自动调用 experiment_logger.py 生成记录。

用法：
  # 监视 checkpoint 目录，每 5 分钟检查一次
  python tools/training/training_monitor.py \
      --watch-dir /path/to/checkpoints/my_exp \
      --interval 300

  # 监视并在完成后自动生成实验日志
  python tools/training/training_monitor.py \
      --watch-dir /path/to/checkpoints/my_exp \
      --interval 300 \
      --on-complete "python tools/training/experiment_logger.py --name my_exp --metrics-file {metrics_file} --output raw/sources/experiments/"

  # 单次检查（不持续监视）
  python tools/training/training_monitor.py \
      --watch-dir /path/to/checkpoints/my_exp \
      --once

  # 检查 GPU 状态
  python tools/training/training_monitor.py --gpu-status
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


def get_gpu_status() -> list[dict]:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,memory.total,memory.used,memory.free,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return []
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []

    gpus = []
    for line in result.stdout.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 6:
            gpus.append({
                "index": int(parts[0]),
                "name": parts[1],
                "memory_total_mb": int(parts[2]),
                "memory_used_mb": int(parts[3]),
                "memory_free_mb": int(parts[4]),
                "gpu_util_pct": int(parts[5]),
            })
    return gpus


def get_training_processes() -> list[dict]:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid,name,used_memory", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return []
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []

    procs = []
    for line in result.stdout.strip().splitlines():
        if not line.strip():
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 3:
            procs.append({
                "pid": parts[0],
                "name": parts[1],
                "memory_mb": parts[2],
            })
    return procs


def scan_checkpoint_dir(watch_dir: Path) -> dict:
    if not watch_dir.exists():
        return {"exists": False, "files": 0, "size_gb": 0, "temp_files": 0, "subdirs": []}

    files = list(watch_dir.rglob("*"))
    regular_files = [f for f in files if f.is_file()]
    temp_patterns = ("*.gstmp", "*.tmp", "*.partial", "*.downloading")
    temp_files = []
    for f in regular_files:
        for pat in temp_patterns:
            if f.match(pat):
                temp_files.append(f)
                break

    total_size = sum(f.stat().st_size for f in regular_files if f.exists())
    subdirs = [d.name for d in watch_dir.iterdir() if d.is_dir()]

    return {
        "exists": True,
        "files": len(regular_files),
        "size_gb": total_size / (1024**3),
        "temp_files": len(temp_files),
        "temp_file_list": [str(f.relative_to(watch_dir)) for f in temp_files[:10]],
        "subdirs": sorted(subdirs),
    }


def check_training_complete(watch_dir: Path, prev_state: dict | None) -> tuple[bool, dict]:
    current = scan_checkpoint_dir(watch_dir)

    if not current["exists"]:
        return False, current

    if current["temp_files"] > 0:
        return False, current

    if prev_state and prev_state.get("exists"):
        files_stable = current["files"] == prev_state.get("files", 0)
        size_stable = abs(current["size_gb"] - prev_state.get("size_gb", 0)) < 0.001
        if files_stable and size_stable and current["files"] > 0:
            return True, current

    return False, current


def print_status(watch_dir: Path, state: dict, gpus: list[dict], procs: list[dict]):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{now}] Monitoring: {watch_dir}")
    print(f"  Files: {state['files']}  Size: {state['size_gb']:.2f} GB  Temp files: {state['temp_files']}")
    if state["subdirs"]:
        print(f"  Subdirs: {', '.join(state['subdirs'])}")
    if state["temp_file_list"]:
        print(f"  Temp files: {', '.join(state['temp_file_list'])}")

    if gpus:
        print(f"  GPU status:")
        for g in gpus:
            used_pct = g["memory_used_mb"] / g["memory_total_mb"] * 100 if g["memory_total_mb"] else 0
            print(f"    [{g['index']}] {g['name']}: {g['memory_used_mb']}/{g['memory_total_mb']} MB "
                  f"({used_pct:.0f}%), util {g['gpu_util_pct']}%")

    if procs:
        print(f"  Training processes:")
        for p in procs:
            print(f"    PID {p['pid']}: {p['name']} ({p['memory_mb']} MB)")


def run_on_complete(cmd: str, watch_dir: Path, state: dict):
    metrics = {
        "checkpoint_files": state["files"],
        "checkpoint_size_gb": round(state["size_gb"], 3),
        "completed_at": datetime.now().isoformat(),
    }

    metrics_file = watch_dir / "_monitor_metrics.json"
    metrics_file.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    final_cmd = cmd.replace("{metrics_file}", str(metrics_file))
    final_cmd = final_cmd.replace("{watch_dir}", str(watch_dir))

    print(f"\n  Running on-complete command: {final_cmd}")
    result = subprocess.run(final_cmd, shell=True)
    if result.returncode != 0:
        print(f"  [WARN] on-complete command exited with code {result.returncode}")


def main():
    parser = argparse.ArgumentParser(description="Monitor training checkpoint directory")
    parser.add_argument("--watch-dir", help="Checkpoint directory to monitor")
    parser.add_argument("--interval", type=int, default=300, help="Check interval in seconds (default: 300)")
    parser.add_argument("--once", action="store_true", help="Check once and exit")
    parser.add_argument("--on-complete", default=None, help="Command to run when training completes")
    parser.add_argument("--gpu-status", action="store_true", help="Print GPU status and exit")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if args.gpu_status:
        gpus = get_gpu_status()
        procs = get_training_processes()
        if args.json:
            print(json.dumps({"gpus": gpus, "processes": procs}, indent=2))
        else:
            if not gpus:
                print("No GPUs detected or nvidia-smi not available")
            else:
                for g in gpus:
                    used_pct = g["memory_used_mb"] / g["memory_total_mb"] * 100 if g["memory_total_mb"] else 0
                    print(f"GPU {g['index']}: {g['name']}")
                    print(f"  Memory: {g['memory_used_mb']}/{g['memory_total_mb']} MB ({used_pct:.0f}%)")
                    print(f"  Utilization: {g['gpu_util_pct']}%")
            if procs:
                print(f"\nActive processes:")
                for p in procs:
                    print(f"  PID {p['pid']}: {p['name']} ({p['memory_mb']} MB)")
        return

    if not args.watch_dir:
        parser.error("--watch-dir is required (or use --gpu-status)")

    watch_dir = Path(args.watch_dir).resolve()

    if args.once:
        state = scan_checkpoint_dir(watch_dir)
        gpus = get_gpu_status()
        procs = get_training_processes()
        if args.json:
            print(json.dumps({"state": state, "gpus": gpus, "processes": procs}, indent=2))
        else:
            print_status(watch_dir, state, gpus, procs)
        return

    print(f"Monitoring {watch_dir} every {args.interval}s")
    print(f"Press Ctrl+C to stop\n")

    prev_state = None
    stable_count = 0

    try:
        while True:
            gpus = get_gpu_status()
            procs = get_training_processes()
            complete, current_state = check_training_complete(watch_dir, prev_state)

            print_status(watch_dir, current_state, gpus, procs)

            if complete:
                stable_count += 1
                if stable_count >= 2:
                    print(f"\n  Training appears COMPLETE (stable for {stable_count} checks)")
                    if args.on_complete:
                        run_on_complete(args.on_complete, watch_dir, current_state)
                    break
                else:
                    print(f"\n  Checkpoint stable ({stable_count}/2 checks needed to confirm)")
            else:
                stable_count = 0
                if current_state["temp_files"] > 0:
                    print(f"\n  Training IN PROGRESS ({current_state['temp_files']} temp files)")
                elif not current_state["exists"]:
                    print(f"\n  Waiting for directory to appear...")
                else:
                    print(f"\n  Monitoring...")

            prev_state = current_state
            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user.")


if __name__ == "__main__":
    main()
