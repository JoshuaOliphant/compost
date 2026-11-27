---
name: verify
description: Proves a change works from fresh evidence before anyone says it does. Use before claiming done, fixed, or passing, before a commit or PR, and when the user asks "is this ready", "verify this", "prove it works", "are the acceptance criteria met", "check coverage", "run mutation testing", "would the tests catch this", or "what could this break".
---

# Verify

A claim that work is done is worth only the evidence behind it, and the evidence has to come from
this tree, run now. A remembered green run, a subagent's "all tests pass", or "it should work"
is not evidence. This skill produces the evidence: the gates run fresh, every acceptance
criterion tied to a passing test, and the one fact the change's safety rests on proven by running
code. Read [prove it works](../../canon/prove-it-works.md) for the principle behind every step.

The repo keeps the mechanical part of that proof as one verify command, so the next session reruns
every check instead of redoing it by hand, and a closed issue's criteria stay checked after it
closes. This skill builds that command when it is missing, runs it, extends it, and does what no
command can: judge whether it ran what changed, and prove the fact the change is safe because of.

## Steps

1. **Find the gates.** Read the gates `compost:setup` recorded in `docs/agents/testing.md`: the
   test command, the coverage threshold and any recorded exclusions, linters, and type checkers.
   If the file is missing, run `compost:setup` now, then continue. Until it exists, the
   project's CI workflow defines green: what `.github/workflows/*` runs, plus any `pre-commit`,
   `Makefile` or `justfile` check target. Read `docs/agents/observability.md` too; if it is
   missing, run `compost:setup`'s observability step now, which records none when the repo has
   nothing running to observe and commits the file. Read the E2E entry in `testing.md` and whether
   the parent issue has a `## Frontend` section; step 6 needs both.

   Then find the verify command `testing.md` names. When it names none, build one before running
   anything, by [the verify command](references/verify-command.md): a `scripts/verify` or task-runner
   target that runs every gate in order, fails when a gate measures nothing, and checks every
   issue's AC table against this run.

   Record it in `testing.md` as the gate and commit both.

   A branch must not judge itself with checks it rewrote: read the gates at the base too
   (`git show <base>:docs/agents/testing.md`, likewise the threshold, verify command and CI
   config). A gate the branch dropped or loosened still runs in step 2 at base strength. List the
   branch's edits to its checks:

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gate_drift.py <base> HEAD
   ```

   It lists each gate change as JSON (exit 1 when any): a changed gate file, an added weakener,
   or a removed test. Rule on each: why the check changed and why that is sound. Unattended
   (implement, a worker), post them as one ruling comment and continue; `compost:finish` lists
   them under Risk.

2. **Run the verify command, and any gate it leaves out, fresh.** Run them in this worktree now. After a gate change, run the base's gates on this tree too;
   one failing fails the run, and only the user can accept that. Read each exit code and the whole output. Stop at the first
   failure and read its log before touching anything else: the first failing log carries the
   information, and later failures are often its echoes. An e2e test is the exception: it gets one
   rerun, as step 6 says. A failing test outside the change gets
   run on the base SHA first. Red there, it is pre-existing: file an issue, fix it in its own `fix:` commit
   only if it blocks a gate, and post a ruling. Green there, the change broke it: fix it if the
   cause is plain; otherwise hand it to `compost:diagnose`. A warning the gate prints is a finding too: fix it, or say why it stays.
   A flaky test is never skipped, slept past, or retried until green: fix its cause, or delete it in a ruling.
   When a subagent did the work, read `git diff` yourself rather than trusting its report.

3. **Hold the coverage gate.** The gate is 100% line coverage, measured with the stack's own tool
   as `docs/agents/testing.md` records it: for example
   `uv run pytest --cov --cov-report=term-missing --cov-fail-under=100`, `go test -coverprofile`,
   `vitest --coverage`, `cargo llvm-cov`, or JaCoCo (`./gradlew jacocoTestReport`, `mvn jacoco:report`). Ask Jev first: hand `test-value` the missing lines
   ([jev](references/jev.md)), as a coverage.py JSON report (`--cov-report=json`) for Python or as
   `{file, lines}` read from the other tool's report.
   Blocks in `exclude` are the proposed exclusions for the third case below; the rest need a
   test. Exit 3 means Jev is unavailable: sort them yourself. For each missing line:
   - It is behavior: go back to `compost:build` and fit a test in.
   - It is dead: delete it.
   - Covering it would take a test that proves nothing (asserting a constant, re-testing the
     framework, a `__main__` guard): stop and bring the user the file and line numbers, with a
     proposed exclusion in the stack's own form (`exclude_also` or `pragma: no cover` for
     coverage.py, `/* c8 ignore next */` or `/* istanbul ignore next */` for JS, JaCoCo `excludes`,
     `--ignore-filename-regex` for `cargo llvm-cov`; Go has no pragma, so filter the profile and
     record the pattern in `testing.md`) or a lower threshold. Do not pad the suite to reach the number. When running
     unattended, under `compost:implement`, or as a worker, post the proposal as a ruling comment
     on the issue, list it in the PR's Risk section, and continue; the user decides at
     `compost:finish`.

4. **Kill the diff's mutants.** When `docs/agents/testing.md` records a mutation tool, run its
   command over the lines this branch changed ([mutation testing](references/mutation.md)). A
   line that runs is not a line a test checks: each surviving mutant is a change to the code that
   no test noticed. Sort every survivor:
   - Unprotected behavior: go back to `compost:build` and fit a case in.
   - Equivalent, so no input can tell the mutant apart: say why in the report.
   - In a recorded exclusion: leave it. A new exclusion is proposed exactly like a coverage one,
     and the same unattended rule applies.

   A timeout is sorted the same way. There is no score to reach; a survivor left unsorted fails the
   step, and so does a run that mutated nothing on lines the tool covers. With a tool that edits
   files in place, run `git diff` after the run and restore any mutant an interrupted run left
   behind. Lines the tool does not cover, outside its recorded paths or in
   another language, have only `compost:build`'s walk by hand: name them in the report. With no
   tool recorded, skip this step for the same reason. Where a tool is recorded, check that the walk
   did its job on those lines: it must have mutated every line the diff adds, including wiring
   (args passed, stdout/stderr hookups, which signal is sent), not only the branch logic. A mutant
   that fails to build is not a kill; it must have been rewritten so it compiles. Walk any line it
   skipped yourself.

5. **Map every acceptance criterion to a passing test.** Build a table from this run's results:
   AC-N, the test's node id, and pass or fail. Find the tests in the AC table
   `compost:build` posted on the issue (AC-N to node id); it is the only one, so edit it, never
   post a second. A criterion with no test is unmet, with no judgment call. So is one
   whose test was skipped, deselected, or marked xfail in this run, because a test that did not
   run proves nothing; one that can't run is `unreachable` or `could_not_boot`
   ([proof ladder](references/proof-ladder.md)), never sent to build. A passing test can still miss its criterion, so ask Jev whether each
   test asserts its Then: run `ac-exercised` with the table ([jev](references/jev.md)) and read
   every criterion in `to_read` against its test. One whose test never checks the Then is unmet.
   Exit 3, or a suite in a language Jev's test tools do not read (any but Python, JS/TS, Go,
   Rust, Java, and Kotlin): say so in one line and read each test's assertions against its Then
   yourself. Under a parent with a Frontend section, or for an undeclared frontend change (step
   6), a user-visible AC-N needs a passing e2e test that drives the running app; one mapped only
   to a unit test is unmet, and verify fails naming the AC-N.

   A green command proves only what it checks. When no line of its output covers an AC-N, extend
   the repo before claiming anything: a test first (load `compost:build` to fit it in), and a new
   check in the command only for what a test can't say. Then run the command again.

   When this issue replaces an earlier issue's behaviour on purpose and removes or rewrites the
   test its AC table names, retire that row instead of weakening the command: set its test cell to
   `superseded by #N`, with N this issue, refresh the cache if the command keeps one, and post a
   ruling on this issue naming the retired row.
   The row edit and the ruling are the record; a row that just disappears, or a check that stops
   reading closed issues, is not. As a `compost:implement` worker, put the retirement in your
   report instead of editing the other issue's table: two lanes editing one comment lose one of
   the edits, so the orchestrator applies retirements after it lands each lane.

