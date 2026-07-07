#!/usr/bin/env node

import fs from "node:fs"
import path from "node:path"

const ROOT = process.cwd()
const OUT_DIR =
  process.env.THESIS_WIKI_UPLOAD_DIR ||
  path.join(ROOT, "wiki_upload_thesis_context")
const WIKI_SOURCES_DIR =
  process.env.LLM_WIKI_THESIS_SOURCES_DIR ||
  path.join(process.env.AUTO_RESEARCH_DIR || ".", "research_project/raw/sources/research_context")

const COPY_RULES = [
  ["thesis/论文总入口.md", "01_thesis_mainline/论文总入口.md"],
  ["thesis/论文证据地图.md", "01_thesis_mainline/论文证据地图.md"],
  ["thesis/论文大纲.md", "01_thesis_mainline/论文大纲.md"],
  ["thesis/论文图表与证据索引.md", "01_thesis_mainline/论文图表与证据索引.md"],
  ["thesis/论文图表标题与图注草稿.md", "01_thesis_mainline/论文图表标题与图注草稿.md"],
  ["thesis/写作推进计划.md", "01_thesis_mainline/写作推进计划.md"],
  ["thesis/深度研究报告.md", "01_thesis_mainline/深度研究报告.md"],
  ["thesis/术语表_中文.md", "01_thesis_mainline/术语表_中文.md"],

  ["thesis/chapters/00摘要.md", "02_chapters/00摘要.md"],
  ["thesis/chapters/00_guidelines.md", "02_chapters/00_guidelines.md"],
  ["thesis/chapters/01绪论.md", "02_chapters/01绪论.md"],
  ["thesis/chapters/02理论基础.md", "02_chapters/02理论基础.md"],
  ["thesis/chapters/03S1静态场景.md", "02_chapters/03S1静态场景.md"],
  ["thesis/chapters/04_chapter_4.md", "02_chapters/04_chapter_4.md"],
  ["thesis/chapters/05_chapter_5.md", "02_chapters/05_chapter_5.md"],
  ["thesis/chapters/06系统实现.md", "02_chapters/06系统实现.md"],
  ["thesis/chapters/07总结展望.md", "02_chapters/07总结展望.md"],
  ["thesis/chapters/章节说明.md", "02_chapters/章节说明.md"],

  ["gpt_deep_research_upload_20260504/core_7/01_OUTLINE.md", "03_s2_core/deep_research_core_7/01_OUTLINE.md"],
  ["gpt_deep_research_upload_20260504/core_7/02_deep-research-report.md", "03_s2_core/deep_research_core_7/02_deep-research-report.md"],
  ["gpt_deep_research_upload_20260504/core_7/03_PHASE_METHOD_THEORY_DIGEST.md", "03_s2_core/deep_research_core_7/03_PHASE_METHOD_THEORY_DIGEST.md"],
  ["gpt_deep_research_upload_20260504/core_7/04_CURRENT_BASELINES.md", "03_s2_core/deep_research_core_7/04_CURRENT_BASELINES.md"],
  ["gpt_deep_research_upload_20260504/core_7/05_sample8_triplet_eval_convention.md", "03_s2_core/deep_research_core_7/05_sample8_triplet_eval_convention.md"],
  ["gpt_deep_research_upload_20260504/core_7/06_SAMPLE8_S1_EVIDENCE_REVIEW_20260502.md", "03_s2_core/deep_research_core_7/06_SAMPLE8_S1_EVIDENCE_REVIEW_20260502.md"],
  ["gpt_deep_research_upload_20260504/core_7/07_S2_NO_GT_EXTRACTION_QA_AND_CORRECTION.md", "03_s2_core/deep_research_core_7/07_S2_NO_GT_EXTRACTION_QA_AND_CORRECTION.md"],
  ["gpt_deep_research_upload_20260504/optional_2/08_sample8_s2_six_axis_stage_experiment_plan.md", "03_s2_core/deep_research_optional_2/08_sample8_s2_six_axis_stage_experiment_plan.md"],
  ["gpt_deep_research_upload_20260504/optional_2/09_sample8_15pt_no_gt_roi_convergence.md", "03_s2_core/deep_research_optional_2/09_sample8_15pt_no_gt_roi_convergence.md"],

  ["thesis/weekly_reports/2026-05-02_S2_Z_案例5修复.md", "03_s2_core/weekly_reports/2026-05-02_S2_Z_案例5修复.md"],
  ["thesis/weekly_reports/details/2026-05-18_进度同步与S2数据评估.md", "03_s2_core/weekly_reports/2026-05-18_进度同步与S2数据评估.md"],
  ["thesis/weekly_reports/details/2026年第19周_结构一致性重做.md", "03_s2_core/weekly_reports/2026年第19周_结构一致性重做.md"],
  ["thesis/weekly_reports/details/2026年第19周_结构一致性v3优化.md", "03_s2_core/weekly_reports/2026年第19周_结构一致性v3优化.md"],
  ["thesis/weekly_reports/details/2026-05-14_边界条件扫描补充实验v3.md", "03_s2_core/weekly_reports/2026-05-14_边界条件扫描补充实验v3.md"],
  ["thesis/weekly_reports/details/2026-05-30_S2方法学补强与金字塔参数搜索.md", "03_s2_core/weekly_reports/2026-05-30_S2方法学补强与金字塔参数搜索.md"],
  ["thesis/weekly_reports/details/2026-05-30_小论文B_V2五档修订与wiki同步.md", "03_s2_core/weekly_reports/2026-05-30_小论文B_V2五档修订与wiki同步.md"],
  ["thesis/weekly_reports/details/2026-05-31_边界SNR多seed串行重跑v4.md", "03_s2_core/weekly_reports/2026-05-31_边界SNR多seed串行重跑v4.md"],
  ["thesis/weekly_reports/details/2026-05-31_算法与架构改进建议报告.md", "03_s2_core/weekly_reports/2026-05-31_算法与架构改进建议报告.md"],
  ["thesis/weekly_reports/details/2026-05-31_动态参考帧A2阶段0代理验证.md", "03_s2_core/weekly_reports/2026-05-31_动态参考帧A2阶段0代理验证.md"],
  ["mainline/docs/sample8_triplet_eval_convention.md", "03_s2_core/mainline_docs/sample8_triplet_eval_convention.md"],
  ["mainline/docs/sample8_15pt_no_gt_roi_convergence.md", "03_s2_core/mainline_docs/sample8_15pt_no_gt_roi_convergence.md"],
  ["mainline/docs/analysis_frame_rule.json", "03_s2_core/mainline_docs/analysis_frame_rule.json"],

  ["thesis/pack/method/00项目章程.md", "04_method_and_experiments/method/00项目章程.md"],
  ["thesis/pack/method/02参数.csv", "04_method_and_experiments/method/02参数.csv"],
  ["thesis/pack/method/02流水线.md", "04_method_and_experiments/method/02流水线.md"],
  ["thesis/pack/method/术语表.md", "04_method_and_experiments/method/术语表.md"],
  ["thesis/pack/experiments/01基准.md", "04_method_and_experiments/experiments/01基准.md"],
  ["thesis/pack/experiments/03样本.csv", "04_method_and_experiments/experiments/03样本.csv"],
  ["thesis/pack/experiments/04证据.md", "04_method_and_experiments/experiments/04证据.md"],
  ["thesis/pack/experiments/04评分准则.md", "04_method_and_experiments/experiments/04评分准则.md"],
  ["thesis/pack/experiments/05正控矩阵.csv", "04_method_and_experiments/experiments/05正控矩阵.csv"],
  ["thesis/pack/experiments/05负面说明.md", "04_method_and_experiments/experiments/05负面说明.md"],

  ["thesis/pack/literature/01文献矩阵.md", "05_literature/01文献矩阵.md"],
  ["thesis/pack/literature/01文献背景_cn.md", "05_literature/01文献背景_cn.md"],
  ["thesis/pack/literature/02补充文献_20260526.md", "05_literature/02补充文献_20260526.md"],
  ["thesis/pack/research/深度研究报告集成说明.md", "05_literature/research_pack/深度研究报告集成说明.md"],
  ["thesis/chat_summaries/2026-07-04_文献深度综述.md", "05_literature/2026-07-04_文献深度综述.md"],
  ["thesis/chat_summaries/2026-07-04_文献精读批注.md", "05_literature/2026-07-04_文献精读批注.md"],
  ["thesis/chat_summaries/2026-07-03_论文精读总结.md", "05_literature/2026-07-03_论文精读总结.md"],
  ["thesis/chat_summaries/2026-07-03_Google_AI_文献调研与方案验证报告.md", "05_literature/2026-07-03_Google_AI_文献调研与方案验证报告.md"],
  ["thesis/chat_summaries/2026-07-04_文献启发与研究实施计划.md", "05_literature/2026-07-04_文献启发与研究实施计划.md"],

  ["thesis/pack/writing/07属性说明.md", "06_writing_and_figures/writing_pack/07属性说明.md"],
  ["thesis/pack/writing/代理运行协议.md", "06_writing_and_figures/writing_pack/代理运行协议.md"],
  ["thesis/pack/writing/审阅记录.md", "06_writing_and_figures/writing_pack/审阅记录.md"],
  ["thesis/pack/writing/总结.md", "06_writing_and_figures/writing_pack/总结.md"],
  ["thesis/pack/writing/执行方案.md", "06_writing_and_figures/writing_pack/执行方案.md"],
  ["thesis/pack/writing/论文写作材料包.md", "06_writing_and_figures/writing_pack/论文写作材料包.md"],
  ["thesis/pack/writing/论文提纲.md", "06_writing_and_figures/writing_pack/论文提纲.md"],
  ["thesis/pack/writing/说明.md", "06_writing_and_figures/writing_pack/说明.md"],
  ["thesis/pack/writing/问题清单.csv", "06_writing_and_figures/writing_pack/问题清单.csv"],
  ["thesis/weekly_reports/2026-05-08_ppt_assets/图片索引.md", "06_writing_and_figures/图片索引.md"],
  ["thesis/weekly_reports/2026-05-08_ppt_assets/PPT大纲.md", "06_writing_and_figures/PPT大纲.md"],
  ["thesis/weekly_reports/2026-05-08_ppt_assets/PPT大纲_基于集合包更新版.md", "06_writing_and_figures/PPT大纲_基于集合包更新版.md"],
  ["thesis/weekly_reports/2026-05-08_ppt_assets/17_18_样本8_full2000对齐说明.md", "06_writing_and_figures/17_18_样本8_full2000对齐说明.md"],
  ["phase_based-main/docs/reports/小论文B_V2五档审计与修订记录_20260530.md", "06_writing_and_figures/小论文B_V2五档审计与修订记录_20260530.md"],
  ["phase_based-main/docs/reports/小论文B_15通道结构一致性评分表_20260531.md", "06_writing_and_figures/小论文B_15通道结构一致性评分表_20260531.md"],
  ["thesis/小论文B优化决策记录.md", "06_writing_and_figures/小论文B优化决策记录.md"],

  ["phase_based-main/end2end/docs/thesis_e2e_section.md", "08_end2end/thesis_e2e_section.md"],
  ["phase_based-main/end2end/docs/m2def_stability_summary.md", "08_end2end/m2def_stability_summary.md"],
  ["phase_based-main/end2end/docs/2026-06-18_M3A滚动参考帧与case1跨场景实验.md", "08_end2end/2026-06-18_M3A滚动参考帧与case1跨场景实验.md"],
  ["phase_based-main/end2end/README.md", "08_end2end/README_e2e_module.md"],
]

