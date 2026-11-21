# Feedback loops

A feedback loop is one command that goes red on this bug and green once it is fixed. Everything else
in diagnosis consumes it. These are the ways to build one, roughly in order of preference; take the
first that reaches the bug.

## The ladder

1. **Failing test** at whatever seam reaches the bug: unit, integration, end to end. Put it in the
   existing suite next to the tests that cover the same behaviour, using their fixtures.
2. **HTTP script** (`curl` or a short script) against a running dev server.
3. **Telemetry query.** Run the trigger, then query the telemetry `docs/agents/observability.md`
   records for the span, log, or metric that shows the symptom, and assert on it. Reach for it
   when the symptom is internal: a branch taken wrongly, a call that never happened, a retry
   storm, a slow span. Scope the query to this run (a fresh trace id, a timestamp, a unique
   request id) so old data cannot make it pass or fail.
4. **CLI invocation** with a fixture input, diffing stdout against a known-good snapshot.
5. **Headless browser script** (Playwright, Puppeteer) that drives the UI and asserts on DOM,
   console, or network. The bundled `/run` skill knows how to launch most apps.
6. **Replay a captured trace.** Save a real request, payload, or event log to disk and replay it
   through the code path in isolation.
7. **Throwaway harness.** Stand up the smallest subset of the system that reaches the bug (one
   service, stand-ins for the rest) and drive it with one function call.
8. **Property or fuzz loop.** For "sometimes wrong output", run a thousand random inputs and look for
   the failure mode.
9. **Bisection harness.** When the bug appeared between two known states (commits, dataset versions,
   dependency versions), script "set up state X, check, report" and hand it to `git bisect run`.
10. **Differential loop.** Run the same input through the old and new version, or two configs, and
   diff the outputs.
11. **Agent eval.** When the symptom is what a model or agent did (a skill that routed to the wrong
    tool, an agent that misread a ticket), no code path above reaches it. Build the case from the
    incident:
    - Write down the real failure from the transcript: what the user wanted, what the agent did,
      and what followed. Keep what it observably did apart from why you think it did it.
    - Rebuild the setup it decided in (instructions, prior state, the tools it had) before you
      invent anything, and start with the simplest case. Add complexity from the incident (stale
      context, competing work, a delayed result) only when the failure doesn't show without it.
    - Run the real agent, headless (`claude -p` with a clean `CLAUDE_CONFIG_DIR`), and assert on its
      tool calls and output, never on its explanation. A simulated tool may feed it context; it
      never stands in for the agent under test.
    - Report a rate with its denominator ("failed 4 of 5"). One trial is the loop while you iterate;
      the rate over the same N trials, before and after the fix, is the proof. A failure that
      doesn't show in N trials is reported as not observed, never forced.
12. **Human-driven script.** Last resort, when a person has to click. Copy
    [`../scripts/hitl-loop.sh`](../scripts/hitl-loop.sh), edit the steps, and run it: the user follows
    the prompts and their answers come back to you as `KEY=VALUE` lines. The loop stays structured
    even with a human in it.

## Tighten it

Treat the loop as a product. Once you have one, ask:

- **Faster?** Cache setup, skip unrelated initialisation, narrow the test selection.
- **Sharper?** Assert on the specific symptom (the wrong value, the exact message), not "didn't
  crash".
- **More deterministic?** Pin the clock, seed the random generator, isolate the filesystem, freeze
  the network.

A 30-second flaky loop is barely better than none. A 2-second deterministic one finds the bug.

## Non-deterministic bugs

The goal is a higher reproduction rate, not a clean single repro. Loop the trigger a hundred times,
run in parallel, add load, narrow timing windows, inject sleeps at suspected race points. A bug that
fails half the time is debuggable; one that fails one time in a hundred is not yet, so keep raising
the rate.

If the flakiness is in a test rather than the code, look for waits that guess at timing: a fixed
`sleep` before an assertion passes on a fast machine and fails under load. Wait for the condition
itself (poll until the file exists, the event arrives, the row appears, with a timeout that fails
loudly and says what it was waiting for). A fixed delay is right only when the behaviour under test
is itself about time, such as a debounce interval.

## When to stop building

The loop is ready when all four hold and you have run it at least once, showing the invocation and
its output:

- Red-capable: it asserts the user's exact symptom on the real code path.
- Deterministic: same verdict every run, or a pinned high rate for a flaky bug.
- Fast: seconds. An agent eval can't get there, so iterate on single trials and keep the N-trial
  rate for the proof.
- Agent-runnable: unattended, or human-driven only through the script above.
