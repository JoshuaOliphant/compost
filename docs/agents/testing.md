# Tests and gates

## Test convention

pytest, adopted from the existing suite.

- The plugin's tests live in `plugin/tests/`. Shared fixtures are in `plugin/tests/conftest.py`,
  which also puts `plugin/scripts/` on the import path.
- The repo-level version check keeps its tests in `scripts/tests/`, collected by the root
  `pytest` run, which also collects the experiment harnesses' tests under `experiments/`.
- Each acceptance criterion AC-N maps to a test node id or parametrize id, recorded in the
  issue's AC table.
- BDD feature files: no.

## Gates

`compost:verify` runs these in order and stops at the first failure. CI runs all of them.

| Gate | Command | Status |
|---|---|---|
| Coverage | `cd plugin && uv run --group dev pytest` | passing |
| Repo tests | `uv run --group dev pytest -q` (version check, experiment harnesses) | passing |
| Lint | `uv run --group dev ruff check .` | passing |
| Format | `uv run --group dev ruff format --check .` | passing |

The live Jev evals (`pytest -m jev`, from `plugin/`) are not a gate: they need a TypeSafe key (or an
Ollaya server, though their floors were set on Jev) and the private compost-evals checkout.

## Coverage

Threshold: 100% line coverage, enforced by `fail_under = 100` in `plugin/pyproject.toml`. The repo-level scripts and
experiments are not gated; new Python there still aims for 100%. It is a gate, not a target to pad: when reaching it would take
tests that prove nothing, bring the uncovered lines to the user with a proposed exclusion or a
lower threshold. When running unattended, under `compost:implement`, or as a worker, post the
proposal as a ruling comment on the issue, list it in the PR's Risk section, and continue; the
user decides at `compost:finish`.

Exclusions agreed so far:

- `if __name__ == "__main__":` guards (`exclude_also` in compost's coverage config).

## Mutation

Tool: thin.py survivors, compost's own. Status: working, last proved on this tool's own branch
(JoshuaOliphant/claude-plugins#123): 219 mutants on 134 changed lines of `scripts/thin.py`, 184 killed, 11 survived, 1 timeout,
23 crashed, 348s.

`compost:verify` runs this over the branch's diff and sorts every surviving mutant as unprotected
behavior, equivalent, or excluded. The exclusions above apply to mutants too.

Run: the Python steps in compost's mutation reference
(`plugin/skills/verify/references/mutation.md`) from `plugin/`, with
`--paths scripts` and the plain `pytest` collecting contexts for every module `addopts` covers
(`uv run --group dev python -m pytest -q -p no:cacheprovider --cov-context=test --cov-report= --cov-fail-under=0`).
Covers `plugin/scripts/` only; the TypeScript hooks and workflows
get only `compost:build`'s walk by hand.

Sorted on JoshuaOliphant/claude-plugins#123: the 11 survivors are equivalent. `workers` 1 to 2 on the baseline's single job;
`strays[0]` to `[-1]` and `- named` to `^`, as on cb0b2ef; `len(new) > 1` to `!= 1`, since a hunk
range has one or two parts; `k != "args"` to `>` or `is not`, and `==` to `is` on "survivors", which
string ordering and interning keep the same; `is TIMED_OUT` to `==`, since TimedOut has no `__eq__`;
stderr's `flush`, and the JSON `indent`. Tuning constants are sorted one at a time, not excluded as a
pattern; where a limit has an edge that breaks behavior (0, negative), test the edge.
