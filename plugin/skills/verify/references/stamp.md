# The verify stamp

Depth for step 10 of `compost:verify`. The stamp is the record `compost:finish` and the verify gate read
instead of anyone's memory of the run, so it says exactly what was proven.

```bash
uv run ${CLAUDE_PLUGIN_ROOT}/scripts/stamp.py write --json \
  '{"gates": "4/4", "ac": "7/7", "mutants": "41/45", "rung": "e2e"}'
```

Fields:

- `gates`: gates green / gates run.
- `ac`: criteria met / total. A criterion whose check is `unreachable` or `could_not_boot` (see
  [the proof ladder](proof-ladder.md#when-a-check-cant-run)) is not met, and the field names it:
  `"6/7, 1 unreachable"`, `"5/7, 1 unreachable, 1 could_not_boot"`.
- `mutants`: killed / run, or `null` when no mutation tool is recorded.
- `rung`: step 7's rung.

`stamp.py write` stamps HEAD (or `--rev`) as a note under `refs/notes/compost-verify`; `stamp.py show <rev>`
and `stamp.py log <range>` read stamps.

## "Done" with a check that couldn't run

Verify says "done", and stamps, when every gate is green and every criterion is either met or
`unreachable` / `could_not_boot` with its question or evidence already put to the user (unattended:
posted as a ruling and listed under Risk). Those rows never go back to `compost:build`; the user's
answer decides what happens to them. Any other unmet criterion means no stamp and no "done".
