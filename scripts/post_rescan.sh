#!/usr/bin/env bash
# post_rescan.sh — rescan 完成后的知识库后处理流程
#
# 用法：
#   bash scripts/post_rescan.sh [选项]
#
# 选项：
#   --community      生成知识社区摘要（调用 LLM，耗时较长，默认关闭）
#   --merge-dups     自动合并近重复实体（需先确认 detect-dups 结果，默认关闭）
#   --trim           LLM 压缩超长实体页面（默认关闭）
#   --dry-run        所有操作仅预览，不写入文件
#   --project vib    指定项目别名（embodied|vib，默认读取 WIKI_PROJECT 环境变量）
#
# 典型使用场景：
#   rescan 完成后（新论文已被 LLM Wiki 处理），运行本脚本维护知识库质量。
#
# 示例：
#   bash scripts/post_rescan.sh                        # 最小流程：图索引 + 去重检测
#   bash scripts/post_rescan.sh --community --trim     # 完整流程（较慢）
#   bash scripts/post_rescan.sh --project vib          # 指定振动研究项目
#   WIKI_PROJECT=vib bash scripts/post_rescan.sh       # 等价写法

set -euo pipefail

# ── 参数解析 ─────────────────────────────────────────────────────────────────

DO_COMMUNITY=0
DO_MERGE_DUPS=0
DO_TRIM=0
DRY_RUN=0
PROJECT="${WIKI_PROJECT:-embodied}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --community)   DO_COMMUNITY=1 ;;
        --merge-dups)  DO_MERGE_DUPS=1 ;;
        --trim)        DO_TRIM=1 ;;
        --dry-run)     DRY_RUN=1 ;;
        --project)     shift; PROJECT="$1" ;;
        -h|--help)
            sed -n '2,/^set /p' "$0" | grep '^#' | sed 's/^# \?//'
            exit 0
            ;;
        *)
            echo "[错误] 未知参数: $1" >&2
            exit 1
            ;;
    esac
    shift
done

# ── 环境检查 ──────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

# 加载 .env（如果存在）
if [[ -f "$REPO_ROOT/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "$REPO_ROOT/.env"
    set +a
fi

WIKI_RETRIEVAL="$REPO_ROOT/tools/wiki_retrieval.py"
WIKI_OPTIMIZER="$REPO_ROOT/tools/wiki_optimizer.py"

if [[ ! -f "$WIKI_RETRIEVAL" ]]; then
    echo "[错误] 未找到 $WIKI_RETRIEVAL" >&2
    exit 1
fi
if [[ ! -f "$WIKI_OPTIMIZER" ]]; then
    echo "[错误] 未找到 $WIKI_OPTIMIZER" >&2
    exit 1
fi

# 根据项目别名设置环境变量
export WIKI_PROJECT="$PROJECT"

DRY_FLAG=""
[[ "$DRY_RUN" -eq 1 ]] && DRY_FLAG="--dry-run"

echo "=== post_rescan.sh ==="
echo "项目: $PROJECT | $(date '+%Y-%m-%d %H:%M:%S')"
[[ "$DRY_RUN" -eq 1 ]] && echo "[dry-run 模式]"
echo ""

# ── 步骤 1：更新知识图索引 ────────────────────────────────────────────────────

echo "步骤 1/4  构建知识图索引 (wiki_retrieval --build-index)..."
if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "  [dry-run] python3 $WIKI_RETRIEVAL --build-index"
else
    python3 "$WIKI_RETRIEVAL" --build-index
fi
echo ""

# ── 步骤 2：近重复检测 ───────────────────────────────────────────────────────

echo "步骤 2/4  检测近重复实体 (wiki_optimizer detect-dups)..."
if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "  [dry-run] python3 $WIKI_OPTIMIZER detect-dups"
else
    python3 "$WIKI_OPTIMIZER" detect-dups
fi
echo ""

# ── 步骤 3（可选）：合并近重复 ───────────────────────────────────────────────

if [[ "$DO_MERGE_DUPS" -eq 1 ]]; then
    echo "步骤 3/4  合并近重复实体 (wiki_optimizer merge-dups)..."
    if [[ "$DRY_RUN" -eq 1 ]]; then
        echo "  [dry-run] python3 $WIKI_OPTIMIZER merge-dups --dry-run"
    else
        # 先预览，再确认
        python3 "$WIKI_OPTIMIZER" merge-dups --dry-run
        echo ""
        read -rp "  确认执行合并？[y/N] " confirm
        if [[ "$confirm" =~ ^[Yy]$ ]]; then
            python3 "$WIKI_OPTIMIZER" merge-dups
        else
            echo "  已跳过合并"
        fi
    fi
    echo ""
else
    echo "步骤 3/4  合并近重复 — 已跳过（用 --merge-dups 开启）"
    echo ""
fi

# ── 步骤 4（可选）：压缩超长实体 ─────────────────────────────────────────────

if [[ "$DO_TRIM" -eq 1 ]]; then
    echo "步骤 4a/4  预览超长实体 (wiki_optimizer trim --dry-run)..."
    python3 "$WIKI_OPTIMIZER" trim --dry-run
    echo ""
    if [[ "$DRY_RUN" -eq 0 ]]; then
        read -rp "  确认压缩？[y/N] " confirm
        if [[ "$confirm" =~ ^[Yy]$ ]]; then
            echo "步骤 4b/4  压缩超长实体..."
            python3 "$WIKI_OPTIMIZER" trim
        else
            echo "  已跳过压缩"
        fi
    fi
    echo ""
else
    echo "步骤 4/4  压缩超长实体 — 已跳过（用 --trim 开启）"
    echo ""
fi

# ── 步骤 5（可选）：知识社区摘要 ─────────────────────────────────────────────
# 注意：这一步会调用 LLM，产生 token 消耗，耗时较长（数分钟）

if [[ "$DO_COMMUNITY" -eq 1 ]]; then
    echo "步骤 5/4  生成知识社区摘要（调用 LLM）..."
    if [[ "$DRY_RUN" -eq 1 ]]; then
        echo "  [dry-run] python3 $WIKI_RETRIEVAL --build-community"
    else
        python3 "$WIKI_RETRIEVAL" --build-community
    fi
    echo ""
else
    echo "注: 知识社区摘要 — 已跳过（用 --community 开启，会调用 LLM）"
    echo ""
fi

echo "=== 完成 $(date '+%H:%M:%S') ==="
echo ""
echo "后续工作流："
echo "  node scripts/wiki_search.mjs search \"关键词\" 8"
echo "  node scripts/wiki_pack.mjs --out tmp/context.md \"主题\""
