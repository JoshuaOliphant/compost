# ABOUTME: Tests the verify gate, the PreToolUse hook on Bash: which commands it gates (git push, PR create), how it
# ABOUTME: finds the repo, and what each mode does with an unstamped HEAD: log it, block it twice then let it through.
import io
import json
import os
import subprocess
import sys

import pytest
import stamp
import verify_gate
from conftest import PLUGIN_ROOT, run_git


@pytest.fixture
def gate_log(tmp_path, monkeypatch):
    path = tmp_path / "home" / ".claude" / "verify-gate" / "log.jsonl"
    monkeypatch.setattr(verify_gate, "LOG", path)
    monkeypatch.delenv(verify_gate.MODE_VAR, raising=False)
    return path


def lines(log) -> list[dict]:
    return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


def gate(payload: dict) -> dict | None:
    """Runs the hook's main on `payload` and returns the decision it printed, or None when it printed nothing."""
    out = io.StringIO()
    assert verify_gate.main(io.StringIO(json.dumps(payload)), out) == 0
    return json.loads(out.getvalue()) if out.getvalue() else None


def hook(command: str, cwd, session: str = "s-1") -> dict:
    return {
        "session_id": session,
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command, "description": "push"},
        "cwd": str(cwd),
    }


def test_observe_lets_an_unstamped_push_through_and_logs_session_repo_and_sha(work_repo, gate_log):
    head = run_git(work_repo, "rev-parse", "HEAD")
    assert gate(hook("git push origin main", work_repo)) is None
    [line] = lines(gate_log)
    assert line | {"time": None} == {
        "time": None,
        "session_id": "s-1",
        "repo": str(work_repo),
        "sha": head,
        "kind": "push",
        "mode": "observe",
        "action": "observed",
    }


@pytest.mark.parametrize(
    "command, kind",
    [
        ("git push", "push"),
        ("git push -u origin main", "push"),
        ("git push -u origin no-such-branch", None),
        ("GIT_TRACE=1 git push", "push"),
        ("git status && git push --follow-tags", "push"),
        ("git -c push.default=current push", "push"),
        ("git --no-pager push", "push"),
        ("git --version && git push", "push"),
        ("git -C && git push", "push"),
        ("FOO=1; git push", "push"),
        ("cd && git push", "push"),
        ("bash -lc true && git push", "push"),
        ("echo 'unterminated && git push", None),
        ("gh pr create --draft --title x --body y", "pr-create"),
        ("gh api repos/o/r/pulls -f title=x -f head=main -f base=main", "pr-create"),
        ("gh api repos/o/r/pulls --raw-field=title=x", "pr-create"),
        ("gh api --method post repos/o/r/pulls --input body.json", "pr-create"),
        ("gh api -X POST /repos/o/r/pulls/", "pr-create"),
        ("gh api repos/o/r/pulls -X POST", "pr-create"),
        ("glab mr create --draft --target-branch main --title x", "pr-create"),
        ("(cd . && git push)", "push"),
        ("env X=1 git push", "push"),
        ("timeout 60 git push", "push"),
        ("command git push", "push"),
        ("nohup git push", "push"),
        ("gh api --method=POST repos/o/r/pulls --input body.json", "pr-create"),
        ("gh api -XPOST repos/o/r/pulls", "pr-create"),
        ("gh api repos/o/r/issues -f title='list pulls'", None),
        ("git push origin :feat", None),
        ("git status", None),
        ("git log --grep push", None),
        ("echo git push", None),
        ("echo push", None),
        ("make push", None),
        ("git push origin --delete feat", None),
        ("git commit -m 'git push later'", None),
        ("gh pr list", None),
        ("glab mr list", None),
        ("echo pr create", None),
        ("hub pr create", None),
        ("gh issue create --title pulls -F body.md", None),
        ("gh api repos/o/r/pulls", None),
        ("gh api repos/o/r/pulls/3 -X PATCH -f body=x", None),
        ("gh api -X PUT repos/o/r/pulls -f title=x", None),
        ("gh api repos/o/r/issues -f title=x", None),
        ("gh api -X GET repos/o/r/pulls -f state=open", None),
    ],
    ids=lambda value: value if isinstance(value, str) else str(value),
)
def test_only_a_push_or_a_pr_create_is_gated(work_repo, gate_log, command, kind):
    assert gate(hook(command, work_repo)) is None
    assert [line["kind"] for line in lines(gate_log)] == ([kind] if kind else [])


