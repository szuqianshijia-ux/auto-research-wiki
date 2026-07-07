# Training Automation Tools

ML 训练实验管理工具集，将实验结果自动归档到 LLM Wiki 知识库。

## 工具列表

| 工具 | 用途 |
|------|------|
| `checkpoint_validator.py` | 验证 checkpoint 目录结构完整性 |
| `experiment_logger.py` | 生成实验记录 Wiki 页面 |
| `training_monitor.py` | 监视训练进程，完成后自动记录 |
| `checkpoint_schema.yaml` | checkpoint 结构验证配置 |

## 快速开始

### 验证 Checkpoint

```bash
# 基本验证
python tools/training/checkpoint_validator.py \
    --checkpoint-dir /path/to/checkpoint

# 使用自定义 schema
python tools/training/checkpoint_validator.py \
    --checkpoint-dir /path/to/checkpoint \
    --config tools/training/checkpoint_schema.yaml

# 自动修复常见问题（如嵌套目录）
python tools/training/checkpoint_validator.py \
    --checkpoint-dir /path/to/checkpoint --fix
```

### 记录实验

```bash
# 手动输入指标
python tools/training/experiment_logger.py \
    --name "my_experiment_v1" \
    --metrics '{"final_loss": 0.023, "accuracy": 0.95, "steps": 30000}' \
    --notes "First run with data augmentation" \
    --tags "baseline,augmented" \
    --output raw/sources/experiments/

# 从 WandB 读取（需要 pip install wandb）
python tools/training/experiment_logger.py \
    --name "my_experiment_v1" \
    --wandb-run "user/project/run_id" \
    --output raw/sources/experiments/

# 从 TensorBoard 读取（需要 pip install tensorboard）
python tools/training/experiment_logger.py \
    --name "my_experiment_v1" \
    --tb-logdir /path/to/tb_logs \
    --output raw/sources/experiments/
```

### 监视训练

```bash
# 持续监视，每 5 分钟检查一次
python tools/training/training_monitor.py \
    --watch-dir /path/to/checkpoints/my_exp \
    --interval 300

# 训练完成后自动生成实验记录
python tools/training/training_monitor.py \
    --watch-dir /path/to/checkpoints/my_exp \
    --interval 300 \
    --on-complete "python tools/training/experiment_logger.py --name my_exp --metrics-file {metrics_file} --output raw/sources/experiments/"

# 检查 GPU 状态
python tools/training/training_monitor.py --gpu-status

# 单次检查
python tools/training/training_monitor.py \
    --watch-dir /path/to/checkpoints/my_exp --once
```

## 工作流

```
训练开始
    │
    ├── training_monitor.py 监视 checkpoint 目录
    │   ├── 检测临时文件（.gstmp/.tmp）→ 训练中
    │   ├── 文件稳定 + 无临时文件 → 训练完成
    │   └── 触发 on-complete 命令
    │
    ├── checkpoint_validator.py 验证结构
    │   ├── 必需目录/文件检查
    │   ├── 平级关系检查（params/ 和 assets/）
    │   └── norm_stats 存在性检查
    │
    └── experiment_logger.py 生成记录
        ├── 从 WandB / TensorBoard / JSON 读取指标
        ├── 生成 markdown（含 YAML frontmatter）
        └── 输出到 raw/sources/experiments/
                │
                └── LLM Wiki rescan → 知识库可检索
```

## 自定义 Checkpoint Schema

编辑 `checkpoint_schema.yaml` 以匹配你的训练框架：

```yaml
# PyTorch 示例
required_dirs: []
required_files: ["model.pt"]
optional_dirs: ["optimizer"]
asset_check:
  enabled: false
sibling_check: []
temp_file_patterns: ["*.tmp"]

# JAX/Orbax 示例（默认配置）
required_dirs: ["params"]
required_files: ["params/_METADATA"]
optional_dirs: ["assets", "train_state"]
asset_check:
  enabled: true
  norm_stats_file: "norm_stats.json"
sibling_check:
  - [params, assets]
```

## 依赖

- Python 3.10+
- PyYAML（可选，用于读取 checkpoint_schema.yaml）
- wandb（可选，用于从 WandB 读取指标）
- tensorboard（可选，用于从 TensorBoard 读取指标）

```bash
pip install pyyaml           # checkpoint_validator schema 支持
pip install wandb             # WandB 集成
pip install tensorboard       # TensorBoard 集成
```
