# /wiki-write

基于知识库完成分析、编写或实验记录任务。

## 工作流

1. **生成证据包**
   ```bash
   node scripts/wiki_pack.mjs
   # 指定输出和参数：
   node scripts/wiki_pack.mjs --out "notes/wiki_logs/$(date +%Y-%m-%d_%H-%M)_evidence.md" --topK 8 --full 2 "关键词A" "关键词B"
   ```

2. **读取证据包** — `notes/wiki_logs/` 下最新的 `.md` 文件

3. **执行任务** — 基于证据回答/编写/分析，标注引用来源

4. **结束后写摘要** — `notes/chat_summaries/YYYYMMDD_类别_主题.md`

5. **同步入库**
   ```bash
   node scripts/sync_notes_to_wiki.mjs --dry-run    # 先预览
   node scripts/sync_notes_to_wiki.mjs --rescan      # 确认后正式同步
   ```

## 常见任务类型

- **分析实验结果**：搜索已有 baseline，对比当前指标
- **调试数据管道**：搜索数据格式、处理规范、历史踩坑记录
- **记录进展**：搜索历史部署/实验笔记，更新状态
- **对比方案**：搜索不同技术路线的优劣分析
- **文献综述**：搜索知识库中的论文实体和概念关联
