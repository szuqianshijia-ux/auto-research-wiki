# Progress Tracking Tools

研究项目进度追踪工具，里程碑和实验状态与 LLM Wiki 联动。

## 工具列表

| 工具 | 用途 |
|------|------|
| `milestones.py` | 里程碑管理（查看/更新/检查依赖） |
| `status_board.py` | 汇总生成项目状态看板 |
| `milestones.yaml.example` | 里程碑配置模板 |

## 快速开始

### 1. 初始化里程碑

```bash
cp tools/progress/milestones.yaml.example milestones.yaml
# 编辑 milestones.yaml，定义你的研究里程碑
```

### 2. 查看状态

```bash
# 完整报告
python tools/progress/milestones.py --config milestones.yaml

# 一行摘要
python tools/progress/milestones.py --config milestones.yaml --summary

# 查看逾期
python tools/progress/milestones.py --config milestones.yaml --overdue
```

### 3. 更新里程碑

```bash
# 更新状态
python tools/progress/milestones.py --config milestones.yaml \
    --update m2 --status completed

# 更新进度
python tools/progress/milestones.py --config milestones.yaml \
    --update m2 --progress "450/500 episodes"
```

### 4. 生成状态看板

```bash
# 汇总里程碑 + 实验日志 → Wiki 页面
python tools/progress/status_board.py \
    --milestones milestones.yaml \
    --experiments raw/sources/experiments/ \
    --output wiki/overview.md
```

## 工作流

```
milestones.yaml                 实验记录
    │                               │
    ├── milestones.py               ├── experiment_logger.py
    │   ├── 查看状态                │   └── raw/sources/experiments/*.md
    │   ├── 更新进度                │
    │   └── 检查依赖                │
    │                               │
    └───────────┬───────────────────┘
                │
                ▼
        status_board.py
                │
                ▼
        wiki/overview.md
                │
                ▼
        LLM Wiki rescan → 知识库可检索
```

## milestones.yaml 格式

```yaml
project: "项目名"
milestones:
  - id: m1              # 唯一 ID
    title: "数据收集"    # 标题
    status: completed    # pending | in_progress | completed | blocked
    due: 2026-08-01     # 截止日期
    depends_on: []       # 依赖的里程碑 ID 列表
    notes: "备注"        # 说明文字
    progress: "380/500"  # 进度文本（可选）
    wiki_refs:           # 关联的 Wiki 页面 slug（可选）
      - "data-quality-report"
    experiments:         # 关联的实验（可选）
      - name: "baseline_v1"
        status: completed
```

## 依赖

- Python 3.10+
- PyYAML（必需）

```bash
pip install pyyaml
```
