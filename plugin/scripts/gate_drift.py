# ABOUTME: Lists every edit a branch makes to the checks that judge it, for compost:verify: changed gate files, added
# ABOUTME: weakeners, and removed test functions, as JSON. Exits 1 with changes. Stdlib only; reads git.
import argparse
import json
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import PurePosixPath

# Files whose content defines a gate: change one and the check that judges the branch changed too.
GATE_FILES = (
    (re.compile(r"(^|/)docs/agents/testing\.md$"), "recorded gates"),
    (re.compile(r"(^|/)REVIEW\.md$"), "review guide"),
    (re.compile(r"(^|/)scripts/verify[^/]*$"), "verify command"),
    (re.compile(r"(^|/)\.github/workflows/"), "CI workflow"),
    (re.compile(r"(^|/)\.pre-commit-config\.ya?ml$"), "pre-commit"),
    (
        re.compile(r"(^|/)(\.?ruff\.toml|pytest\.ini|tox\.ini|setup\.cfg|\.coveragerc|\.?mypy\.ini)$"),
        "lint/test config",
    ),
    # JS and TS runners, linters, and coverage tools keep thresholds and ignores in their own configs.
    (
        re.compile(
            r"(^|/)((jest|vitest|playwright|karma)\.config\.[cm]?[jt]s|\.eslintrc(\.\w+)?|eslint\.config\.[cm]?[jt]s|\.nycrc(\.\w+)?|\.c8rc(\.\w+)?)$"
        ),
        "lint/test config",
    ),
    (re.compile(r"(^|/)conftest\.py$"), "test fixtures/collection"),
)
GATE_CONFIG = "lint/test config"
# pyproject.toml holds gates beside everything else, so only a change inside one of these tables counts.
PYPROJECT_GATES = ("tool.coverage", "tool.pytest", "tool.ruff", "tool.mypy", "tool.ty", "tool.pyright")
SLEEP = "sleep/retry in a test"
# Added lines that weaken a check in place. `\bxit\(` keeps `exit(` from reading as a skipped Jasmine test.
WEAKENERS = (
    (re.compile(r"pragma:\s*no cover"), "coverage exclusion"),
    (re.compile(r"#\s*noqa"), "lint suppression"),
    (re.compile(r"#\s*type:\s*ignore"), "type suppression"),
    (re.compile(r"@pytest\.mark\.(skip|xfail)|pytest\.skip\(|\bxit\(|\bit\.skip\("), "skipped test"),
    (re.compile(r"fail_under\s*=|--cov-fail-under"), "coverage threshold"),
    (re.compile(r"exclude_also|omit\s*="), "coverage exclusion config"),
    (re.compile(r"\b(per-file-ignores|extend-ignore|ignore\s*=)"), "lint ignore config"),
    (re.compile(r"time\.sleep\(|\bretry\b|flaky|reruns"), SLEEP),
)
# Prose can name a weakener without applying one.
DOCS = {".md", ".rst", ".txt"}
TEST_PATH = re.compile(r"(^|/)tests?/|(^|/)test_[^/]*\.py$|_test\.py$|\.test\.")
TEST_DEF = re.compile(r"^\s*(?:async\s+)?def (test_\w+)")
HUNK = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")
TABLE = re.compile(r"^\s*\[\[?\s*([^\]\s]+)\s*\]\]?")


class GateDriftError(Exception):
    pass


@dataclass(frozen=True)
class GateChange:
    kind: str
    path: str
    detail: str


def drift(repo, base: str, head: str) -> list[GateChange]:
    """Every change in what `head` changed since its merge-base with `base`, so commits the base gained since are not
    the branch's: changed gate files first, then added weakeners in diff order, gate tables changed in a
    pyproject.toml, and test functions removed from a file that does not define them again."""
    fork = _git(repo, "merge-base", base, head).strip()
    changes = [
        GateChange(kind, path, "file changed")
        for path in _git(repo, "diff", "--name-only", fork, head).splitlines()
        if (kind := gate_file(path))
    ]
    diff = _git(repo, "diff", "-U0", "--no-color", "--no-ext-diff", fork, head)
    return changes + line_changes(
        diff, lambda side, path: _git(repo, "show", f"{fork if side == '-' else head}:{path}")
    )