const COPY_DIR_RULES = [
  ["thesis/chat_summaries", "07_chat_summaries"],
]

const COPY_DIR_EXCLUDE = new Set([
  "2026-06-23_wiki工作流优化.md",
  "2026-07-03_Google_AI_研究咨询提示词.md",
  "2026-07-04_文献深度综述.md",
  "2026-07-04_文献精读批注.md",
  "2026-07-03_论文精读总结.md",
  "2026-07-03_Google_AI_文献调研与方案验证报告.md",
  "2026-07-04_文献启发与研究实施计划.md",
])

const COPY_DIR_ALLOWED_EXTENSIONS = new Set([".md", ".txt", ".csv", ".json"])

const README = `# LLM Wiki 导入说明

这个文件夹是给 LLM Wiki 导入的研究上下文包，包含文档、实验记录和文献资料。

## 使用方式

在 LLM Wiki 中导入本目录，或由脚本同步到 LLM Wiki 项目的 raw/sources 目录。

## 阅读优先级

1. \`01_thesis_mainline/论文总入口.md\`
2. \`02_chapters/\`
3. \`03_s2_core/\`
4. \`04_method_and_experiments/\`
5. \`05_literature/\`（含文献矩阵、深度综述、精读批注）
6. \`06_writing_and_figures/\`
7. \`07_chat_summaries/\`（实验记录摘要，仅中等价值）
8. \`08_end2end/\`

## 重要口径


## 不包含的内容

本包故意不包含原始视频、大型图片、\`.npy\`、\`.mat\`、缓存目录、构建产物和完整源代码，避免 LLM Wiki 导入过慢或生成无关知识节点。

## 同步排除规则

以下文件已排除同步（低价值或已重新分类）：
- 低价值 wiki 工作流日志和纯 prompt 文本不再同步到 07_chat_summaries/
- 5 篇高价值文献综述已从 07_chat_summaries/ 重新映射到 05_literature/
`

