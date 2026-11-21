# Issue tracker: Linear

Specs, slices, and maps for this repo live as Linear issues. Use the Linear connector's tools
(`mcp__Linear__*`); there is no CLI. Pull requests stay on the repo's forge: take the **Pull
requests** commands from [GitHub](issue-tracker-github.md) or [GitLab](issue-tracker-gitlab.md)
(whichever `git remote -v` points at) and copy that section into `docs/agents/issue-tracker.md`.

Record the workspace, the team key, and (if the repo has one) the project here, and pass `team`
(and `project`) on every create. Identifiers look like `<KEY>-17`; the examples use `OLI`.

## Commands

- **Create:** `save_issue` with `team`, `project`, `title`, `description` (Markdown, real newlines),
  `labels`. It returns the identifier.
- **Read:** `get_issue` (`id: "OLI-17"`), then `list_comments` (`issueId`); `get_issue` does not
  return comments.
- **List:** `list_issues` with `team`, `project`, and `label`, `state`, `parentId`, `query` as
  needed. Follow `cursor` while `hasNextPage` is true.
- **Comment:** `save_comment` with `issueId` and `body`.
- **Labels:** `save_issue` with `id` and `addLabels` / `removeLabels`. Never pass `labels` on an
  update: it replaces the whole set. Create a missing label with `save_issue_label`.
- **Close:** comment first, then `save_issue` with `id` and `state: "Done"` (`"Canceled"` for a
  won't-do). Check the team's states with `list_issue_statuses`; the default set is Backlog, Todo,
  In Progress, In Review, Done, Canceled, Duplicate. Opening a pull request is not done: move the
  issue to `In Review` then, and to `Done` when the pull request merges.
- **Sub-issue:** `save_issue` with `parentId: "OLI-<parent>"` on create, or on an existing issue.
- **Blocking:** `save_issue` with `blockedBy: ["OLI-<n>"]`. Also write a `Blocked by OLI-<n>`
  line in the body, so the edge is readable everywhere.
- **Branch name:** use the issue's `gitBranchName` from `get_issue`; it contains the identifier,
  which links the branch and its pull request to the issue.

A bare `#42` in an issue body links to a GitHub pull request or issue in whichever repo Linear
guesses. Write `OLI-<n>` for Linear issues and a full URL for GitHub ones.

## Labels

| Role | Label | Meaning |
|---|---|---|
| Spec | `spec` | The parent issue holding a spec from `compost:spec` |
| Ready for agent | `ready-for-agent` | A slice an agent can build without a person |
| Ready for human | `ready-for-human` | A slice that needs a person (credentials, a manual step) |
| Map | `map` | A map issue for long, foggy work |
| Decision | `decision` | A decision sub-issue of a map |

Linear's own `Bug`, `Feature` and `Improvement` labels are the user's to triage; compost never
reads them.

## Records

- **Rulings** (a decision made without stopping: what, why, cost if wrong) are comments on the
  issue being worked, summarized in the pull request.
- **Progress** is the sub-issues of the parent plus the git log. Commits and pull request bodies
  name the issue (`OLI-<n>`); the issue reaches `Done` when its pull request merges.

## Reading states with `frontier.py`

`frontier.py` cannot call the connector, so snapshot first. With the connector, read the parent
and every sub-issue (`list_issues` with `parentId`, `get_issue` with `includeRelations: true` for
`blockedBy`, `list_comments` for each), then write one JSON file in the scratchpad:

```json
{"issues": [
  {"identifier": "OLI-10", "state": "In Progress", "labels": ["spec"], "description": "...",
   "children": ["OLI-11", "OLI-12"], "blockedBy": [], "comments": []},
  {"identifier": "OLI-12", "state": "Todo", "labels": ["ready-for-agent"], "description": "...",
   "children": [], "blockedBy": ["OLI-11"],
   "comments": [{"body": "Started oli-12-slug\n\ncompost-session: s-1a2b", "createdAt": "2026-11-21T06:00:00Z"}]}
]}
```

Include any blocker that is not itself a sub-issue, so a Done one counts. Then run
`frontier.py issues OLI-10 --tracker linear --snapshot <file>`. A snapshot is a moment in time:
write it fresh before each run. A branch named `oli-12-slug` or `user/oli-12-slug` (Linear's
`gitBranchName`) counts as issue 12's branch.

## Map operations

Used by `compost:slice` for map issues.

- **Map:** one issue labelled `map`; its decisions are sub-issues labelled `decision`.
- **Frontier:** the map's open sub-issues (state not Done, Canceled, or Duplicate) with no open
  blocker (every `blockedBy` issue is Done) and no live claim; first in map order wins.
- **Claim:** post a comment `Claimed by <session>`, then snapshot the decision (as above, with its
  comments) and keep the claim only if `frontier.py claim OLI-<n> --tracker linear --snapshot <file>`
  prints your session (the earliest claim whose session is live).
- **Resolve:** comment the answer and close the issue (Commands above), then add the gist and link
  to the map's Decisions so far.
