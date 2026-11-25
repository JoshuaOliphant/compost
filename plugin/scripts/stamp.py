#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
# ABOUTME: The verify stamp: one line of JSON kept as a git note under refs/notes/compost-verify on the verified commit.
# ABOUTME: `write` stamps a commit with compost:verify's summary, `show <rev>` prints it or `none`, `log <range>` lists both.
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REF = "compost-verify"
NONE = "none"


class GitError(Exception):
    pass


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def git_lines(repo: Path, *args: str) -> list[str]:
    """Runs a git command in `repo` and returns its stdout lines, raising GitError when it fails."""
    ran = git(repo, *args)
    if ran.returncode:
        raise GitError(ran.stderr.strip())
    return ran.stdout.splitlines()


def commit_of(repo: Path, rev: str) -> str:
    ran = git(repo, "rev-parse", "--verify", "--quiet", "--end-of-options", f"{rev}^{{commit}}")
    if ran.returncode:
        raise GitError(f"{rev} is not a commit")
    return ran.stdout.strip()


def read(repo: Path, rev: str) -> str | None:
    """The stamp on `rev`, or None when it has none. A note is per SHA, so a stamp on an older commit never counts."""
    sha = commit_of(repo, rev)
    shown = git(repo, "notes", f"--ref={REF}", "show", sha)
    return shown.stdout.strip() or None


def write(repo: Path, rev: str, summary: dict) -> None:
    """Stamps `rev` with the summary plus the time it was written, replacing any stamp already there."""
    sha = commit_of(repo, rev)
    line = json.dumps({**summary, "time": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    git_lines(repo, "notes", f"--ref={REF}", "add", "--force", "--message", line, sha)


def log(repo: Path, revisions: str) -> list[tuple[str, str | None]]:
    """Every commit `git rev-list <revisions>` names, newest first, with its stamp or None."""
    return [(sha, read(repo, sha)) for sha in git_lines(repo, "rev-list", revisions)]


def main(argv: list[str] | None = None, out=sys.stdout) -> int:
    parser = argparse.ArgumentParser(prog="stamp.py")
    commands = parser.add_subparsers(dest="command", required=True)
    writing = commands.add_parser("write", help="stamp a commit with a verify summary")
    writing.add_argument("--rev", default="HEAD")
    writing.add_argument("--json", required=True, dest="summary", help="the summary, one JSON object")
    commands.add_parser("show", help="print a commit's stamp, or none").add_argument("rev")
    commands.add_parser("log", help="list each commit in a range with its stamp, or none").add_argument("revisions")
    args = parser.parse_args(argv)
    repo = Path.cwd()
    try:
        if args.command == "write":
            try:
                summary = json.loads(args.summary)
            except json.JSONDecodeError:
                summary = None
            if not isinstance(summary, dict):
                print("stamp.py: --json takes one JSON object", file=sys.stderr)
                return 2
            write(repo, args.rev, summary)
        elif args.command == "show":
            print(read(repo, args.rev) or NONE, file=out)
        else:
            for sha, stamped in log(repo, args.revisions):
                print(f"{sha[:12]} {stamped or NONE}", file=out)
    except GitError as error:
        print(f"stamp.py: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
