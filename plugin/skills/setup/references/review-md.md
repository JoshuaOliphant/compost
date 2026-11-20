# REVIEW.md starter

`compost:setup` and `compost:review` offer this file; write it at the repo root only on a yes. The
review workflow reads the four sections below by their headings: Failure, Minor cap, and Skip set
how it grades and filters findings, and the whole file goes to every reviewer as a standards
source. Without a REVIEW.md, the workflow applies exactly these defaults. Edit a section to fit the
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

When the offer comes from a review, add to Skip each path the review dropped or the user pushed
back on as noise, and to Failure each kind of harm a pushed-back blocker turned out not to be.