def gate_file(path: str) -> str | None:
    return next((kind for pattern, kind in GATE_FILES if pattern.search(path)), None)


def weakeners(path: str, line: str) -> list[str]:
    if PurePosixPath(path).suffix in DOCS:
        return []
    in_test = bool(TEST_PATH.search(path))
    return [kind for pattern, kind in WEAKENERS if (in_test or kind != SLEEP) and pattern.search(line)]


def line_changes(diff: str, show: Callable[[str, str], str]) -> list[GateChange]:
    """Changes in a `git diff -U0`; `show(side, path)` returns the file before ("-") or after ("+") the change."""
    changes: list[GateChange] = []
    tables: dict[tuple[str, str], None] = {}
    removed: dict[str, list[str]] = {}
    added: dict[str, set[str]] = {}
    texts: dict[tuple[str, str], list[str]] = {}
    paths = {"-": "", "+": ""}
    numbers = {"-": 0, "+": 0}
    in_header = False
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            in_header, paths = True, {"-": "", "+": ""}
            continue
        if in_header and line[:4] in ("--- ", "+++ "):
            paths[line[0]] = "" if line[4:] == "/dev/null" else line[6:]
            continue
        if hunk := HUNK.match(line):
            in_header = False
            numbers = {"-": int(hunk[1]), "+": int(hunk[2])}
            continue
        side = line[:1]
        if in_header or side not in numbers:
            continue
        path = paths["+"] or paths["-"]
        number = numbers[side]
        numbers[side] += 1
        body = line[1:]
        if side == "+":
            changes += [GateChange(kind, path, body.strip()[:120]) for kind in weakeners(path, body)]
        if PurePosixPath(path).name == "pyproject.toml" and body.strip():
            if (side, path) not in texts:
                texts[side, path] = show(side, paths[side]).splitlines()
            table = table_at(texts[side, path], number)
            if any(table == gate or table.startswith(gate + ".") for gate in PYPROJECT_GATES):
                tables[path, table] = None
        if TEST_PATH.search(path) and (test := TEST_DEF.match(body)):
            if side == "-":
                removed.setdefault(path, []).append(test[1])
            else:
                added.setdefault(path, set()).add(test[1])
    changes += [GateChange(GATE_CONFIG, path, f"[{table}] changed") for path, table in tables]
    for path, names in removed.items():
        changes += [
            GateChange("test removed or renamed", path, name)
            for name in dict.fromkeys(names)
            if name not in added.get(path, ())
        ]
    return changes


def table_at(lines: list[str], number: int) -> str:
    """The TOML table that line `number` (1-based) sits in; "" above the first header."""
    table = ""
    for line in lines[:number]:
        if header := TABLE.match(line):
            table = header[1]
    return table


def history(repo) -> list[dict]:
    """drift over every merged pull request on the first-parent line, newest first: merge^1 against merge^2."""
    report = []
    for row in _git(repo, "log", "--merges", "--first-parent", "--format=%H %s").splitlines():
        sha, _, subject = row.partition(" ")
        if not subject.startswith("Merge pull request"):
            continue
        try:
            changes = drift(repo, f"{sha}^1", f"{sha}^2")
        except GateDriftError as error:
            report.append({"merge": sha, "subject": subject, "error": str(error)})
            continue
        report.append({"merge": sha, "subject": subject, "changes": [asdict(change) for change in changes]})
    return report


def _git(repo, *args: str) -> str:
    command = ["git", "-C", str(repo), "-c", "core.quotePath=false", *args]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        raise GateDriftError(f"git {args[0]} failed in {repo}: {result.stderr.strip()}")
    return result.stdout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="List every edit a branch makes to the checks that judge it.")
    parser.add_argument("base", nargs="?", help="the branch's base, such as origin/main")
    parser.add_argument("head", nargs="?", help="the branch's head, such as HEAD")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--history", action="store_true", help="scan every merged pull request instead")
    args = parser.parse_args(argv)
    if not args.history and not (args.base and args.head):
        parser.error("give <base> <head>, or --history")
    try:
        if args.history:
            report = history(args.repo)
            found = any(row.get("changes") for row in report)
        else:
            report = [asdict(change) for change in drift(args.repo, args.base, args.head)]
            found = bool(report)
    except GateDriftError as error:
        print(error, file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2))
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
