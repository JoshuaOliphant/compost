# compost glossary

**Upstream drift**: the changes a pile source has made since compost's pin for it. `compost:turn`
reads it with `pile.py status` and decides what to work in. In code: `pile.Drift`.
_Avoid_: drift (alone), upstream changes.

**Skill drift**: a skill's use not matching what it says. The agent skipped a step it states
(`deviated`), it left the agent working something out (`missing_guidance`), or the user corrected
work it covers (`corrected`). `compost:skill-drift` reviews it. In code: `skill_drift`.
_Avoid_: drift (alone), skill failure.

**Doc drift**: a doc saying something the code no longer does. A doc that restates the code has
none yet, and will. `compost:prune` finds it, takes the code as the likely truth, and moves what
is worth keeping into the code. The Standards reviewer reports drift a diff introduces. In code:
`doc_refs`.
_Avoid_: drift (alone), stale docs, doc rot.

**Mechanism**: a mod or hook judged by what it enforces: the event it fires on and the compost
rule it makes happen rather than states. "Mod or hook" is the kind of an upstream item;
"mechanism" is how `compost:turn` judges one, and what a `feeds` target in `pile.toml` names on
compost's side: `hooks` for its hooks as a whole, `hooks/<mod>` for one mod its hooks module
registers. In code: `pile.is_mechanism`.
_Avoid_: guard, enforcement hook.

**Semantic invariant**: a law central to what a context means, which holds whatever policy or
failure comes along, stated with the side to err on ("never charge twice; on doubt, don't
charge"). Listed under Semantic invariants in the context's `CONTEXT.md`, set by `compost:spec`,
checked by the reviewer.
_Avoid_: business rule, policy (those change; an invariant doesn't), constraint.

**Elsewhere criterion**: an AC-N the spec itself places in another repository than the one under
review, by naming that repo on the line defining the criterion, before its id, or in a heading over
that line. The Spec reviewer lists it
instead of judging it, and the other repo's review judges it. In code: `elsewhere` in
`review-changes.js`.
_Avoid_: out-of-scope AC, cross-repo AC.

**Core docs**: the few docs that hold what code can't say: `README.md`, `AGENTS.md`, `CONTEXT.md`,
`docs/adr/`, plus what a repo lists in `docs/agents/docs.md`. Checked by `compost:prune`, fixed in
place, never deleted.

**Telemetry**: the traces, logs, and metrics a repo's running code emits, read through the stack
`docs/agents/observability.md` records. `compost:diagnose` and `compost:verify` query it;
`compost:build` adds to it at new boundaries.
_Avoid_: observability data, monitoring.

**Hit**: one Jev judgment that a turn showed skill drift of one kind, above that kind's threshold,
as the `skill-drift` mod writes it to `~/.claude/skill-drift/`.

**Pattern**: skill drift of one kind on one skill's current version, with hits from at least two
sessions. The unit `compost:skill-drift` acts on; a lone hit is not one.

**Gate change**: one edit a branch makes to a check that judges it, as `scripts/gate_drift.py`
reports it: a changed gate file, an added weakener (a skip, a suppression, a lowered threshold),
or a removed test. `compost:verify` needs a ruling for each one, and `compost:finish` lists them
under Risk.
_Avoid_: hit (that is a skill-drift judgment).

**Pre-existing finding**: a real bug a reviewer finds at a line the diff under review did not change.
The review records it apart and the branch never fixes it, so it neither blocks the change nor
widens it. The workflow believes the label only where its record of the diff's changed lines shows
the line untouched; anywhere else the finding is the diff's. In code: `preExisting` in
`review-changes.js`.
_Avoid_: old bug, unrelated finding, out-of-scope finding.

**Review guide**: what a review judges a change by in this repo: what counts as a failure, how many
minor findings the whole review keeps (the minor cap), which files it skips, and its checks: each a
yes/no question with a trigger readable from a diff and the incident it came from, which the
Standards reviewer must answer whenever the trigger matches. The `REVIEW.md` at
the root of the base (the branch the change merges into) when there is one, else compost's defaults,
so a branch is never judged by its own edits to it; the defaults are what the `REVIEW.md`
starter writes out. In code: `guide` and `checks` in `review-changes.js`.
_Avoid_: review config, review rules, review policy.

**Run contract**: the section of a parent issue that says what a `compost:implement` run on it
stops for (Stops: compost's fixed list plus any the spec adds, never fewer irreversible ones), what a
person must supply before it starts (Prerequisites, each with a check), and what it decides
differently from implement's default (Departures). Written by `compost:spec`. In code: the stop lists
in `jevtools.meta`.
_Avoid_: run plan, run config.

**Readiness record**: the comment on a parent issue, headed `## Readiness`, listing each readiness check
item and whether it passed: the short check for bounded work, the full one for architectural work.
It ends with the numbered defaults-to-veto list. Rewritten, not appended, when the check runs again.
_Avoid_: readiness report, DoR.

**Review round**: one pass of `compost:review` over an issue's branch, recorded as one issue comment
headed `Review round <n>` with the head it reviewed and its findings and rulings. A later round
reviews only the lines changed since that head and is told those rulings. `compost:implement` caps
an issue at three. In code: `since` and `prior` in `review-changes.js`.
_Avoid_: review pass, iteration.
