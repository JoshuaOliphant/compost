# Proving frontend work

Depth for `compost:verify` step 6. Unit tests prove the code; only the running app proves what a
user sees. This applies when the parent issue has a `## Frontend` section, or when the diff
changes UI files under a parent without one.

## What counts as UI files

A file whose change can alter what a page renders:

- markup and templates: `.html`, Jinja, Django or ERB templates, `templates/`
- components: `.tsx`, `.jsx`, `.vue`, `.svelte`, `.astro`
- styles: `.css`, `.scss`, `.sass`, `.less`, Tailwind config
- static assets a page shows: images, icons, fonts under `static/`, `public/`, `assets/`
- the routes and view code that pick what a page renders

Tests, stories, and build config alone don't count. With no Frontend section, list the UI files the
diff touches (`git diff --name-only <base>...HEAD`). Any match is an undeclared frontend change:
say so in the report and prove it like declared frontend work. Running unattended, under
`compost:implement`, or as a worker, post it on the issue as a ruling: which files, why they are
UI, and that verify applied the e2e and screenshot rules to them.

## The e2e tests

Read the E2E entry in `docs/agents/testing.md`: Tool, Tests, Start app, Baselines. With
`Tool: none`, no entry, or a tool the project's dependencies lack, no e2e test can run and every
user-visible AC-N is unmet: fail verify naming them, and send the issue back to `compost:build`
to add the tool the way `compost:slice` step 3 describes.

Start the app with the Start app command, in the background, and wait until its URL answers. A
Playwright config with a `webServer` block starts it for you. Run the tests under Tests. Each
user-visible AC-N maps to one of them in the AC table, and that test must drive the app (load the
page, act, check what renders), not call the code behind it.

A failing e2e test gets exactly one rerun of the failures alone: `npx playwright test
--last-failed`, `uv run pytest --lf <tests path>`, or `npx cypress run --spec <file>`.

- Fails again: verify fails, naming the test and quoting both failures.
- Passes: the test is flaky. Verify goes on, lists it under Risk, and files an issue titled
  `Flaky e2e test: <test>` in the tracker with both runs' output. The report's Flaky list
  names the test and that issue's id. A test the tool's own `retries` marked flaky counts too.

## Screenshots

Find the screens the diff changes: each Frontend bullet names a page, and each changed UI file
maps to the pages that render it. Capture each one from the running app with the e2e tool
(`page.screenshot(path=..., full_page=True)` in pytest-playwright,
`await page.screenshot({ path, fullPage: true })` or `npx playwright screenshot <url> <file>`
with Playwright, `cy.screenshot()` in Cypress) into a temp directory outside the worktree. Drive
the page to the state the AC-N describes first.

Read every screenshot. For each, write one line of what it shows against the Then of the AC-N it
concerns, such as "AC-4: the settings page shows the Export button under Data, enabled". A
screenshot that doesn't show its Then leaves that AC unmet, whatever the test said.

## Baselines

Pixel comparison runs only against a baseline that already exists: a file under the Baselines
path for that screen. Run it with the tool's comparison (`toHaveScreenshot` in Playwright) and
`--update-snapshots=none`. A diff the AC asks for means the branch must update that baseline:
back to `compost:build`. Any other diff fails verify.

Never create a baseline. Playwright writes a missing one by default, so pass
`--update-snapshots=none` on every run, and after the run check `git status --porcelain`: delete
any new file under the Baselines path or a `*-snapshots/` directory before anything is committed.
With `Baselines: none`, there is no comparison to run.

## The screenshots branch

Screenshots never go on the feature branch. They go on `screenshots/<feature branch>`, an orphan
branch that is never merged, at `<issue id>/<AC-N>-<screen>.png`:

```bash
feature=$(git branch --show-current)
branch="screenshots/$feature"
dir=$(mktemp -d)
if git fetch origin "$branch"; then
  git worktree add -B "$branch" "$dir" "origin/$branch"
else
  git worktree add --orphan -b "$branch" "$dir"
fi
mkdir -p "$dir/<issue id>" && cp <shots>/<AC-N>-<screen>.png "$dir/<issue id>/"
git -C "$dir" add . && git -C "$dir" commit -m "screenshots: <issue id>"
git -C "$dir" push origin "$branch" || { git -C "$dir" pull --rebase origin "$branch" && git -C "$dir" push origin "$branch"; }
git worktree remove "$dir"
```

Parallel lanes push to the same branch; each writes only its own issue's directory, so the rebase
after a rejected push never conflicts. The report's Screenshots list gives each AC-N, the raw URL
of its file on that branch (on GitHub,
`https://raw.githubusercontent.com/<owner>/<repo>/screenshots/<feature branch>/<issue id>/<AC-N>-<screen>.png`),
and the line of what it shows.