function parseArgs(argv) {
  return {
    dryRun: argv.includes("--dry-run"),
    noWiki: argv.includes("--no-wiki"),
    help: argv.includes("-h") || argv.includes("--help"),
  }
}

function usage() {
  console.log(`Usage:
  node scripts/sync_thesis_to_wiki_sources.mjs
  node scripts/sync_thesis_to_wiki_sources.mjs --dry-run
  node scripts/sync_thesis_to_wiki_sources.mjs --no-wiki

Environment:
  THESIS_WIKI_UPLOAD_DIR       default: ./wiki_upload_thesis_context
  LLM_WIKI_THESIS_SOURCES_DIR  default: \${AUTO_RESEARCH_DIR}/research_project/raw/sources/research_context`)
}

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true })
}

function removeDir(dir) {
  if (fs.existsSync(dir)) fs.rmSync(dir, { recursive: true, force: true })
}

function copyFile(srcRel, dstRoot, dstRel, dryRun) {
  const src = path.join(ROOT, srcRel)
  const dst = path.join(dstRoot, dstRel)
  if (!fs.existsSync(src)) return { copied: false, missing: srcRel }
  if (!dryRun) {
    ensureDir(path.dirname(dst))
    fs.copyFileSync(src, dst)
  }
  return { copied: true, srcRel, dstRel, size: fs.statSync(src).size }
}

