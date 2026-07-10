#!/usr/bin/env node
// 将对话摘要（chat summaries）增量同步至 LLM Wiki 知识库的 raw sources 目录
// 用法：node scripts/sync_notes_to_wiki.mjs [--dry-run] [--rescan]
//
//   --dry-run   只显示将要复制的文件，不实际写入
//   --rescan    同步后触发 LLM Wiki rescan（不与 --dry-run 同用）
//   -h, --help  显示帮助

import fs from "node:fs"
import path from "node:path"

const ROOT = process.cwd()

const SRC_DIR = process.env.NOTES_SRC_DIR || path.join(ROOT, "notes/chat_summaries")

const AUTO_RESEARCH_DIR = process.env.AUTO_RESEARCH_DIR || ""
const DST_DIR =
  process.env.NOTES_DST_DIR ||
  (AUTO_RESEARCH_DIR
    ? path.join(AUTO_RESEARCH_DIR, "raw/sources/ai_chats/对话摘要")
    : "")

const API_BASE = process.env.LLM_WIKI_API_BASE || "http://127.0.0.1:19828"
const APP_STATE =
  process.env.LLM_WIKI_APP_STATE ||
  path.join(process.env.HOME || "", ".local/share/com.llmwiki.app/app-state.json")

function parseArgs(argv) {
  return {
    dryRun: argv.includes("--dry-run"),
    rescan: argv.includes("--rescan"),
    help: argv.includes("-h") || argv.includes("--help"),
  }
}

function printUsage() {
  console.log(`用法：node scripts/sync_notes_to_wiki.mjs [--dry-run] [--rescan]

  --dry-run   只预览将要复制的文件，不实际写入
  --rescan    同步后触发 LLM Wiki rescan（dry-run 时忽略）
  -h, --help  显示此帮助

环境变量：
  NOTES_SRC_DIR         摘要源目录（默认：notes/chat_summaries/）
  NOTES_DST_DIR         同步目标目录（覆盖 AUTO_RESEARCH_DIR 推导）
  AUTO_RESEARCH_DIR     LLM Wiki 工作目录（用于推导目标路径）
  LLM_WIKI_API_BASE     Wiki API 地址（默认：http://127.0.0.1:19828）
  LLM_WIKI_API_TOKEN    Wiki API Token
  LLM_WIKI_APP_STATE    LLM Wiki app-state.json 路径（token 备用来源）`)
}

function loadToken() {
  if (process.env.LLM_WIKI_API_TOKEN) return process.env.LLM_WIKI_API_TOKEN
  try {
    const state = JSON.parse(fs.readFileSync(APP_STATE, "utf8"))
    return state.apiConfig?.token || null
  } catch {
    return null
  }
}

async function triggerRescan() {
  const token = loadToken()
  if (!token) {
    console.warn("未找到 LLM Wiki token，跳过 rescan")
    return
  }
  const res = await fetch(`${API_BASE}/api/v1/projects/current/sources/rescan`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({}),
  })
  if (res.ok) {
    const body = await res.json().catch(() => ({}))
    const queued = body.queued ?? "?"
    console.log(`触发知识库 rescan 成功 — ${queued} 个文件已加入处理队列`)
  } else {
    const text = await res.text()
    console.warn(`rescan 请求返回 ${res.status}: ${text.slice(0, 200)}`)
  }
}

async function main() {
  const args = parseArgs(process.argv)

  if (args.help) {
    printUsage()
    process.exit(0)
  }

  const dryRun = args.dryRun
  const doRescan = args.rescan && !dryRun

  if (!DST_DIR) {
    console.error(
      "错误：未配置目标目录。请设置 AUTO_RESEARCH_DIR 或 NOTES_DST_DIR 环境变量。\n" +
        "示例：AUTO_RESEARCH_DIR=/path/to/auto_research node scripts/sync_notes_to_wiki.mjs",
    )
    process.exit(1)
  }

  if (dryRun) console.log("【dry-run 模式】只预览，不实际写入\n")

  if (!fs.existsSync(SRC_DIR)) {
    console.log(`源目录不存在，无文件需同步：${SRC_DIR}`)
    console.log("提示：创建 notes/chat_summaries/ 目录并放入 .md 摘要文件后重试。")
    process.exit(0)
  }

  if (!dryRun) fs.mkdirSync(DST_DIR, { recursive: true })

  const files = fs.readdirSync(SRC_DIR).filter((f) => f.endsWith(".md"))
  if (files.length === 0) {
    console.log("notes/chat_summaries/ 中没有 .md 文件，无需同步")
    process.exit(0)
  }

  let willCopy = 0
  let copied = 0
  let skipped = 0

  for (const file of files) {
    const src = path.join(SRC_DIR, file)
    const dst = path.join(DST_DIR, file)

    const dstExists = fs.existsSync(dst)
    if (dstExists) {
      const srcMtime = fs.statSync(src).mtimeMs
      const dstMtime = fs.statSync(dst).mtimeMs
      if (srcMtime <= dstMtime) {
        skipped++
        continue
      }
    }

    willCopy++
    if (dryRun) {
      console.log(`  [会复制] ${file}${dstExists ? " (更新)" : " (新增)"}`)
    } else {
      fs.copyFileSync(src, dst)
      console.log(`  复制: ${file}${dstExists ? " (更新)" : " (新增)"}`)
      copied++
    }
  }

  if (dryRun) {
    console.log(`\ndry-run 结果：${willCopy} 个文件将被复制，${skipped} 个文件已是最新`)
    console.log(`目标目录：${DST_DIR}`)
    console.log("\n确认无误后去掉 --dry-run 正式执行。")
  } else {
    console.log(`\n同步完成：${copied} 个文件已复制，${skipped} 个文件已是最新`)
    console.log(`目标目录：${DST_DIR}`)
    if (doRescan) {
      console.log("\n触发 LLM Wiki rescan …")
      await triggerRescan()
    } else {
      console.log("\n提示：加 --rescan 参数可在同步后自动触发知识库重新扫描")
    }
  }
}

main().catch((err) => {
  console.error(`同步失败: ${err.message}`)
  process.exit(1)
})
