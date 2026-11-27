# Readiness

A spec is ready when a run can take it from posted to draft pull request without the user. Spec
step 10 writes the run contract and runs the check.

## The run contract

The Run contract section of the [parent issue](parent-issue.md) has three lists:

- **Stops:** `compost:implement`'s fixed stop list, plus any stop the interview settled. A contract
  can add stops but never drop the irreversible ones the template names. When the user asked to run
  without one, keep it and say the contract cannot drop it.
- **Prerequisites:** what only a person can supply (keys, accounts, services, test data), each with
  a command that checks it and marked confirmed or unconfirmed.
- **Departures:** decisions the run makes differently from implement's default, or "None".

## The check

The short check, for bounded work:

- every AC-N names the kind of test and the seam that will prove it;
- with a Frontend section on the parent, every AC-N whose Then is user-visible names an e2e test;
- every prerequisite's check has run;
- no open question is left unsorted.

The full check, for architectural work, adds:

- the rabbit holes: where the build could sink time;
- the no-gos: what it must not touch;
- a pre-mortem: how the run fails, told as if it already had.

Post the result as the readiness record, in the format the parent issue template gives.

## Defaults to veto

The readiness record ends with a numbered list of the low-stakes values the spec settled without
asking: the `(assumed)` bullets of the refined prompt and any `(proposed)` value from the
[early critique](early-critique.md) the user never settled. One line each, with the value and why
it is safe to assume:

```markdown
### Defaults to veto
1. A cancelled export link expires after 24 hours, the same as a finished one.
2. The list shows 50 rows a page, the existing table's page size.
```

Show the same list in the message that hands the spec over: the approval ask for architectural work,
the closing message for bounded work. Confirming the spec accepts every default unless the user
vetoes its number; a vetoed number becomes an open question like any other, and its answer goes
back into the spec and the refined prompt. Empty is a fine result: write "None".

Some decisions never go on the list, however small they look: anything touching auth or
credentials, untrusted input, who can read what, a destructive action, or overwriting the only copy
of some data. Each is asked as an explicit question. With nobody to answer, it stays an open
question and the run contract gets a stop for it.

## A parent without a record

`compost:implement` runs the same check when it starts on a parent with no readiness record. It
fills each gap as a ruling marked `(assumed)`, posts the record, and stops before the first build
only when a gap is on the contract's Stops list ([implement's run contract](../../implement/references/run-contract.md)).
