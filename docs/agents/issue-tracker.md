# Issue tracker: Linear

Specs, slices, and maps for this repo live as Linear issues in the Oliphant workspace: team `OLI`,
project `Compost`. Use the Linear connector's tools (`mcp__Linear__*`); there is no CLI. Pull
requests stay on GitHub (see Pull requests below). Issues filed before 2026-11-20 were migrated from
GitHub issues of this repo; each links back to its GitHub issue, and the GitHub originals stay
open until the user closes them.

Always pass `team: "OLI"` and `project: "Compost"` when creating an issue. Identifiers look like
`OLI-17`. The migrated issues carry a `repo:compost` label; give new ones the same label.

## Commands

- **Create:** `save_issue` with `team`, `project`, `title`, `description` (Markdown, real newlines),
  `labels`. It returns the identifier.
- **Read:** `get_issue` (`id: "OLI-17"`), then `list_comments` (`issueId`); `get_issue` does not
  return comments.
- **List:** `list_issues` with `team: "OLI"`, `project: "Compost"`, and `label`, `state`,
  `parentId`, `query` as needed. Follow `cursor` while `hasNextPage` is true.
- **Comment:** `save_comment` with `issueId` and `body`.
- **Labels:** `save_issue` with `id` and `addLabels` / `removeLabels`. Never pass `labels` on an
  update: it replaces the whole set.
- **Close:** comment first, then `save_issue` with `id` and `state: "Done"` (`"Canceled"` for a
  won't-do). States on this team: Backlog, Todo, In Progress, In Review, Done, Canceled,
  Duplicate. Opening a pull request is not done: move the issue to `In Review` then, and to
  `Done` when the pull request merges.
- **Sub-issue:** `save_issue` with `parentId: "OLI-<parent>"` on create, or on an existing issue.
- **Blocking:** `save_issue` with `blockedBy: ["OLI-<n>"]`. Also write a `Blocked by OLI-<n>`
  line in the body, so the edge is readable everywhere.
- **Branch name:** use the issue's `gitBranchName` from `get_issue`; it contains the identifier,
  which links the branch and its pull request to the issue.

A bare `#42` in an issue body links to a GitHub pull request or issue in whichever repo Linear
guesses. Write `OLI-<n>` for Linear issues and a full URL for GitHub ones.

## Pull requests

Used by `compost:finish`. `{owner}/{repo}` fills in as above; `<n>` is the pull request number.

- **Default branch:** `gh api repos/{owner}/{repo} --jq .default_branch`.
- **Create (draft):** `gh api repos/{owner}/{repo}/pulls -f title="..." -f head=<branch> -f base=<target> -F draft=true -F body=@- --jq '.number, .html_url'`
  with the PR body as a heredoc on stdin.
- **Edit body:** `gh api -X PATCH repos/{owner}/{repo}/pulls/<n> -F body=@-` with a heredoc body.
- **Ready for review:** the forge refuses to merge a draft, and the public REST API has no
  endpoint for leaving draft. Locally, `gh pr ready <n>` (GraphQL). In a Claude Code cloud session
  that is blocked; use `gh api -X POST repos/{owner}/{repo}/pulls/<n>/ccr/ready_for_review`, an
  endpoint specific to cloud sessions that the 403 message names.
- **Merge (merge commit):** `gh api -X PUT repos/{owner}/{repo}/pulls/<n>/merge -f merge_method=merge`.
  Never `squash` or `rebase` unless the user asks.
- **Close without merging:** `gh api -X PATCH repos/{owner}/{repo}/pulls/<n> -f state=closed`.
- **Merge state:** `gh api repos/{owner}/{repo}/pulls/<n> --jq '{mergeable, mergeable_state, sha: .head.sha}'`.
  `mergeable` is `null` while GitHub is still computing it; read it again.
- **Checks:** `gh api --paginate repos/{owner}/{repo}/commits/<sha>/check-runs --jq '.check_runs[] | {id, name, status, conclusion}'`,
  plus `gh api repos/{owner}/{repo}/commits/<sha>/status --jq '.statuses[] | {context, state}'` for CI
  that reports commit statuses.
- **Failed log:** `gh api repos/{owner}/{repo}/actions/jobs/<check run id>/logs` (an Actions check
  run's id is its job id).
- **Rerun failed jobs:** `gh api -X POST repos/{owner}/{repo}/actions/runs/<run id>/rerun-failed-jobs`,
  the run id from `gh api repos/{owner}/{repo}/actions/jobs/<check run id> --jq .run_id`.
- **Review threads:** `gh api --paginate repos/{owner}/{repo}/pulls/<n>/comments --jq '.[] | {id, in_reply_to_id, user: .user.login, path, line, body}'`
  and `gh api --paginate repos/{owner}/{repo}/pulls/<n>/reviews --jq '.[] | {user: .user.login, state, body}'`,
  plus the PR's conversation, `gh api --paginate repos/{owner}/{repo}/issues/<n>/comments --jq '.[] | {user: .user.login, created_at, body}'`.
  REST can't see whether a thread is resolved, so a thread is open until it has a reply that
  settles it.
- **Reply to a thread:** `gh api repos/{owner}/{repo}/pulls/<n>/comments/<id>/replies -f body=...`.

## Labels

| Role | Label in this team | Meaning |
|---|---|---|
| Spec | `spec` | The parent issue holding a spec from `compost:spec` |
| Ready for agent | `ready-for-agent` | A slice an agent can build without a person |
| Ready for human | `ready-for-human` | A slice that needs a person (credentials, a manual step) |
| Map | `map` | A map issue for long, foggy work |
| Decision | `decision` | A decision sub-issue of a map |

All five exist on the OLI team. Linear's own `Bug`, `Feature` and `Improvement` labels are free for
the user's triage; compost never reads them.

## Records

- **Rulings** (a decision made without stopping: what, why, cost if wrong) are comments on the
  issue being worked, summarized in the pull request.
- **Progress** is the sub-issues of the parent plus the git log. Commits and pull request bodies
  name the issue (`OLI-<n>`); the issue reaches `Done` when its pull request merges.

## Map operations

Used by `compost:slice` for map issues.

- **Map:** one issue labelled `map`; its decisions are sub-issues labelled `decision`.
- **Frontier:** the map's open sub-issues (state not Done, Canceled, or Duplicate) with no open
  blocker (every `blockedBy` issue is Done) and no live claim; first in map order wins.
- **Claim:** post a comment `Claimed by <session>`, then snapshot the decision and its comments to
  JSON (format in `plugin/skills/setup/references/issue-tracker-linear.md`) and keep the claim only
  if `frontier.py claim OLI-<n> --tracker linear --snapshot <file>` prints your session. The
  `implement` states work the same way: `frontier.py issues OLI-<n> --tracker linear --snapshot <file>`.
- **Resolve:** comment the answer and close the issue (Commands above), then add the gist and link
  to the map's Decisions so far.
