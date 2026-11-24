#!/bin/bash
# ABOUTME: Has Jev's stop-guard judge every turn end of one phase of one arm, then prints count.py's report for it.
# ABOUTME: usage: classify.sh <transcripts dir> <phase>; both arms are judged by this checkout's jev.py.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
JEV=$HERE/../../plugin/scripts/jev.py
DIR=$1
PHASE=$2
FILES=("$DIR"/[0-9][0-9]-"$PHASE".jsonl)
VERDICTS=$DIR/verdicts-$PHASE.jsonl
: > "$VERDICTS"
python3 "$HERE/count.py" payloads "${FILES[@]}" | while IFS= read -r payload; do
  echo "$payload" | uv run --quiet "$JEV" stop-guard | jq -c . >> "$VERDICTS"
done
python3 "$HERE/count.py" report --verdicts "$VERDICTS" "${FILES[@]}"
