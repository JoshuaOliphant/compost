# Skeptics by hand

When the review workflow can't run and step 1 falls back to spawning `compost:skeptic` agents
yourself, give each skeptic what the workflow's task would, and settle its verdict the way the
workflow does. The workflow's `skepticPrompt` and `judge` in `workflows/review-changes.js` are
the source; this page is what to copy from them.

## The task

- The finding: its axis, severity, `file:line`, claim and evidence, and the diff command.
- For a Spec finding, the spec text.
- The severity rubric, quoted from the Severity section of `agents/reviewer.md` (blocker, major,
  minor), and the review guide's Failure section when the base has a `REVIEW.md`. The skeptic grades
  by these lines; without them it grades against a rubric it never sees.
- The verdict it returns: `verdict`, `harm`, `introduced`, `severity`, `limit`, `correction`,
  `outsideSpec` and `reason`, as `agents/skeptic.md` describes them.

## Settling the verdict

- `refute`, or `uphold` with `harm: none`: refuted.
- `unsure`: survives as a minor, marked unsure.
- `uphold` with `introduced: false` at a line the diff didn't change: pre-existing.
- Otherwise it survives at the skeptic's severity, never above the reviewer's. A drop of more than
  one step stands only when `limit` cites a path with an extension and a line (`app/cli.py:40`);
  without one, lower it one step.
- Keep the `correction`. A Spec finding with `outsideSpec` moves to the Standards list.
