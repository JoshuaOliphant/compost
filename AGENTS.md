# AGENTS.md

This file provides guidance to coding agents (Claude Code reads it natively) when working in this repository.

## Project overview

compost is one Claude Code plugin: a software-engineering workflow made from several skill
collections, tracked against them in `plugin/pile.toml`. This repo is also its own marketplace
(`compost`), and the `oliphant-plugins` marketplace in
[JoshuaOliphant/claude-plugins](https://github.com/JoshuaOliphant/claude-plugins) lists it too,
through a `git-subdir` source pointing at `plugin/` here. Its history up to the split lives in
that repo; `#N` references in old commit messages were rewritten to `JoshuaOliphant/claude-plugins#N`.

## Layout

```
compost/
├── .claude-plugin/marketplace.json   # one plugin, source ./plugin; carries no version
├── plugin/                           # what installs: skills, agents, hooks, workflows, canon, scripts, tests
│   ├── .claude-plugin/plugin.json    # the version's source of truth
│   ├── CHANGELOG.md CONTEXT.md NOTICE README.md pile.toml
│   └── pyproject.toml                # the plugin's dev group and its 100% coverage gate
├── experiments/                      # eval harnesses and results; never installed
├── scripts/check_version_bumps.py    # CI on PRs into main: version above main's, with a changelog entry
├── docs/agents/                      # how the compost skills work in this repo
└── pyproject.toml                    # root dev group (pytest, ruff) for scripts/ and experiments/
```

compost has no state machine: each skill ends with Next moves naming the skills that usually
follow, and work is tracked in the repo's issue tracker. Its `[replaces]` table in `pile.toml`
lists the plugins and skills it supersedes, which `compost:setup` offers to switch off. Its
vocabulary is in `plugin/CONTEXT.md`; the workflow is described in `plugin/README.md`.

## Model IDs

Use the current family in examples and generated code: `claude-opus-5-5`, `claude-sonnet-5-5`,
`claude-haiku-5-5`, and `claude-fable-5-1` for the most demanding reasoning. Subagent frontmatter
uses the aliases `opus` / `sonnet` / `haiku` / `fable`.

## Versioning

`plugin/.claude-plugin/plugin.json` is the only version. Neither marketplace entry carries one.

When changing anything under `plugin/` outside `plugin/tests/`:
1. Bump the version in `plugin/.claude-plugin/plugin.json`.
2. Add a `## [<new version>] - YYYY-MM-DD` section to `plugin/CHANGELOG.md`, in the same commit as
   the bump. Format is [Keep a Changelog](https://keepachangelog.com/en/1.1.0/): newest first,
   grouped under `### Added`, `### Changed`, `### Fixed`, `### Removed`, one bullet per
   user-visible change.

On an integration branch that merges several issues (a `compost:implement` run), lanes leave the
version alone and the orchestrator bumps once, in a commit right after the first lane lands. CI
enforces the rule on pull requests into `main` with `python scripts/check_version_bumps.py`
(base `origin/main`). The version must be strictly greater than the one on current `main`, not the
fork point: two branches that both bump 0.8.1 to 0.9.0 pass alone, but the second fails once the
first has merged, because an install that recorded 0.9.0 never re-fetches it. When the check fails
that way, bump past `main`'s version.

## Agent skills

### Issue tracker

GitHub issues via `gh`; specs are parent issues labelled `spec`, slices are sub-issues. See
`docs/agents/issue-tracker.md`.

### Domain docs

Single context, glossary in `plugin/CONTEXT.md`. See `docs/agents/domain.md`.

### Tests and gates

pytest; the 100% coverage gate runs from `plugin/`. See `docs/agents/testing.md`.

### Observability

None: nothing here runs long enough to observe. See `docs/agents/observability.md`.

### Docs

Code is the source of truth; docs hold only what it can't say, in the core docs. Put a new fact in
a name, type, test, or comment before a core doc, and never in a new file. See `docs/agents/docs.md`.