function copyDir(srcDirRel, dstRoot, dstDirRel, dryRun) {
  const srcDir = path.join(ROOT, srcDirRel)
  if (!fs.existsSync(srcDir)) return { copied: [], missing: [srcDirRel] }

  const copied = []
  const missing = []
  for (const src of listFiles(srcDir)) {
    if (!COPY_DIR_ALLOWED_EXTENSIONS.has(path.extname(src))) continue
    if (COPY_DIR_EXCLUDE.has(path.basename(src))) continue
    const fileRel = path.relative(srcDir, src)
    const srcRel = path.join(srcDirRel, fileRel)
    const dstRel = path.join(dstDirRel, fileRel)
    const result = copyFile(srcRel, dstRoot, dstRel, dryRun)
    if (result.copied) copied.push(result)
    else missing.push(result.missing)
  }
  return { copied, missing }
}

function listFiles(dir) {
  const out = []
  if (!fs.existsSync(dir)) return out
  function walk(current) {
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const full = path.join(current, entry.name)
      if (entry.isDirectory()) walk(full)
      else if (entry.isFile()) out.push(full)
    }
  }
  walk(dir)
  return out.sort()
}

function writeSupportFiles(root, copied, missing, dryRun) {
  if (dryRun) return
  const relFiles = listFiles(root).map((file) => path.relative(root, file))
  fs.writeFileSync(path.join(root, "MANIFEST.txt"), `${relFiles.join("\n")}\n`, "utf8")
  fs.writeFileSync(path.join(root, "README_FOR_LLM_WIKI.md"), README, "utf8")
  const status = [
    "# Wiki Upload Status",
    "",
    `updated_at: ${new Date().toISOString()}`,
    `copied_files: ${copied.length}`,
    `missing_files: ${missing.length}`,
    "",
    "## Missing",
    "",
    ...(missing.length ? missing.map((m) => `- ${m}`) : ["- none"]),
    "",
    "## Copied",
    "",
    ...copied.map((c) => `- ${c.dstRel} <= ${c.srcRel}`),
    "",
  ].join("\n")
  fs.writeFileSync(path.join(root, "STATUS_SYNC.md"), status, "utf8")
}

function syncDir(srcDir, dstDir, dryRun) {
  if (dryRun) return
  removeDir(dstDir)
  ensureDir(dstDir)
  for (const src of listFiles(srcDir)) {
    const rel = path.relative(srcDir, src)
    const dst = path.join(dstDir, rel)
    ensureDir(path.dirname(dst))
    fs.copyFileSync(src, dst)
  }
  const relFiles = listFiles(dstDir).map((file) => path.relative(dstDir, file))
  fs.writeFileSync(path.join(dstDir, "MANIFEST_IMPORTED.txt"), `${relFiles.join("\n")}\n`, "utf8")
}

function main() {
  const opts = parseArgs(process.argv.slice(2))
  if (opts.help) {
    usage()
    return
  }

  const copied = []
  const missing = []

  if (!opts.dryRun) {
    removeDir(OUT_DIR)
    ensureDir(OUT_DIR)
  }

  for (const [srcRel, dstRel] of COPY_RULES) {
    const result = copyFile(srcRel, OUT_DIR, dstRel, opts.dryRun)
    if (result.copied) copied.push(result)
    else missing.push(result.missing)
  }

  for (const [srcDirRel, dstDirRel] of COPY_DIR_RULES) {
    const result = copyDir(srcDirRel, OUT_DIR, dstDirRel, opts.dryRun)
    copied.push(...result.copied)
    missing.push(...result.missing)
  }

  writeSupportFiles(OUT_DIR, copied, missing, opts.dryRun)
  if (!opts.noWiki) syncDir(OUT_DIR, WIKI_SOURCES_DIR, opts.dryRun)

  console.log(`copied=${copied.length}`)
  console.log(`missing=${missing.length}`)
  console.log(`upload_dir=${OUT_DIR}`)
  if (!opts.noWiki) console.log(`wiki_sources_dir=${WIKI_SOURCES_DIR}`)
  if (missing.length) {
    console.log("missing files:")
    for (const m of missing) console.log(`- ${m}`)
  }
  if (opts.dryRun) console.log("dry-run: no files were changed")
}

main()
