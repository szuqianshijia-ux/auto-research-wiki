# Auto Research Wiki

> AI 驱动的研究工作台 — 知识库 · 资料管理 · Agent 工作流 · 模型训练 · 进度追踪

将 [LLM Wiki](https://llmwiki.app) 作为知识中枢，串联研究全流程：文献获取、资料组织、知识图谱构建、AI Agent 协作、模型训练和进度管理。

## 核心能力

```
┌──────────────────────────────────────────────────────────────┐
│                     Auto Research Wiki                        │
├──────────┬──────────┬───────────┬───────────┬────────────────┤
│  论文获取  │  资料管理  │  知识检索   │  Agent    │  训练 & 进度   │
│          │          │           │  工作流    │               │
│ arXiv    │ 分类同步   │ 语义搜索   │ Wiki 闭环  │ Checkpoint    │
│ DOI      │ 排除规则   │ 证据包    │ Claude    │ 实验日志       │
│ 多源下载  │ 多项目    │ 知识图谱   │ 模板      │ 里程碑追踪     │
├──────────┴──────────┴───────────┴───────────┴────────────────┤
│                      LLM Wiki 知识中枢                        │
│              entities · concepts · sources · graph            │
└──────────────────────────────────────────────────────────────┘
```

## 功能模块

| 模块 | 功能 | 工具 |
|------|------|------|
| **论文获取** | arXiv ID / DOI 自动下载 PDF + 元数据 | `tools/wiki_paper_downloader/` |
| | 多源自动 fallback（arXiv → Unpaywall → Semantic Scholar） | |
| | 下载后自动触发 Wiki rescan | |
| **资料管理** | 研究资料按规则同步到 Wiki 源目录 | `scripts/sync_thesis_to_wiki_sources.mjs` |
| | 文件排除规则（过滤低价值内容） | |
| | 源文件自动分类（添加 category frontmatter） | `tools/wiki_categorize_vib.py` |
| | 批量导入并生成结构化 wiki 页面 | `tools/vib_batch_ingest.py` |
| **知识检索** | 命令行语义搜索 Wiki 知识库 | `scripts/wiki_search.mjs` |
| | 多关键词证据包生成（写作辅助） | `scripts/wiki_pack.mjs` |
| | 多跳检索 + 知识图谱社区发现 | `tools/wiki_retrieval.py` |
| **Wiki 优化** | 近重复页面检测与合并 | `tools/wiki_optimizer.py` |
| | 超长页面 LLM 压缩 | |
| **Agent 工作流** | Claude Code Agent 模板（CLAUDE.md + Skills） | `agents/` |
| | Wiki 知识循环技能（搜索→执行→归档） | `agents/skills/` |
| | /wiki-write、/wiki-summary 命令 | `agents/commands/` |
| **训练自动化** | Checkpoint 结构验证与自动修复 | `tools/training/checkpoint_validator.py` |
| | 实验记录生成（WandB/TensorBoard/手动） | `tools/training/experiment_logger.py` |
| | 训练进程监控 + 完成回调 | `tools/training/training_monitor.py` |
| **进度追踪** | YAML 里程碑管理（状态/依赖/逾期） | `tools/progress/milestones.py` |
| | 项目状态看板生成（含甘特图） | `tools/progress/status_board.py` |
| **多项目** | 环境变量切换项目，多项目并行操作 | `WIKI_PROJECT` env |

## 快速开始

### 1. 前置依赖

- [LLM Wiki](https://llmwiki.app) 桌面应用（提供 API 服务）
- Node.js 18+
- Python 3.10+
- PyYAML（进度追踪需要）：`pip install pyyaml`

### 2. 配置

```bash
git clone https://github.com/szuqianshijia-ux/auto-research-wiki.git
cd auto-research-wiki
cp .env.example .env
# 编辑 .env，填写你的 LLM Wiki API Token 和项目路径
```

### 3. 基本使用

```bash
# 下载论文（arXiv ID 或 DOI）
python tools/wiki_paper_downloader/download.py 2301.12345 --dir papers/core

# 同步资料到 Wiki
node scripts/sync_thesis_to_wiki_sources.mjs

# 搜索知识库
node scripts/wiki_search.mjs search "your keywords" 8

# 生成证据包
node scripts/wiki_pack.mjs --out tmp/context.md --topK 8 --full 3 "topic A" "topic B"
```

### 4. Agent 工作流（Claude Code 集成）

```bash
# 复制 Agent 模板到你的研究项目
mkdir -p .claude/skills/wiki-knowledge-loop .claude/commands
cp agents/claude-md-template/CLAUDE.md.template .claude/CLAUDE.md
cp agents/skills/wiki-knowledge-loop/SKILL.md .claude/skills/wiki-knowledge-loop/
cp agents/commands/*.md .claude/commands/
# 编辑 .claude/CLAUDE.md，替换 {{...}} 占位符
```

详见 [agents/README.md](agents/README.md)。

### 5. 训练实验管理

```bash
# 验证 checkpoint 完整性
python tools/training/checkpoint_validator.py --checkpoint-dir /path/to/checkpoint

# 记录实验结果
python tools/training/experiment_logger.py \
    --name "my_exp_v1" \
    --metrics '{"loss": 0.023, "accuracy": 0.95}' \
    --output raw/sources/experiments/

# 监视训练进程
python tools/training/training_monitor.py \
    --watch-dir /path/to/checkpoints/my_exp --interval 300
```

详见 [tools/training/README.md](tools/training/README.md)。

### 6. 进度追踪

```bash
# 初始化里程碑
cp tools/progress/milestones.yaml.example milestones.yaml

# 查看状态
python tools/progress/milestones.py --config milestones.yaml

# 生成状态看板
python tools/progress/status_board.py \
    --milestones milestones.yaml \
    --experiments raw/sources/experiments/ \
    --output wiki/overview.md
```

详见 [tools/progress/README.md](tools/progress/README.md)。

## 项目结构

```
├── agents/                                 # Agent 工作流模板
│   ├── claude-md-template/                 # CLAUDE.md 项目模板
│   ├── skills/wiki-knowledge-loop/         # Wiki 知识循环技能
│   └── commands/                           # /wiki-write, /wiki-summary
├── scripts/                                # Node.js 工作流脚本
│   ├── sync_thesis_to_wiki_sources.mjs     # 资料 → Wiki 源目录同步
│   ├── wiki_search.mjs                     # 知识库搜索
│   └── wiki_pack.mjs                       # 证据包生成
├── tools/                                  # Python 工具
│   ├── wiki_paper_downloader/              # 论文自动下载器
│   ├── training/                           # 训练自动化
│   │   ├── checkpoint_validator.py         # checkpoint 验证
│   │   ├── experiment_logger.py            # 实验日志生成
│   │   ├── training_monitor.py             # 训练监控
│   │   └── checkpoint_schema.yaml          # 验证配置
│   ├── progress/                           # 进度追踪
│   │   ├── milestones.py                   # 里程碑管理
│   │   ├── status_board.py                 # 状态看板
│   │   └── milestones.yaml.example         # 配置模板
│   ├── wiki_retrieval.py                   # 多跳检索
│   ├── wiki_optimizer.py                   # Wiki 页面优化
│   ├── wiki_categorize_vib.py              # 自动分类
│   └── vib_batch_ingest.py                 # 批量导入
├── .env.example                            # 配置模板
└── LICENSE
```

## 工作流示意

```
论文/资料 ──→ Wiki raw/sources ──→ LLM Wiki Ingest ──→ 知识图谱
                                                        │
                     ┌──────────────────────────────────┘
                     ▼
              ┌─────────────┐     ┌──────────────┐
              │ wiki_search │     │  wiki_pack   │
              │  语义搜索    │     │  证据包生成   │
              └──────┬──────┘     └──────┬───────┘
                     │                   │
                     ▼                   ▼
              ┌─────────────────────────────────┐
              │        AI Agent 工作流           │
              │   /wiki-write → 推理 → 执行     │
              │   /wiki-summary → 归档 → 同步    │
              └──────────────┬──────────────────┘
                             │
                     ┌───────┴──────────┐
                     ▼                  ▼
              ┌────────────┐     ┌────────────┐
              │  训练自动化  │     │  进度追踪   │
              │ checkpoint │     │ milestones │
              │ experiment │     │ status     │
              │ monitor    │     │ board      │
              └─────┬──────┘     └──────┬─────┘
                    │                   │
                    └───────┬───────────┘
                            ▼
                    Wiki raw/sources ──→ rescan ──→ 知识更丰富
```

## 多项目管理

```bash
# 不同终端、不同项目，互不干扰
WIKI_PROJECT=project_a python tools/wiki_paper_downloader/download.py 2301.12345
WIKI_PROJECT=project_b python tools/wiki_paper_downloader/download.py 2509.18644
```

## License

MIT
