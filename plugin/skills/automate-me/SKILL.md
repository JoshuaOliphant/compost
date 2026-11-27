---
name: automate-me
description: Turns how the user works into a personal mode skill agents follow, mined from this project's past sessions and confirmed with the user, or refreshes the one they have. Use when the user types /compost:automate-me; only they know when their working style is worth capturing.
disable-model-invocation: true
---

# Automate me

The user corrects agents the same way session after session: shorter replies, a live repro before
"done", no em dashes, one PR per issue. Each correction costs a turn and dies with the session.
Automate-me collects the ones that recur and writes them into one skill, `<handle>-mode`, that
the user turns on with `/<handle>-mode` so agents work the way the user does.

`compost:retro` reads one session for environment fixes; this reads many for the user's own
conventions. A single workflow ("how I write commit messages") is a regular skill, not a mode, and
a task-specific skill needs no mining: write it with `skill-creator` when installed.

## Steps

1. **Find an existing mode skill.** Look for `*-mode/SKILL.md` under `~/.claude/skills/` and the
   project's `.claude/skills/`, including one level of category directory. If one matches the
   user, update it, unless they asked to start over; ask why before starting over, since it throws
   away rules they already settled. Updating changes the steps below: mine only history since the
   file last changed (its mtime, or `git log -1 --format=%cI <path>` when it is in a repo), ask
   what changed or is missing instead of what to capture, and edit the file in place, keeping every
   section the new evidence does not contradict.

2. **Mine this project's sessions.** Claude Code keeps transcripts as JSONL under
   `~/.claude/projects/`, one directory per project, named for its absolute path with every
   character other than a letter, digit, or `-` turned into `-` (`/home/me/my.app` is
   `-home-me-my-app`). A name over 200 characters keeps its first 200 and gains `-` and a hash.
   List the directory rather than building the name: pick the entry equal to the sanitized cwd,
   or, when that is over 200 characters, the entry that is its first 200 followed by `-` and a
   hash. A shorter prefix is a parent project, not this one. Ask the user when none or more than one fits.
   Read only this project's directory: another project's transcripts are other work, often
   private, and the user did not offer them. Split the last two to four weeks into three slices and
   spawn one subagent per slice in a single message, each told its slice's file list and the
   signals below, and to read only what the user typed: a `type: user` entry whose `origin.kind` is
   `human` when it has an `origin`, skipping entries flagged `isMeta`, `isSidechain`,
   `isCompactSummary`, or `isVisibleInTranscriptOnly` (skill bodies, compaction summaries, subagent
   turns), tool results, and injected tags. A wrapper around the user's own message (a `<wake>` in
   Claude Projects) holds what they typed: read inside it. A loaded skill's text shows up in every slice and would
   pass for a convention. Each returns the patterns it saw, each with a pointer (file and timestamp)
   to where it shows; the skill holds rules, not transcript excerpts.
   - how replies should read: length, tone, format, corrections like "shorter" or "plainer"
   - how much to do without asking, and what always needs asking
   - what "done" means: tests, a live run, a reviewer, evidence in the reply
   - code and prose rules: style, principles cited, linters and formatters
   - process: branches, worktrees, commits, PRs, merging, the tracker
   - delegation: subagents, models, parallelism
   - fixing a skill or the environment mid-task

   Keep a pattern seen in two or more slices. Drop one seen once: a preference stated once and
   contradicted elsewhere is noise.

3. **Ask the user.** Mining misses what hasn't come up yet. Use `AskUserQuestion`: a first round
   of one or two questions, four to six options each, multiple choice allowed ("Which of these
   should agents always do?"), then one round following up on what they picked, then one
   free-form question for anything the options missed. No more than that.

4. **Group and draft.** Sort what holds into sections, and keep a section only when it carries a
   specific rule that differs from the default: "Communicate clearly" is not a section; "Short
   paragraphs. Tables when comparing options. Bullets only for parallel items." is. Typical
   sections: Replies, Autonomy, Verification, Code and prose, Process, Delegation. Skip any with
   nothing specific.
   - Write imperatives about "the user", not their name.
   - Name the skills they rely on (`compost:verify`, `compost:review`) instead of pasting their
     text, and point to principle docs they keep elsewhere instead of copying them.
   - Keep it operational: no metaphors, no restating what a named skill already says.
   - Frontmatter: `name: <handle>-mode`, `disable-model-invocation: true`, and a `description`
     that says in one line what the skill is for: with the flag on, the user starts it with
     `/<handle>-mode`, and the description only labels it in the menu. A mode skill the model
     loaded on its own phrases would compete with every other skill for routing; rules the user
     wants on every turn go to the user-level CLAUDE.md instead (step 6).

5. **Iterate with the user.** Show the whole draft and take their edits. Expect more than one
   round, and cut on every pass: a mode skill is a short list of rules, not a manual. Judge it by
   whether it reads like them and misses nothing they care about; a pass/fail benchmark doesn't
   fit a working style.

6. **Place it.** By default it is personal: `~/.claude/skills/<handle>-mode/SKILL.md`, which
   lands by writing the file. When the user wants it shared in the project, write
   `.claude/skills/<handle>-mode/SKILL.md` on a branch and land it through `compost:finish`.
   A rule the user wants on every turn without invoking anything belongs in their user-level
   `~/.claude/CLAUDE.md` instead; offer to move those lines there, and write them only on their
   word.

## Next moves

- `compost:retro` when a recurring correction is really an environment fix (a missing check, a
  pointer, a tool) rather than a preference.
- `compost:finish` when the mode skill lives in the project and is ready to land.
