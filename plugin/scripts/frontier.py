#!/usr/bin/env python3
# ABOUTME: Computes compost:implement's issue states (done, blocked, taken, frontier) and map-decision claims from the
# ABOUTME: tracker and git alone. CLI: `session`, `issues PARENT`, `claim DECISION`, for GitHub, GitLab, or local trackers.
import argparse
import json
import os
import re
import secrets
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

LEASE = timedelta(days=1)
TRAILER = re.compile(r"^compost-session:\s*(\S+)(?:\s+(\S+))?\s*$", re.MULTILINE)
STARTED = re.compile(r"^Started\s+`?([^`\s]+)`?", re.MULTILINE)
RESUMES = re.compile(r"^Resumes:\s*`?([^`\s]+)`?", re.MULTILINE)
CLAIMED = re.compile(r"^Claimed(?: by|:)\s+`?([^`\s]+)`?(?:\s+(\S+))?", re.MULTILINE)
TICK = re.compile(r"^\s*[-*]\s+\[([ xX])\]\s+\[?#?(\d+)\b", re.MULTILINE)
BLOCKED_LINE = re.compile(r"^\s*(?:[-*]\s+)?\**Blocked by\**:?\**\s*(.*)$", re.MULTILINE | re.IGNORECASE)
SECTION = re.compile(r"^##\s+(.*)$", re.MULTILINE)
STATUS = re.compile(r"^Status:\s*(\S+)", re.MULTILINE)

Run = Callable[[list[str]], str]


class FrontierError(Exception):
    pass


@dataclass
class Comment:
    body: str
    at: datetime | None

    @property
    def session(self) -> str | None:
        found = TRAILER.search(self.body)
        return found.group(1) if found else None

    @property
    def when(self) -> datetime | None:
        """The forge's own time, else the time a local comment's trailer carries."""
        if self.at is not None:
            return self.at
        found = TRAILER.search(self.body)
        return parse_time(found.group(2)) if found and found.group(2) else None


@dataclass
class Issue:
    number: int
    body: str
    closed: bool
    labels: list[str]
    comments: list[Comment] = field(default_factory=list)


@dataclass
class Row:
    number: int
    state: str
    why: str
    branch: str | None = None


def parse_time(text: str) -> datetime | None:
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def utc(moment: datetime) -> str:
    return f"{moment.astimezone(UTC):%Y-%m-%d %H:%M}Z"


def ticks(body: str) -> dict[int, bool]:
    """The parent's checklist: each listed issue and whether its box is ticked."""
    return {int(number): box != " " for box, number in TICK.findall(body)}


def blockers(body: str) -> set[int]:
    """Issue numbers on "Blocked by" lines, and the bullets under a "## Blocked by" section."""
    found: set[int] = set()
    for line in BLOCKED_LINE.findall(body):
        rest = line.strip()
        if "#" in rest:
            found |= {int(n) for n in re.findall(r"#(\d+)", rest)}
        elif re.fullmatch(r"[\d,\s]+", rest):
            found |= {int(n) for n in re.findall(r"\d+", rest)}
    sections = SECTION.split(body)
    for title, text in zip(sections[1::2], sections[2::2], strict=True):
        if title.strip().lower() == "blocked by":
            found |= {int(n) for n in re.findall(r"^\s*[-*]\s+#?(\d+)", text, re.MULTILINE)}
    return found


def hold(events: list[tuple[datetime, str, str | None]]) -> tuple[str | None, str | None, datetime | None]:
    """Who holds a claim: the first claim, displaced only by a claim made after its holder had been silent a day.

    Events are (time, session, claim): a claim carries a payload (the branch, for an issue), any other tagged comment
    None and only marks its session as active. Returns the holder, its payload, and its newest activity, so a holder
    is never displaced while it keeps posting, and a session back from the dead doesn't win its claim back.
    """
    holder, payload, seen = None, None, {}
    for when, who, claim in sorted(events, key=lambda event: event[0]):
        if claim is not None and (holder is None or when - seen[holder] >= LEASE):
            holder, payload = who, claim
        seen[who] = max(seen.get(who, when), when)
    return holder, payload, seen.get(holder) if holder else None


def activity(issues: list[Issue]) -> list[tuple[datetime, str, str | None]]:
    """Every tagged comment across the parent and its sub-issues, as liveness for the session that tagged it."""
    return [(c.when, c.session, None) for issue in issues for c in issue.comments if c.session and c.when]


def own_sessions(me: str, issues: list[Issue]) -> set[str]:
    """This session, plus every session it (or one it resumed) named on a `Resumes:` line."""
    own, grew = {me}, True
    while grew:
        grew = False
        for issue in issues:
            for comment in issue.comments:
                found = RESUMES.search(comment.body)
                if found and comment.session in own and found.group(1) not in own:
                    own.add(found.group(1))
                    grew = True
    return own


