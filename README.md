# Wiki Knowledge Base Workflow

LLM Wiki 知识库管理工作流工具集，用于学术论文的自动化下载、分类、同步和检索。

## 项目结构

```
├── scripts/                        # Node.js 工作流脚本
│   ├── sync_thesis_to_wiki_sources.mjs  # 论文资料 → Wiki 源目录同步
│   ├── wiki_search.mjs             # Wiki 知识库搜索
│   └── wiki_pack.mjs               # 生成证据包（写作前定界用）
├── tools/                          # Python 工具
│   ├── wiki_paper_downloader/      # 论文自动下载器（arXiv/OpenAlex/Unpaywall）
│   ├── wiki_retrieval.py           # Wiki API 检索封装
│   ├── wiki_categorize_vib.py      # Wiki 源文件分类（添加 category frontmatter）
│   ├── wiki_optimizer.py           # Wiki 页面优化
│   └── vib_batch_ingest.py         # 批量导入脚本
└── .env.example                    # 环境变量配置模板
```

## 前置依赖

- [LLM Wiki](https://github.com/nicholasgriffintn/llm-wiki) 应用运行中（API 端口 19828）
- Node.js 18+
- Python 3.10+

## 快速开始

1. 复制环境变量模板并填写：

```bash
cp .env.example .env
source .env
```

2. 下载论文到 Wiki 源目录：

```bash
python tools/wiki_paper_downloader/download.py 2301.12345 --dir papers/core
```

3. 同步论文资料到 Wiki：

```bash
node scripts/sync_thesis_to_wiki_sources.mjs
```

4. 搜索 Wiki 知识库：

```bash
node scripts/wiki_search.mjs search "your search keywords" 8
```

5. 生成写作证据包：

```bash
node scripts/wiki_pack.mjs --out tmp/context.md --topK 8 --full 3 "关键词"
```

## 工作流

```
论文下载 → Wiki 源目录 → LLM Wiki Ingest → 知识图谱
     ↑                                         ↓
  论文库管理                              搜索/证据包 → 写作
```

### 同步脚本排除规则

`sync_thesis_to_wiki_sources.mjs` 内置了排除机制：
- `COPY_RULES`：精确的文件映射（源路径 → 目标路径）
- `COPY_DIR_RULES`：整目录批量复制
- `COPY_DIR_EXCLUDE`：排除低价值文件（wiki 工作流日志、纯 prompt 等）

### 多项目支持

通过 `WIKI_PROJECT` 环境变量切换项目：

```bash
WIKI_PROJECT=embodied python tools/wiki_paper_downloader/download.py 2509.18644
WIKI_PROJECT=vibration python tools/wiki_paper_downloader/download.py 2301.12345
```

## License

MIT