6. **Prove frontend work in the running app.** When the parent has a Frontend section, or the diff
   changes UI files when it has none, follow [frontend](references/frontend.md): start the app from
   the E2E entry; rerun a failing e2e test once (a pass is flaky: list it under Risk and file an
   issue; a second failure fails verify, naming the test); screenshot each changed screen and state
   what it shows against its AC-N; run the pixel comparison only against baselines that already
   exist, never creating one; push the screenshots to `screenshots/<feature branch>`. UI files
   under a parent with no Frontend section are an undeclared frontend change: report it, apply this
   step and step 5's e2e rule anyway, and post the finding as a ruling when unattended.

7. **Prove the one fact the change is safe because of.** Most changes that look risky are safe
   because of one fact, such as "this call only evicts entries that are already expired". Name
   it, then push it as far down this ladder as is cheap:
   1. Asserted: you said so. Worth nothing on its own.
   2. Cited: you pointed at the `file:line`, in this repo or in the library's source at the pinned
      version, with the line read from that file alone (`cat -n a b c` numbers across files).
   3. Walked: you traced the bad case step by step and showed it cannot happen.
   4. Ran: a script or test calls the real code and fails loudly if the fact is false.
   5. Reproduced live: the running app shows it. Run the `## Run` smoke command from
      `docs/agents/testing.md` (at the changed path, if it takes one); use the bundled `/run`
      only when `## Run` is missing or `none`. The bundled `/verify` is the user's to run;
      suggest it when they want to see it themselves.

   Report the `## Run` feature-map rows the change touches, each with its result.

   When `docs/agents/observability.md` records a stack and the change runs at runtime, reach the
   last rung through it: exercise the changed path once, then query for its span, log, or metric
   carrying the values the fact depends on ([read the running system](../../canon/read-the-running-system.md)).
   An empty result means the path did not run or the pipeline is down; find out which before
   claiming anything.

   Look where grep stops: the library's own source, JSON a service returns, a database column, a
   feature flag, another program reading the same bytes. Report the rung you reached. Below
   "ran", call the fact unproven. See [the proof ladder](references/proof-ladder.md) for examples.
   When the fact is a performance claim, run
   [the benchmark checklist](../diagnose/references/benchmarks.md) and report its verdict.

