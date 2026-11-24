# The run contract

The parent's Run contract section (spec's [parent issue](../../spec/references/parent-issue.md)
template) says what this run stops for (Stops), what a person must supply first (Prerequisites,
each with a check), and what it decides differently from this skill's defaults (Departures).
Step 1 keeps to it before any worker branches, in this order.

1. **Readiness record.** Look for the parent comment headed `## Readiness`. On a parent without
   one, run the [readiness check](../../spec/references/readiness.md) for the parent's class
   yourself: the short check for bounded work, the full check for architectural work. Fill each gap
   it finds as a ruling comment on the parent whose **Ruling:** line ends `(assumed)`, then post
   the readiness record with each item you filled ticked and ending `(assumed)`. A parent with no
   Run contract section is one such gap: assume implement's fixed stop list, no prerequisites, and
   no departures. Stop before the first build only when a gap is on the Stops list, such as a
   prerequisite only a person can supply; any other gap stays a ruling and the run goes on.
2. **Print the Stops.** Print the contract's Stops in an assistant message as plain text starting at
   the beginning of a line, never bold or inside a code block: a line `Run contract stops:`, then
   one `- <stop>` line per Stops item, word for word, then a blank line. For example:

   ```text
   Run contract stops:
   - merging to the repository's default branch
   - choosing the payment provider

   ```

   Print it again every time implement loads, a resume or a reload after an early
   `compost:finish` included: the [stop guard](stop-guard.md) reads only the latest block printed
   since the latest load.
3. **Check the prerequisites.** Run each prerequisite's check before any worker branches. A
   prerequisite marked unconfirmed, or one whose check fails now, stops the run there: name the
   prerequisite and the check you ran, with its output. A person confirms one by marking it
   confirmed on the parent once it is in place.
4. **Keep to the Departures.** Each binds the run the way an earlier ruling does.

From then on step 9 holds: stop only for an item on the contract's Stops, and post every other
decision as a ruling comment.
