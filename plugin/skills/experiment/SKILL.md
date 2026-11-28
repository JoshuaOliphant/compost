---
name: experiment
description: Runs an eval, A/B, ablation, replay, or benchmark as a preregistered experiment, writing down and committing the hypothesis, the predicted result, the pass bar, the counted sets, controls, n, the exact commit under test, and a stop rule before anything runs, then scoring the result against what was written. Use before running an eval whose result will decide something - "does this prompt change help", "A/B these two versions", "run the evals on this branch", "rerun the replay", "ablate this mechanism", "is the new version better", "measure whether", "benchmark this" - or when a number is about to justify a merge, a revert, or a claim in a write-up.
---

# Experiment

An eval answers a question only if the answer was fixed before the run. Once the numbers are in, it
is easy to move the bar to where they landed, count a different set, rerun until the noise breaks
your way, or test a commit that isn't the one you mean to ship, and each of those feels like a
fair correction at the time. A preregistration closes all of them: what you expect, what counts,
and what you will do about it, committed before the first run, and the verdict read from that
commit. `compost:diagnose` runs the same loop for a bug; this skill runs it for a measurement. The
why is in [prove it works](../../canon/prove-it-works.md), under Numbers.

The mechanical part lives in `scripts/prereg.py`: `check` refuses an incomplete, unpinned, or
uncommitted preregistration, and `score` judges a run's results by the bars in the registration
commit, so editing the file afterwards changes nothing.

## Steps

1. **Name the decision first.** Write the question, then what you will do if the answer is yes and
   what you will do if it is no: merge or don't, keep the mechanism or cut it, file a follow-up.
   When no decision hangs on the result, say so and don't run it; a number nobody acts on costs
   money and adds noise to the record. When the user's request has no decision in it, propose one
   and ask.

2. **Pick the instrument and read it.** Prefer a harness that already exists over a new one, and
   read its scorer before you write a bar, so the bar is in the units the scorer prints:
   - `claude plugin eval` cases in compost-evals `evals/plugin-eval/`, run with
     `scripts/run-plugin-eval.sh <checkout> <ref> [model]` (does a skill fire, does its output beat
     the no-plugin arm);
   - `evals/review-recall/run.sh` and `score.py` (does `/compost:review-changes` catch known bugs),
     and its skeptic replay, `replay/run.py` and `replay/bars.py` (the reviewer's output held
     fixed, only the skeptics rerun);
   - the Jev evals, `pytest -m jev` from `plugin/` (labeled cases per tool);
   - an `experiments/<name>/` harness in compost when none of these fits.

   If the scorer leaves a judgement to a reader (a free-text reason sorted by hand, a judge model's
   call), that judgement is part of the instrument: fix its rule now, in the preregistration.

3. **Pin the subject.** Resolve the commit under test to a full 40-character SHA with
   `git rev-parse <branch>` and check it is the head you mean: the branch's current tip, pushed,
   not a local commit that differs from it and not an older run's pin. Each arm names its own SHA
   when the arms are two commits. A short SHA, a branch name, or "main" is not a pin; the run must
   be reproducible from the file alone.

4. **Write the preregistration.** Copy
   [references/prereg-template.toml](references/prereg-template.toml) next to where the results
   will land (in compost-evals, `evals/<harness>/results/<date>-<slug>/prereg.toml`) and fill
   every field:
   - **question, hypothesis, prediction**: the prediction is a number in the scorer's units, with
     the direction you expect.
   - **decision**: `pass` and `miss`, from step 1.
   - **subject**: the repo and the SHA from step 3.
   - **arms and controls**: what each arm runs, and what tells you the instrument works at all: a
     no-plugin arm, the base commit, clean control cases, a known-good case that must stay good.
     When there is no control, write `"none: <why>"`.
   - **sets**: the members of every set a bar counts, listed by id. "The wrong claims" is not a
     set; ten case ids are. A set defined after the run is the commonest way a bar moves.
   - **n and the noise**: how many runs, and why that many is enough. Read the run-to-run spread
     from earlier results of the same harness; when single cases flip between runs, a bar on one
     run can't tell 7 from 8, so run more or bar on every run (`aggregate = "each"`).
   - **bars**: each a metric the scorer prints, an operator, a value, and how the n runs combine
     (`each`, `mean`, `sum`, `min`, `max`). Every bar must be one a skeptical reader would accept
     as the test of the hypothesis, not one the arm is sure to clear.
   - **scorer**: the exact command that turns a run into those metrics.
   - **stop and budget**: when the experiment ends (after n runs; an errored or rate-limited run is
     rerun once and logged; no extra runs to rescue a miss) and what it may spend.

5. **Check and commit before the first run.** Run
   `uv run ${CLAUDE_PLUGIN_ROOT}/scripts/prereg.py check <prereg.toml> --subject-repo <checkout>`,
   fix what it names, commit the file, run check again, and record the registration commit it
   prints: in the commit message that adds the results and in the write-up. Push it when the repo
   has a remote, so the registration has a timestamp someone else can see. Nothing runs before this
   commit exists. Under `compost:implement` or as a worker, post the preregistration and its
   commit as a ruling comment on the issue before running.

6. **Run exactly what you registered.** Same SHA, same n, same command. Anything that departs
   from the file (a run that errored and was rerun, a usage limit that split the run, a case that
   couldn't be prepared) goes in a Deviations list in the write-up, with what it might have done
   to the result. Do not edit the preregistration to match what happened.

7. **Score against the registration.** Have the scorer write a results JSON:
   `{"ref": "<SHA>", "n": <runs>, "metrics": {"<metric>": <number or one value per run>}}`, then run
   `prereg.py score <prereg.toml> --registered <commit> --results <results.json>`. It exits 0 on
   PASS, 1 on MISS, 2 when the results don't match the registration (another ref, another n, a
   metric missing), and says so when the file was amended after registration. A 2 is not a
   verdict: fix the run, not the file, and score again.

8. **Report the verdict as the scorer gave it.** Lead the write-up with the verdict line, the
   registration commit, and the subject SHA. A miss is a miss, even by one: say which bar and by
   how much. Then the deviations. Anything you noticed after the run that the preregistration did
   not ask (another set that looks better, a subgroup, a different reading of a reason) goes under
   **Exploratory**, labelled as such, and is a hypothesis for the next preregistration, never a
   new verdict on this one.

9. **Act on the decision you wrote down.** Do what `decision.pass` or `decision.miss` says. When
   the user wants to act otherwise, such as merging after a miss, that is their call to make: put
   the override in their words, the bar it overrides, and the reason in the PR body or on the
   issue. Never restate the result so the override looks like a pass.

## Before you call it done

- `prereg.py check` passed on the committed file before the first run, and the write-up names
  the registration commit.
- The subject SHA in the results equals the registered one.
- `prereg.py score` produced the verdict line the write-up leads with.
- Deviations and Exploratory are separate sections, and neither changes the verdict.

## Next moves

- `compost:diagnose` when the result is a surprise you can't explain, or a run fails in a way
  that looks like a bug in the harness rather than the subject.
- `compost:fan-out` when the experiment is a comparison of several designs at once.
- `compost:spec` or `compost:slice` when the decision is to build something.
- `compost:verify` or `compost:finish` when the experiment was the proof a PR was waiting on.
- `compost:experiment` again for any Exploratory finding worth a verdict.
