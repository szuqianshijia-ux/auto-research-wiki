# Auto Research Wiki

> 基于 [LLM Wiki](https://llmwiki.app) 的学术研究知识库自动化工作流

自动化完成论文下载 → 知识库导入 → 知识图谱检索 → 写作辅助的全流程。

## 它能做什么

| 功能 | 说明 |
|------|------|
| **论文自动下载** | 输入 arXiv ID 或 DOI，自动从 arXiv / OpenAlex / Unpaywall / Semantic Scholar 获取 PDF 和元数据 |
| **批量导入** | 将论文批量导入 LLM Wiki，自动生成结构化 wiki 页面 |
| **智能分类** | 自动识别文件类型并添加 category frontmatter |
| **知识库搜索** | 命令行直接搜索 Wiki 知识图谱 |
| **证据包生成** | 写作前一键生成多关键词证据包，避免凭记忆写作 |
| **多项目管理** | 通过环境变量切换不同研究项目，互不干扰 |
| **源目录同步** | 将分散的研究资料按规则同步到 Wiki 源目录，支持排除规则 |

## 工作流

```
                    ┌──────────────┐
                    │  arXiv / DOI │
                    └──────┬───────┘
                           ▼
              ┌────────────────────────┐
              │  wiki_paper_downloader │  ← 自动下载 PDF + 元数据
              └────────────┬───────────┘
                           ▼
              ┌────────────────────────┐
              │    Wiki raw/sources    │  ← 源文件目录
              └────────────┬───────────┘
                           ▼
              ┌────────────────────────┐
              │   LLM Wiki Ingest     │  ← 自动解析、生成 entity/concept
              └────────────┬───────────┘
                           ▼
         ┌─────────────────┴─────────────────┐
         ▼                                   ▼
┌─────────────────┐                ┌──────────────────┐
│  wiki_search    │                │   wiki_pack      │
│  关键词检索      │                │  生成证据包       │
└─────────────────┘                └──────────────────┘
```

## 快速开始

### 1. 前置依赖

- [LLM Wiki](https://llmwiki.app) 桌面应用（提供 API 服务）
- Node.js 18+
- Python 3.10+

### 2. 配置

```bash
cp .env.example .env
# 编辑 .env，填写你的 LLM Wiki API Token 和项目路径
```

### 3. 下载论文

```bash
# 通过 arXiv ID 下载
python tools/wiki_paper_downloader/download.py 2301.12345 --dir papers/core

# 通过 DOI 下载
python tools/wiki_paper_downloader/download.py 10.1016/j.xxx.2024.xxx --dir papers
```

下载器会自动：
- 尝试多个源获取 PDF（arXiv → Unpaywall → Semantic Scholar）
- 获取论文元数据（标题、作者、年份、摘要）
- 生成 Markdown 摘要页
- 触发 LLM Wiki rescan

### 4. 搜索知识库

```bash
# 搜索关键词
node scripts/wiki_search.mjs search "deep learning" 8

# 查看某个 Wiki 页面全文
node scripts/wiki_search.mjs content "wiki/sources/example.md"

# 浏览知识图谱
node scripts/wiki_search.mjs graph "keyword" 100
```

### 5. 生成写作证据包

```bash
# 写作前生成证据包，汇总多个关键词的检索结果
node scripts/wiki_pack.mjs --out tmp/context.md --topK 8 --full 3 \
  "topic A" "topic B" "topic C"
```

证据包包含：检索结果摘要、相关页面路径、关键内容摘录，适合喂给 AI 辅助写作。

## 项目结构

```
├── scripts/                            # Node.js 工作流脚本
│   ├── sync_thesis_to_wiki_sources.mjs # 研究资料 → Wiki 源目录同步
│   ├── wiki_search.mjs                 # Wiki 知识库搜索
│   └── wiki_pack.mjs                   # 证据包生成
├── tools/                              # Python 工具
│   ├── wiki_paper_downloader/          # 论文自动下载器
│   │   ├── download.py                 # 入口脚本
│   │   ├── downloader.py               # 下载核心逻辑
│   │   ├── resolver.py                 # 多源 PDF 解析
│   │   ├── sources/                    # 数据源适配器
│   │   │   ├── arxiv.py
│   │   │   ├── openalex.py
│   │   │   ├── semantic_scholar.py
│   │   │   └── unpaywall.py
│   │   ├── wiki_sync.py               # Wiki rescan 触发
│   │   └── config.py                   # 多项目配置
│   ├── wiki_retrieval.py               # Wiki API 检索封装
│   ├── wiki_categorize_vib.py          # 源文件自动分类
│   ├── wiki_optimizer.py               # Wiki 页面优化
│   └── vib_batch_ingest.py             # 批量导入
├── .env.example                        # 环境变量模板
└── .gitignore
```

## 多项目管理

支持同时管理多个 LLM Wiki 项目，通过环境变量切换：

```bash
# 项目 A
WIKI_PROJECT=project_a python tools/wiki_paper_downloader/download.py 2301.12345

# 项目 B（同时进行，互不干扰）
WIKI_PROJECT=project_b python tools/wiki_paper_downloader/download.py 2509.18644
```

在 `tools/wiki_paper_downloader/config.py` 中配置项目映射。

## 同步规则

`sync_thesis_to_wiki_sources.mjs` 提供灵活的文件同步：

- **`COPY_RULES`** — 精确映射：源文件 → 目标路径（一对一）
- **`COPY_DIR_RULES`** — 目录批量复制
- **`COPY_DIR_EXCLUDE`** — 排除列表（跳过低价值文件）

```bash
# 预览同步（不实际写入）
node scripts/sync_thesis_to_wiki_sources.mjs --dry-run

# 执行同步
node scripts/sync_thesis_to_wiki_sources.mjs
```

## License

MIT
