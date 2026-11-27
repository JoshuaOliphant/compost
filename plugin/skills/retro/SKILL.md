---
name: retro
description: Looks back over a coding session and files the changes to the agent's environment (checks, pointers, instruction files, tooling, access) that would have made it go better. Use when the user says "retro", "run a retrospective", "what slowed you down", or "what should we change so this goes smoother next time"; when a run has just finished through compost:finish; and, without being asked, once a task is done that was harder than it should have been, such as the same mistake made twice, a long hunt for a file or fact, a fact you had to guess because you could not reach it, an error no check caught, or a tool call that cost far more than its answer.
---

# Retro

A session that went badly usually went badly for a reason outside the code: a file the agent could
not find, a mistake no check caught, a rule buried in an instruction file nobody weighs, a log it
could not see. Retro reads one session after it ends and asks what in the environment should
change so the next session does not pay the same cost. The fixes are to the environment, never to
the session's own work: that went through review already.

This differs from `compost:skill-drift`, which watches one skill's text across many sessions, and
from `compost:prune`, which checks docs against the code. A candidate that is really one of theirs
goes to them.

The user can ask for a retro at any time. Start one yourself when a task you just finished cost
more than it should have, for one of the reasons in the description. Finish the task first:
a retro mid-task derails the work it is about, and only a finished session shows the whole cost.
Scope it to the stretch that struggled, not the whole session. A retro that finds nothing worth
fixing files nothing and says so in one line.

## Steps

1. **Read the tracker.** Find it in `docs/agents/issue-tracker.md`. If that file is missing, run
   `compost:setup` now, then continue. A GitHub one without the fork check takes it from
   [setup's GitHub reference](../setup/references/issue-tracker-github.md).

2. **Read the session's primary sources.** Default to the current session; when the user names
   another, find its transcript under `~/.claude/projects/<the cwd with / as ->/<session-id>.jsonl`.
   Read what happened, not a summary of it: the transcript, the branch diff, the rulings and
   review findings on its issues. A long transcript goes to a subagent that returns each costly
   moment with its line in the transcript: a long search, a repeated mistake, an expensive call,
   a correction from the user, a fact the agent had to guess.

3. **Read the environment as it stands.** The repo's `AGENTS.md` and `CLAUDE.md` and the user's
   global one, `docs/agents/`, the repo's own check command, its CI workflow, its pre-commit
   hooks, and the hooks Claude Code loads. A check that exists but is unwired or silently broken
   is the finding; building a second one is not the fix.

4. **Look for candidates.** Each candidate cites the moment in the session that shows it.
   - **Navigation:** finding the right file or fact took a long time, or a dependency between files
     was hidden. The fix is usually a pointer where the agent first looked.
   - **Automated checks:** the agent made a mistake a lint rule, type check, test, or hook could
     have caught. A repo whose lint, type check, and tests run in neither a pre-commit hook nor CI
     is a finding on its own.
   - **Coding standards:** the reviewer missed a mistake, or a standard is unclear or obsolete. A
     miss is a defect a review passed that something later caught: red CI on the diff's own logic,
     the merge result, the user, a revert, a bug filed against merged work.
     Classify it first: a mechanical one gets a check
     ([make mistakes impossible](../../canon/make-mistakes-impossible.md)); only a judgement call
     becomes a written standard. A judgement a diff shows is at stake becomes a check for
     `REVIEW.md`, in the shape [the starter](../setup/references/review-md.md) gives, with the
     session's issue or PR as its Source, so review asks it whenever its trigger matches.
   - **Instruction weight:** `AGENTS.md` or `CLAUDE.md` carries steering that belongs in a check or
     in what review reads.
   - **Tool economy:** a tool call, CLI, or MCP server cost far more tokens or time than the answer
     was worth.
   - **No-ops:** an instruction that changed nothing the agent did. It costs context and earns
     nothing.
   - **Information access:** the agent needed a fact it could not reach: dev-server logs,
     read-only access to a service, a doc behind a login.

5. **Check each cause against the run's own numbers.** A candidate that says a cost happened
   because of something ("the review was expensive because it ran without Jev") is a causal claim,
   and the fix it files is only as right as the cause. Before you keep one:
   - Find the data that would show it: token counts per agent or per call in the transcript, the
     diff size against the thresholds that pick a path (review's light path is 50 changed lines
     or fewer), the workflow's result, the transcript line where the cost landed.
   - Say what the run would have done without the cause, from the same data. If the cost would
     have landed anyway, the cause is wrong. The Gather retro blamed the missing Jev for an
     expensive review, but the diff was 260 changed lines, so the review took the full path with
     Jev or without it; the cost was elsewhere.
   - A candidate the data contradicts is restated with the cause the data shows, or dropped. One
     with no data either way is filed without its cause: the issue names the cost and the moment,
     says the cause is unchecked and what data would settle it, and proposes no fix yet.

6. **Place each fix where it costs least.** The implementing agent carries the most context
   pressure: it explores, writes, and debugs. The reviewer reads a diff and carries the least. So
   a standard is enforced at review, not taught to the implementer, and `AGENTS.md` holds pointers
   rather than rules, since every agent in the repo pays for every line of it. Go as high as the
   fix allows: a check, then a standard the reviewer reads, then a pointer in `AGENTS.md`. A
   mistake that a written rule already forbids is a repeat: its fix is the highest level that
   works, and a second copy of the rule is never it. A fact for the docs follows
   [core docs](../../canon/core-docs.md).

7. **File the candidates, most severe first.** One issue per candidate in the repo's tracker, with
   the session evidence, what step 5 found (the data that backs the cause and what the run would
   have done without it, or, with no data, that the cause is unchecked and what would settle it),
   the category, and the fix with its placement, if step 5 left one. A proposed `REVIEW.md` check
   goes in its issue as the exact bullet. Count it by pattern first: list the tracker's open
   issues labelled `review-rule` and read each one's trigger. When none is the same pattern, file
   the candidate with that label; the user adds the check. When one is, this is the pattern's
   second miss: comment the new Source on that issue instead of filing, and open the check as its
   own change, a branch off the default branch that edits only `REVIEW.md` (both Sources on the
   bullet), pushed as a draft pull request where there is a forge. Only the user merges it, so an
   unattended run opens it too, and never writes `REVIEW.md` on any other branch. Never add it to
   the change that had the miss: review reads `REVIEW.md` from the base, so it judges the next
   change, not this one. One miss can be noise; two of a kind is a check worth its cost. A candidate outside the
   repo (the user's global `CLAUDE.md`, a personal skill, an MCP server's config) is not filed:
   write the proposed change as exact text in the report. End with one line per candidate:
   severity, category, and the issue link or proposal.

## Next moves

- `compost:build` when a filed candidate is small and worth doing now.
- `compost:spec` when several candidates add up to one change to how the repo works.
- `compost:skill-drift` when a candidate is a compost skill saying the wrong thing.
- `compost:prune` when a candidate is a doc that drifted from the code.
