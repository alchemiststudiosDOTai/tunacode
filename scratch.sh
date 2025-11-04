#!/usr/bin/env bash
# thought-ledger.sh — one-file, multi-agent Markdown thought ledger
# Dependencies: bash, flock, grep, sed, awk, date, printf

set -euo pipefail

# -------- Config --------
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
[[ -f "${REPO_ROOT}/.llm-tools.conf" ]] && source "${REPO_ROOT}/.llm-tools.conf" || true

CLAUDE_DIR="${CLAUDE_DIR:-${HOME:-${REPO_ROOT}}/.claude}"
LEDGER_DIR="${LEDGER_DIR:-${CLAUDE_DIR}/scratchpad}"
LEDGER_FILE="${LEDGER_FILE:-${LEDGER_DIR}/ledger.md}"

EDITOR_DEFAULTS=("$(command -v "$EDITOR" 2>/dev/null || true)" \
                 "$(command -v vim 2>/dev/null || true)" \
                 "$(command -v nano 2>/dev/null || true)" \
                 "$(command -v vi 2>/dev/null || true)")
PAGER_DEFAULTS=("$(command -v "$PAGER" 2>/dev/null || true)" \
                "$(command -v less 2>/dev/null || true)" \
                "$(command -v more 2>/dev/null || true)" \
                "cat")

# Colors (respect NO_COLOR or non-tty)
if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  C_Y="\033[1;33m"; C_G="\033[0;32m"; C_R="\033[0;31m"; C_B="\033[0;34m"; C_N="\033[0m"
else
  C_Y=""; C_G=""; C_R=""; C_B=""; C_N=""
fi

die() { printf "%bERROR:%b %s\n" "$C_R" "$C_N" "$*" >&2; exit 1; }
note() { printf "%b[%s]%b %s\n" "$C_B" "$(date +%H:%M:%S)" "$C_N" "$*"; }

ensure_ledger() {
  mkdir -p "${LEDGER_DIR}"
  if [[ ! -f "${LEDGER_FILE}" ]]; then
    {
      printf "# Thought Ledger\n\n"
      printf "> One shared Markdown file for multi-agent notes and working memory.\n\n"
      printf "---\n\n"
    } > "${LEDGER_FILE}"
    note "Created ledger at ${LEDGER_FILE}"
  fi
}

pick_cmd() {
  # pick first non-empty, executable
  local cmd
  for cmd in "$@"; do
    [[ -n "${cmd}" && -x "${cmd}" ]] && { echo "${cmd}"; return 0; }
  done
  echo ""  # none found
}

now_iso() { date +"%Y-%m-%d %H:%M:%S %z"; }
ts_id()   { date +"%Y%m%d-%H%M%S"; }

append_entry() {
  local agent="${1:-${CLAUDE_AGENT_ID:-unknown}}"; shift || true
  local topic="${1:-general}"; shift || true
  local tags_csv="${1:-}"; shift || true
  local content="${1:-}"

  # If no inline content, read from STDIN
  if [[ -z "${content}" ]]; then
    if [[ -t 0 ]]; then
      note "Enter content, end with Ctrl-D:"
    fi
    content="$(cat)"
  fi
  [[ -z "${content//[[:space:]]/}" ]] && die "Empty content."

  local id; id="$(ts_id)"
  local tstamp; tstamp="$(now_iso)"
  local tags_md=""
  if [[ -n "${tags_csv}" ]]; then
    # normalize tags -> [tag1, tag2]
    local norm; norm="$(echo "${tags_csv}" | tr ' ' '_' | sed 's/, */, /g')"
    tags_md="**Tags:** [${norm}]  "
  fi

  ensure_ledger

  # Atomic append with flock
  {
    flock -w 5 200 || die "Could not lock ledger for writing."
    {
      printf "## %s — %s\n" "${tstamp}" "${topic}"
      printf "**Agent:** %s  " "${agent}"
      [[ -n "${tags_md}" ]] && printf "%s" "${tags_md}"
      printf "\n\n"
      printf "%s\n\n" "${content}"
      printf "---\n\n"
    } >> "${LEDGER_FILE}"
  } 200>>"${LEDGER_FILE}"

  printf "%b✓ Appended entry id=%s%b\n" "$C_G" "$id" "$C_N"
}

cmd_add() {
  # usage: add --agent A --topic T --tags "x,y" [--] [content or stdin]
  local agent="${CLAUDE_AGENT_ID:-unknown}" topic="general" tags=""
  local content=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --agent) agent="${2:-}"; shift 2 ;;
      --topic) topic="${2:-}"; shift 2 ;;
      --tags)  tags="${2:-}"; shift 2 ;;
      --) shift; content="${*:-}"; break ;;
      *) content="${*:-}"; break ;;
    esac
  done
  append_entry "${agent}" "${topic}" "${tags}" "${content}"
}