@pytest.mark.parametrize(
    "command",
    [
        "git -C {repo} push origin HEAD",
        "cd {repo} && git push",
        "cd work; git push",
        "git -c core.pager=cat -C work push",
        "git -C ~/work push",
        "cd ~/work && git push",
    ],
    ids=["git -C absolute", "cd absolute", "cd relative", "git -C relative after -c", "git -C home", "cd home"],
)
def test_the_repo_is_the_one_the_command_points_at(work_repo, gate_log, command, monkeypatch):
    monkeypatch.setenv("HOME", str(work_repo.parent))
    gate(hook(command.format(repo=work_repo), work_repo.parent))
    assert [line["repo"] for line in lines(gate_log)] == [str(work_repo)]


@pytest.mark.parametrize(
    "command, pushed",
    [
        ("git push origin feature", "feature"),
        ("git push -u origin +feature:other", "feature"),
        ("git push --push-option ci.skip origin feature", "feature"),
        ("git push origin HEAD:main", None),
        ("git push origin refs/notes/compost-verify", None),
        ("git push origin +refs/notes/compost-verify:refs/notes/compost-verify", None),
        ("git push", None),
    ],
)
def test_the_commit_judged_is_the_one_the_push_sends(work_repo, gate_log, command, pushed, monkeypatch):
    """HEAD is stamped and `feature` (one commit back) is not: only a push that sends `feature` is logged."""
    run_git(work_repo, "branch", "feature", "HEAD~1")
    monkeypatch.chdir(work_repo)
    assert stamp.main(["write", "--json", "{}"]) == 0
    gate(hook(command, work_repo))
    expected = [run_git(work_repo, "rev-parse", pushed)] if pushed else []
    assert [line["sha"] for line in lines(gate_log)] == expected


@pytest.mark.parametrize(
    "command",
    [
        "git commit -m \"$(cat <<'EOF'\nfeat: gate pushes\n\ngit push of an unstamped HEAD is now logged\nEOF\n)\"",
        "gh issue create --title t --body-file - <<EOF\ngh pr create --draft\ngit push origin main\nEOF",
        'git commit -m "fix: x; git push later (maybe) | gh pr create"',
        "cat <<-EOF > notes.md\n\tgit push\n\tEOF",
    ],
    ids=["heredoc-commit-message", "heredoc-issue-body", "quoted-message", "indented-heredoc"],
)
def test_words_inside_quotes_or_a_heredoc_are_never_a_command(work_repo, gate_log, monkeypatch, command):
    monkeypatch.setenv(verify_gate.MODE_VAR, "enforce")
    assert gate(hook(command, work_repo)) is None
    assert lines(gate_log) == []


def test_a_push_after_a_heredoc_is_still_gated(work_repo, gate_log):
    gate(hook("cat <<EOF > m.txt\ngit push\nEOF\ngit push origin main", work_repo))
    assert [line["kind"] for line in lines(gate_log)] == ["push"]


@pytest.mark.parametrize(
    "command, judged",
    [
        ("gh pr create --head feature --title t", "feature"),
        ("gh pr create --head=me:feature", "feature"),
        ("gh pr create -H feature", "feature"),
        ("gh api repos/o/r/pulls -H 'Accept: application/vnd.github+json' -f head=feature -f base=main", "feature"),
        ("gh api repos/o/r/pulls --raw-field=head=me:feature", "feature"),
    ],
    ids=["--head", "--head=owner:branch", "-H", "api -f head with -H header", "api --raw-field=head="],
)
def test_a_pr_create_is_judged_by_its_head_branch(work_repo, gate_log, monkeypatch, command, judged):
    run_git(work_repo, "branch", "feature", "HEAD~1")
    monkeypatch.chdir(work_repo)
    assert stamp.main(["write", "--json", "{}"]) == 0
    gate(hook(command, work_repo))
    assert [line["sha"] for line in lines(gate_log)] == [run_git(work_repo, "rev-parse", judged)]


def test_a_push_outside_any_repo_is_left_to_git(tmp_path, gate_log):
    assert gate(hook("git push", tmp_path)) is None
    assert lines(gate_log) == []


