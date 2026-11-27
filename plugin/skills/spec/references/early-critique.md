# Early critique

The builder check (step 9) finds a spec's gaps after the interview, when every question it raises
costs the user another turn. The early critique runs the same kind of fresh reader before the
interview, on a draft built from the facts step 1 found, so the first round asks the questions a
critic showed matter instead of the ones the author thought of. It spends agent effort to save the
user's turns, which is worth it only when a wrong build is expensive.

## The rework ladder

Place the request on it in one line, out loud, before the first round:

- **Rerun:** a wrong build is thrown away and run again. Nothing outside the branch changed.
- **Unpick:** a wrong build is undone by changing some code. Still nothing outside the code.
- **Migrate:** undoing it means moving data or callers: rows already written in the new shape, a
  config others now read, an interface another team builds against.
- **Can't undo:** a sent message, a published API or package version, deleted data, money moved.

Rerun and unpick may skip the critique: say the rung and why, and go to the first round. Migrate and
can't undo always get it. When torn between two rungs, take the costlier one, as with the class.

## Draft, then critique

1. **Draft** the smallest spec the facts support, in the [parent issue](parent-issue.md) template's
   sections: stories, a few AC-N, and the approach you would pick. Mark every assumption as one and
   every policy value (a limit, a duration, a threshold) as `(proposed)`. The draft decides nothing;
   it exists to be attacked.
2. **Critique** it with a fresh general-purpose subagent: not a fork, not you, and without your
   reasoning. Pass only the draft and the facts, each with where it came from (`file:line`, command,
   doc) and when you read it:

   ```
   Attack this draft spec before anyone is asked about it. Its author is not reachable; work from
   the draft and the facts below, and read the code they cite to check them.

   Find: contradictions between parts; premises the facts do not back, or back only from a stale
   source; decisions the draft makes silently; actors or callers it leaves out; numbers that break a
   real limit in the code or the platform. For each, give the draft line it concerns, the evidence,
   and what would change if it is wrong. Most damaging first. If nothing matters, reply
   "nothing important".

   [DRAFT]
   [FACTS]
   ```

3. **Fold each finding in** as one of three: a fact to re-check (do it now, before the round), an
   area the interview must cover (it joins the decision tree), or a question (it joins the frontier,
   and when it is among the costliest it goes in the first round). Nothing from the draft reaches the
   spec without a decision: a `(proposed)` value the user never settles is an assumption, listed like
   any other.

Unattended, run the critique the same way and sort its questions as the builder check does: minor
ones settled and marked `(assumed)`, the rest left as open questions on the issue.

## No subagent tool

Critique the draft yourself, as a reader who never saw the conversation, and say in one line that
the critique was not independent.
