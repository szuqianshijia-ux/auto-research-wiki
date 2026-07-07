# Agent 工作流模板

将 [Claude Code](https://claude.ai/claude-code) 与 LLM Wiki 知识库深度集成，实现 **搜索 → 推理 → 执行 → 归档** 的自动化闭环。

## 快速开始

### 1. 复制模板到你的项目

```bash
# 假设你的项目在 ~/my-project/
cd ~/my-project

# 创建 .claude 目录
mkdir -p .claude/skills/wiki-knowledge-loop .claude/commands

# 复制模板
cp path/to/auto-research-wiki/agents/claude-md-template/CLAUDE.md.template .claude/CLAUDE.md
cp path/to/auto-research-wiki/agents/skills/wiki-knowledge-loop/SKILL.md .claude/skills/wiki-knowledge-loop/
cp path/to/auto-research-wiki/agents/commands/*.md .claude/commands/

# 复制 Wiki 工具脚本
cp -r path/to/auto-research-wiki/scripts/ scripts/
```

### 2. 填写占位符

编辑 `.claude/CLAUDE.md`，替换所有 `{{...}}` 占位符：

| 占位符 | 说明 | 示例 |
|--------|------|------|
| `{{PROJECT_NAME}}` | 你的项目名称 | `My Research` |
| `{{PROJECT_ROOT}}` | 项目根目录 | `/home/user/my-project` |
| `{{WIKI_PROJECT_ID}}` | LLM Wiki 项目 ID | `64e92d8a-850e-...` |
| `{{KB_NAME}}` | 知识库名称 | `机器学习文献库` |
| `{{WIKI_VAULT_DIR}}` | Wiki vault 目录名 | `wiki-vault` |
| `{{EXAMPLE_QUERY_1}}` | 示例搜索词 | `transformer attention mechanism` |
| `{{EXAMPLE_QUERY_2}}` | 示例搜索词 | `training loss convergence` |

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填写 LLM_WIKI_API_TOKEN 和项目路径
```

### 4. 开始使用

在 Claude Code 中：

```bash
# 生成证据包（开始新对话前）
/wiki-write

# 写对话摘要（对话结束后）
/wiki-summary
```

## 知识闭环

```
┌─────────────────────────────────────────┐
│            Claude Code Agent            │
│                                         │
│  1. /wiki-write                         │
│     ├── wiki_pack.mjs → 证据包          │
│     ├── 基于证据推理和执行               │
│     └── 产出代码/文档/分析               │
│                                         │
│  2. /wiki-summary                       │
│     ├── 生成对话摘要                     │
│     ├── sync_notes_to_wiki.mjs → 同步   │
│     └── LLM Wiki Rescan                │
│                                         │
│  3. 下次对话                             │
│     └── wiki_pack.mjs 能搜到上次的结论   │
└─────────────────────────────────────────┘
```

## 文件说明

| 文件 | 用途 |
|------|------|
| `claude-md-template/CLAUDE.md.template` | 项目级 CLAUDE.md 模板 |
| `skills/wiki-knowledge-loop/SKILL.md` | Wiki 知识循环技能定义 |
| `commands/wiki-write.md` | `/wiki-write` 命令 |
| `commands/wiki-summary.md` | `/wiki-summary` 命令 |

## 自定义

### 添加项目特定搜索词

编辑 `scripts/wiki_pack.mjs` 中的 `DEFAULT_QUERIES` 数组。

### 添加新命令

在 `.claude/commands/` 下创建 `your-command.md`，然后在 Claude Code 中用 `/your-command` 调用。

### 扩展技能

编辑 `.claude/skills/wiki-knowledge-loop/SKILL.md`，添加项目特定的工作流步骤。