def starts(issue: Issue) -> list[tuple[datetime, str, str | None]]:
    """The issue's `Started <branch>` comments as claims, each by the session that tagged it."""
    return [
        (c.when, c.session, found.group(1))
        for c in issue.comments
        if c.session and c.when and (found := STARTED.search(c.body))
    ]


def branch_for(number: int, branches: list[str]) -> str | None:
    """The branch named `<number>-*`; a second session may have picked another slug, so match by prefix."""
    matches = sorted(name for name in branches if re.fullmatch(rf"0*{number}-.+", name))
    return matches[0] if matches else None


def states(parent: Issue, issues: list[Issue], branches: list[str], me: str, now: datetime) -> list[Row]:
    checklist = ticks(parent.body)
    by_number = {issue.number: issue for issue in issues}
    done = {n for n, ticked in checklist.items() if ticked} | {issue.number for issue in issues if issue.closed}
    own = own_sessions(me, [parent, *issues])
    active = activity([parent, *issues])
    rows = []
    for number in checklist:
        issue = by_number.get(number)
        branch = branch_for(number, branches)
        if number in done:
            rows.append(Row(number, "done", "closed" if issue and issue.closed else "ticked on the parent", branch))
            continue
        if issue is None:
            raise FrontierError(f"#{number} is on the parent's checklist but could not be read")
        if "ready-for-human" in issue.labels:
            rows.append(Row(number, "ready-for-human", "needs a person; list it under Risk", branch))
            continue
        open_blockers = sorted(blockers(issue.body) - done)
        if open_blockers:
            rows.append(Row(number, "blocked", "waits on " + ", ".join(f"#{n}" for n in open_blockers), branch))
            continue
        if branch is None:
            rows.append(Row(number, "frontier", "no branch yet: push one at the feature SHA and post Started"))
            continue
        holder, started, latest = hold(active + starts(issue))
        branch = started if started in branches else branch
        if holder in own:
            rows.append(Row(number, "frontier", f"your branch (claimed by {holder}): continue from its head", branch))
            continue
        if holder and latest and now - latest < LEASE:
            rows.append(Row(number, "taken", f"{holder} is live (last comment {utc(latest)})", branch))
            continue
        why = f"{holder} silent since {utc(latest)}" if holder and latest else "no live session posted Started for it"
        rows.append(Row(number, "frontier", f"claim expired ({why}): take it over from its head", branch))
    return rows


def claim_winner(comments: list[Comment], now: datetime) -> str | None:
    """The session holding a map decision under `hold`'s rule, if it is still live."""
    events: list[tuple[datetime, str, str | None]] = []
    for comment in comments:
        found = CLAIMED.search(comment.body)
        when = comment.when or (parse_time(found.group(2)) if found and found.group(2) else None)
        who = found.group(1) if found else comment.session
        if when is not None and who is not None:
            events.append((when, who, "claim" if found else None))
    holder, _, latest = hold(events)
    return holder if holder and latest and now - latest < LEASE else None


# Trackers: each reads an issue (body, closed, labels, comments) through the same Run seam, so tests feed it JSON.


def run_command(args: list[str]) -> str:
    try:
        return subprocess.run(args, check=True, capture_output=True, text=True).stdout
    except (OSError, subprocess.CalledProcessError) as error:
        detail = getattr(error, "stderr", "") or str(error)
        raise FrontierError(f"{' '.join(args[:3])} failed: {detail.strip()}") from error


def read_github(number: int, run: Run) -> Issue:
    raw = json.loads(run(["gh", "api", f"repos/{{owner}}/{{repo}}/issues/{number}"]))
    lines = run(
        [
            "gh",
            "api",
            "--paginate",
            f"repos/{{owner}}/{{repo}}/issues/{number}/comments",
            "--jq",
            ".[] | {body, created_at}",
        ]
    )
    comments = [json.loads(line) for line in lines.splitlines() if line.strip()]
    return Issue(
        number,
        raw.get("body") or "",
        raw["state"] == "closed",
        [label["name"] for label in raw.get("labels", [])],
        [Comment(c["body"] or "", parse_time(c["created_at"])) for c in comments],
    )


def read_gitlab(number: int, run: Run) -> Issue:
    raw = json.loads(run(["glab", "api", f"projects/:fullpath/issues/{number}"]))
    notes = pages(run(["glab", "api", "--paginate", f"projects/:fullpath/issues/{number}/notes?sort=asc"]))
    return Issue(
        number,
        raw.get("description") or "",
        raw["state"] == "closed",
        list(raw.get("labels", [])),
        [Comment(n["body"], parse_time(n["created_at"])) for n in notes if not n.get("system")],
    )


