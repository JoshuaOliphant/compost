---
name: pause
description: Stops work at a safe point with everything committed and a resumable status comment on the parent issue, and picks paused work back up from the tracker and git. Use when the user says "pause", "stop here for today", "wrap up for now", "hand this off", "write a handoff", "pick up where we left off", "resume", "continue from yesterday", or when a session is about to end mid-run.
---

# Pause

A paused run is only as good as what a cold-start agent can find. The state lives where the work
already lives: commits in git, and on the parent issue a status comment, the checklist, and the
ruling comments. No handoff file, no notes in `/tmp`, nothing that only this session knows. Pausing
writes that state down; picking up reads it back and trusts it instead of redoing the work.

Pause only when asked or when the session has to end. "Keep going", "going to bed, don't stop", and
"finish while I'm away" mean keep working, not pause.

## Pausing

1. **Stop at a safe boundary.** Finish the step you are in or back out of it cleanly. Start nothing
   new. Stop any subagents or teammates still running, and collect what they had.

2. **Make the work durable.** In every worktree the run owns (yours and each worker's), commit
   uncommitted edits as one `wip:` commit on its branch. If the tree is broken, say so in one line of
   the commit body. If the feature branch already tracks a remote, push it (and any worker branch that
   holds unmerged work) so the checkpoint survives this machine. Take no other outward action to
   pause: no new PR, no merge, no comment on anything but the issues in this run.

3. **Write the status comment on the parent issue.** Use the tracker from
   `docs/agents/issue-tracker.md` (`gh api repos/{owner}/{repo}/issues/<n>/comments -F body=@-` when it is absent). Reference artifacts by link
   or path rather than restating them; the spec, the issues, the rulings, and the commits already say
   what they say.

   ```markdown
   ## Paused: <date>

   **Where things stand**
   - #13 done, reviewed, merged into `feature/12-export` at abc1234
   - #14 built and verified, review round 1 found two majors, fixes not started; branch `14-export-csv` at def5678 (worktree `.worktrees/14-export-csv`)
   - #15 not started; blocked by #14

   **Next action:** spawn a worker on `14-export-csv`'s head with round 1's findings (linked)
   to fix them, re-run `compost:verify`, land it, run review round 2, then start #15.

   **Open rulings:** rulings the user should look at before the run goes further, as links, each with
   its cost if wrong. "None" if there are none.

   **Lane records:** in a lane-routing run, each lane's tokens from the workers that finished
   (their completion notices), and which workers the pause stopped, so their lanes' totals are
   marked "incomplete" as lane routing says. Omit otherwise.

   **Gotchas:** anything the next session would otherwise rediscover the slow way (a service that
   must be running, a flaky test and its issue, a command that needs a flag).

   **Skills to load:** `compost:implement`, plus any the next action needs.

   compost-session: <this run's id, from `frontier.py session`>
   ```

   If the user said what the next session is for, shape the next action around that. Leave the
   parent's checklist alone: `compost:implement` ticks an issue once it passes review, and the
   status comment already says what is done.

4. **Report.** Where you stopped, the commits you made and whether each tree is clean, the link to the
   status comment, and the first action on resume. This is a pause, not a final report; don't
   recap the whole run.

## Picking up

1. **Read the trail.** Read `docs/agents/issue-tracker.md`, then the parent issue: the latest status
   comment, the checklist, and every ruling posted since. Read the sub-issues the next action names.
   The trail is authoritative; resist re-deriving it.

2. **Reconstruct the working state.** Run `git worktree list`, `git branch`, and `git log` on the
   feature branch and each worker branch. Check the branch heads against the SHAs in the status
   comment; a mismatch means someone worked after the pause, so read those commits before going on.
   Uncommitted changes in a worktree mean the pause was not clean; commit them as `wip:` and say so.

3. **Diff done against pending.** Compare what landed with what the parent issue asks for, using
   `frontier.py issues` (`compost:implement` step 2), run with the id the status comment was
   tagged with as `--session`, so the paused run's branches count as its own; name the resume point, and don't redo finished work or rerun an old repro.

4. **Check the claim the next step rests on.** Before building on inherited work, prove the one
   fact it depends on against the real artifact: run the suite on the feature branch, or the check
   that showed the last issue working. A passing report from the previous session is not proof
   ([prove it works](../../canon/prove-it-works.md)).

5. **Continue.** First post a one-line comment on the parent issue saying the run resumed and
   from which status comment, with a `Resumes: <the status comment's session id>` line, tagged
   with your own id (`frontier.py session`; if the paused session might still be running in this
   clone, set `COMPOST_SESSION` to a new id first, since the clone's id is shared); that line makes the paused session's branches this
   run's own, so implement's frontier sees them that way (`compost:implement` step 2). Then load
   `compost:implement`, even when the next action belongs to another skill: a pause the user
   asked for ended the run for compost's Stop hook, and only an implement load starts it again.
   Then hand the next action to the skill it names.

## Next moves

- `compost:implement` when resuming a run with open issues on the frontier.
- `compost:review` when the next action is reviewing work that was built before the pause.
- `compost:diagnose` when the pause left a broken tree or the suite fails on pickup.
- `compost:finish` when pickup finds every issue done and only the hand-off is left.
