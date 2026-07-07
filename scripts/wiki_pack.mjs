#!/usr/bin/env node

import fs from "node:fs"
import path from "node:path"

const API_BASE = process.env.LLM_WIKI_API_BASE || "http://127.0.0.1:19828"
const APP_STATE =
  process.env.LLM_WIKI_APP_STATE ||
  "${LLM_WIKI_APP_STATE}"

const DEFAULT_QUERIES = [
  "毕业论文主线 S1 S2 S3 p08 单锚点 尺度传递",
  "S2 相机运动 p03 p08 p13 GT 闭环",
  "相机自运动补偿 视频测振 Lee 2020 Su 2025",
  "全场振动 SSI-COV no-GT 结构一致性",
]

function loadToken() {
  if (process.env.LLM_WIKI_API_TOKEN) return process.env.LLM_WIKI_API_TOKEN
  const state = JSON.parse(fs.readFileSync(APP_STATE, "utf8"))
  const token = state.apiConfig?.token
  if (!token) {
    throw new Error(
      `LLM Wiki API token not found. Check ${APP_STATE} or set LLM_WIKI_API_TOKEN.`,
    )
  }
  return token
}

async function request(pathname, options = {}) {
  const token = loadToken()
  const res = await fetch(`${API_BASE}${pathname}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  })
  const text = await res.text()
  let body
  try {
    body = JSON.parse(text)
  } catch {
    body = { raw: text }
  }
  if (!res.ok || body.ok === false) {
    throw new Error(`LLM Wiki API ${res.status}: ${JSON.stringify(body).slice(0, 800)}`)
  }
  return body
}

function parseArgs(argv) {
  const opts = {
    out: "tmp/wiki_context.md",
    topK: 8,
    full: 3,
    queries: [],
  }
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i]
    if (arg === "--out") opts.out = argv[++i]
    else if (arg === "--topK") opts.topK = Number(argv[++i])
    else if (arg === "--full") opts.full = Number(argv[++i])
    else if (arg === "-h" || arg === "--help") opts.help = true
    else opts.queries.push(arg)
  }
  if (!opts.queries.length) opts.queries = DEFAULT_QUERIES
  opts.topK = Number.isFinite(opts.topK) ? Math.max(1, opts.topK) : 8
  opts.full = Number.isFinite(opts.full) ? Math.max(0, opts.full) : 3
  return opts
}

function usage() {
  console.log(`Usage:
  node scripts/wiki_pack.mjs [--out tmp/wiki_context.md] [--topK 8] [--full 3] "query 1" "query 2"

Examples:
  node scripts/wiki_pack.mjs "S2 相机运动 p03 p08 p13" "相机自运动补偿 Lee 2020"
  node scripts/wiki_pack.mjs --out tmp/wiki_s2.md --topK 10 --full 5 "S2 GT 闭环 单锚点尺度传递"

If no query is provided, the script uses thesis-default queries for S1/S2/S3.`)
}

function cleanSnippet(text, limit = 900) {
  return String(text || "")
    .replace(/\r/g, "")
    .replace(/[ \t]+/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .slice(0, limit)
}

async function main() {
  const opts = parseArgs(process.argv.slice(2))
  if (opts.help) {
    usage()
    return
  }

  const projects = await request("/api/v1/projects")
  const currentProject = projects.currentProject
  const byPath = new Map()
  const sections = []

  for (const query of opts.queries) {
    const body = await request("/api/v1/projects/current/search", {
      method: "POST",
      body: JSON.stringify({ query, topK: opts.topK, includeContent: true }),
    })
    const results = body.results || []
    sections.push({ query, mode: body.mode, results })
    for (const r of results) {
      if (!r.path || byPath.has(r.path)) continue
      byPath.set(r.path, r)
    }
  }

  const fullPaths = [...byPath.keys()].slice(0, opts.full)
  const fullContents = []
  for (const wikiPath of fullPaths) {
    try {
      const body = await request(
        `/api/v1/projects/current/files/content?path=${encodeURIComponent(wikiPath)}`,
      )
      fullContents.push({ path: wikiPath, content: cleanSnippet(body.content, 6000) })
    } catch (err) {
      fullContents.push({
        path: wikiPath,
        content: `读取失败：${err instanceof Error ? err.message : String(err)}`,
      })
    }
  }

  const lines = []
  lines.push("# LLM Wiki Evidence Pack")
  lines.push("")
  lines.push(`生成时间：${new Date().toISOString()}`)
  lines.push(`Wiki 项目：${currentProject?.name || "current"} (${currentProject?.path || "unknown"})`)
  lines.push(`查询数：${opts.queries.length}`)
  lines.push(`每个查询 topK：${opts.topK}`)
  lines.push("")
  lines.push("## 使用规则")
  lines.push("")
  lines.push("- 这个文件是写论文前的临时证据包，不是论文正文。")
  lines.push("- 写作或改文件时，优先把证据落到 `thesis/` 真实章节里。")
  lines.push("- 若证据包和本地论文文件冲突，以本地 `thesis/` 文件的最新口径为准，并说明冲突。")
  lines.push("- 不要把 Wiki 结论夸大成本文已经完成的实验。")
  lines.push("")
  lines.push("## 查询结果")
  for (const section of sections) {
    lines.push("")
    lines.push(`### ${section.query}`)
    lines.push("")
    lines.push(`检索模式：${section.mode || "unknown"}`)
    for (const [i, r] of section.results.entries()) {
      lines.push("")
      lines.push(`#### ${i + 1}. ${r.title || r.name || r.path}`)
      lines.push("")
      lines.push(`- path: \`${r.path}\``)
      lines.push(`- score: ${r.score ?? "?"}`)
      lines.push("")
      lines.push(cleanSnippet(r.content))
    }
  }

  if (fullContents.length) {
    lines.push("")
    lines.push("## Top Full Excerpts")
    for (const item of fullContents) {
      lines.push("")
      lines.push(`### ${item.path}`)
      lines.push("")
      lines.push("```markdown")
      lines.push(item.content)
      lines.push("```")
    }
  }

  fs.mkdirSync(path.dirname(opts.out), { recursive: true })
  fs.writeFileSync(opts.out, `${lines.join("\n")}\n`, "utf8")
  console.log(`Wrote ${opts.out}`)
  console.log(`Queries: ${opts.queries.length}; unique paths: ${byPath.size}; full excerpts: ${fullContents.length}`)
}

main().catch((err) => {
  console.error(err instanceof Error ? err.message : String(err))
  process.exit(1)
})