cmd_tail() {
  local n="${1:-20}"
  ensure_ledger
  pick_cmd "${PAGER_DEFAULTS[@]}" >/dev/null
  local pager; pager="$(pick_cmd "${PAGER_DEFAULTS[@]}")"
  awk '1' "${LEDGER_FILE}" | tail -n "${n}" | ${pager:-cat}
}

cmd_view() {
  ensure_ledger
  local pager; pager="$(pick_cmd "${PAGER_DEFAULTS[@]}")"
  ${pager:-cat} "${LEDGER_FILE}"
}

cmd_edit() {
  ensure_ledger
  local ed; ed="$(pick_cmd "${EDITOR_DEFAULTS[@]}")"
  [[ -z "${ed}" ]] && die "No editor found (tried \$EDITOR, vim, nano, vi)."
  "${ed}" "${LEDGER_FILE}"
}

cmd_search() {
  local q="${1:-}"; shift || true
  [[ -z "${q}" ]] && die "search requires a term"
  ensure_ledger
  # Show matching headers and 4 lines of context
  if grep -Hn --color=never -i -q -- "${q}" "${LEDGER_FILE}"; then
    grep -Hn -i -- "${q}" "${LEDGER_FILE}" | sed 's/^/match: /'
    printf "\n"
    awk -v IGNORECASE=1 -v q="${q}" '
      /^## /{hdr=$0; next}
      { if (index(tolower($0), tolower(q))) { print "-----"; print hdr; print $0; cnt=3; while (cnt-- && getline) print; print "-----" } }
    ' "${LEDGER_FILE}" | sed 's/^/  /'
  else
    note "No matches."
  fi
}

cmd_list() {
  # list just the headers (entries)
  ensure_ledger
  nl -ba "${LEDGER_FILE}" | sed -n 's/^\s*\([0-9]\+\)\s*## \(.*\)$/\1  \2/p'
}

cmd_since() {
  # show entries since a timestamp string matched in headers
  local since="${1:-}"; [[ -z "${since}" ]] && die "since requires a timestamp substring (e.g., 2025-11-04)"
  ensure_ledger
  awk -v s="${since}" '
    BEGIN{print "---- since:", s}
    /^## /{print_it=(index($0,s)>0)||print_it}
    {if(print_it) print}
  ' "${LEDGER_FILE}"
}

cmd_compact() {
  # remove consecutive blank lines > 2 and trim trailing spaces
  ensure_ledger
  tmp="$(mktemp)"
  sed -E 's/[[:space:]]+$//; /^$/ {N;/^\n$/ {N;/^\n\n$/! {P;D}}; }; P; D' "${LEDGER_FILE}" 2>/dev/null || cat "${LEDGER_FILE}" > "${tmp}"
  mv "${tmp}" "${LEDGER_FILE}"
  printf "%b✓ Compacted ledger%b\n" "$C_G" "$C_N"
}

usage() {
  cat <<EOF
thought-ledger.sh — one-file, multi-agent Markdown scratchpad

USAGE:
  $(basename "$0") add [--agent NAME] [--topic TOPIC] [--tags "t1,t2"] [--] [content | read from stdin]
  $(basename "$0") view                # open entire ledger in \$PAGER
  $(basename "$0") tail [N]            # show last N lines (default 20)
  $(basename "$0") list                # list entry headers (line no + title)
  $(basename "$0") search TERM         # grep with small context
  $(basename "$0") since "YYYY-MM-DD"  # show entries since matching timestamp text
  $(basename "$0") edit                # open ledger in \$EDITOR
  $(basename "$0") compact             # tidy spacing

ENV:
  CLAUDE_DIR     (default: \$HOME/.claude)
  LEDGER_DIR     (default: \$CLAUDE_DIR/scratchpad)
  LEDGER_FILE    (default: \$LEDGER_DIR/ledger.md)
  CLAUDE_AGENT_ID  agent name for --agent default
  EDITOR, PAGER

EXAMPLES:
  echo "Investigating 500s in auth." | $(basename "$0") add --agent fabian --topic "auth-500" --tags "debug,api"
  $(basename "$0") add --agent bot-1 --topic "plan" -- "Ship hotfix then write tests"
  $(basename "$0") search auth-500
EOF
}

main() {
  local cmd="${1:-}"; shift || true
  case "${cmd}" in
    add)      cmd_add "$@" ;;
    view)     cmd_view ;;
    tail)     cmd_tail "${1:-}" ;;
    list)     cmd_list ;;
    search)   cmd_search "${1:-}" ;;
    since)    cmd_since "${1:-}" ;;
    edit)     cmd_edit ;;
    compact)  cmd_compact ;;
    ""|-h|--help|help) usage ;;
    *) die "unknown command: ${cmd}";;
  esac
}

ensure_ledger
main "$@"
