#!/usr/bin/env python3
"""
实验记录器 — 生成结构化的实验记录 Wiki 页面

将实验指标、配置和备注生成为 markdown 文件（含 YAML frontmatter），
可直接放入 Wiki raw/sources/ 目录由 LLM Wiki 索引。

用法：
  # 手动输入指标
  python tools/training/experiment_logger.py \
      --name "exp_v1" \
      --metrics '{"final_loss": 0.023, "accuracy": 0.95, "steps": 30000}' \
      --notes "First run with augmented data" \
      --output raw/sources/experiments/

  # 从 JSON 文件读取指标
  python tools/training/experiment_logger.py \
      --name "exp_v1" \
      --metrics-file /path/to/metrics.json \
      --output raw/sources/experiments/

  # 从 WandB 读取（需要 wandb 包和 WANDB_API_KEY）
  python tools/training/experiment_logger.py \
      --name "exp_v1" \
      --wandb-run "user/project/run_id" \
      --output raw/sources/experiments/

  # 从 TensorBoard 日志读取（需要 tensorboard 包）
  python tools/training/experiment_logger.py \
      --name "exp_v1" \
      --tb-logdir /path/to/tb_logs \
      --output raw/sources/experiments/
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path


def load_metrics_from_json(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_metrics_from_wandb(run_path: str) -> dict:
    try:
        import wandb
    except ImportError:
        print("[ERROR] wandb not installed. Run: pip install wandb", file=sys.stderr)
        sys.exit(1)

    api = wandb.Api()
    run = api.run(run_path)
    summary = dict(run.summary)
    config = dict(run.config)

    metrics = {}
    for key in ("loss", "train_loss", "eval_loss", "accuracy", "success_rate", "lr"):
        if key in summary:
            metrics[key] = summary[key]

    if "_step" in summary:
        metrics["steps"] = summary["_step"]
    if "_runtime" in summary:
        metrics["runtime_seconds"] = summary["_runtime"]

    metrics["wandb_config"] = config
    return metrics


def load_metrics_from_tensorboard(logdir: str) -> dict:
    try:
        from tensorboard.backend.event_processing.event_accumulator import EventAccumulator
    except ImportError:
        print("[ERROR] tensorboard not installed. Run: pip install tensorboard", file=sys.stderr)
        sys.exit(1)

    ea = EventAccumulator(logdir)
    ea.Reload()

    metrics = {}
    for tag in ea.Tags().get("scalars", []):
        events = ea.Scalars(tag)
        if events:
            last = events[-1]
            clean_tag = tag.replace("/", "_").replace(" ", "_")
            metrics[clean_tag] = last.value
            metrics[f"{clean_tag}_step"] = last.step

    return metrics


def format_value(v) -> str:
    if isinstance(v, float):
        if abs(v) < 0.001 and v != 0:
            return f"{v:.6f}"
        return f"{v:.4f}"
    return str(v)


def generate_markdown(name: str, metrics: dict, notes: str, tags: list[str]) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    tag_list = ", ".join(tags) if tags else "experiment, training"

    lines = [
        "---",
        "type: source",
        "category: experiment",
        f'title: "Experiment: {name}"',
        f"updated: {today}",
        f"tags: [{tag_list}]",
        "---",
        "",
        f"# {name}",
        "",
    ]

    config_keys = {}
    metric_keys = {}
    for k, v in metrics.items():
        if isinstance(v, dict):
            config_keys[k] = v
        elif k.endswith("_config"):
            config_keys[k] = v
        else:
            metric_keys[k] = v

    if config_keys:
        lines.append("## Configuration")
        lines.append("")
        for section_name, section_data in config_keys.items():
            lines.append(f"### {section_name}")
            lines.append("")
            if isinstance(section_data, dict):
                for ck, cv in section_data.items():
                    lines.append(f"- **{ck}**: `{cv}`")
            else:
                lines.append(f"- {section_data}")
            lines.append("")

    if metric_keys:
        lines.append("## Results")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        for k, v in sorted(metric_keys.items()):
            lines.append(f"| {k} | {format_value(v)} |")
        lines.append("")

    if notes:
        lines.append("## Notes")
        lines.append("")
        lines.append(notes)
        lines.append("")

    lines.append("## Metadata")
    lines.append("")
    lines.append(f"- Generated: {datetime.now().isoformat()}")
    lines.append(f"- Tool: experiment_logger.py")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate experiment log as Wiki source page")
    parser.add_argument("--name", required=True, help="Experiment name (used as filename and title)")
    parser.add_argument("--metrics", default=None, help="Metrics as JSON string")
    parser.add_argument("--metrics-file", default=None, help="Path to metrics JSON file")
    parser.add_argument("--wandb-run", default=None, help="WandB run path (user/project/run_id)")
    parser.add_argument("--tb-logdir", default=None, help="TensorBoard log directory")
    parser.add_argument("--notes", default="", help="Free-text notes about the experiment")
    parser.add_argument("--tags", default="", help="Comma-separated tags")
    parser.add_argument("--output", default=".", help="Output directory for the markdown file")
    args = parser.parse_args()

    metrics = {}
    if args.metrics:
        metrics = json.loads(args.metrics)
    elif args.metrics_file:
        metrics = load_metrics_from_json(args.metrics_file)
    elif args.wandb_run:
        metrics = load_metrics_from_wandb(args.wandb_run)
    elif args.tb_logdir:
        metrics = load_metrics_from_tensorboard(args.tb_logdir)
    else:
        print("[WARN] No metrics source provided. Generating empty template.", file=sys.stderr)

    tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []

    md = generate_markdown(args.name, metrics, args.notes, tags)

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    safe_name = args.name.replace("/", "_").replace(" ", "_")
    out_path = out_dir / f"{safe_name}.md"
    out_path.write_text(md, encoding="utf-8")

    print(f"Wrote experiment log: {out_path}")
    print(f"  Metrics: {len(metrics)} entries")
    print(f"  Tags: {tags or ['experiment', 'training']}")


if __name__ == "__main__":
    main()