def test_enforce_blocks_twice_naming_verify_then_lets_the_third_through_as_a_bypass(work_repo, gate_log, monkeypatch):
    """Pushes observed in between, in the same session, are not blocks and do not count toward the bypass."""
    for attempt, observed_after in ((1, 2), (2, 0)):
        monkeypatch.setenv(verify_gate.MODE_VAR, "enforce")
        output = gate(hook("git push", work_repo))["hookSpecificOutput"]
        assert output["hookEventName"] == "PreToolUse"
        assert output["permissionDecision"] == "deny"
        assert "compost:verify" in output["permissionDecisionReason"]
        assert f"block {attempt} of 2" in output["permissionDecisionReason"]
        monkeypatch.setenv(verify_gate.MODE_VAR, "observe")
        for _ in range(observed_after):
            gate(hook("git push", work_repo))
    monkeypatch.setenv(verify_gate.MODE_VAR, "enforce")
    assert gate(hook("git push", work_repo)) is None
    actions = ["blocked", "observed", "observed", "blocked", "bypass"]
    assert [line["action"] for line in lines(gate_log)] == actions
    for other in ("s-0", "s-2"):
        assert gate(hook("git push", work_repo, session=other)) is not None, f"{other} inherited s-1's blocks"


def test_enforce_still_counts_its_blocks_past_a_corrupt_log_line(work_repo, gate_log, monkeypatch):
    """The log is shared by every session; a torn or hand-edited line must not turn enforce into a silent pass."""
    gate_log.parent.mkdir(parents=True)
    gate_log.write_text('{"session_id": "s-1", "action": "blo\n[1, 2]\n{"action": "blocked"}\n')
    monkeypatch.setenv(verify_gate.MODE_VAR, "enforce")
    for attempt in (1, 2):
        reason = gate(hook("git push", work_repo))["hookSpecificOutput"]["permissionDecisionReason"]
        assert f"block {attempt} of 2" in reason
    assert gate(hook("git push", work_repo)) is None


@pytest.mark.parametrize(
    "mode, stamped",
    [("observe", True), ("enforce", True), ("off", False), ("OFF", False)],
    ids=["stamped observe", "stamped enforce", "off", "off uppercase"],
)
def test_a_stamped_head_or_mode_off_is_neither_logged_nor_blocked(work_repo, gate_log, monkeypatch, mode, stamped):
    monkeypatch.setenv(verify_gate.MODE_VAR, mode)
    if stamped:
        stamp.write(work_repo, "HEAD", {"ac": "7/7"})
    assert gate(hook("git push", work_repo)) is None
    assert lines(gate_log) == []


def test_an_unknown_mode_observes(work_repo, gate_log, monkeypatch):
    monkeypatch.setenv(verify_gate.MODE_VAR, "strict")
    assert gate(hook("git push", work_repo)) is None
    assert [line["mode"] for line in lines(gate_log)] == ["observe"]


@pytest.mark.parametrize(
    "stdin",
    ["not json", json.dumps({"tool_name": "Bash"}), json.dumps({"tool_name": "Bash", "tool_input": {"command": 3}})],
    ids=["unparseable", "no tool input", "command not a string"],
)
def test_bad_input_never_traps_the_call(stdin, gate_log):
    out = io.StringIO()
    assert verify_gate.main(io.StringIO(stdin), out) == 0
    assert out.getvalue() == ""


def test_the_registered_hook_command_blocks_an_unstamped_push_under_enforce(work_repo, tmp_path):
    """Runs the command hooks.json registers, as Claude Code would: plain python3, stdin JSON, stdout the decision."""
    [entry] = json.loads((PLUGIN_ROOT / "hooks" / "hooks.json").read_text())["hooks"]["PreToolUse"]
    assert entry["matcher"] == "Bash"
    [command] = [handler["command"] for handler in entry["hooks"]]
    env = {**os.environ, "CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT), "HOME": str(tmp_path), verify_gate.MODE_VAR: "enforce"}
    ran = subprocess.run(
        command.replace("python3", sys.executable, 1),
        shell=True,
        input=json.dumps(hook("git push", work_repo)),
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    assert json.loads(ran.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert (tmp_path / ".claude" / "verify-gate" / "log.jsonl").exists()
