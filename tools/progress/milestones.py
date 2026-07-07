#!/usr/bin/env python3
"""
里程碑管理工具

从 milestones.yaml 读取研究里程碑，显示状态、检查依赖、更新进度。

用法：
  python tools/progress/milestones.py --config milestones.yaml            # 显示所有里程碑
  python tools/progress/milestones.py --config milestones.yaml --summary  # 简洁摘要
  python tools/progress/milestones.py --config milestones.yaml --update m2 --status completed
  python tools/progress/milestones.py --config milestones.yaml --update m2 --progress "450/500"
  python tools/progress/milestones.py --config milestones.yaml --overdue  # 显示逾期里程碑
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


VALID_STATUSES = {"pending", "in_progress", "completed", "blocked"}

STATUS_ICONS = {
    "pending": "[ ]",
    "in_progress": "[~]",
    "completed": "[x]",
    "blocked": "[!]",
}


def load_config(config_path: str) -> dict:
    path = Path(config_path)
    if not path.exists():
        print(f"Config not found: {config_path}", file=sys.stderr)
        print(f"Copy milestones.yaml.example to milestones.yaml and customize it.", file=sys.stderr)
        sys.exit(1)

    if not HAS_YAML:
        print("PyYAML required. Install with: pip install pyyaml", file=sys.stderr)
        sys.exit(1)

    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_config(config: dict, config_path: str):
    if not HAS_YAML:
        print("PyYAML required for saving.", file=sys.stderr)
        sys.exit(1)

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def find_milestone(config: dict, milestone_id: str) -> dict | None:
    for m in config.get("milestones", []):
        if m.get("id") == milestone_id:
            return m
    return None


def check_dependencies(config: dict) -> list[str]:
    issues = []
    milestones = config.get("milestones", [])
    id_set = {m["id"] for m in milestones}
    status_map = {m["id"]: m.get("status", "pending") for m in milestones}

    for m in milestones:
        deps = m.get("depends_on", [])
        for dep in deps:
            if dep not in id_set:
                issues.append(f"{m['id']}: depends on unknown milestone '{dep}'")
            elif m.get("status") == "in_progress" and status_map.get(dep) != "completed":
                issues.append(f"{m['id']}: in_progress but dependency '{dep}' is {status_map[dep]}")

    return issues


def get_overdue(config: dict) -> list[dict]:
    today = datetime.now().date()
    overdue = []
    for m in config.get("milestones", []):
        if m.get("status") in ("completed",):
            continue
        due = m.get("due")
        if due:
            if isinstance(due, str):
                due_date = datetime.strptime(due, "%Y-%m-%d").date()
            else:
                due_date = due
            if due_date < today:
                days = (today - due_date).days
                overdue.append({**m, "overdue_days": days})
    return overdue


def print_full(config: dict):
    project = config.get("project", "Unnamed Project")
    desc = config.get("description", "")
    milestones = config.get("milestones", [])

    print(f"\n{'=' * 60}")
    print(f"  {project}")
    if desc:
        print(f"  {desc}")
    print(f"{'=' * 60}")

    completed = sum(1 for m in milestones if m.get("status") == "completed")
    total = len(milestones)
    print(f"\n  Progress: {completed}/{total} milestones completed")

    dep_issues = check_dependencies(config)
    if dep_issues:
        print(f"\n  Dependency issues:")
        for issue in dep_issues:
            print(f"    [!] {issue}")

    overdue = get_overdue(config)
    if overdue:
        print(f"\n  Overdue:")
        for m in overdue:
            print(f"    [!] {m['id']}: {m['title']} ({m['overdue_days']} days overdue)")

    print(f"\n  Milestones:")
    for m in milestones:
        icon = STATUS_ICONS.get(m.get("status", "pending"), "[ ]")
        due = m.get("due", "")
        due_str = f" (due: {due})" if due else ""
        deps = m.get("depends_on", [])
        dep_str = f" [depends: {', '.join(deps)}]" if deps else ""

        print(f"\n    {icon} {m['id']}: {m['title']}{due_str}{dep_str}")

        if m.get("progress"):
            print(f"        Progress: {m['progress']}")
        if m.get("notes"):
            print(f"        Notes: {m['notes']}")
        if m.get("wiki_refs"):
            print(f"        Wiki refs: {', '.join(m['wiki_refs'])}")
        if m.get("experiments"):
            for exp in m["experiments"]:
                exp_icon = STATUS_ICONS.get(exp.get("status", "pending"), "[ ]")
                print(f"        {exp_icon} Experiment: {exp['name']}")

    print()


def print_summary(config: dict):
    milestones = config.get("milestones", [])
    completed = sum(1 for m in milestones if m.get("status") == "completed")
    in_progress = sum(1 for m in milestones if m.get("status") == "in_progress")
    pending = sum(1 for m in milestones if m.get("status") == "pending")
    blocked = sum(1 for m in milestones if m.get("status") == "blocked")

    print(f"{config.get('project', 'Project')}: "
          f"{completed} done, {in_progress} active, {pending} pending, {blocked} blocked "
          f"({completed}/{len(milestones)} total)")


def generate_wiki_page(config: dict) -> str:
    project = config.get("project", "Project")
    milestones = config.get("milestones", [])
    today = datetime.now().strftime("%Y-%m-%d")

    lines = [
        "---",
        "type: source",
        "category: management",
        f'title: "Project Status: {project}"',
        f"updated: {today}",
        "tags: [project, milestones, status]",
        "---",
        "",
        f"# {project} — Status Board",
        "",
        f"_Updated: {today}_",
        "",
        "## Milestones",
        "",
        "| ID | Title | Status | Due | Progress |",
        "|----|-------|--------|-----|----------|",
    ]

    for m in milestones:
        status = m.get("status", "pending")
        icon = {"completed": "done", "in_progress": "active", "blocked": "BLOCKED"}.get(status, "pending")
        due = m.get("due", "-")
        progress = m.get("progress", "-")
        lines.append(f"| {m['id']} | {m['title']} | {icon} | {due} | {progress} |")

    completed = sum(1 for m in milestones if m.get("status") == "completed")
    lines.extend([
        "",
        "## Summary",
        "",
        f"- Total milestones: {len(milestones)}",
        f"- Completed: {completed}",
        f"- Completion: {completed / len(milestones) * 100:.0f}%" if milestones else "- Completion: N/A",
        "",
    ])

    overdue = get_overdue(config)
    if overdue:
        lines.append("## Overdue")
        lines.append("")
        for m in overdue:
            lines.append(f"- **{m['id']}**: {m['title']} ({m['overdue_days']} days overdue)")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Research milestone tracker")
    parser.add_argument("--config", default="milestones.yaml", help="Path to milestones YAML config")
    parser.add_argument("--summary", action="store_true", help="Print one-line summary")
    parser.add_argument("--overdue", action="store_true", help="Show only overdue milestones")
    parser.add_argument("--wiki", action="store_true", help="Generate Wiki status page (markdown)")
    parser.add_argument("--wiki-output", default=None, help="Write Wiki page to file (with --wiki)")
    parser.add_argument("--update", default=None, help="Milestone ID to update")
    parser.add_argument("--status", default=None, choices=list(VALID_STATUSES), help="New status")
    parser.add_argument("--progress", default=None, help="Progress text")
    parser.add_argument("--notes", default=None, help="Notes text")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    config = load_config(args.config)

    if args.update:
        m = find_milestone(config, args.update)
        if not m:
            print(f"Milestone not found: {args.update}", file=sys.stderr)
            sys.exit(1)
        if args.status:
            m["status"] = args.status
            if args.status == "completed":
                m["completed_at"] = datetime.now().strftime("%Y-%m-%d")
        if args.progress:
            m["progress"] = args.progress
        if args.notes:
            m["notes"] = args.notes
        save_config(config, args.config)
        print(f"Updated {args.update}: status={m.get('status')}, progress={m.get('progress')}")
        return

    if args.wiki:
        md = generate_wiki_page(config)
        if args.wiki_output:
            Path(args.wiki_output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.wiki_output).write_text(md, encoding="utf-8")
            print(f"Wrote Wiki page: {args.wiki_output}")
        else:
            print(md)
        return

    if args.overdue:
        overdue = get_overdue(config)
        if args.json:
            print(json.dumps(overdue, ensure_ascii=False, indent=2, default=str))
        elif not overdue:
            print("No overdue milestones.")
        else:
            for m in overdue:
                print(f"  [!] {m['id']}: {m['title']} — {m['overdue_days']} days overdue (due: {m['due']})")
        return

    if args.json:
        print(json.dumps(config, ensure_ascii=False, indent=2, default=str))
    elif args.summary:
        print_summary(config)
    else:
        print_full(config)


if __name__ == "__main__":
    main()
