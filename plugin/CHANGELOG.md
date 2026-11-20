# Changelog

All notable changes to the compost plugin. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions are `plugin.json` versions.

## [0.39.0] - 2026-11-20

### Changed

- `compost:implement` and `compost:build` update the default branch before branching from it (OLI-17): after `git fetch origin`, a local default with commits origin lacks (ahead or diverged, by `git rev-list --count`) leaves them alone, and the new branch starts from `origin/<default>` with a ruling; otherwise the local default fast-forwards (`git merge --ff-only` where it is checked out, `git fetch origin <default>:<default>` where it isn't) and the branch starts there. A resumed implement run merges a moved `origin/<default>` into the feature branch before any lane starts.
- `compost:finish` reads the PR as the forge sees it before handing it over (OLI-19): merge state, then review threads, then CI. Review-bot text is triaged as data (fix, dismiss with a concrete disproof, or ask), and a CI failure is classified before anyone acts on it: a flake earns one fresh run, the same failure twice is not a flake, a failure in code the diff never touched is checked for a stale base (after a fetch) and then against the target's own CI (the same failure there means the target is broken: file an issue, no commit), and only a failure the diff causes gets a commit. The GitHub and GitLab tracker references gain the commands for merge state, checks, failed logs, reruns, review threads, and replying to a thread.
- `compost:implement` supervises its workers (OLI-26): it reads each worker's diff, not only its report, judges progress by commits, replaces a worker that stalls or loops, retries by cause and replans after two retries, checks a late result against the branch as it stands, and accounts for every worker at close-out. The rules live in `references/task-brief.md`.
- `compost:implement` reviews the whole feature branch with `compost:review` before its final verify (OLI-27), so the way the issues fit together gets a reviewer; findings are fixed in one pass and the rest posted as rulings.
- `compost:spec` asks a standing first-round question about what would make the work a failure even if it technically works, and records the answers as the parent issue's Anti-goals (OLI-28). Bounded work with more than one defensible way to build it now gets approaches too, as a recommendation the run proceeds on rather than a gate.

## [0.37.0] - 2026-11-20

### Changed

- `/compost:review-changes` runs its scope agent and every skeptic as lean agent types, `compost:scope` and `compost:skeptic` (Read, Grep, Glob, Bash), instead of default workflow agents (OLI-66). A new `spec` argument carries the issue text from the caller, so the scope agent fetches nothing; `compost:review` passes it when the tracker reads issues through tools rather than a shell command (an MCP tracker such as Linear). Without a `jev` argument, scoping ranks the files with the plugin's own `jev.py`, so a direct call gets the same ranking and path as one from `compost:review`. Every result lists the harness code review under `notRun` and in its summary, and the workflow's `whenToUse` names `compost:review` as the entry point.
- Review findings gain a fourth severity, `pre-existing`: a real bug at a line the diff did not change (OLI-67). Scoping records the diff's changed line ranges, and the workflow keeps a pre-existing finding in the axis's new `preExisting` list, with no skeptic, only where those ranges show the line untouched; it is never a survivor, never fails the review, and is counted in the status. One at a changed line, with no line, or without the ranges to check is judged as a major. `compost:review` records them in the round comment and fixes none of them on the branch.
- A re-review round judges only what changed since the last round (OLI-68). `/compost:review-changes` takes `since` (the head the last round reviewed) and `prior` (its findings and rulings): scoping records the lines changed since then, every reviewer is told to judge only those (Spec still maps every AC-N across the whole branch), the workflow drops a finding at a line untouched since before any skeptic and counts it in the status (a Spec finding that names an AC-N stays, and a bug the new lines cause elsewhere is cited at the line that causes it), and reviewers and skeptics are told the prior rulings, so a pushback holds unless its code changed. A `since` that does not resolve or is not an ancestor of the head gives a whole-branch review, with `delta.problem` saying why. `compost:review` passes both from the last `Review round` comment, which now records a `Head:` line and a `Findings and rulings` list for the next round to read.
- A repo's `REVIEW.md` sets the review guide: what a failure means, the minor cap, and what to skip (OLI-70). Scoping reads it (or applies the defaults when there is none: failure is a change that breaks behaviour, loses or leaks data, or blocks a rollback; at most five minors; skip generated, vendored, and lock files and what a linter enforces; every behaviour claim cites a file:line) and lists the changed files a skip rule covers. Every reviewer gets the guide; the workflow drops findings in skipped files before any skeptic, keeps the first minors up to the cap across both axes, unjudged ones included (Standards first, in the order each reviewer listed them), and reports `guide` with the cut count in its summary. `compost:setup` offers to write the defaults out from a new starter, and `compost:review` offers once, seeded with what the review dropped and the pushbacks, when a review ran on the defaults.
- `compost:retro` checks each cause it names against the run's own numbers before it files a fix (OLI-69): the data that would show the cause, and what the run would have done without it. A candidate the data contradicts is restated with the cause the data shows, or dropped; one with no data either way is filed without its cause and with no fix yet.

## [0.36.0] - 2026-11-20

### Changed

- `/compost:review-changes` judges only the criteria of the repo under review when a spec spans several repos (#40). Scoping records the repo (`owner/name` from origin) and copies the spec with its headings, and the Spec reviewer lists each AC-N the spec places in another repo under `elsewhere` instead of reporting it unmet. The workflow keeps an entry only when the spec names that repo on the AC-N's defining line before its id or in a heading over it, and it is not this repo's name (a fork's upstream counts as this repo); a refused one leaves the AC-N unmapped and the axis failed, with the reason. Accepted ones come back as `spec.elsewhere` and in the Spec status ("not verifiable here: AC-3 (agent-plugins)"), and the Spec skeptics are told those AC-N, so they refute a finding that one is missing here.
- `compost:review` lists each elsewhere criterion in its issue comment with the repo whose review covers it, and its by-hand fallback names the repo to the Spec reviewer and checks `elsewhere` entries by the same rule.
- `compost:spec` names the repo each criterion lives in when a spec spans several repos.

## [0.35.1] - 2026-11-13

### Added

- `pile.toml` watches swyxio/skills as a reference, pinned at the commit read, so `compost:turn` reports what it adds from here on. make-evals is filed as an add to `compost:diagnose` (#38).

## [0.35.0] - 2026-11-13

### Added

- `scripts/frontier.py` computes `compost:implement`'s issue states from the tracker and git: `issues <parent>` prints each sub-issue as done, blocked, taken, frontier, or ready-for-human with the reason; `claim <decision>` prints the session holding a map decision's earliest live claim; `session` prints this clone's session id (kept in its common git dir, so the main checkout and its worktrees agree), or `COMPOST_SESSION` when set, for a second session in the same clone (prefixed on every call, since an `export` doesn't outlive one Bash call). It reads GitHub (`gh api`), GitLab (`glab api`), and local trackers, and reads a blocker that isn't on the parent's checklist, so a closed one from an earlier spec counts as done.

### Changed

- Every comment an implement run posts ends with `compost-session: <id>` (a local tracker adds the time from `date -u`), and starting an issue posts `Started <branch>` on it, then reruns `frontier.py issues`: the earliest live `Started` holds the issue (a later one takes over only after the holder has been silent a day), so a late starter backs off and a confirmed holder is never displaced. A branch is taken only while the session holding it is live, meaning some comment it tagged on the parent or any sub-issue is under a day old. Liveness now belongs to the claimant, so another session's comments no longer keep a dead claim alive, and comments on sub-issues (where rulings and review rounds go on GitHub) count. Resuming posts `Resumes: <id>` before loading implement, and pause's status comment carries its session tag; the `Resumes` line makes the paused session's branches this run's own; it replaces the branch list in the status comment as the record of ownership.
- Map-decision claims use the same claimant-keyed liveness through `frontier.py claim`: the first claim holds until its session has been silent a day; a claim made after that takes over, and the old session coming back doesn't take it back. Rerun `compost:setup` to refresh `docs/agents/issue-tracker.md`. A claim posted by 0.34 names a branch or time rather than a tagged session, so it expires a day after posting even while that session works.
- `compost:implement`'s rolling window starts a dependant once its blocker is ticked (reviewed and landed), not merely merged, matching the one definition of done. The draft PR's `Closes` line (implement and `compost:finish`) leaves out sub-issues another session holds, and the parent while any is held.
- `compost:implement` says to load implement again after a mid-run `compost:finish`, and that the Stop hook sends a stop back only once.

## [0.34.3] - 2026-11-13

### Fixed

- The skill-drift mod's `missing_guidance` question fired on nearly every `compost:build` turn (16 of 18 turns with no gap scored over 0.6). It now asks whether something the skill relies on failed to fit the case: a command returning an outcome the skill doesn't say how to handle, or a method it prefers that its own tools can't check, with no fallback given. The threshold is now 0.5. On the 23 labeled build turns, 5 hit a real gap (Jev find-test exiting 2, or duplicate-test not seeing a doctest build preferred). Over ten runs it flagged at most 1 of the other 18 and 4 or 5 of the 5; the margin is a few hundredths, so the live eval allows one false hit. Only Jev-tool gaps are labeled so far.
- `compost:build` says what to do when Jev can't see a test: find-test's exit 2 `no tests found`, or duplicate-test leaving a new test (a doctest, say) out of its `tests`, means do the step by hand. The labeled exit-2 turns came from the unittest collector bug that 0.34.1 fixed, so today this mostly covers suites Jev really can't read, and doctests. A real Opus run that hit the doctest gap was flagged at 0.73 before this change; a run with the same gap on the new build scores 0.35 when replayed.
- The live eval drops the 60-turn whole-skill eval, whose data never reached compost-evals (#16), and allows one false hit for `deviated` too: over six runs a clean turn crossed 0.75 in two. `corrected` has no labeled data and is unmeasured.

## [0.34.2] - 2026-11-13

### Fixed

- The skill-drift mod judges `deviated` step by step: one Jev question per numbered step of the skill, and the turn deviates by its likeliest skipped step, which the hit's evidence names. The single whole-skill question scored every `compost:build` turn 0.75-0.95 whether or not a step was skipped, so it flagged all of them. On 23 hand-labeled build turns from two toy repos, step by step at 0.75 flags none of the 8 that did every step and 11 or 12 of the 15 that skipped one (it varies run to run). The threshold was chosen on 17 of those turns and held on the other 6, from a second repo. Steps are keyed by position, so a skill with two numbered lists (pause) has every step asked. A skill with no numbered steps keeps the whole-skill question, whose `deviated` threshold also moves from 0.7 to 0.75; only `wait-what` has no steps. The labeled turns are compost-evals' `skill-drift-steps.json`, replayed by `tests/test_evals_skill_drift.py`.

## [0.34.1] - 2026-11-13

### Fixed

- The skill-drift mod judges a skill loaded through the Skill tool against the turn of the loop that loaded it. A skill a subagent loaded (an implement worker's `compost:build`) was judged against the main session's turn, which never ran it, so every lane run logged a false `deviated` hit for build. Subagent turns are now judged on their own transcript; only the main loop's turns get the next-message correction check. A skill an agent definition preloads (no Skill call) still counts as the main loop's.
- The skill-drift mod hands Jev a skill's whole text (16,000 characters, up from 8,000). Eleven of compost's skills were cut short, so Jev judged steps it never read; a test keeps every skill under the limit.
- Jev's `find-test` and `duplicate-test` see unittest test classes, not only pytest's `Test*` classes: a class counts when a base's name says Test (`TestCase`, `APITestCase`, `BaseTest`) or the base is a test class in the same file. On a suite of `unittest.TestCase` classes they exited "no tests found", and build fell back to placing tests by hand.
- `compost:build` gives the exact `find-test` and `duplicate-test` commands inline and says to run them even when the placement looks obvious or there is one new test. Workers skipped both in every observed run; that was the real drift the mod flagged. The AC table is posted as a comment the way `docs/agents/issue-tracker.md` says.

## [0.34.0] - 2026-11-13

### Changed

- `compost:implement` step 2 defines done (closed, or ticked on the parent), blocked, taken (another session's branch for the issue, matched as `<issue>-*`, exists; it is pushed when the issue starts so other clones see it, and the claim expires after a day with no comment on the parent from any other session), and the frontier in one place, and `compost:build` checks blockers against the same "done". On GitHub a reviewed, landed blocker stays open until the PR merges, so build's old "every blocker is closed" check reported it as blocking.
- The frontier leaves out issues labelled `ready-for-human`, and close-out doesn't wait on them; the recap lists them under Risk, and the PR's `Closes` line leaves them (and the parent) open.
- Inside an implement run, `compost:setup` takes its recommended answers as rulings on the parent and leaves the orphan uninstall to the user.
- `compost:pause`'s pickup loads `compost:implement` before handing off the next action, so the resumed run is guarded again.
- `compost:review` heads its issue comment `Review round <n>`, and implement counts those comments for its three-round cap, so the cap holds across a pause or a compacted context. `compost:pause`'s status comment carries the review round and, in a lane-routing run, the tokens of the workers that finished, marking stopped ones' lanes incomplete.
- `compost:slice` and `compost:implement` stop for approval on a `Class: architectural` parent with no approval comment.
- Map decisions are claimed with a comment naming the session, read back so the earliest live claim wins, with a one-day lease; every session runs as the same user, so an assignee couldn't tell two apart. Rerun `compost:setup` to refresh the claim command in `docs/agents/issue-tracker.md`.
- `compost:build` posts the issue's AC table, which `compost:verify` edits rather than adding a second; implement workers report AC-row retirements and leave a committed AC-table cache alone, and the orchestrator applies both after landing.
- `compost:turn` runs `pile.py status --references` and `classify-change` (given the checkout's `pile.toml`) from a compost checkout, skips changes an open `upstream` issue already carries, and passes `advance` the full hash status printed.
- `compost:skill-drift` doesn't draft a second fix while a `claude/skill-drift-<skill>` pull request is open.

### Fixed

- The Stop hook treats a `compost:pause` load as the end of an implement run, like `compost:finish`, once the user has sent a message during the run, so a run the user paused no longer guards later turns that background notifications start. A pause the agent starts on its own leaves the guard on.
- `pile.py advance` refuses anything but a full commit hash: a ref resolved after the fetch could move the pin past changes nobody ruled on. `pile.py status --references` lists changes in reference sources, which were recorded but never compared.
- The skill-drift mod queues its log writes, so a turn's judgment and the next prompt's correction check that overlap no longer drop one batch of hits. `skill_drift.py mark` writes `reviewed.json` atomically, keeping mode 0644.
- `thin.py matrix --resume` reruns a mutant when a test file it ran, or a `conftest.py` above one, changed since the journal (hashes in `matrix.jsonl.tests`), instead of trusting kills the old tests found.

## [0.33.2] - 2026-11-12

### Fixed

- `thin.py` no longer crashes on a test whose parametrize id contains `|`: it cuts the coverage context's phase off the last `|`, not the first, so `test_x[a|b]` stays one test id.
- `compost:thin` step 7 now checks what thinning left behind: the remaining parametrize rows still cover every True/False value and still match the test's name and docstring, and the comment above a removed row or function goes with it.

## [0.33.1] - 2026-11-12

### Fixed

- `compost:setup` catches compost enabled under two ids (`compost@compost` and `compost@oliphant-plugins`): `pile.py replaced` offers to disable the copy that isn't running, and never the one that is.

## [0.33.0] - 2026-11-12

### Changed

- compost moved to its own repository, JoshuaOliphant/compost, with history; `compost@oliphant-plugins` keeps installing it from there.
- Skill drift recognizes compost's own skills when it runs in a one-plugin repo laid out as `plugin/`, not only in a marketplace's `plugins/<name>/`.

## [0.32.5] - 2026-11-12

### Added

- CHANGELOG.md, with a section per released version backfilled from git history.

## [0.32.4] - 2026-11-09

### Changed

- Maintenance release.

## [0.32.3] - 2026-11-09

### Changed

- Compost stop-guard: let a message's origin decide whether the user sent it (#206)
- Compost stop-guard: name the sender check sent_by_user
- Compost stop-guard: treat a null or non-dict origin as not the user's, explicitly

## [0.32.2] - 2026-11-08

### Changed

- Setup: verify the tracker has issues enabled before recording it (#204)

### Removed

- Setup: order the issues check before labels, name the settings path, drop template notes (#204)

## [0.32.1] - 2026-11-06

### Changed

- Skill-drift writes a digest on no-pattern runs and lists sub-threshold hits

## [0.32.0] - 2026-11-05

### Changed

- Run the Jev tools on Ollaya when the TypeSafe SDK variables say so
- Settle review findings on the Ollaya backend
- Hold an exported key back from plain-HTTP servers; keep old cache hits
- Explain a refused placeholder; rewrap the edited doc lines
- A keyed Ollaya needs a key; say Ollaya support is untested on a real server

## [0.31.0] - 2026-10-30

### Changed

- Verify builds and keeps a repo verify command (#196)
- Name the timestamp the cache staleness check compares

### Removed

- Retire superseded AC rows on record; read AC tables in bulk
- Keep the AC-table cache fresh on retirement; show the table shape

## [0.30.0] - 2026-10-30

### Changed

- Mutate wiring in verify's hand walk, and don't count a mutant that fails to build (#191)
- Say verify checks build's walk on uncovered lines; keep the skip sentence next to its referent (#191)

## [0.29.0] - 2026-10-30

### Changed

- Review-changes fails a reviewer with no record of what it checked (#193)
- Pin the AC-N word boundary and the Standards checked prompt in the workflow suite
- An unchecked review keeps its findings; AC-N maps by name
- An AC-N maps only through a cited entry or a finding
- An AC-N maps through a finding only when its claim names it

## [0.27.0] - 2026-10-29

### Changed

- Thin: say where the AC remap lands and what to run without a verify command

### Removed

- Thin: remap AC tables when it folds or deletes a test

## [0.25.0] - 2026-10-29

### Changed

- Implement spawns a lane only when it outweighs the handoff; review runs code-review only on executable code (#184)
- Deepen picks two to four designer stances per problem; fan-out judges only diverging attempts (#185)
- README and review intro say code-review runs on executable code
- Name check.md for both its uses; state the map's subagent rule once
- Fan-out keeps the judge when converging attempts match a favoured frame
- Map-issue names which step 5 sends research to subagents (#186 re-review)

### Removed

- Prune and slice fan out only when it pays; builder check drops its persona line (#186)

## [0.24.3] - 2026-10-29

### Changed

- Thin.py survivors runs thin's own operators by default (#94)

## [0.24.2] - 2026-10-29

### Changed

- Fetch the Spec issue by the tracker's own id; let deploy and people-facing stops through

### Fixed

- Address review on the tracker-id and stop-guard fixes

## [0.24.1] - 2026-10-24

### Changed

- Cite lines from per-file reads, not cat -n over several files

## [0.24.0] - 2026-10-22

### Added

- Address PR #175 review on lane routing (#138)

### Changed

- Opt-in lane routing table for implement (#138)
- Tighten lane routing after review (#138)
- Close lane routing's second-round review gaps (#138)
- Last lane routing review round (#138)

## [0.23.3] - 2026-10-20

### Changed

- Spec fires on rules and limits added to existing code (#176)
- Keep spec description under the 1024 limit (#176)

## [0.23.2] - 2026-10-19

### Changed

- Spec fires on Sonnet for "acceptance criteria" asks; README says compost targets Opus (#135)

### Removed

- Drop 'answer inline' from spec's new trigger sentence so it can't read as covering questions (#135)

## [0.23.1] - 2026-10-19

### Added

- Address review: state green rule, tighten evidence claims, headless wording

### Changed

- Diagnose: require the failing output of the check before the first edit

## [0.23.0] - 2026-10-18

### Added

- Add a deeper-ask step to spec (#156)

### Changed

- Make the deeper ask its own skill, compost:deeper-ask (#156)

## [0.22.1] - 2026-10-18

### Changed

- Maintenance release.

## [0.22.0] - 2026-10-18

### Changed

- Every change is reviewed; a small diff gets one reviewer on both axes (#161)
- Light review proves itself small, not structural, and checked on every axis (#161)
- Light review keeps stray-tagged findings and names a missing risk ranking (#161)

## [0.21.4] - 2026-10-18

### Changed

- Thin.py survivors reports a mutation score (#114)

## [0.21.3] - 2026-10-17

### Changed

- Jev scripts re-run under uv when typesafe-sdk is missing (#167)
- A failed uv install exits 3, and the re-exec marker stops at the child (#167)

## [0.21.1] - 2026-10-17

### Changed

- Finish uses gh api REST for PR commands (#153)

## [0.21.0] - 2026-10-17

### Changed

- Journal thin.py matrix rows and resume a killed run (#143)
- Collect coverage contexts with the fail-under gate off (#147)
- Jev.py says Jev is unavailable in one line when TypeSafe is unreachable (#145)
- Rename the resume journal into place so a kill mid-rewrite keeps its rows (#143)
- Keep a killed matrix run's journal and children safe (#143)
- Jev.py status builds the client, so a key or proxy it can't use exits 3 (#145)

### Removed

- A finished matrix run deletes its journal, so only a killed run's blocks a fresh one (#143)

## [0.20.1] - 2026-10-17

### Changed

- Give spec/slice descriptions margin on the disk-access routing case

## [0.20.0] - 2026-10-17

### Changed

- Thin's own mutation operators for the breaks cosmic-ray can't make (#124)
- Thin's operators after review (#124)
- Thin's operators after the Standards review; docs; compost 0.19.0 (#124)
- Thin reaps what a run's escaped sessions leave behind (#128)
- Record thin's own operators and the AC-6 measurement in the kill-matrix reference
- Report and uninstall installs their marketplace no longer lists (#85)
- /drift shows the open hits skill_drift.py counts, and survives a bad log line (#97)
- Count a wrong-typed skill-drift log line as unreadable (#97)
- Validate marketplace catalogs and name orphans one way (#85)
- /drift names the exception a crashed skill_drift.py ends on, and its test pins the argv (#97)
- Skip unreadable catalogs and uninstall rather than disable orphans (#85)
- Find_active decides which superseded plugins to disable (#85)

## [0.19.0] - 2026-10-17

### Changed

- The answer-read check flags reads past the view, not any dict keyed 'score' (#105)
- Narrow skips a group that would pass the cap and keeps smaller likely ones (#105)
- Classify-change always sends a change feeding a mechanism to be read (#70)
- List plugins lazily, from the same claude dir, keeping local installs local (#104)

## [0.18.0] - 2026-10-17

### Changed

- Thin.py survivors, diff-scoped mutation testing for verify (#123)

## [0.17.4] - 2026-10-17

### Changed

- Maintenance release.

## [0.17.3] - 2026-10-17

### Changed

- Maintenance release.

## [0.17.2] - 2026-10-17

### Added

- Initial release.