def pages(text: str) -> list[dict]:
    """A paginated listing, whether the CLI printed one merged array or one array per page."""
    decoder, items, at, text = json.JSONDecoder(), [], 0, text.strip()
    while at < len(text):
        page, at = decoder.raw_decode(text, at)
        items += page
        while at < len(text) and text[at].isspace():
            at += 1
    return items


def read_local(path: Path) -> Issue:
    head, _, tail = path.read_text().partition("\n## Comments")
    status = STATUS.search(head)
    found = re.match(r"\d+", path.name)
    return Issue(
        int(found.group()) if found else 0,
        head,
        bool(status and status.group(1) == "closed"),
        [status.group(1)] if status else [],
        local_comments(tail),
    )


def local_comments(tail: str) -> list[Comment]:
    """Local comments are blocks under `## Comments`; each that ends in a trailer is one comment."""
    comments, block = [], []
    for line in tail.splitlines():
        block.append(line)
        if TRAILER.match(line):
            comments.append(Comment("\n".join(block), None))
            block = []
    return comments


def remote_branches(run: Run) -> list[str]:
    out = run(["git", "ls-remote", "--heads", "origin"])
    return [line.split("refs/heads/", 1)[1] for line in out.splitlines() if "refs/heads/" in line]


def load(tracker: str, parent: str, run: Run) -> tuple[Issue, list[Issue]]:
    """The parent and its checklist's issues, plus any blocker off the checklist, so a closed one counts as done."""
    if tracker == "local":
        spec = Path(parent)
        top = read_local(spec)
        files = {issue.number: issue for issue in map(read_local, sorted((spec.parent / "issues").glob("*.md")))}
        listed = [files[n] for n in ticks(top.body) if n in files]
        wanted = {n for issue in listed for n in blockers(issue.body)} - {issue.number for issue in listed}
        return top, listed + [files[n] for n in sorted(wanted) if n in files]
    read = read_github if tracker == "github" else read_gitlab
    top = read(int(parent.lstrip("#")), run)
    listed = [read(n, run) for n in ticks(top.body)]
    wanted = {n for issue in listed for n in blockers(issue.body)} - {issue.number for issue in listed}
    return top, listed + [read(n, run) for n in sorted(wanted)]


def session_id(run: Run) -> str:
    """COMPOST_SESSION when set (a second session in the same clone sets its own), else this clone's id.

    The clone's id is made once and kept in its common git dir, so it outlives a compacted context and reads the
    same from the main checkout and every worktree of the clone (the run moves into a feature worktree).
    """
    if os.environ.get("COMPOST_SESSION"):
        return os.environ["COMPOST_SESSION"]
    path = Path(run(["git", "rev-parse", "--git-common-dir"]).strip()) / "compost-session"
    if not path.exists():
        path.write_text(f"s-{secrets.token_hex(4)}\n")
    return path.read_text().strip()


def main(argv: list[str] | None = None, run: Run = run_command, now: datetime | None = None) -> int:
    parser = argparse.ArgumentParser(prog="frontier.py", description="compost issue states and map claims")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("session", help="print this worktree's compost session id, making it on first use")
    issues = commands.add_parser("issues", help="every sub-issue of PARENT with its state: done, blocked, taken, ...")
    claim = commands.add_parser("claim", help="the session holding map decision DECISION's earliest live claim")
    for command in (issues, claim):
        command.add_argument("target", help="issue number, or for --tracker local the spec/decision file")
        command.add_argument("--tracker", choices=("github", "gitlab", "local"), required=True)
    issues.add_argument("--session", help="this session's id (default: `frontier.py session`)")
    args = parser.parse_args(argv)
    now = now or datetime.now(UTC)
    try:
        if args.command == "session":
            print(session_id(run))
        elif args.command == "issues":
            parent, subs = load(args.tracker, args.target, run)
            rows = states(parent, subs, remote_branches(run), args.session or session_id(run), now)
            for row in rows:
                branch = f" [{row.branch}]" if row.branch else ""
                print(f"#{row.number} {row.state}{branch}: {row.why}")
        else:
            if args.tracker == "local":
                decision = read_local(Path(args.target))
                comments = [Comment(decision.body, None), *decision.comments]
            else:
                read = read_github if args.tracker == "github" else read_gitlab
                comments = read(int(args.target.lstrip("#")), run).comments
            print(claim_winner(comments, now) or "none")
    except FrontierError as error:
        print(f"frontier.py: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
