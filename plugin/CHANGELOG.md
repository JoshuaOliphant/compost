# Changelog

All notable changes to the compost plugin. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions are `plugin.json` versions.

## [0.58.0] - 2026-11-27

### Changed

- A review skeptic judges the claim the reviewer made: what it says the code does and the harm it says follows. Its verdict gains `harm` (`reached`, `rule` or `none`): a skeptic that upholds a finding whose claimed harm it could not find, and whose claimed rule the base doesn't document or the code doesn't break outright, has refuted it, and the workflow counts it so. A harm is refuted only where the skeptic shows the file:line it stops at (a guard, a loud failure, a search that finds nothing reaching it), never by arguing that untrusted text crossing a quoting boundary won't be misread; a claim holds when any path it names reaches the harm; and a different, smaller defect left over is named in the reason, not upheld in the claim's place. A missing or misquoted citation and a spec that doesn't mention the defect still don't refute a harm that happens (OLI-155).
- The skeptic grades severity by the reviewer's rubric, quoted in its task with the review guide's Failure section, by the kind of harm that happens rather than its likelihood. Its verdict gains `limit`: a skeptic lowers a finding more than one step only with the file:line that caps the harm, and without one the workflow lowers it one step. In the review-recall eval 0.57.0's skeptic lowered 34 of 38 upheld findings and kept 3 of 9 wrong claims refuted (OLI-155).
- A skeptic sets `introduced` to false only when the claimed harm happens the same way at the base. A diff that adds the path, caller, or input reaching an older line, or adds a check that misses it, introduced the defect, so it is judged on the branch rather than sent to `preExisting` (OLI-155; the jev-cache-partial loss in the review-recall eval).

## [0.57.0] - 2026-11-27

### Changed

- A review skeptic refutes a finding only when it shows at a `file:line` that the code doesn't behave as claimed (or the finding is a linter nit, an ask nobody needs, or an unreachable state). A real defect with a misquoted rule, an overstated severity, or a spec that doesn't mention it is upheld instead: the skeptic's verdict is `uphold`, `refute` or `unsure`, with the severity the defect deserves, a citation `correction`, whether this diff `introduced` it, and for Spec findings `outsideSpec`. The workflow keeps a lower severity (never a higher one; `reviewerSeverity` records the original), keeps the correction, sends a defect the diff didn't introduce at an untouched line to `preExisting`, moves a real defect outside the spec to the Standards axis, and keeps an unsure finding as a minor. A finding a skeptic lowered to minor is exempt from the minor cap. "When you are uncertain, it is refuted" is gone. In the review-recall eval the old rule refuted 3 of 13 real bugs (OLI-133, OLI-153).

## [0.56.0] - 2026-11-27

### Changed

