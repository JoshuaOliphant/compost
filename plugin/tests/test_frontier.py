# ABOUTME: Tests frontier.py: implement's issue states (done, blocked, taken, frontier, ready-for-human), claim liveness
# ABOUTME: keyed to the claimant, map-decision claims, and the GitHub, GitLab, and local readers behind its CLI.
import json
import subprocess
from datetime import UTC, datetime, timedelta

import frontier
import pytest
from frontier import Comment, Issue

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
FRESH = NOW - timedelta(hours=2)
STALE = NOW - timedelta(days=2)
PARENT = "## Slices\n- [x] #10 Greet\n- [ ] #11 Greet all\n- [ ] #12 Farewell\n- [ ] #13 Docs\n"


def said(body: str, session: str | None = None, at: datetime = FRESH) -> Comment:
    return Comment(body + (f"\n\ncompost-session: {session}" if session else ""), at)


def issue(number: int, body: str = "", *comments: Comment, closed: bool = False, labels=()) -> Issue:
    return Issue(number, body, closed, list(labels), list(comments))


def rows(subs, branches=(), parent_comments=(), me="s-me", parent=PARENT):
    top = Issue(1, parent, False, [], list(parent_comments))
    return {row.number: row for row in frontier.states(top, subs, list(branches), me, NOW)}


def test_ticked_or_closed_is_done_and_unblocks_what_waits_on_it():
    got = rows([issue(10), issue(11, "Blocked by #10"), issue(12, "Blocked by #13"), issue(13, closed=True)])
    assert [(n, r.state) for n, r in got.items()] == [(10, "done"), (11, "frontier"), (12, "frontier"), (13, "done")]
    assert got[10].why == "ticked on the parent" and got[13].why == "closed"


def test_an_open_unticked_blocker_blocks_and_ready_for_human_is_left_out():
    got = rows([issue(10), issue(11, "Blocked by #12"), issue(12), issue(13, labels=["ready-for-human"])])
    assert (got[11].state, got[11].why) == ("blocked", "waits on #12")
    assert got[13].state == "ready-for-human"


OTHER_STARTED = said("Started 11-greet-all", "s-other")


@pytest.mark.parametrize(
    ("branches", "comments", "parent_comments", "state", "why"),
    [
        ([], [], [], "frontier", "no branch yet"),
        (["11-greet-all"], [OTHER_STARTED], [], "taken", "s-other is live"),
        (["11-everyone"], [OTHER_STARTED], [], "taken", "s-other is live"),
        (["11-greet-all"], [said("Started 11-greet-all", "s-other", STALE)], [], "frontier", "claim expired (s-other"),
        (["11-greet-all"], [said("Started 11-greet-all", "s-me")], [], "frontier", "your branch"),
        (["11-greet-all"], [], [], "frontier", "no live session posted Started"),
        (
            ["11-greet-all"],
            [said("Started 11-greet-all", "s-dead", STALE)],
            [said("Review round 1", "s-me")],
            "frontier",
            "claim expired",
        ),
        (
            ["11-greet-all"],
            [said("Started 11-greet-all", "s-other", STALE)],
            [said("Ruling: use a dict", "s-other")],
            "taken",
            "s-other is live",
        ),
        (["111-other", "1-x"], [], [], "frontier", "no branch yet"),
    ],
    ids=[
        "no branch",
        "another live session's branch",
        "matched by prefix whatever the slug",
        "claimant silent a day",
        "this session's own",
        "branch with no Started comment",
        "my own comments don't keep a dead claim alive",
        "the claimant's comment elsewhere keeps it live",
        "11 matches neither 111- nor 1-",
    ],
)
def test_a_branch_is_taken_only_while_the_session_that_started_it_is_live(
    branches, comments, parent_comments, state, why
):
    got = rows([issue(10), issue(11, "", *comments), issue(12), issue(13)], branches, parent_comments)[11]
    assert got.state == state
    assert why in got.why


def test_the_earliest_live_start_holds_so_a_late_starter_backs_off_on_its_recheck():
    first = said("Started 11-x", "s-a", FRESH - timedelta(minutes=5))
    late = said("Started 11-y", "s-b", FRESH)
    subs = [issue(10), issue(11, "", first, late), issue(12), issue(13)]
    as_b = rows(subs, ["11-x", "11-y"], me="s-b")[11]
    assert (as_b.state, as_b.branch) == ("taken", "11-x")
    assert rows(subs, ["11-x", "11-y"], me="s-a")[11].why.startswith("your branch (claimed by s-a)")


