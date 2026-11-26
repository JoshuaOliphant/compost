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

## A parent without a record

`compost:implement` runs the same check when it starts on a parent with no readiness record. It
fills each gap as a ruling marked `(assumed)`, posts the record, and stops before the first build
only when a gap is on the contract's Stops list ([implement's run contract](../../implement/references/run-contract.md)).
