#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
# ABOUTME: compost:experiment's preregistration: `check` refuses a prereg.toml that is incomplete, unpinned, or uncommitted;
# ABOUTME: `score` judges a run's results JSON by the bars as committed at registration, so later edits can't move them.
from __future__ import annotations

import argparse
import json
import operator
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from statistics import mean
from typing import TextIO

TEXT_FIELDS = ("question", "hypothesis", "prediction", "scorer", "stop", "budget")
OPS = {">=": operator.ge, ">": operator.gt, "<=": operator.le, "<": operator.lt, "==": operator.eq}
AGGREGATES = {"mean": mean, "sum": sum, "min": min, "max": max}
SHA = re.compile(r"[0-9a-f]{40}")
PASS, MISS, MALFORMED = 0, 1, 2


class Refused(Exception):
    """A preregistration or results file the experiment can't be judged by; the message says why."""


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def problems(prereg: dict) -> list[str]:
    """Every way `prereg` falls short of a registration, as one line each; empty when it is complete."""
    found = [
        f"missing {name}: say it in words before the run"
        for name in TEXT_FIELDS
        if not str(prereg.get(name, "")).strip()
    ]
    decision = prereg.get("decision")
    if not isinstance(decision, dict) or not all(str(decision.get(side, "")).strip() for side in ("pass", "miss")):
        found.append("missing decision.pass or decision.miss: what happens on each outcome")
    subject = prereg.get("subject")
    if not isinstance(subject, dict) or not str(subject.get("repo", "")).strip():
        found.append("missing subject.repo")
    if not isinstance(subject, dict) or not SHA.fullmatch(str(subject.get("ref", ""))):
        found.append("subject.ref must be the full 40-character SHA under test, not a branch or short SHA")
    if not isinstance(prereg.get("arms"), dict) or not prereg["arms"]:
        found.append("missing arms: name each arm and what it runs")
    controls = prereg.get("controls")
    if not isinstance(controls, list) or not controls:
        found.append('missing controls: list them, or one entry "none: <why>"')
    if not isinstance(prereg.get("sets"), dict):
        found.append("missing sets: list the members of every counted set, or an empty [sets] table")
    n = prereg.get("n")
    if not isinstance(n, int) or isinstance(n, bool) or n < 1:
        found.append("n must be a whole number of runs, 1 or more")
    bars = prereg.get("bars")
    if not isinstance(bars, list) or not bars:
        found.append("missing bars: at least one [[bars]] with metric, op and value")
    for index, bar in enumerate(bars if isinstance(bars, list) else []):
        found.extend(f"bars[{index}]: {line}" for line in bar_problems(bar))
    return found


def bar_problems(bar: object) -> list[str]:
    if not isinstance(bar, dict):
        return ["must be a table"]
    found = []
    if not str(bar.get("metric", "")).strip():
        found.append("missing metric")
    if bar.get("op") not in OPS:
        found.append(f"op must be one of {' '.join(OPS)}")
    if not isinstance(bar.get("value"), int | float) or isinstance(bar.get("value"), bool):
        found.append("value must be a number")
    if "aggregate" in bar and bar["aggregate"] not in {"each", *AGGREGATES}:
        found.append(f"aggregate must be one of each {' '.join(AGGREGATES)}")
    return found


def parse(text: str, where: str) -> dict:
    try:
        prereg = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise Refused(f"{where} is not valid TOML: {error}") from None
    if found := problems(prereg):
        raise Refused("\n".join([f"{where} is not a complete preregistration:", *(f"  - {line}" for line in found)]))
    return prereg


def located(path: Path) -> tuple[Path, str]:
    """The git top level holding `path`, and `path` relative to it."""
    path = path.resolve()
    top = git(path.parent, "rev-parse", "--show-toplevel")
    if top.returncode:
        raise Refused(f"{path} is not in a git repo; commit the preregistration before running")
    root = Path(top.stdout.strip())
    return root, path.relative_to(root).as_posix()


def registration(path: Path) -> str:
    """The last commit to `path`: the registration, once the file is clean. Commits after the run starts are amendments."""
    root, rel = located(path)
    last = git(root, "log", "-1", "--format=%H", "--", rel).stdout.strip()
    if not last:
        raise Refused(f"{rel} is not committed; commit it before running")
    return last