def test_a_start_after_the_holder_went_silent_a_day_takes_over_for_good():
    dead = said("Started 11-x", "s-a", STALE)
    taken_over = said("Started 11-y", "s-b", FRESH - timedelta(hours=1))
    back = said("Ruling: I'm back", "s-a", FRESH)
    got = rows([issue(10), issue(11, "", dead, taken_over, back), issue(12), issue(13)], ["11-x", "11-y"])[11]
    assert (got.state, got.branch, got.why) == ("taken", "11-y", "s-b is live (last comment 2026-11-13 09:00Z)")


def test_a_holder_that_restarts_on_a_new_slug_moves_its_claim_to_the_new_branch():
    first = said("Started 11-x", "s-a", FRESH - timedelta(hours=1))
    again = said("Started 11-x-v2", "s-a", FRESH)
    got = rows([issue(10), issue(11, "", first, again), issue(12), issue(13)], ["11-x", "11-x-v2"])[11]
    assert (got.state, got.branch) == ("taken", "11-x-v2")


def test_the_branch_shown_is_the_one_the_claimant_started_when_slugs_differ():
    subs = [issue(10), issue(11, "", said("Started 11-b", "s-other")), issue(12), issue(13)]
    assert rows(subs, ["11-a", "11-b"])[11].branch == "11-b"


def test_a_session_this_one_resumed_counts_as_this_one_and_so_does_its_own_resume():
    resumed = said("Resumed from the status comment.\nResumes: s-old", "s-mid")
    again = said("Resumed again.\nResumes: s-mid", "s-me")
    subs = [issue(10), issue(11, "", said("Started 11-a", "s-old")), issue(12), issue(13)]
    assert rows(subs, ["11-a"], [resumed, again])[11].why.startswith("your branch (claimed by s-old)")


def test_an_issue_on_the_checklist_that_could_not_be_read_is_an_error():
    with pytest.raises(frontier.FrontierError, match="#11 is on the parent's checklist"):
        rows([issue(10)])


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("Blocked by #3, #5", {3, 5}),
        ("**Blocked by:** #41: refunds for 2 orders", {41}),
        ("Status: ready-for-agent\nBlocked by: 01, 03", {1, 3}),
        ("## Blocked by\n\n- #41: Refunds can be issued\n- #42: Orders\n\n## Files\n- 7 files", {41, 42}),
        ("## Blocked by\n\nNone (can start immediately)\n", set()),
        ("Blocked by: none", set()),
    ],
    ids=["inline forge", "bold with a title", "local file numbers", "section bullets", "section saying none", "none"],
)
def test_blockers_read_every_form_slice_writes(body, expected):
    assert frontier.blockers(body) == expected


def test_the_parent_checklist_lists_slices_and_skips_acceptance_criteria_boxes():
    body = "- [ ] **AC-1: greets**\n- [x] #13 Greet\n- [ ] [14-greet-all](issues/14-greet-all.md)\n* [X] 02 Local\n"
    assert frontier.ticks(body) == {13: True, 14: False, 2: True}


@pytest.mark.parametrize(
    ("comments", "winner"),
    [
        ([said("Claimed by s-a", at=FRESH - timedelta(minutes=1)), said("Claimed by s-b")], "s-a"),
        ([said("Claimed by s-a", at=STALE), said("Claimed by s-b")], "s-b"),
        ([said("Claimed by s-a", at=STALE), said("Claimed by s-b"), said("Progress: read the API", "s-a")], "s-b"),
        (
            [
                said("Claimed by s-a", at=STALE),
                said("Progress", "s-a", FRESH - timedelta(hours=1)),
                said("Claimed by s-b"),
            ],
            "s-a",
        ),
        ([said("Claimed by s-a", at=STALE)], None),
        ([said("A question for whoever picks this up")], None),
        ([Comment("Status: claimed\nClaimed: s-l 2026-11-13T11:00:00Z", None)], "s-l"),
        ([Comment("Claimed: s-l 2026-11-10T11:00:00Z", None)], None),
        ([Comment("Claimed by s-x", None)], None),
    ],
    ids=[
        "earliest live claim wins",
        "a dead earlier claim loses to a live later one",
        "a claimant back from the dead doesn't take it back",
        "a later claim doesn't displace a holder that kept posting",
        "every claim dead",
        "no claims",
        "local claim line with its time",
        "local claim older than a day",
        "a claim with no time is ignored",
    ],
)
def test_the_earliest_claim_whose_claimant_is_live_wins(comments, winner):
    assert frontier.claim_winner(comments, NOW) == winner


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2026-11-13T11:00:00Z", datetime(2026, 11, 13, 11, tzinfo=UTC)),
        ("2026-11-13T11:00", datetime(2026, 11, 13, 11, tzinfo=UTC)),
        ("soon", None),
    ],
    ids=["zulu", "naive is UTC", "garbage"],
)
def test_parse_time(text, expected):
    assert frontier.parse_time(text) == expected


