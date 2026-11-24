#!/bin/bash
# ABOUTME: Drives one arm of the interruptions experiment: setup, spec, then implement in a fresh throwaway repo, headless.
# ABOUTME: Every turn that ends before its phase's file check passes is resumed with one fixed reply, up to a cap.
# usage: drive.sh <arm> <plugin dir> <port> <out dir>
set -u
ARM=$1
PLUGIN=$2
PORT=$3
OUT=$4/$ARM
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$OUT/repo
LOG=$OUT/transcripts
DEADLINE=$(( $(date +%s) + 150 * 60 ))
REPLY="I'm away; decide it yourself and continue."
# Installed copies of compost must not load beside the plugin under test; --setting-sources drops the user's
# other plugins and hooks too, and the empty strict MCP config keeps the run away from real trackers and inboxes.
FLAGS=(--model claude-sonnet-5-5 --plugin-dir "$PLUGIN"
  --settings '{"enabledPlugins":{"compost@compost":false,"compost@oliphant-plugins":false}}'
  --setting-sources project,local --strict-mcp-config --mcp-config '{"mcpServers":{}}'
  --permission-mode auto --permission-prompts none --output-format stream-json --verbose)

mkdir -p "$LOG" "$REPO"
cp -R "$HERE/sample/." "$REPO/"
sed -i '' "s/8123/$PORT/g" "$REPO/playwright.config.js" "$REPO/README.md"
(cd "$REPO" && npm ci --silent && git init -q -b main && git add -A && git commit -qm "Initial notes app")

TURN=0
SESSION=""
turn() {
  local phase=$1 prompt=$2 left file resume=()
  left=$(( DEADLINE - $(date +%s) ))
  [ "$left" -le 0 ] && return 1
  TURN=$(( TURN + 1 ))
  file=$LOG/$(printf %02d $TURN)-$phase.jsonl
  [ -n "$SESSION" ] && resume=(--resume "$SESSION")
  (cd "$REPO" && timeout "$left" claude -p "$prompt" ${resume[@]+"${resume[@]}"} "${FLAGS[@]}" > "$file" 2> "$file.err")
  local id
  id=$(jq -r 'select(.type=="result") | .session_id' "$file" | tail -1)
  [ -z "$id" ] && echo "turn $TURN ended with no result event; see $file.err" >> "$LOG/summary.txt" && return 1
  SESSION=$id
  find "$HOME/.claude/projects" -name "$SESSION.jsonl" -exec cp {} "$LOG/session-$SESSION.jsonl" \;
  return 0
}

setup_done() { [ -f "$REPO/docs/agents/issue-tracker.md" ]; }
spec_done() { compgen -G "$REPO/.scratch/*/spec.md" > /dev/null; }
pr_body_posted() { grep -rlq '^## Goal' "$REPO/.scratch" 2> /dev/null && grep -rlq '^## Validation' "$REPO/.scratch"; }

phase() {
  local name=$1 prompt=$2 done_check=$3 cap=$4 resumes=0 start
  start=$(date +%s)
  SESSION=""
  turn "$name" "$prompt" || return
  while ! $done_check && [ "$resumes" -lt "$cap" ] && turn "$name" "$REPLY"; do
    resumes=$(( resumes + 1 ))
  done
  local reached=no
  $done_check && reached=yes
  echo "$name resumes=$resumes reached=$reached secs=$(( $(date +%s) - start ))" >> "$LOG/summary.txt"
}

phase setup "/compost:setup Use the local markdown tracker (.scratch/). This repo has no remote and stays local: never create a GitHub repository or push." setup_done 3
phase spec "/compost:spec On the settings page, add an Export button that downloads the current settings as settings.json." spec_done 3
phase implement "/compost:implement the spec in .scratch/" pr_body_posted 8
echo "finished $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$LOG/summary.txt"
