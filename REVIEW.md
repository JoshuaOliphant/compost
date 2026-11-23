# Review guide

How code review judges changes in this repo. compost's review reads it on every run.

## Failure

A change that breaks behaviour, loses or leaks data, or blocks a rollback.

## Minor cap

5

## Skip

Generated, vendored, and lock files, and anything a configured linter or formatter enforces.

## Evidence

Every behaviour claim cites a file:line, not an inference from naming.

## Checks

- **transcript-untyped-entries**: Trigger: the diff changes code that reads Claude Code transcript entries (a `.jsonl` under `~/.claude/projects`, or a hook's `transcript_path`). Check: does it skip user entries nobody typed, as `stop_guard.py` does with the flags in `UNTYPED` (skill bodies, compaction summaries, sidechains) and with tool results and injected tags? Source: `UNTYPED` in `plugin/scripts/stop_guard.py`; JoshuaOliphant/claude-plugins#206, where the stop guard took entries nobody typed for the user's messages.
- **gh-origin-not-fork**: Trigger: the diff adds a `gh` call, or a new reader of `docs/agents/issue-tracker.md`, in a skill, agent, workflow, or script. Check: does it run the fork check in `plugin/skills/setup/references/issue-tracker-github.md` (or set `GH_REPO`) first, so `{owner}/{repo}` is origin and not a fork's upstream? Source: OLI-31 (54485d4, 9e9ad8e, 7ccb2e9), issues read and filed on a fork's upstream parent.
- **hook-reexec-before-stdin**: Trigger: the diff changes the imports or start-up path of a hook script in `plugin/scripts/` (`stop_guard.py`, or anything `needs_uv.py` guards). Check: does the re-exec under uv still happen before the script reads the hook's stdin? Source: OLI-78 review round 1 (3390165), where a deferred import let the re-exec'd stop guard read empty input and allow every stop.
- **markdown-code-fences**: Trigger: the diff changes code that reads Markdown line by line for headings, ids, or sections (the spec placement or `REVIEW.md` checks in `plugin/workflows/review-changes.js`, `doc_refs.py`). Check: are lines inside ``` and ~~~ fences left out as CommonMark does, so a `# ` comment or sample output in a fence is never read as structure? Source: OLI-71 (d0955ea, cf812ab).
