# Interruptions on one sample run (OLI-128)

The question: does the run contract (OLI-117) change how often a compost run waits on the user
between the posted spec and the PR body? One run per arm, n=1, so the numbers below are counts and
not rates.

## Setup

- **Arms:** before is compost 0.48.0 (`e34d7ab`). After is the `oli-117-run-contract` branch
  (`6f17c14`, 0.49.0). Each arm ran alone through `--plugin-dir`, with both installed compost
  entries turned off, `--setting-sources project,local` (so no user plugins or hooks), an empty
  strict MCP config, `--model claude-sonnet-5-5`, `--permission-mode auto`, and
  `--permission-prompts none`. The init events list only the plugin under test, and every
  `Base directory for this skill:` line points into that arm's checkout.
- **Sample:** `sample/` is a static two-page notes app with one Playwright test, copied into a
  fresh local repo for each arm, with no remote. Prerequisites were checked before the runs: node
  26.7, Playwright 1.65.1, and Chromium headless shell v1255. The existing test passed.
- **Driver:** `drive.sh` sends three prompts, each in a fresh session:
  `/compost:setup` (local tracker, never push), `/compost:spec On the settings page, add an Export
  button that downloads the current settings as settings.json.`, and `/compost:implement the spec
  in .scratch/`. Until a phase's file check passes, it resumes every stop with "I'm away; decide it
  yourself and continue." The caps are 3 resumes each for setup and spec, 8 for implement, and 150
  minutes per arm. The implement check is a `## Goal` and a `## Validation` heading in
  `.scratch/`: finish's PR body posted on an issue file.
- **Counting:** `classify.sh` sends every turn end to the after checkout's
  `jev.py stop-guard`. `count.py` counts a turn end as a wait when `waits >= 0.5`, and the wait
  names a Stop when `allowed >= 0.5`. For after/implement, the stops are the spec's Run contract
  Stops. For every other arm and phase they are `[]`, which leaves Jev the fixed allowed list.
  Permissions are counted as denials, not prompts, because a headless run has no prompts (the ruling
  is on OLI-128). Per-phase reports are in `results/<arm>-<phase>.json`.

## Results

| | before (0.48.0) | after (0.49.0) |
|---|---|---|
| implement: turn ends | 11 | 10 |
| implement: waits on the user | 8 | 5 |
| implement: waits naming a Stop | 8 | 5 |
| implement: permission denials | 0 | 0 |
| implement: resumes | 8 (cap) | 8 (cap) |
| implement: first wait already at the merge stop | yes | yes |
| reached the PR body | no | no |
| setup + spec: waits on the user | 1 + 1 | 1 + 1 |
| stop-guard blocks (all sessions) | 0 | 0 |
| wall clock, setup + spec + implement | 445 s | 344 s |

Turn ends outnumber invocations, because a background review workflow's notification adds a turn
inside one `claude -p` call. Denials are 0 in the on-disk session and subagent transcripts as well.

## Reading

- **AC-22 is not met.** Its first clause fails: neither run reached the PR body. Its second clause
  holds for after: all 5 of its waits named a Stop.
- **Both arms skipped the hand-off.** Both built, tested, and reviewed the feature on an
  `export-settings` branch. Neither loaded `compost:finish`, which implement's step 10 names in
  both versions ("push, and hand off through `compost:finish`"). Instead, both said the only step
  left was merging to main and held there for the remaining resumes. The same step also says
  "Without a PR, report the feature branch by name", and with a local tracker both runs read that as
  the end.
- **The counts don't show a contract effect.** Each arm's first wait was already at the merge stop,
  and every wait after it repeats that stop. 8 against 5 is how many repeated holding messages Jev
  scored as waiting. Every wait named a Stop in both arms. The after spec's Stops only restate
  implement's fixed list (merging, force-push, deploy, deleting data, outside messages), so this
  sample can't separate the contract from the fixed list.
- **The after run never printed a `Run contract stops:` block.** It loaded implement from the
  checkout under test, but neither its stream-json nor its on-disk transcript contains the block
  (case-insensitive search for "contract stops").
  So the guard ran on the fixed list, and the after/implement stops above come from `spec.md`.
- **After's first implement stop asked for review.** It skipped `compost:review` and closed with
  "Say if you want the review run, or the branch merged." Jev scored it as naming a Stop
  (allowed 0.89), on the merge half. It ran review after the resume.
- **Permission denials are 0 in both arms,** a baseline for OLI-119 under auto mode.

## Caveats

- n=1 per arm on one bounded frontend spec, with Sonnet and no user plugins, not the user's
  everyday setup.
- Each wait is one Jev judgment. A single misjudged message moves the count.
- The fixed reply is a user message, so from the first resume on the stop guard treats the run as
  attended in both arms.