def check(path: Path, subject_repo: Path | None) -> str:
    """Refuses an incomplete, unpinned, or uncommitted preregistration; returns its registration commit."""
    prereg = parse(path.read_text(), str(path))
    ref = prereg["subject"]["ref"]
    if subject_repo is not None and git(subject_repo, "cat-file", "-e", f"{ref}^{{commit}}").returncode:
        raise Refused(f"subject.ref {ref} is not a commit in {subject_repo}")
    root, rel = located(path)
    if git(root, "status", "--porcelain", "--", rel).stdout.strip():
        raise Refused(f"{rel} has uncommitted changes; commit it before running")
    return registration(path)


def judge(bar: dict, values: object, n: int) -> tuple[bool, float, str]:
    """Whether `values` clears `bar`, the number compared, and how it was reduced from the runs."""
    aggregate = bar.get("aggregate")
    if isinstance(values, list):
        if aggregate is None:
            raise Refused(f"{bar['metric']} has one value per run, but its bar names no aggregate")
        if len(values) != n:
            raise Refused(f"{bar['metric']} has {len(values)} values, but {n} runs were registered")
        if aggregate == "each":
            worst = min(values) if bar["op"] in (">=", ">") else max(values)
            return all(OPS[bar["op"]](value, bar["value"]) for value in values), worst, "each"
        return OPS[bar["op"]](got := AGGREGATES[aggregate](values), bar["value"]), got, aggregate
    if aggregate is not None and n > 1:
        raise Refused(f"{bar['metric']} has one value, but its bar asks for the {aggregate} of {n} runs")
    return OPS[bar["op"]](values, bar["value"]), values, "value"


def score(path: Path, results: dict, registered: str, out: TextIO) -> int:
    """Prints PASS or MISS per registered bar and overall; returns the exit code."""
    root, rel = located(path)
    shown = git(root, "show", f"{registered}:{rel}")
    if shown.returncode:
        raise Refused(f"{rel} is not in commit {registered}")
    prereg = parse(shown.stdout, f"{rel} at {registered[:12]}")
    if results.get("ref") != prereg["subject"]["ref"]:
        raise Refused(f"INVALID: the run used ref {results.get('ref')}, not the registered {prereg['subject']['ref']}")
    if results.get("n") != prereg["n"]:
        raise Refused(f"INVALID: the run has n={results.get('n')}, not the registered n={prereg['n']}")
    metrics = results.get("metrics", {})
    passed = True
    for bar in prereg["bars"]:
        if bar["metric"] not in metrics:
            raise Refused(f"INVALID: the results have no {bar['metric']}")
        ok, got, how = judge(bar, metrics[bar["metric"]], prereg["n"])
        passed &= ok
        print(f"{'PASS' if ok else 'MISS'}  {bar['metric']} ({how}) {got:g} {bar['op']} {bar['value']:g}", file=out)
    if path.read_text() != shown.stdout:
        print(
            f"amended after registration: judged by the bars at {registered[:12]}, not the file as it stands", file=out
        )
    print(f"VERDICT: {'PASS' if passed else 'MISS'}", file=out)
    return PASS if passed else MISS


def main(argv: list[str] | None = None, out: TextIO = sys.stdout) -> int:
    parser = argparse.ArgumentParser(prog="prereg.py")
    commands = parser.add_subparsers(dest="command", required=True)
    checking = commands.add_parser("check", help="refuse an incomplete, unpinned, or uncommitted prereg.toml")
    checking.add_argument("prereg", type=Path)
    checking.add_argument("--subject-repo", type=Path, help="a checkout that must hold subject.ref")
    scoring = commands.add_parser("score", help="judge a results JSON by the registered bars")
    scoring.add_argument("prereg", type=Path)
    scoring.add_argument(
        "--results", type=Path, required=True, help='{"ref": SHA, "n": N, "metrics": {name: number or per-run list}}'
    )
    scoring.add_argument("--registered", required=True, help="the commit `check` printed before the run")
    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            print(f"registered at {check(args.prereg, args.subject_repo)}; record it and pass it to score", file=out)
            return PASS
        return score(args.prereg, json.loads(args.results.read_text()), args.registered, out)
    except Refused as refusal:
        print(refusal, file=out)
        return MALFORMED


if __name__ == "__main__":
    sys.exit(main())