- verify names two outcomes for a check that can't reach the code, neither of them failed and neither a fix loop: `unreachable` (the state the check needs is one nothing creates; the user is asked to delete the branch or say what reaches it) and `could_not_boot` (the app or a service it needs won't start; the check is reported unverified with its evidence). A skip written into a test stays unmet. A verifier that ran out of ideas gets one more attempt with a sharper brief, then is recorded as `could_not_boot` with both attempts as evidence. Such a criterion is not met but never goes to build; "done" and the stamp's `ac` field name it (`"6/7, 1 unreachable"`). From ray-amjad/skills' verify-round (OLI-151).
- spec places a Bounded or Architectural request on a rework ladder (rerun, unpick, migrate, can't undo) before the first round; a migrate or can't-undo request gets an early critique, where a fresh agent attacks a draft built from the facts and each finding becomes a re-check, an area to cover, or a question. The readiness record ends with a numbered defaults-to-veto list that confirming the spec accepts unless the user vetoes a number; auth, credentials, untrusted input, read access, destructive actions and a sole copy of data never go on it. From ray-amjad/skills' idea-to-spec (OLI-152).

## [0.55.0] - 2026-11-27

### Changed

- `compost:retro` counts reviewer misses by trigger (OLI-146). Before filing a proposed `REVIEW.md` check it lists the open `review-rule` issues: a new trigger is filed with that label; a trigger already open is its second miss, so retro comments the new Source there and opens the check as its own draft pull request off the default branch, never inside the change that had the miss. A miss now names its later catchers (red CI on the diff's own logic, the merge result, the user, a revert, a bug against merged work), and `compost:finish` names a CI failure the diff caused after review passed under Risk, where retro finds it.
- A review finding that asks for new handling of a state (a null, an empty list, an error, a retry, a race) must quote the caller, route, or input that produces it, or it is at most minor; the skeptic refutes one whose state nothing reaches (OLI-147).
- `compost:finish` re-reads the PR's review threads and conversation and the issue's comments before it merges, down to its merge-decision report: a new commit or thread goes back through step 5, and a person's comment that changes intent stops the merge (OLI-148). The GitHub **Review threads** command also reads the PR's conversation comments.
- `pile.toml` tracks ray-amjad/skills as an input (OLI-149), for the miss count and the reaching-path rule above, both from its task-lifecycle skill; NOTICE lists it. The re-read before merge comes from Anthropic's "Worse Together" study, not from ray-amjad/skills.

## [0.54.1] - 2026-11-27

### Fixed

- The stop-guard Stop hook no longer lets a reload of implement widen the run contract's stops (OLI-135). The first `Run contract stops:` block in the transcript, printed after the first implement load, is the ceiling for the whole session; the block since the latest load counts only for the stops the ceiling also lists, so a reload can narrow the stops, never widen them.
## [0.54.0] - 2026-11-26

### Added

- `compost:ketchup` (OLI-138), adapted from pstack's ketchup: on `/compost:ketchup`, Claude catches the user up on everything since their last message and lists every call waiting on them, each with its pick, evidence, and risk, so it can be decided from the reply alone. It is read-only, reads the run's state from the tracker and git (parent checklist, status comment, rulings, run-contract stops, live PR and CI state) as well as the conversation, names things by the glossary's terms, and draws only Mermaid diagrams and the screenshots `compost:verify` took.
- `compost:reframe` (OLI-139), adapted from pstack's reframe: on `/compost:reframe`, Claude gives the expert terms for a problem the user can't name yet, ranked by how much each changes what gets built, each tied to their description and a source it opened and confirmed, plus terms from neighboring fields, then rewrites the description. It uses the glossary's word where one exists and leaves `CONTEXT.md` to `compost:spec`.
- `compost:automate-me` (OLI-141), adapted from pstack's automate-me: on `/compost:automate-me`, Claude mines this project's Claude Code transcripts (never other projects') in parallel slices, keeps conventions seen in two or more, confirms them with structured questions, and writes or updates a personal, user-invoked `<handle>-mode` skill, offering the user-level CLAUDE.md for rules that must apply every turn.

### Changed

- `compost:spec`'s glossary format bolds another glossary term when a definition mentions it, and the sentence says how the two relate (OLI-140, from mattpocock/skills).
- The routing eval (`jev.py route`) routes only over skills Claude may load on its own: a skill with `disable-model-invocation: true` (wait-what, ketchup, reframe, automate-me) can't be picked by the model, so counting it as a route measured nothing real. ketchup had taken a "what's the status" prompt and dropped the eval to 26/30; without it the eval scores 28/30, as main did on the same run. The flag is read from the frontmatter alone, quoted or not, so a `disable-model-invocation: true` line in a skill's body doesn't hide it.
- Upstream pins move to the heads the 2026-11-26 turn read: mattpocock 6f7f783, pstack b7b93c3, code-guardian 9a01d29, swyx-skills 0d3e9b4 (OLI-137).

## [0.53.0] - 2026-11-25

### Added

- `compost:spec` ends with a readiness check and posts a run contract on the parent (OLI-122): Stops (compost's fixed list plus any the spec adds; the five irreversible stops can't be dropped, and each stop is its own bullet), Prerequisites (what only a person can supply, each with a check, confirmed or unconfirmed), and Departures. The result goes on the parent as a readiness record: a short check for bounded work, a full one with rabbit holes, no-gos, and a pre-mortem for architectural work. Bounded work hands off with no approval; architectural work asks once, naming the spec and its run contract.
- `compost:spec` declares frontend work (OLI-125): a parent that changes a rendered page or component gets a Frontend section naming each user-facing flow, every user-visible Then names an e2e test as its proof, and the readiness check fails one that doesn't.
- `compost:setup` records an E2E entry in `docs/agents/testing.md` (OLI-124): the e2e tool, where its tests live, the command that starts the app, and where screenshot baselines live. It adopts the tool in use, recommends Playwright in the stack's flavour (`pytest-playwright` or `@playwright/test`) for a repo that renders pages or components, and records `Tool: none` otherwise. When a frontend spec meets a repo without the tool, `compost:slice` has the first frontend issue install it, fill the E2E entry, and add its run as a gate.
- `compost:verify` proves frontend work in the running app (OLI-126), in a new step 6 with `references/frontend.md`: each user-visible AC-N needs a passing e2e test that drives the app, and one mapped only to a unit test fails verify; each changed screen is screenshotted from the running app, read against its AC-N, and pushed to a `screenshots/<feature branch>` branch that is never merged; a pixel comparison runs only against baselines the repo already has, and none is created; a UI change under a parent with no Frontend section is flagged and held to the same proof. A failing e2e test gets exactly one rerun with the tool's own retries off: a pass is listed as flaky under Risk with a filed issue, a second failure fails verify.
- `compost:finish` shows verify's screenshots under Validation in the pull request, each with its AC-N and raw URL on the screenshots branch, and lists flaky e2e tests with their filed issues under Risk (OLI-127).

### Changed

- `compost:implement` keeps to the parent's run contract (OLI-123): it reads its run-contract reference first and, before anything that can stop the run, prints the contract's Stops as a `Run contract stops:` block; it runs the readiness check itself on a parent with no readiness record (gaps become rulings marked `(assumed)`) and checks each prerequisite before any worker branches. A missing or unconfirmed prerequisite is the eighth allowed stop.
- The stop-guard Stop hook reads the first `Run contract stops:` block since implement last loaded (a later block can't widen it) and allows the contract's added stops beside the fixed list, with no tracker call.
- `compost:implement` says again that committing, pushing the feature branch, and opening the draft PR need no one's OK; only the merge does.
- `compost:implement`'s close-out loads `compost:finish`, which posts the PR body (on the issue file with a local tracker), instead of ending on the feature branch's name.
- `compost:verify`'s steps after the new frontend step move from 6-9 to 7-10, so the verify stamp is written in step 10; references that cite them, including finish and the verify gate's message, follow.

## [0.52.0] - 2026-11-25

### Added

- Verify stamps and a push gate (OLI-109). `compost:verify` step 9 stamps the commit it verified as a git note under `refs/notes/compost-verify` (`scripts/stamp.py write|show|log`), and `compost:finish` reads the stamp on HEAD instead of trusting memory, then pushes the notes. A new PreToolUse hook, `scripts/verify_gate.py`, watches `git push` and PR creates (`gh`, `glab`), judging every commit a push sends (or the PR's head branch); deletes, wildcards and `refs/notes/` refspecs are never gated, and `--all`, `--mirror`, `--branches` and a wildcard-only push judge HEAD only. With `COMPOST_VERIFY_GATE` unset it observes: an unstamped commit goes through and is logged to `~/.claude/verify-gate/log.jsonl`. `enforce` blocks twice per session, then lets every later attempt in that session through as a logged bypass; `off` disables it.
- Diff-triggered checks (OLI-111). A `## Checks` section in the base's REVIEW.md lists items with a Trigger, a Check, and a Source. review-changes decides which ones the diff triggers, sends those to the Standards reviewer, and fails the axis unless each one is answered at a `file:line`. diagnose, retro, and review propose new checks after a miss, and prune removes stale ones. compost's own REVIEW.md starts with four checks from real incidents.
- A recorded smoke command (OLI-110). `compost:setup` writes a `## Run` section into `docs/agents/testing.md`: a smoke command that boots the app and drives one real flow, plus a feature map. `compost:verify` reaches the "reproduced live" rung through it, and `compost:build` tries it before `/run`. compost has its own `scripts/smoke`: it installs the plugin from the working tree into a throwaway config, runs its Stop hooks, and runs one haiku turn that must load a compost skill.
- Gate drift (OLI-113). `scripts/gate_drift.py <base> <head>` lists every edit a branch makes to the checks that judge it: changed gate files, added weakeners (`pragma: no cover`, `noqa`, skips, threshold or ignore config, sleeps or retries in tests), and removed tests. `compost:verify` reads the gates as recorded at the base, runs those too, and needs a ruling for every gate change. `compost:finish` lists them under Risk.

## [0.51.0] - 2026-11-25

### Changed

- Jev's test tools (find-test, duplicate-test, ac-exercised) read Go, Rust, Java, and Kotlin suites, not only Python and JS/TS (OLI-132). Go takes `Test*`, `Example*`, and `Fuzz*` functions in `*_test.go` as `go test` names them (not `TestMain` or `Testable`); Rust takes functions under `#[test]`, `#[tokio::test]`, and `#[rstest]`, keyed by their `mod` path; Java and Kotlin take methods under `@Test` and its JUnit relatives in `Test*`, `*Test(s)`, `*TestCase`, and `*IT` files (JUnit style; Kotest and Spek DSL specs are not read). Each test's source runs to its closing brace, ignoring braces inside one-line strings, rune and char literals, and comments; a literal or comment that spans lines still counts, within an 80-line cap. Two tests that read as one id in a file both stay, the second as `name#2`. ac-exercised reads a Go subtest id, `TestX/case`, as a case of `TestX`. JS/TS also reads `.mts` and `.cts`. `target/`, `vendor/`, and compost's own `.worktrees/` are skipped in every language, so a repo with a build worktree open no longer sees each test twice.
- build, verify, and diagnose no longer assume Python. build's survey names each stack's fixtures and case tables; build, verify, and diagnose say to skip Jev's test tools with a one-line note when the suite is in a language they do not read, instead of calling them and getting `no tests found`. verify's coverage gate names the other stacks' tools, and its `test-value` reference says how to turn a Go, Rust, JS, or JaCoCo report into `uncovered` lines. jev-lint and thin.py stay Python-only and the skills now say so where they are called.

## [0.48.0] - 2026-11-21

### Changed

- The stop-guard Stop hook loads Jev and the TypeSafe SDK only when it has a message to judge (OLI-78). It runs on every turn of every session but acts only during a `compost:implement` run; with no run open it now takes about 55 ms instead of 250 ms (median, same machine). It looks the SDK up with `find_spec` first, so under plain python3 the re-exec under uv still happens before it reads the hook's input. Behavior during an implement run is unchanged.
- `compost:diagnose`'s agent-eval rung lists harness checks to make before trusting its rate (OLI-79): count no-answer trials apart from failures, start each trial clean, check the model that served it, give the prompt the symptom rather than the answer, add a case where the action is right, and read the transcripts when a fix scores worse.
- `pile.toml` notes on the code-guardian and anthropic-skills references name the ideas OLI-78 and OLI-79 took from them. Both stay references: compost wrote those ideas in its own words and took no text.

## [0.47.1] - 2026-11-21

### Changed

- `pile.toml` pins move to each source's head as of the 2026-11-21 turn (mattpocock, superpowers, pstack, code-guardian, anthropic-skills, vercel-skills, swyx-skills), so `/compost:turn` reports only what changed after it. The turn filed OLI-78 (stop-guard start cost) and OLI-79 (agent-eval harness checks).

## [0.47.0] - 2026-11-21

### Changed

- `/compost:review-changes` reads `REVIEW.md` and the standards sources (CLAUDE.md, AGENTS.md, CONTEXT.md, ADRs, and the rest) as they stand at the base, the branch the change merges into, with `git show <base>:<path>`, never from disk (OLI-72). A branch is no longer judged by its own edits to its rules: a `Skip:` line it adds, or a rule it drops, takes effect once it merges, and reviewers review those edits as changes. A review whose checkout isn't the head under review no longer picks up the checkout's guide. Reviewers and skeptics are told the standards are the base's.

## [0.46.0] - 2026-11-21

### Fixed

- `/compost:review-changes` grades a local tracker's issue given as its file path (`issue: ".scratch/<feature>/issues/01-x.md"`). Before, scope reported a file it read as a spec file with no id, so the workflow failed the Spec axis with "the scoping agent fetched  instead", and every per-issue review in a local-tracker `compost:implement` run lost its Spec half. When the given issue is a `.md` path and scope reports no id, the fetch now matches on its source; an id issue that comes back without its id is still refused.

## [0.44.0] - 2026-11-21

### Added

- `compost:setup` offers a Linear tracker (OLI-73): `references/issue-tracker-linear.md` records the connector commands, the label vocabulary, and how a run reads states and claims.
- `frontier.py` takes `--tracker linear --snapshot FILE`: the agent reads the parent, its sub-issues, blockers, and comments with the Linear connector (MCP only, so a script cannot call it) and writes them to JSON; `issues` and `claim` then print the same states as for the other trackers. A Linear branch name (`oli-17-slug`, or `user/oli-17-slug`) counts as issue 17's branch. `--snapshot` goes only with `--tracker linear`.

## [0.42.0] - 2026-11-21

### Added

- `compost:diagnose`'s feedback-loop ladder has an agent-eval rung for bugs in what a model or agent did, where no code path reaches the symptom. The case is built from the incident: the real failure written down with what the agent did kept apart from why, the setup it decided in rebuilt before anything is invented, the real agent run headless with assertions on its tool calls and output (not its explanation), and a failure rate reported with its denominator. One trial is the loop while iterating; the rate over the same N trials, before and after the fix, is the proof, and a failure that doesn't show is reported as not observed. The headless agent gets back the skills and plugins it had, and on a flaky loop step 3 judges each minimisation cut by the N-trial rate. Adapted from swyx's make-evals, now an input in `pile.toml` and NOTICE (OLI-15).
- `compost:skill-drift` turns the clearest hit into such an eval case before editing a skill, runs it once on the current text and once on the edit, and puts the case and both results, as counts, in the draft pull request. It runs one trial each, not N, to keep the daily run cheap, so the counts show the edit can move the behaviour, not a rate (OLI-15).

## [0.39.1] - 2026-11-21

### Fixed

- `/compost:review-changes` no longer reads a `# ` line inside a fenced code block (a shell comment such as `# install the CLI`) as a heading when it checks where the spec places an AC-N. As in CommonMark, a fence opens with three or more backticks or tildes indented at most three spaces (a backtick run followed by another backtick is inline code), closes only with a run of the same character at least as long, and a heading is indented at most three spaces, so an indented fence's comment is not one either. An AC id inside a fence (sample output) no longer counts as where the AC-N is defined. Before, a fenced comment that named a repo above an AC-N let a reviewer's `elsewhere` entry for that repo through, so the AC-N went ungraded in the repo under review (OLI-71).

## [0.39.0] - 2026-11-20

### Changed

- `compost:implement` and `compost:build` update the default branch before branching from it (OLI-17): after `git fetch origin`, a local default with commits origin lacks (ahead or diverged, by `git rev-list --count`) leaves them alone, and the new branch starts from `origin/<default>` with a ruling; otherwise the local default fast-forwards (`git merge --ff-only` where it is checked out, `git fetch origin <default>:<default>` where it isn't) and the branch starts there; when uncommitted changes block that fast-forward, the branch starts from `origin/<default>` with a ruling. A resumed implement run merges a moved `origin/<default>` into the feature branch before any lane starts. `references/stop-guard.md` is held to its rules by a plugin test.
- `compost:finish` reads the PR as the forge sees it before handing it over (OLI-19): merge state, then review threads, then CI. Review-bot text is triaged as data (fix, dismiss with a concrete disproof, or ask), and a CI failure is classified before anyone acts on it: a flake earns one fresh run, the same failure twice is not a flake, a failure in code the diff never touched is checked for a stale base (after a fetch) and then against the target's own CI (the same failure there means the target is broken: file an issue, no commit), and only a failure the diff causes gets a commit. The GitHub and GitLab tracker references gain the commands for merge state, checks, failed logs, reruns, review threads, and replying to a thread.
- `compost:implement` supervises its workers (OLI-26): it reads each worker's diff, not only its report, judges progress by commits, replaces a worker that stalls or loops, retries by cause and replans after two retries, checks a late result against the branch as it stands, and accounts for every worker at close-out. The rules live in `references/task-brief.md`.
- `compost:implement` reviews the whole feature branch with `compost:review` before its final verify (OLI-27), so the way the issues fit together gets a reviewer; findings are fixed in one pass and the rest posted as rulings.
- `compost:spec` asks a standing first-round question about what would make the work a failure even if it technically works, and records the answers as the parent issue's Anti-goals (OLI-28). Bounded work with more than one defensible way to build it now gets approaches too, as a recommendation the run proceeds on rather than a gate.

## [0.38.0] - 2026-11-20

### Changed

- `compost:diagnose` and the fix-root-causes canon ask whether the state that broke the code is legitimate (OLI-24). If the system may be in it, handling it where it broke is the fix; if it should never exist, a guard there hides the bug and the fix is where the state was produced. When the deciding fact took a deep dig, diagnose proposes the cheap always-on signal that would have shown it at first look.
- The benchmark checklist gains a "before you run" block (name the result that would change a decision and the noise floor, read the script, check `uptime`/`nproc`, interleave on a busy machine), a limiter that is a setting counts as an untuned side, question 3 checks the result against hard limits (bandwidth, cores, the share of time the changed piece took), and eval results get the same questions (OLI-23).
- `compost:skill-drift` writes each fix in the form that matches the failure: a prohibition with its reason for a rule skipped under pressure, a recipe for output of the wrong shape, a required slot for a missing element, a condition on something observable for behaviour that depends on a case; no nuance or exemption clauses (OLI-21).
- The make-mistakes-impossible canon adds the repeat rule (a mistake against a written rule counts as a class at once and is fixed at the highest level that works, never with a second copy of the rule), ratcheting checks for common patterns, one-line check suppressions with a reason and an expiry date, and fixing or deleting tests that guard nothing; `compost:retro` applies the repeat rule when it places a fix (OLI-25).
- `compost:deepen` says, for each candidate, what a test through the new seam catches and what it misses (OLI-30).

### Fixed

- The GitLab tracker reference lists issues with `glab issue list -O json`; `-F` there picks `details`, `ids`, or `urls`, not JSON (OLI-34).
- The GitHub tracker reference checks, before the first `gh` call of a session or subagent, that `{owner}/{repo}` is origin and not a fork's upstream parent (`gh api` ranks a remote named `upstream` first and ignores `gh repo set-default`), comparing names without case; when they differ, every `gh` call is prefixed with `GH_REPO=<origin's owner/name>`. `compost:setup` runs that check before it reads `has_issues`. `frontier.py` reads origin's repo by name unless `GH_REPO` is set, and prints a note on stderr when an `upstream` or `github` remote would have won. A tracker doc written before this release has no fork check: every skill and agent that reads the doc (`compost:build`, `compost:spec`, `compost:slice`, `compost:retro`, `compost:implement`, `compost:finish`, `compost:pause`, `compost:prune`, and the review workflow's scope and reviewer agents) takes it from setup's reference, a plugin test holds each one to that, and rerunning `compost:setup` adds it to the doc. `frontier.py` stops at the first of `upstream` and `github` that exists, as gh does, so a clone whose `upstream` is origin gets no note (OLI-31).

## [0.37.1] - 2026-11-20

### Changed

- The `/compost:review-changes` skeptic prompt keeps a one-line checklist beside its refute rule (read the cited code and what it depends on, check the rule or AC-N exists and says what is claimed and that nothing elsewhere (a test, a caller, a later hunk) already answers it, refute linter-owned nits and asks nobody uses), so a skeptic still knows what to check if the `compost:skeptic` definition does not load.

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
