# Auto Research Wiki

> AI 驱动的研究工作台 — 知识库 · 资料管理 · 进度追踪 · 模型训练 · Agent 工作流

将 [LLM Wiki](https://llmwiki.app) 作为知识中枢，串联研究全流程：文献获取、资料组织、知识图谱构建、AI Agent 协作和模型训练。

## 核心能力

```
┌─────────────────────────────────────────────────────────┐
│                   Auto Research Wiki                     │
├──────────┬──────────┬───────────┬───────────┬───────────┤
│  论文获取  │  资料管理  │  知识检索   │  Agent    │  模型训练  │
│          │          │           │  工作流    │          │
│ arXiv    │ 分类同步   │ 语义搜索   │           │          │
│ DOI      │ 排除规则   │ 证据包    │  🚧       │  🚧      │
│ 多源下载  │ 多项目    │ 知识图谱   │           │          │
├──────────┴──────────┴───────────┴───────────┴───────────┤
│                    LLM Wiki 知识中枢                      │
│            entities · concepts · sources · graph         │
└─────────────────────────────────────────────────────────┘
```

> 🚧 = 开发中

## 功能模块

### ✅ 已实现

| 模块 | 功能 | 工具 |
|------|------|------|
| **论文获取** | arXiv ID / DOI 自动下载 PDF + 元数据 | `wiki_paper_downloader/` |
| | 多源自动 fallback（arXiv → Unpaywall → Semantic Scholar） | |
| | 下载后自动触发 Wiki rescan | |
| **资料管理** | 研究资料按规则同步到 Wiki 源目录 | `sync_thesis_to_wiki_sources.mjs` |
| | 文件排除规则（过滤低价值内容） | |
| | 源文件自动分类（添加 category frontmatter） | `wiki_categorize_vib.py` |
| | 批量导入并生成结构化 wiki 页面 | `vib_batch_ingest.py` |
| **知识检索** | 命令行语义搜索 Wiki 知识库 | `wiki_search.mjs` |
| | 多关键词证据包生成（写作辅助） | `wiki_pack.mjs` |
| | Wiki API 检索封装 | `wiki_retrieval.py` |
| **多项目** | 环境变量切换项目，多项目并行操作 | `WIKI_PROJECT` env |

### 🚧 规划中

| 模块 | 方向 |
|------|------|
| **Agent 工作流** | Agent 自动查询 Wiki → 规划 → 执行 → 结果写回 Wiki 的闭环 |
| **模型训练** | 训练流程自动化，实验结果自动归档到知识库 |
| **进度追踪** | 研究里程碑、实验状态、TODO 与知识库联动 |

## 快速开始

### 1. 前置依赖

- [LLM Wiki](https://llmwiki.app) 桌面应用（提供 API 服务）
- Node.js 18+
- Python 3.10+

### 2. 配置

```bash
git clone https://github.com/szuqianshijia-ux/auto-research-wiki.git
cd auto-research-wiki
cp .env.example .env
# 编辑 .env，填写你的 LLM Wiki API Token 和项目路径
```

### 3. 使用

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

## 项目结构

```
├── scripts/                            # Node.js 工作流脚本
│   ├── sync_thesis_to_wiki_sources.mjs # 资料 → Wiki 源目录同步
│   ├── wiki_search.mjs                 # 知识库搜索
│   └── wiki_pack.mjs                   # 证据包生成
├── tools/                              # Python 工具
│   ├── wiki_paper_downloader/          # 论文自动下载器
│   │   ├── download.py                 # 入口
│   │   ├── sources/                    # 多源适配器（arXiv/OpenAlex/Unpaywall/...）
│   │   ├── wiki_sync.py               # Wiki rescan 触发
│   │   └── config.py                   # 多项目配置
│   ├── wiki_retrieval.py               # Wiki API 封装
│   ├── wiki_categorize_vib.py          # 自动分类
│   ├── wiki_optimizer.py               # 页面优化
│   └── vib_batch_ingest.py             # 批量导入
├── .env.example                        # 配置模板
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
              │        AI Agent / 写作          │  🚧
              │   查询 Wiki → 推理 → 写回 Wiki   │
              └──────────────┬──────────────────┘
                             │
                             ▼
              ┌─────────────────────────────────┐
              │         模型训练                 │  🚧
              │  实验结果 → 自动归档到知识库      │
              └─────────────────────────────────┘
```

## 多项目管理

```bash
# 不同终端、不同项目，互不干扰
WIKI_PROJECT=project_a python tools/wiki_paper_downloader/download.py 2301.12345
WIKI_PROJECT=project_b python tools/wiki_paper_downloader/download.py 2509.18644
```

## License

MIT
