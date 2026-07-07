#!/usr/bin/env python3
"""
项目状态看板 — 从里程碑和实验日志汇总生成状态报告

读取 milestones.yaml 和 raw/sources/experiments/ 下的实验记录，
生成项目状态概览 markdown，可作为 Wiki overview 页面。

用法：
  python tools/progress/status_board.py \
      --milestones milestones.yaml \
      --experiments raw/sources/experiments/ \
      --output wiki/overview.md

  python tools/progress/status_board.py \
      --milestones milestones.yaml
"""

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


def load_milestones(config_path: str) -> dict | None:
    if not config_path or not Path(config_path).exists():
        return None
    if not HAS_YAML:
        print("[WARN] PyYAML not installed, skipping milestones", file=sys.stderr)
        return None
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def scan_experiments(exp_dir: str) -> list[dict]:
    d = Path(exp_dir)
    if not d.exists():
        return []

    experiments = []
    for f in sorted(d.glob("*.md")):
        content = f.read_text(encoding="utf-8", errors="replace")

        title = f.stem
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if title_match:
            title = title_match.group(1).strip()

        date = None
        date_match = re.search(r'^updated:\s*(.+)$', content, re.MULTILINE)
        if date_match:
            date = date_match.group(1).strip()

        metrics = {}
        in_results = False
        for line in content.splitlines():
            if "## Results" in line:
                in_results = True
                continue
            if in_results and line.startswith("##"):
                break
            if in_results and "|" in line and not line.strip().startswith("|--"):
                parts = [p.strip() for p in line.split("|") if p.strip()]
                if len(parts) >= 2 and parts[0] != "Metric":
                    try:
                        metrics[parts[0]] = float(parts[1])
                    except ValueError:
                        metrics[parts[0]] = parts[1]

        tags = []
        tags_match = re.search(r'^tags:\s*\[(.+)\]', content, re.MULTILINE)
        if tags_match:
            tags = [t.strip() for t in tags_match.group(1).split(",")]

        experiments.append({
            "file": f.name,
            "title": title,
            "date": date,
            "metrics": metrics,
            "tags": tags,
        })

    return experiments


def generate_gantt(milestones: list[dict]) -> list[str]:
    if not milestones:
        return []

    lines = ["## Timeline", ""]
    lines.append("```")

    dates = []
    for m in milestones:
        due = m.get("due")
        if due:
            if isinstance(due, str):
                dates.append(datetime.strptime(due, "%Y-%m-%d").date())
            else:
                dates.append(due)
        completed = m.get("completed_at")
        if completed:
            if isinstance(completed, str):
                dates.append(datetime.strptime(completed, "%Y-%m-%d").date())
            else:
                dates.append(completed)

    if not dates:
        return []

    min_date = min(dates)
    max_date = max(dates)
    span = (max_date - min_date).days or 1
    width = 40

    for m in milestones:
        mid = m.get("id", "?")
        title = m.get("title", "")[:20]
        status = m.get("status", "pending")
        due = m.get("due")

        if due:
            if isinstance(due, str):
                due_date = datetime.strptime(due, "%Y-%m-%d").date()
            else:
                due_date = due
            pos = int((due_date - min_date).days / span * width)
        else:
            pos = width

        bar_char = {"completed": "#", "in_progress": "=", "blocked": "!", "pending": "."}
        char = bar_char.get(status, ".")
        bar = char * max(1, pos) + " " * max(0, width - pos)

        lines.append(f"  {mid:>4} |{bar}| {title} ({status})")

    lines.append(f"       |{'_' * width}|")
    lines.append(f"        {str(min_date):20} → {str(max_date)}")
    lines.append("```")
    lines.append("")

    return lines


def generate_board(milestones_config: dict | None, experiments: list[dict]) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [
        "---",
        "type: source",
        "category: management",
        f'title: "Project Status Board"',
        f"updated: {today}",
        "tags: [project, status, overview]",
        "---",
        "",
    ]

    project_name = "Research Project"
    all_milestones = []

    if milestones_config:
        project_name = milestones_config.get("project", project_name)
        all_milestones = milestones_config.get("milestones", [])

    lines.append(f"# {project_name} — Status Board")
    lines.append("")
    lines.append(f"_Generated: {today}_")
    lines.append("")

    if all_milestones:
        completed = sum(1 for m in all_milestones if m.get("status") == "completed")
        total = len(all_milestones)
        pct = completed / total * 100 if total else 0

        lines.append("## Overview")
        lines.append("")
        lines.append(f"- **Milestones**: {completed}/{total} completed ({pct:.0f}%)")
        lines.append(f"- **Experiments logged**: {len(experiments)}")
        lines.append("")

        gantt_lines = generate_gantt(all_milestones)
        lines.extend(gantt_lines)

        lines.append("## Milestones")
        lines.append("")
        lines.append("| Status | ID | Title | Due | Progress |")
        lines.append("|--------|----|-------|-----|----------|")

        status_emoji = {
            "completed": "done",
            "in_progress": ">>",
            "blocked": "BLOCKED",
            "pending": "--",
        }

        for m in all_milestones:
            s = status_emoji.get(m.get("status", "pending"), "--")
            due = m.get("due", "-")
            progress = m.get("progress", "-")
            lines.append(f"| {s} | {m['id']} | {m['title']} | {due} | {progress} |")

        lines.append("")

    if experiments:
        lines.append("## Experiments")
        lines.append("")

        all_metric_names = set()
        for exp in experiments:
            all_metric_names.update(exp["metrics"].keys())

        key_metrics = sorted(all_metric_names)[:5]

        header = "| Experiment | Date | " + " | ".join(key_metrics) + " |"
        separator = "|------------|------| " + " | ".join("---" for _ in key_metrics) + " |"
        lines.append(header)
        lines.append(separator)

        for exp in experiments:
            date = exp.get("date", "-")
            values = []
            for km in key_metrics:
                v = exp["metrics"].get(km, "-")
                if isinstance(v, float):
                    values.append(f"{v:.4f}")
                else:
                    values.append(str(v))
            row = f"| {exp['title'][:30]} | {date} | " + " | ".join(values) + " |"
            lines.append(row)

        lines.append("")

    if not all_milestones and not experiments:
        lines.append("_No milestones or experiments found._")
        lines.append("")
        lines.append("Get started:")
        lines.append("1. Copy `milestones.yaml.example` to `milestones.yaml`")
        lines.append("2. Run experiments with `experiment_logger.py`")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate project status board")
    parser.add_argument("--milestones", default="milestones.yaml", help="Path to milestones YAML")
    parser.add_argument("--experiments", default="raw/sources/experiments", help="Path to experiment logs directory")
    parser.add_argument("--output", default=None, help="Output file path (default: stdout)")
    args = parser.parse_args()

    milestones_config = load_milestones(args.milestones)
    experiments = scan_experiments(args.experiments)

    board = generate_board(milestones_config, experiments)

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(board, encoding="utf-8")
        print(f"Wrote status board: {args.output}")
        if milestones_config:
            ms = milestones_config.get("milestones", [])
            completed = sum(1 for m in ms if m.get("status") == "completed")
            print(f"  Milestones: {completed}/{len(ms)}, Experiments: {len(experiments)}")
    else:
        print(board)


if __name__ == "__main__":
    main()