8. **Make silent checks prove they ran.** A check that prints nothing when it fails looks the
   same as one that never ran. Before counting it as a pass, show it did work: the number of
   tests collected, the number of files linted, or one run where it caught a planted defect.
   Common cases, such as a runner collecting nothing (pytest's `collected 0 items`, Go's
   `[no test files]`) or coverage measuring the wrong package, are
   in [the proof ladder](references/proof-ladder.md).

9. **Check the comments in the diff.** For Python, run [jev-lint](references/jev-lint.md) over
   the branch first; it reads only Python, so for other languages say so in one line and go
   straight to the manual pass. If it exits 3 (no key), say so and do the manual pass. Either way, read every
   comment the diff adds. Keep only:
   - legal or license headers
   - behavior forced by an external dependency, platform, or protocol we cannot reshape
   - a lint suppression whose rule is wrong for that line (a suppression hiding a correctness or
     safety rule means the code needs fixing, not the suppression)
   - doc comments that define a public API contract
   - issue or RFC links for a constraint the code cannot express

   Delete the rest: narration, banners, commented-out code, workaround explanations, and history
   ("changed from X"). A comment explaining a surprise in our own code means the code needs a
   better name, an extracted function, or a type. Change the code and drop the comment.

10. **Report the evidence.** Give the commands and their counts (`214 passed, 0 failed`), the
    coverage result and any proposed exclusion, the mutants run, killed, and sorted as equivalent
    or excluded, the AC table, the Screenshots list (AC-N, raw URL on the screenshots branch, one
    line of what it shows), the Flaky list (each e2e test that passed on rerun, with its filed issue
    id), the safety fact with its rung and the proof output (the telemetry query and what it
    returned, when a stack is recorded), and the comments removed. Post the AC table on the issue in the shape the verify command checks, so
    every later run checks it too, by editing the AC-table comment already on the issue (the one
    `compost:build` posted, or yours from an earlier run) instead of adding another. Before saying "done", ask
    Jev whether the output you captured backs each claim: run `claim-backed` with every claim
    and its command's output ([jev](references/jev.md)), and fix or drop each one in `unbacked`.
    Exit 3: reread each output against its claim yourself. Say "done" only
    when every row is met and every gate is green. Otherwise state the actual status.
    When you say "done", and never otherwise, stamp the commit you verified for `compost:finish`
    and the verify gate:

    ```bash
    uv run ${CLAUDE_PLUGIN_ROOT}/scripts/stamp.py write --json \
      '{"gates": "4/4", "ac": "7/7", "mutants": "41/45", "rung": "e2e"}'
    ```

    Fields: gates green/run, AC met/total, mutants killed/run (or `null`),
    step 7's rung. It stamps HEAD (or `--rev`) as a note under `refs/notes/compost-verify`;
    `stamp.py show <rev>` and `log <range>` read stamps.

## Next moves

- `compost:review` when every gate is green and every AC is met.
- `compost:build` when an AC is unmet, or a coverage gap or a surviving mutant is real behavior.
- `compost:diagnose` when a gate fails and the cause is not plain.
- `compost:finish` when review findings are addressed and this run is on the final commit.
