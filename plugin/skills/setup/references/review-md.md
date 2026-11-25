# REVIEW.md starter

`compost:setup` and `compost:review` offer this file; write it at the repo root only on a yes. The
review workflow reads the four sections below by their headings, and a Checks section when the
repo adds one (below): Failure, Minor cap, and Skip set how it grades and filters findings, and
the whole file goes to every reviewer as a standards source. Without a REVIEW.md, the workflow applies exactly these defaults. Edit a section to fit the
repo and leave the heading as it is.

```markdown
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
```

## Checks

A repo adds a `## Checks` section once it has its first check; the starter writes none, and
without the section review runs as it would without it. A check is a judgement a past miss
taught: one bullet per check, in this shape.

```markdown
## Checks

- **transcript-untyped-entries**: Trigger: the diff changes code that reads Claude Code transcript entries. Check: does it skip user entries nobody typed (the flags in `UNTYPED` in `scripts/stop_guard.py`)? Source: JoshuaOliphant/claude-plugins#206.
```

- **name**: short and unique; reviewers cite the check by it.
- **Trigger**: something a reader can see in the diff alone (a path, a call, a kind of change).
- **Check**: a question with a yes or no answer, where yes is the safe answer.
- **Source**: the incident, pull request, or issue the check came from.

The review's scope agent reads each trigger against the diff and the result lists every check as
`triggered` or `not triggered`, each with why. The Standards reviewer answers each triggered one
at a `file:line`, or the Standards axis fails. Checks come from misses: `compost:diagnose` after a
root cause, `compost:retro`, and `compost:review` on a survivor no lint rule could catch each
propose one with its Source; a person adds it, and an unattended run only proposes it in a
ruling. A check that is now mechanical becomes a lint rule or test instead, and `compost:prune`
removes checks whose trigger names code that is gone.

When the offer comes from a review, add to Skip each path the review dropped or the user pushed
back on as noise, and to Failure each kind of harm a pushed-back blocker turned out not to be.
