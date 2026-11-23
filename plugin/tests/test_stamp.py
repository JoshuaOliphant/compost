# ABOUTME: Tests stamp.py, the verify stamp kept as a git note under refs/notes/compost-verify: write, show, and log
# ABOUTME: against a real repo, and that a summary that is not one JSON object is refused without writing anything.
import io
import json

import pytest
import stamp
from conftest import run_git

SUMMARY = {"gates": "4/4", "ac": "7/7", "mutants": "41/45", "rung": "e2e"}


def run(*argv: str) -> tuple[int, str]:
    out = io.StringIO()
    code = stamp.main(list(argv), out)
    return code, out.getvalue()


@pytest.fixture
def commits(work_repo, monkeypatch) -> list[str]:
    monkeypatch.chdir(work_repo)
    return run_git(work_repo, "rev-list", "--reverse", "HEAD").split()


def test_a_written_stamp_shows_on_its_commit_and_no_other(commits):
    first, second, _ = commits
    assert run("write", "--rev", first, "--json", json.dumps(SUMMARY)) == (0, "")

    code, shown = run("show", first)
    assert code == 0
    stamped = json.loads(shown)
    assert stamped | {"time": None} == SUMMARY | {"time": None}
    assert stamped["time"].endswith("+00:00")
    assert shown.count("\n") == 1
    assert run("show", second) == (0, "none\n")


def test_writing_again_replaces_the_stamp_and_write_defaults_to_head(commits):
    run("write", "--json", json.dumps({"ac": "6/7"}))
    run("write", "--json", json.dumps({"ac": "7/7"}))
    assert json.loads(run("show", "HEAD")[1])["ac"] == "7/7"
    assert run("show", commits[-1])[1] != "none\n"


def test_log_lists_every_commit_in_the_range_with_its_stamp_or_none(commits):
    first, second, third = commits
    run("write", "--rev", second, "--json", json.dumps(SUMMARY))
    code, listed = run("log", f"{first}..HEAD")
    assert code == 0
    lines = listed.splitlines()
    assert [line.split(" ", 1)[0] for line in lines] == [third[:12], second[:12]]
    assert lines[0].split(" ", 1)[1] == "none"
    assert json.loads(lines[1].split(" ", 1)[1])["rung"] == "e2e"


@pytest.mark.parametrize("summary", ["not json", "[1, 2]", '"done"'], ids=["unparseable", "a list", "a bare string"])
def test_a_summary_that_is_not_a_json_object_is_refused(commits, summary, capsys):
    assert run("write", "--json", summary)[0] == 2
    assert "one JSON object" in capsys.readouterr().err
    assert run("show", "HEAD") == (0, "none\n")


@pytest.mark.parametrize("argv", [["show", "no-such-rev"], ["log", "no-such-rev..HEAD"]], ids=["show", "log"])
def test_a_revision_git_cannot_resolve_is_an_error_not_none(commits, argv, capsys):
    assert run(*argv) == (2, "")
    assert "no-such-rev" in capsys.readouterr().err
