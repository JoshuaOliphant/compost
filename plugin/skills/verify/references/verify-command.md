# Building the verify command

Depth for `compost:verify` step 1, when `docs/agents/testing.md` names no verify command.

Build one before running anything: a `scripts/verify`, or a target in the repo's task runner, that
- runs every gate in order and exits non-zero on the first failure;
- fails when a gate collects, lints, or measures nothing;
- fails on a skipped or xfailed test that an AC table names;
- checks every issue's AC table (AC-N to test node id) against this run, closed issues
  included: each named test must exist, run, and pass. A row whose test cell reads
  `superseded by #N` is retired: the command skips it and prints it, so the report names it.
  The table it reads looks like this:

  ```markdown
  | AC | Test |
  |---|---|
  | AC-1 | tests/test_fees.py::test_no_fee_inside_grace_period |
  | AC-3 | superseded by #42 |
  ```
- reads the tables in bulk, not one tracker call per issue: from the local tracker's files, or
  for a remote tracker one listing call scoped to issues that carry a table, or a committed
  cache of the tables. Verify refreshes the cache whenever it posts a table or retires a row, except as a
  `compost:implement` worker: parallel lanes that each rewrite one committed file conflict when
  they land, so workers leave the cache alone and the orchestrator refreshes it after each
  landing. The command warns when the cache is older than the newest edit to an AC table itself:
  the edit time of the comment or file that holds a table, not the issue's updated time, which
  moves on every comment or label change and would make the warning noise. A table edited
  outside verify won't reach the cache otherwise. With hundreds of issues, a call per issue is
  slow and runs into rate limits.

