# The proof ladder and silent checks

Depth for steps 7 and 8 of `compost:verify`.

## One fact, five rungs

Take the change from `compost:build`'s worked example: `authorize` drops its 60-second grace
period, so a token is refused at its expiry instant. The tests prove `authorize` does that. The
change is only safe because of a fact outside `authorize`:

> Clients never present a token within seconds of its expiry, because the issuer hands out tokens
> that live an hour and clients refresh them five minutes early.

That fact moves down the ladder like this:

1. **Asserted.** "Clients refresh early." A sentence, which reads the same whether it is true or not.
2. **Cited.** `issuer.py:31` sets `expires_in=timedelta(hours=1)`; the client SDK's
   `session.py:88` refreshes when `expires_at - now < timedelta(minutes=5)`. Cite the SDK at the
   version the clients actually pin, not the latest release.
3. **Walked.** Follow a request whose token is 4 minutes from expiry: the SDK refreshes before
   sending, so the server sees a token with 60 minutes left. Then look for the case the walk
   misses: a client whose clock runs 6 minutes slow refreshes too late. Clock skew is where grep
   stops.
4. **Ran.** A script that imports the real issuer and the real SDK, freezes the client's clock 6
   minutes behind the server's, makes a request, and asserts that the SDK refreshed first. If it
   fails, the fact is false and the grace period was covering for skew. The change then needs a
   decision, not a merge.
5. **Reproduced live.** Start the app with the bundled `/run`, log in, shift the client clock,
   and watch the request log for a refresh followed by a 200. With telemetry recorded in
   `docs/agents/observability.md`, query that request's trace instead: the refresh span comes
   before the request span, and the request span's status is 200.

Stop at the cheapest rung that settles the fact, and report where you stopped. Below rung 4, the
fact is unproven. Say so in the report and in the PR's Risk section.

## When a check can't run

Some checks never get a verdict on the code, wherever verify runs them: an AC-N's test (step 5),
the app an e2e test needs (step 6), or a rung of this ladder (step 7). Two outcomes say why, and
neither is `failed`: *failed*
says the code is wrong, and these say the check never reached it. Neither goes back to
`compost:build`, and neither gets a fix loop.

- **`unreachable`**: the check's precondition is a state the code never creates. A test needs a
  null the only caller rejects, or a flow starts from a row nothing writes. Don't build a harness to
  force the state. Name the branch the check was covering and put it to the user as a question:
  delete it, or say what reaches it. Unattended, post it as a ruling and list it under Risk. If every
  check for what the issue asked for passed, the change is verified.
- **`could_not_boot`**: the app, or a service the check needs, won't start: a missing credential,
  env var, or database. No code change repairs a credential. Record the evidence (the command and
  its error), mark the check unverified, and report it as such; it counts below rung 4, so the fact
  it was proving is unproven.

A test skipped by a `skip`, `skipif` or `xfail` written into it is not either of these: it stays
unmet, as step 5 says. A test that ran and failed because the app or a service it needs would not
start is `could_not_boot`.

A check that only ran out of ideas (the state exists but you found no way in) is never
`unreachable`. Give it one more attempt with a sharper brief: what you tried, and where the state is
written. If that fails too, report it as unproven with both attempts, the same way as
`could_not_boot`; never a third try. `unreachable` needs
evidence that nothing creates the state: the callers or writers you searched, each at a `file:line`.

## Where grep stops

A symbol search finds callers. It does not find:

- the library's own behavior at the version in the lockfile, or a local patch to it
- data shapes crossing a process boundary: JSON from an API, a database column, a queue message,
  a file another program reads
- a feature flag or config value that selects the old path at runtime
- code reaching the symbol by string: `getattr`, entry points, templates, serializers
- timing: teardown order, retries, clock skew, a cache that outlives a deploy

## Silent checks

Each of these passes without doing the work you think it does. Next to each is the proof that it
ran.

| Check | How it passes silently | Proof it ran |
|---|---|---|
| `pytest -k <expr>` | The expression matches nothing: exit code 5, and the summary says only "8 deselected" | The collected count in the summary is the number you expect |
| pytest overall | Tests skipped by a missing optional dependency or a `skipif` | `-rs` lists skips; count them against the AC table |
| `go test` | A package prints `[no test files]`, or `-run <regex>` matches nothing and prints `ok ... [no tests to run]` | `-v` lists a `--- PASS` line for each test the AC table names |
| `cargo test` | A filter matches nothing: `running 0 tests` and `test result: ok` | The `running N tests` count and the named tests in the output |
| vitest, jest | `No test files found` (vitest exits 1, jest with `--passWithNoTests` exits 0), or `.skip`/`.only` left in a file | The summary's test count, and no `skipped` beyond the ones you expect |
| coverage | `source` names the wrong package, or the installed copy is measured instead of `src/` | The report lists the files the diff touched |
| ruff, mypy, ty | An `exclude` or `include` setting leaves the changed path out | `ruff check --show-files` or the checker's file count includes the changed files |
| pre-commit hook | Its `files:` pattern misses the changed files and it reports "Skipped" | The hook's line shows "Passed", not "(no files to check)Skipped" |
| a shell pipeline | `cmd \| grep x` exits with the status of `grep` | `set -o pipefail`, or check `cmd`'s own exit code |
| a hook or CI step | It never triggered for this path or event | Its own log line for this run |
| a telemetry query | It returns an earlier run's data, or nothing because the pipeline is down, read as "no errors" | The query is scoped to this run's trace id or start time, and returns the span you expected |
| editing then re-running Python | An edit of the same size in the same second can leave stale bytecode running | `PYTHONDONTWRITEBYTECODE=1`, or clear `__pycache__` between runs |

When nothing on this list fits, plant a defect: break the line the check protects, run the
check, see it fail, and restore the line. One red run proves the check can see the failure.
