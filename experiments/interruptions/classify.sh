#!/bin/bash
# ABOUTME: Has Jev's stop-guard judge every turn end of one phase of one arm, then prints count.py's report for it.
# ABOUTME: usage: classify.sh <transcripts dir> <phase> [stops JSON array, replacing the transcript's contract block].
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
JEV=$HERE/../../plugin/scripts/jev.py
DIR=$1
PHASE=$2
STOPS=${3:-}
FILES=("$DIR"/[0-9][0-9]-"$PHASE".jsonl)
VERDICTS=$DIR/verdicts-$PHASE.jsonl
: > "$VERDICTS"
python3 "$HERE/count.py" payloads "${FILES[@]}" | while IFS= read -r payload; do
  [ -n "$STOPS" ] && payload=$(echo "$payload" | jq -c --argjson stops "$STOPS" '.contract_stops = $stops')
  echo "$payload" | uv run --quiet "$JEV" stop-guard | jq -c . >> "$VERDICTS"
done
python3 "$HERE/count.py" report --verdicts "$VERDICTS" "${FILES[@]}" | jq --argjson stops "${STOPS:-null}" '.contract_stops = ($stops // .contract_stops)'