class Forge:
    """Answers the gh/glab/git commands frontier.py runs, from canned issues, the way the real CLIs print them."""

    def __init__(self, issues: dict[int, dict], branches=(), session="s-me"):
        self.issues, self.branches, self.session, self.calls = issues, branches, session, []

    def __call__(self, args: list[str]) -> str:
        self.calls.append(args)
        if args[:2] == ["git", "ls-remote"]:
            return "".join(f"abc123\trefs/heads/{name}\n" for name in self.branches)
        if args[:2] == ["git", "rev-parse"]:
            raise frontier.FrontierError("no session file in this stub")
        number = int(next(part for part in args if "/issues/" in part).split("/issues/")[1].split("/")[0].split("?")[0])
        found = self.issues[number]
        if args[0] == "gh":
            if args[-1].startswith(".[]"):
                return "".join(json.dumps({"body": b, "created_at": t}) + "\n" for b, t in found["comments"])
            return json.dumps(
                {
                    "body": found["body"],
                    "state": found.get("state", "open"),
                    "labels": [{"name": n} for n in found.get("labels", [])],
                }
            )
        if args[-1].startswith("projects") and "/notes" in args[-1]:
            notes = [{"body": b, "created_at": t, "system": False} for b, t in found["comments"]]
            system = {"body": "added label", "created_at": "2026-11-13T11:59:00Z", "system": True}
            return json.dumps(notes[:1]) + "\n" + json.dumps([*notes[1:], system]) + "\n"
        return json.dumps(
            {"description": found["body"], "state": found.get("state", "opened"), "labels": found.get("labels", [])}
        )


ISSUES = {
    1: {
        "body": "- [x] #10 a\n- [ ] #11 b\n- [ ] #12 c\n- [ ] #13 d",
        "comments": [("Ruling\n\ncompost-session: s-other", "2026-11-13T11:00:00Z")],
    },
    10: {"body": "", "comments": []},
    11: {"body": "Blocked by #10", "comments": [("Started 11-b\n\ncompost-session: s-other", "2026-11-12T00:00:00Z")]},
    12: {"body": "Blocked by #11", "labels": ["ready-for-agent"], "comments": []},
    13: {"body": "Blocked by #90", "comments": []},
    90: {"body": "", "state": "closed", "comments": []},
}
EXPECTED = [
    "#10 done: ticked on the parent",
    "#11 taken [11-b]: s-other is live (last comment 2026-11-13 11:00Z)",
    "#12 blocked: waits on #11",
    "#13 frontier: no branch yet: push one at the feature SHA and post Started",
]


@pytest.mark.parametrize("tracker", ["github", "gitlab"])
def test_cli_issues_reads_the_forge_and_prints_each_state(tracker, capsys):
    forge = Forge(ISSUES, ["main", "11-b"])
    assert frontier.main(["issues", "#1", "--tracker", tracker, "--session", "s-me"], forge, NOW) == 0
    assert capsys.readouterr().out.splitlines() == EXPECTED
    assert {call[0] for call in forge.calls} == {"git", "gh" if tracker == "github" else "glab"}


@pytest.mark.parametrize("tracker", ["github", "gitlab"])
def test_cli_claim_on_the_forge_prints_the_winner(tracker, capsys):
    decision = {
        7: {
            "body": "",
            "comments": [("Claimed by s-a", "2026-11-13T10:00:00Z"), ("Claimed by s-b", "2026-11-13T10:01:00Z")],
        }
    }
    assert frontier.main(["claim", "7", "--tracker", tracker], Forge(decision), NOW) == 0
    assert capsys.readouterr().out == "s-a\n"


