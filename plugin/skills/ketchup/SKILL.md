---
name: ketchup
description: Catches the user up on everything that changed since their last message, in plain words and small pictures, then lists every call waiting on them with what they need to make it from the reply alone. Use when the user types /compost:ketchup; only they know when they have been away.
disable-model-invocation: true
---

# Ketchup

The user stepped away while the work went on: a `compost:implement` run, a review loop, a
`compost:finish` waiting on a merge. They remember their last message and nothing after it.
Ketchup catches them up from there and puts every call that waits on them in front of them, each
with enough to decide it without opening anything. `compost:wait-what` re-pitches one thing the
user lost; ketchup covers everything since they last wrote.

The window starts at the last message the user wrote before `/compost:ketchup`. Hook output,
notifications, and subagent reports are not their messages.

## Gather

This turn is read-only. Change no code, start no job or app, and write nothing anywhere: no
commit, push, comment, or tracker update.

1. **The conversation.** Your own work since the window opened, every subagent's report, and
   anything anyone else wrote here.
2. **The tracker and git.** A run's state lives there, not in this session
   ([compost:pause](../pause/SKILL.md)), so read it even when the conversation seems to say it all.
   Read the tracker from `docs/agents/issue-tracker.md`; on GitHub, a doc without the fork check, or
   no doc, takes it from [setup's GitHub reference](../setup/references/issue-tracker-github.md). On the parent issue of any run this
   conversation touched, read the checklist, the latest status comment, the run contract's Stops,
   and every ruling comment posted inside the window. Check each PR's and CI run's state now, not
   as last reported: a PR reported green an hour ago may be behind its base now.
3. **The numbers.** Check each number you will show against the record it comes from. When one
   differs from what was said earlier, give the right one and say it changed.

An **action item** is a call or step only the user can take:

- a ruling posted for the user to look at, such as a pause comment's **Open rulings**, a
  `ready-for-human` issue, or a finding a review left to them;
- a stop on the run contract the run reached: a merge to the default branch, a force-push, a
  deploy, a data delete, a message to people outside the run, an architectural approval, a
  self-written workflow, or a prerequisite only a person can supply;
- access, a credential, or a product choice the work cannot go on without.

Count one raised before the window opened if it still waits. Work you can still do yourself is
not an action item. Never invent one to fill the reply. A step the user did not ask for and the
work does not need gets one line, and only when it cannot be undone.

For each item, collect its link, what it changes for users, the evidence for your pick, its risk,
and your pick. Write "unknown" for a fact the call needs that you do not have. Leave out a link
you do not have.

## Write

Use plain words and short sentences, as one person catching up another. Name domain things by the
glossary's terms in `CONTEXT.md` (follow `CONTEXT-MAP.md` when the repo has several), never their
_Avoid_ synonyms. Say what changed for the user, not how you did it: "the tests pass", not "CI is
green". Leave out hashes, paths, commands, and counts unless the user needs one to act. Call each
PR, issue, or worker by a name the user knows, with its identifier when they will act on it.

1. **Open with one sentence** naming what waits on the user, or saying nothing does. If nothing
   happened and nothing waits, say that and stop.
2. **What happened,** under 100 words, not counting pictures, and less when less happened.
   Pictures first (see below). Then one bullet per thing the user asked for: what came of it, and
   whether it is done, still running, failed, or not checked. Write each as you would say it
   aloud ("search was slow from a missing index"), and keep it true when read alone. Name any bug
   found and fixed on the way. Never mark something done while it waits on the user, and leave
   out what an action item says. Then at most three lines that change what the user knows or must
   do, and one line naming the work left that you can do yourself.
3. **Action items,** about 30 words each. Never drop items or shrink them to fit a word count: no
   count in place of a list, no link in place of an item. A link adds depth; the reply alone must
   be enough to decide.
   - Ask the call the user owns (merge, approve, pick) and give your pick. What you would do first,
     what must happen first, and what cannot be undone go in the pick.
   - One item: one bullet with the call, your pick, what it changes for users, the evidence, and
     its risk.
   - Items sharing a call (three PRs awaiting merge): the call and your pick once, then one
     bullet per item, riskiest first, with its link, what it changes, the evidence, and its risk.
     Give an item's pick only where it differs.
   - Give every item's risk, even when low ("low risk: only the wording changes"). Say what
     waiting costs only when it is more than a delay: a deadline, lost data, a branch going stale.
   - A call between options: every option weighed, each with what it gets the user, what it
     costs, and the current state when there is one. Those costs are the risk.

## Pictures

A picture is a screenshot or a Mermaid diagram. A Markdown table is not one.

Draw when a picture says it faster than sentences: how a design or flow works, a chain of PRs or
issues with each one's state, a before and after, options side by side. Never draw a status list,
the action items, or boxes with nothing connecting them. At most six boxes, at most eight words in
each, labelled as a person would say them ("waiting on your merge"), never as tags ("PR: open").

Show the screenshots `compost:verify` took for a changed screen inline, from the
`screenshots/<feature branch>` branch. A visible change with no screenshot gets "no screenshot
yet" on its line and a sentence on what changed on screen. Draw only from facts you have: never
invent a number, never draw a screen you did not capture, and link only what exists. Give no fact
twice, in the text or across pictures.

## Next moves

- `compost:finish` when the call the user makes is a merge and they say go.
- `compost:pause` when the user is about to step away again mid-run.
- `compost:wait-what` when one point in the catch-up still doesn't land.
