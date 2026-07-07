# wiki_paper_downloader

多源学术论文下载器，集成到具身智能 LLM Wiki 工作流。

## 支持的输入格式

| 格式 | 示例 | 数据源 |
|------|------|--------|
| arXiv ID | `2509.18644` | arXiv API + OpenAlex |
| arXiv URL | `https://arxiv.org/abs/2509.18644` | arXiv API + OpenAlex |
| 裸 DOI | `10.1109/ICRA.2023.xxx` | OpenAlex → Unpaywall → S2 |
| DOI URL | `https://doi.org/10.xxxx/...` | OpenAlex → Unpaywall → S2 |
| GitHub URL | `https://github.com/owner/repo` | GitHub API（保存 README） |
| S2 ID | 40 位十六进制字符串 | Semantic Scholar |
| 标题 | `"Diffusion Policy"` | OpenAlex 模糊搜索 |

## 快速开始

### 单项目使用（默认具身智能项目）

```bash
# arXiv 单篇（下载后自动触发 Wiki Rescan）
python3 download.py 2509.18644 --dir training

# 批量 + 自定义主题（生成清单文件）
python3 download.py 2303.18080 2203.06173 2203.12601 \
  --dir training --topic 视觉预训练

# DOI（非 arXiv 论文）
python3 download.py 10.1109/ICRA48891.2023.10160830 --dir vla

# GitHub 仓库 README → references/
python3 download.py https://github.com/Physical-Intelligence/openpi --dir refs

# 预览（不下载，不 Rescan）
python3 download.py 2509.18644 --dir training --dry-run

# 禁用自动 Rescan
python3 download.py 2509.18644 --dir training --no-rescan

# 单独触发 Rescan（不下载）
python3 -c "
import sys; sys.path.insert(0, '..')
from wiki_paper_downloader import wiki_sync
wiki_sync.rescan()
"
```

### 多项目并行使用 ⚡（新增）

支持同时处理两个项目，无需在 LLM Wiki GUI 中切换：

```bash
# 具身智能项目下载论文（自动 rescan 打到具身智能）
WIKI_PROJECT=embodied python3 download.py 2509.18644 --dir training

# 项目 B 下载论文
WIKI_PROJECT=vibration python3 download.py 2301.12345 --dir papers

# 两条命令可以同时执行（在两个终端窗口）
```

**项目别名**：
| 别名 | 项目 ID | 基目录 |
|------|--------|--------|
| `embodied` | `${EMBODIED_PROJECT_ID}` | `${AUTO_RESEARCH_DIR}/knowledge_bases/02_embodied_intelligence/raw/sources` |
| `project_b` | `${VIBRATION_PROJECT_ID}` | `${AUTO_RESEARCH_DIR}/research_project/raw/sources` |

## 目录别名

| 别名 | 实际目录 |
|------|---------|
| `vla` | `vla_foundation/` |
| `action` | `action_chunking_latency/` |
| `data` | `data_imitation/` |
| `deploy` | `efficient_deployment/` |
| `training` | `training_theory/` |
| `refs` | `references/` |

也可以直接用完整子目录名 `--dir vla_foundation`。

## 配置

```bash
cp .env.example .env
# 编辑 .env，填写：
# - UNPAYWALL_EMAIL    用于 Unpaywall API（需真实 email）
# - SEMANTIC_SCHOLAR_API_KEY  可选，提高 S2 rate limit
```

未配置时仍可用，只是 Unpaywall 路径会被跳过。

## 数据源解析顺序

```
输入类型            解析链
─────────────────────────────────────────────
arXiv ID/URL   →  arXiv API  ─→  OpenAlex 补充 PDF URL
DOI            →  OpenAlex  ─→  Unpaywall（如配置）→ Semantic Scholar
GitHub URL     →  GitHub API  →  保存 README 到 references/
S2 ID          →  Semantic Scholar
标题           →  OpenAlex 搜索（不保证准确）
```

## 输出

- **PDF** → `WIKI_PAPERS_BASE/<子目录>/<arXivID>_<短名>.pdf`
- **GitHub README** → `WIKI_PAPERS_BASE/references/github_<owner>_<repo>.md`
- **清单** → `WIKI_PAPERS_BASE/_补充论文清单_YYYYMMDD_<主题>.md`

下载成功后自动调用 `POST /api/v1/projects/{id}/sources/rescan`，无需手动点击。
Token 从 `~/.local/share/com.llmwiki.app/app-state.json` 自动读取。

## 项目结构

```
wiki_paper_downloader/
├── download.py          主入口（CLI）
├── resolver.py          输入解析和源分发
├── downloader.py        PDF 下载（带 %PDF 验证）
├── output.py            Wiki 输出 + 清单生成
├── config.py            配置（.env 加载）
├── .env.example         配置模板
└── sources/
    ├── base.py           PaperMeta 数据结构
    ├── arxiv.py          arXiv API
    ├── openalex.py       OpenAlex API
    ├── semantic_scholar.py  Semantic Scholar API
    ├── unpaywall.py      Unpaywall API
    └── github.py         GitHub README 抓取
```