@pytest.fixture
def local(tmp_path):
    spec = tmp_path / ".scratch" / "greet" / "spec.md"
    (spec.parent / "issues").mkdir(parents=True)
    spec.write_text("# Greet\n## Slices\n- [x] 01 greet\n- [ ] 02 greet all\n- [ ] 03 farewell\n- [ ] 05 wave\n")
    (spec.parent / "issues" / "01-greet.md").write_text("# 01 Greet\nStatus: closed\n")
    (spec.parent / "issues" / "04-hello.md").write_text("# 04 Hello, from an earlier spec\nStatus: closed\n")
    (spec.parent / "issues" / "05-wave.md").write_text("# 05 Wave\nStatus: ready-for-agent\nBlocked by: 04, 07\n")
    (spec.parent / "issues" / "02-greet-all.md").write_text(
        "# 02 Greet all\nStatus: ready-for-agent\nBlocked by: 01\n\n## Comments\n\nStarted 02-greet-all\n"
        "compost-session: s-other 2026-11-13T11:30:00Z\n\nA note with no trailer yet\n"
    )
    (spec.parent / "issues" / "03-farewell.md").write_text("# 03 Farewell\nStatus: ready-for-human\n")
    return spec


def test_cli_issues_on_a_local_tracker_reads_the_files(local, capsys):
    forge = Forge({}, ["02-greet-all"])
    assert frontier.main(["issues", str(local), "--tracker", "local", "--session", "s-me"], forge, NOW) == 0
    assert capsys.readouterr().out.splitlines() == [
        "#1 done: closed",
        "#2 taken [02-greet-all]: s-other is live (last comment 2026-11-13 11:30Z)",
        "#3 ready-for-human: needs a person; list it under Risk",
        "#5 blocked: waits on #7",
    ]


def test_cli_claim_on_a_local_decision_reads_its_claim_line(tmp_path, capsys):
    decision = tmp_path / "01-store.md"
    decision.write_text("# 01 Store\nKind: research\nStatus: claimed\nClaimed: s-l 2026-11-13T11:00:00Z\n")
    assert frontier.main(["claim", str(decision), "--tracker", "local"], Forge({}), NOW) == 0
    assert capsys.readouterr().out == "s-l\n"


def test_cli_reports_a_failed_command_and_exits_one(local, capsys):
    assert frontier.main(["issues", str(local), "--tracker", "local"], Forge({}), NOW) == 1
    assert capsys.readouterr().err == "frontier.py: no session file in this stub\n"


def test_run_command_turns_a_failure_into_a_frontier_error():
    assert frontier.run_command(["echo", "hi"]) == "hi\n"
    with pytest.raises(frontier.FrontierError, match="git rev-parse --verify failed: fatal"):
        frontier.run_command(["git", "rev-parse", "--verify", "no-such-ref-anywhere"])
    with pytest.raises(frontier.FrontierError, match="no-such-binary-xyz failed"):
        frontier.run_command(["no-such-binary-xyz"])


def test_session_is_made_once_per_clone_and_reads_the_same_from_its_worktrees(tmp_path, monkeypatch, capsys):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    git = ["git", "-C", str(tmp_path), "-c", "user.email=t@t", "-c", "user.name=t", "-c", "commit.gpgsign=false"]
    subprocess.run([*git, "commit", "-q", "--allow-empty", "-m", "x"], check=True)
    subprocess.run([*git, "worktree", "add", "-q", str(tmp_path / "wt"), "-b", "feature"], check=True)
    monkeypatch.chdir(tmp_path)
    assert frontier.main(["session"], now=NOW) == 0
    first = capsys.readouterr().out.strip()
    assert first.startswith("s-") and len(first) == 10
    assert frontier.main(["session"]) == 0
    assert capsys.readouterr().out.strip() == first
    assert (tmp_path / ".git" / "compost-session").read_text().strip() == first
    monkeypatch.chdir(tmp_path / "wt")
    assert frontier.main(["session"]) == 0
    assert capsys.readouterr().out.strip() == first
    monkeypatch.setenv("COMPOST_SESSION", "s-second-window")
    assert frontier.main(["session"]) == 0
    assert capsys.readouterr().out.strip() == "s-second-window"


def test_remote_branches_reads_origin_heads_from_real_git(tmp_path, monkeypatch):
    origin, clone = tmp_path / "origin.git", tmp_path / "clone"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
    subprocess.run(["git", "clone", "-q", str(origin), str(clone)], check=True, capture_output=True)
    git = ["git", "-C", str(clone), "-c", "user.email=t@t", "-c", "user.name=t", "-c", "commit.gpgsign=false"]
    subprocess.run([*git, "commit", "-q", "--allow-empty", "-m", "x"], check=True)
    subprocess.run([*git, "push", "-q", "origin", "HEAD:refs/heads/14-export", "HEAD:refs/heads/main"], check=True)
    monkeypatch.chdir(clone)
    assert sorted(frontier.remote_branches(frontier.run_command)) == ["14-export", "main"]
