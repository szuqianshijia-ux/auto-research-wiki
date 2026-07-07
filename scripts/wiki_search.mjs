#!/usr/bin/env node

import fs from "node:fs"
import path from "node:path"

const API_BASE = process.env.LLM_WIKI_API_BASE || "http://127.0.0.1:19828"
const APP_STATE =
  process.env.LLM_WIKI_APP_STATE ||
  path.join(process.env.HOME || "", ".local/share/com.llmwiki.app/app-state.json")

function loadToken() {
  if (process.env.LLM_WIKI_API_TOKEN) return process.env.LLM_WIKI_API_TOKEN
  try {
    const state = JSON.parse(fs.readFileSync(APP_STATE, "utf8"))
    const token = state.apiConfig?.token
    if (token) return token
  } catch {}
  return null
}

async function request(path, options = {}) {
  const token = loadToken()
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) }
  if (token) headers.Authorization = `Bearer ${token}`
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
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

function printUsage() {
  console.log(`Usage:
  node scripts/wiki_search.mjs search "相机运动 S2" [topK]
  node scripts/wiki_search.mjs content "wiki/sources/example-page.md"
  node scripts/wiki_search.mjs files [wiki|sources|all]
  node scripts/wiki_search.mjs graph "keyword" [limit]

Examples for Claude/Codex:
  node scripts/wiki_search.mjs search "相机运动补偿 Lee 2020 S2" 8
  node scripts/wiki_search.mjs search "example search query" 8
`)
}

const [cmd, ...args] = process.argv.slice(2)

try {
  if (!cmd || cmd === "-h" || cmd === "--help") {
    printUsage()
    process.exit(0)
  }

  if (cmd === "search") {
    const query = args[0]
    const topK = Number(args[1] || 8)
    if (!query) throw new Error("Missing search query.")
    const body = await request("/api/v1/projects/current/search", {
      method: "POST",
      body: JSON.stringify({ query, topK, includeContent: true }),
    })
    for (const [i, r] of (body.results || []).entries()) {
      const content = String(r.content || "").replace(/\s+/g, " ").slice(0, 700)
      console.log(`\n#${i + 1} score=${r.score ?? "?"}`)
      console.log(`path: ${r.path}`)
      console.log(`title: ${r.title || r.name || ""}`)
      console.log(content)
    }
    process.exit(0)
  }

  if (cmd === "content") {
    const path = args[0]
    if (!path) throw new Error("Missing wiki file path.")
    const body = await request(
      `/api/v1/projects/current/files/content?path=${encodeURIComponent(path)}`,
    )
    console.log(body.content || "")
    process.exit(0)
  }

  if (cmd === "files") {
    const root = args[0] || "wiki"
    const body = await request(
      `/api/v1/projects/current/files?root=${encodeURIComponent(root)}&recursive=true&maxFiles=10000`,
    )
    if (body.error) {
      console.error(`Error: ${body.error}`)
      process.exit(1)
    }
    function walk(nodes) {
      for (const n of nodes || []) {
        if (!n.isDir) console.log(n.path)
        if (n.children) walk(n.children)
      }
    }
    walk(body.files)
    process.exit(0)
  }

  if (cmd === "graph") {
    const q = args[0] || ""
    const limit = Number(args[1] || 100)
    const suffix = q
      ? `?q=${encodeURIComponent(q)}&limit=${limit}`
      : `?limit=${limit}`
    const body = await request(`/api/v1/projects/current/graph${suffix}`)
    console.log(JSON.stringify(body, null, 2))
    process.exit(0)
  }

  throw new Error(`Unknown command: ${cmd}`)
} catch (err) {
  console.error(err instanceof Error ? err.message : String(err))
  process.exit(1)
}
