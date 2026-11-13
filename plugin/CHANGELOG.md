# Changelog

All notable changes to the compost plugin. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions are `plugin.json` versions.

## [0.35.0] - 2026-11-13

### Added

- `scripts/frontier.py` computes `compost:implement`'s issue states from the tracker and git: `issues <parent>` prints each sub-issue as done, blocked, taken, frontier, or ready-for-human with the reason; `claim <decision>` prints the session holding a map decision's earliest live claim; `session` prints this clone's session id (kept in its common git dir, so the main checkout and its worktrees agree), or `COMPOST_SESSION` when set, for a second session in the same clone. It reads GitHub (`gh api`), GitLab (`glab api`), and local trackers, and reads a blocker that isn't on the parent's checklist, so a closed one from an earlier spec counts as done.

### Changed

- Every comment an implement run posts ends with `compost-session: <id>` (a local tracker adds the time from `date -u`), and starting an issue posts `Started <branch>` on it, then reruns `frontier.py issues`: the earliest live `Started` holds the issue (a later one takes over only after the holder has been silent a day), so a late starter backs off and a confirmed holder is never displaced. A branch is taken only while the session on its newest `Started` comment is live, meaning some comment it tagged on the parent or any sub-issue is under a day old. Liveness now belongs to the claimant, so another session's comments no longer keep a dead claim alive, and comments on sub-issues (where rulings and review rounds go on GitHub) count. Resuming posts `Resumes: <id>` before loading implement, and pause's status comment carries its session tag; the `Resumes` line makes the paused session's branches this run's own; it replaces the branch list in the status comment as the record of ownership.
- Map-decision claims use the same claimant-keyed liveness through `frontier.py claim`: the first claim holds until its session has been silent a day; a claim made after that takes over, and the old session coming back doesn't take it back. Rerun `compost:setup` to refresh `docs/agents/issue-tracker.md`. A claim posted by 0.34 names a branch or time rather than a tagged session, so it expires a day after posting even while that session works.
- `compost:implement`'s rolling window starts a dependant once its blocker is ticked (reviewed and landed), not merely merged, matching the one definition of done. The draft PR's `Closes` line (implement and `compost:finish`) leaves out sub-issues another session holds, and the parent while any is held.
- `compost:implement` says to load implement again after a mid-run `compost:finish`, and that the Stop hook sends a stop back only once.

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
