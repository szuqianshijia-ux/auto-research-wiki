# Wiki Knowledge Loop

## 目的

保持项目工作区与知识库的自我改进闭环：

```
搜索 wiki → 制定计划 → 执行 → 总结有价值的发现 → 同步入库 → rescan → 下次搜索更丰富
```

## 豁免清单：以下情况跳过 wiki 检索（直接动手更快）

- 调试代码报错、看 traceback、排查运行时崩溃
- 查项目文件结构、文件路径、目录定位
- 闲谈和概念澄清（无实验/训练实际操作）
- 单步 git/shell 操作（`git status`、`ls`、`nvidia-smi` 等）
- 简单文本编辑或注释补充（无跨模块影响）

## 第一步：生成证据包（实质性任务开始前）

```bash
# 默认关键词搜索，带时间戳输出
node scripts/wiki_pack.mjs

# 指定输出路径（便于在会话总结中精确引用）
node scripts/wiki_pack.mjs --out "notes/wiki_logs/$(date +%Y-%m-%d_%H-%M)_evidence.md" --topK 8 --full 2

# 追加自定义关键词
node scripts/wiki_pack.mjs "关键词A" "关键词B"
```

快速单次搜索：
```bash
node scripts/wiki_search.mjs search "<关键词>" 8
```

读取证据包，基于其中内容约束判断。若 wiki 证据与本地文件冲突，以最新本地文件为准并说明冲突。

**记录证据包路径**：运行后记住带时间戳的路径，填入会话总结的 `Wiki证据包路径` 字段。

## 第二步：执行（带证据的对话/编码）

记录对未来有复用价值的事实：
- 具体问题与假设
- 成功或失败的命令
- 输出路径与指标（loss、准确率、延迟等）
- 根因分析，尤其是负面结果
- 改变方向的关键决策

**不记录**：原始数据文件、二进制产物、checkpoint、缓存、完整源码。

## 第三步：对话结束写摘要

实质性任务结束后主动判断是否值得写会话总结。有价值则写入：

```
notes/chat_summaries/YYYYMMDD_类别_主题.md
```

类别自行定义，参考：训练 / 数据 / 部署 / 调试 / 实验 / 配置 / 分析

**必填结构**：

```markdown
# YYYYMMDD 类别 主题

## 元数据
- 文档类型：聊天会话总结 / Wiki 入口索引
- 日期：YYYY-MM-DD
- 主题：[一句话]
- Wiki证据包路径：`notes/wiki_logs/YYYY-MM-DD_HH-MM_evidence.md`
- 关联深度文档：[文件路径列表 或 none]
- 关联模块：[相关代码模块 或 none]
- 关键词：[逗号分隔]

## 这次会话解决了什么
[具体描述，要点形式]

## 关键结论
[最重要的发现或决策，1-3 条]

## 产出文件
[本次产生的代码/配置/文档/数据改动列表]

## 对项目的影响
[说明对项目方向或方案的影响]

## 后续建议
[下次对话应关注什么，或需要继续做什么]

## 同步状态
- [ ] sync_notes_to_wiki.mjs --dry-run 已校验
- [ ] 正式 sync 已执行
- [ ] 已在 LLM Wiki 中 Rescan Raw Sources
```

深度技术细节（如具体实验分析过程）放在独立文档：
```
docs/YYYYMMDD_主题详情.md
```
会话总结链接到深度文档，不重复所有细节。

## 第四步：同步入库

```bash
# 先 dry-run 预览
node scripts/sync_notes_to_wiki.mjs --dry-run

# 确认后正式同步并触发 rescan
node scripts/sync_notes_to_wiki.mjs --rescan
```

然后在 LLM Wiki App 中手动 Rescan Raw Sources（如果 API rescan 未生效）。

## 什么该/不该进 wiki

**该记录**：
- 实验结论与指标对比
- 根因分析
- 失败路线与原因
- 数据格式转换踩坑
- 配置最优值
- 未来应复用的工作流规则

**不该记录**：
- 原始数据转储
- 大型二进制输出
- 无结论的临时日志
- 未加解释直接粘贴的源码
- 无可复用结果的闲聊

## 使用技巧

### 定制默认搜索词

编辑 `scripts/wiki_pack.mjs` 中的 `DEFAULT_QUERIES` 数组，添加你项目的核心搜索词组合。

### 远端使用

如果 LLM Wiki 运行在本地机器，但你在远程服务器上工作：

```bash
# 在远程机器上建立 SSH 隧道（替换为你的本地 IP）
ssh -L 19828:127.0.0.1:19828 your_user@your_local_ip

# 然后在远程机器上正常运行脚本
node scripts/wiki_pack.mjs
```
