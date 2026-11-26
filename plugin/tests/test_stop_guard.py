# ABOUTME: Tests the compost:implement Stop hook: when it acts (an implement run, not already continuing), how it finds
# ABOUTME: the final message, and that every failure allows the stop and leaves one line in the log.
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest
import stop_guard
from conftest import StubClient, noul
from jevtools.core import Unavailable

LOADS_IMPLEMENT = {
    "type": "assistant",
    "message": {
        "id": "m0",
        "content": [{"type": "tool_use", "name": "Skill", "input": {"skill": "compost:implement"}}],
    },
}
SLASH_IMPLEMENT = {
    "type": "user",
    "message": {
        "content": "<command-message>compost:implement</command-message>\n<command-name>/compost:implement</command-name>"
    },
}
SKILL_LISTING = {
    "type": "attachment",
    "attachment": {"content": "- compost:implement: the entry point once issues exist"},
}


def said(message_id: str, text: str, **extra) -> dict:
    return {"type": "assistant", "message": {"id": message_id, "content": [{"type": "text", "text": text}]}, **extra}


@pytest.fixture
def log(tmp_path, monkeypatch):
    path = tmp_path / "logs" / "stop-guard.log"
    monkeypatch.setattr(stop_guard, "LOG", path)
    return path


@pytest.fixture
def transcript(tmp_path):
    def write(*entries, raw: str = "") -> str:
        path = tmp_path / "session.jsonl"
        path.write_text(raw + "".join(json.dumps(entry) + "\n" for entry in entries))
        return str(path)

    return write


def judging(waits: float, allowed: float):
    return lambda: StubClient(lambda state, questions: {"waits": noul(waits), "allowed": noul(allowed)})


@pytest.mark.parametrize("loaded", [LOADS_IMPLEMENT, SLASH_IMPLEMENT], ids=["skill tool", "typed command"])
def test_a_question_mid_implement_is_sent_back_with_the_ruling_instruction(transcript, loaded):
    path = transcript(loaded, said("m1", "Which library do you prefer?"))
    verdict = stop_guard.decide({"transcript_path": path, "stop_hook_active": False}, judging(0.9, 0.1))
    assert verdict == {"decision": "block", "reason": stop_guard.reason()}
    assert "post a ruling as an issue comment" in verdict["reason"]


def test_an_allowed_stop_goes_through(transcript):
    path = transcript(SLASH_IMPLEMENT, said("m1", "All issues landed. Shall I merge to main?"))
    assert stop_guard.decide({"transcript_path": path}, judging(0.9, 0.9)) is None


def test_a_stop_hook_continuation_is_never_blocked_again(tmp_path):
    hook = {"transcript_path": str(tmp_path / "never-read.jsonl"), "stop_hook_active": True}
    assert stop_guard.decide(hook, judging(1.0, 0.0)) is None


@pytest.mark.parametrize(
    "entries",
    [[said("m1", "Which library do you prefer?")], [SKILL_LISTING, said("m1", "Which library do you prefer?")]],
    ids=["implement never mentioned", "implement only listed, never loaded"],
)
def test_sessions_that_never_loaded_implement_are_left_alone(transcript, entries):
    client = StubClient(lambda state, questions: {})
    assert stop_guard.decide({"transcript_path": transcript(*entries)}, lambda: client) is None
    assert client.calls == []


def test_the_final_message_comes_from_the_hook_input_when_given(transcript):
    client = StubClient(lambda state, questions: {"waits": noul(0.1), "allowed": noul(0.1)})
    path = transcript(LOADS_IMPLEMENT, said("m1", "from the transcript"))
    stop_guard.decide({"transcript_path": path, "last_assistant_message": "from the hook"}, lambda: client)
    assert client.calls[0][0]["message"] == "from the hook"


def test_the_final_message_is_the_last_main_thread_reply_read_from_the_transcript(transcript):
    client = StubClient(lambda state, questions: {"waits": noul(0.1), "allowed": noul(0.1)})
    path = transcript(
        LOADS_IMPLEMENT,
        said("m1", "An earlier reply."),
        {"type": "summary", "message": "not a dict of content"},
        said("m2", "Two options: dateparser or pendulum."),
        {"type": "assistant", "message": {"id": "m2", "content": [{"type": "tool_use", "name": "Bash"}, "stray"]}},
        said("m2", "Which library do you prefer?"),
        said("s1", "A subagent's reply.", isSidechain=True),
        raw="not json\n[1, 2]\n",
    )
    stop_guard.decide({"transcript_path": path}, lambda: client)
    assert client.calls[0][0]["message"] == "Two options: dateparser or pendulum.\nWhich library do you prefer?"


def test_a_turn_with_no_text_is_not_judged(transcript):
    client = StubClient(lambda state, questions: {})
    assert stop_guard.decide({"transcript_path": transcript(LOADS_IMPLEMENT)}, lambda: client) is None
    assert client.calls == []


def test_main_prints_the_block_for_claude_code(transcript, capsys, log):
    path = transcript(LOADS_IMPLEMENT, said("m1", "Which library do you prefer?"))
    assert stop_guard.main(io.StringIO(json.dumps({"transcript_path": path})), judging(0.9, 0.1)) == 0
    assert json.loads(capsys.readouterr().out)["decision"] == "block"
    assert not log.exists()


def test_main_reads_stdin_and_prints_nothing_when_the_stop_is_allowed(transcript, capsys, monkeypatch):
    path = transcript(LOADS_IMPLEMENT, said("m1", "Done: PR #52 is up and the suite is green."))
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"transcript_path": path})))
    assert stop_guard.main(client_factory=judging(0.05, 0.3)) == 0
    assert capsys.readouterr().out == ""


def refuse():
    raise Unavailable("TYPESAFE_API_KEY is not set")


@pytest.mark.parametrize(
    ("stdin", "client_factory", "logged"),
    [
        ("not json", judging(1.0, 0.0), "allowed the stop after JSONDecodeError"),
        (json.dumps({}), judging(1.0, 0.0), "allowed the stop after KeyError"),
        (None, refuse, "allowed the stop after Unavailable: TYPESAFE_API_KEY is not set"),
    ],
    ids=["bad hook json", "no transcript path", "no key"],
)
def test_any_failure_allows_the_stop_silently_and_logs_one_line(transcript, capsys, log, stdin, client_factory, logged):
    hook = stdin or json.dumps({"transcript_path": transcript(LOADS_IMPLEMENT, said("m1", "Which one?"))})
    assert stop_guard.main(io.StringIO(hook), client_factory) == 0
    assert capsys.readouterr().out == ""
    [line] = log.read_text().splitlines()
    assert logged in line


LOADS_FINISH = {
    "type": "assistant",
    "message": {"id": "f0", "content": [{"type": "tool_use", "name": "Skill", "input": {"skill": "compost:finish"}}]},
}
LOADS_PAUSE = {
    "type": "assistant",
    "message": {"id": "p0", "content": [{"type": "tool_use", "name": "Skill", "input": {"skill": "compost:pause"}}]},
}
SLASH_PAUSE = {
    "type": "user",
    "message": {
        "content": "<command-message>compost:pause</command-message>\n<command-name>/compost:pause</command-name>"
    },
}
SLASH_FINISH = {
    "type": "user",
    "message": {
        "content": "<command-message>compost:finish</command-message>\n<command-name>/compost:finish</command-name>"
    },
}
NOTIFIED = {
    "type": "user",
    "message": {"content": "<task-notification>\n<status>completed</status>\n</task-notification>"},
}
WAITS = said("m9", "PR #52 merged. On naming: I'd call it Ledger. If you agree, I'd rename it.")


def user(content, **extra) -> dict:
    return {"type": "user", "message": {"role": "user", "content": content}, **extra}


@pytest.mark.parametrize(
    "entries",
    [
        [LOADS_IMPLEMENT, said("m1", "PR #52 is up."), LOADS_FINISH, WAITS],
        [SLASH_IMPLEMENT, said("m1", "PR #52 is up."), SLASH_FINISH, WAITS],
        [LOADS_IMPLEMENT, LOADS_FINISH, said("m2", "Discarded."), NOTIFIED, WAITS],
        [
            LOADS_IMPLEMENT,
            said("m1", "#13 landed."),
            user("Stop here for today."),
            LOADS_PAUSE,
            said("m2", "Paused; resume from #14."),
            NOTIFIED,
            WAITS,
        ],
        [LOADS_IMPLEMENT, said("m1", "#13 landed."), SLASH_PAUSE, said("m2", "Paused."), NOTIFIED, WAITS],
    ],
    ids=[
        "finish loaded after implement",
        "finish typed after implement",
        "finish then a notification",
        "pause the user asked for, then a notification",
        "pause typed, then a notification",
    ],
)
def test_finish_or_a_pause_the_user_asked_for_ends_the_run_so_a_stop_after_it_is_never_judged(transcript, entries):
    client = StubClient(lambda state, questions: {})
    assert stop_guard.decide({"transcript_path": transcript(*entries)}, lambda: client) is None
    assert client.calls == []


def test_a_pause_the_agent_starts_on_its_own_leaves_the_run_guarded(transcript):
    path = transcript(LOADS_IMPLEMENT, said("m1", "#13 landed."), LOADS_PAUSE, NOTIFIED, WAITS)
    assert stop_guard.decide({"transcript_path": path}, judging(0.9, 0.1))["decision"] == "block"


@pytest.mark.parametrize("ended", [LOADS_FINISH, SLASH_PAUSE], ids=["after finish", "after pause"])
def test_an_implement_load_after_the_run_ended_starts_a_new_run(transcript, ended):
    path = transcript(LOADS_IMPLEMENT, ended, SLASH_IMPLEMENT, said("m1", "Which library do you prefer?"))
    assert stop_guard.decide({"transcript_path": path}, judging(0.9, 0.1)) == {
        "decision": "block",
        "reason": stop_guard.reason(),
    }


@pytest.mark.parametrize(
    "question",
    [
        user("Should the ledger live under scripts/?"),
        user([{"type": "text", "text": "Should the ledger live under scripts/?"}]),
        user("<system-reminder>The plan changed.</system-reminder>\nShould the ledger live under scripts/?"),
        user(
            "<command-message>compost:wait-what</command-message>\n<command-name>/compost:wait-what</command-name>\n"
            "<command-args>what's a ledger?</command-args>"
        ),
    ],
    ids=["plain string", "text block", "typed text beside an injected reminder", "slash command typed mid-run"],
)
def test_a_stop_answering_a_message_typed_during_the_run_is_allowed(transcript, question):
    client = StubClient(lambda state, questions: {})
    path = transcript(LOADS_IMPLEMENT, said("m1", "Working on #78."), question, WAITS)
    assert stop_guard.decide({"transcript_path": path}, lambda: client) is None
    assert client.calls == []


@pytest.mark.parametrize(
    "injected",
    [
        user([{"type": "tool_result", "tool_use_id": "t1", "content": "Should we?"}]),
        user("Base directory for this skill: compost/skills/implement", isMeta=True),
        user("<system-reminder>Should we?</system-reminder>"),
        user("<task-notification>\n<status>completed</status>\n</task-notification>"),
        user("Should the ledger live under scripts/?", isSidechain=True),
        user("This session is being continued from a previous conversation.", isCompactSummary=True),
        user("Shown in the transcript only.", isVisibleInTranscriptOnly=True),
        {**LOADS_FINISH, "isSidechain": True},
        user('<teammate-message teammate_id="w1">Should we?</teammate-message>'),
    ],
    ids=[
        "tool result",
        "meta entry",
        "system reminder",
        "task notification",
        "sidechain prompt",
        "compaction summary",
        "transcript-only entry",
        "sidechain finish load",
        "teammate message",
    ],
)
def test_user_entries_claude_code_writes_do_not_count_as_typed(transcript, injected):
    path = transcript(LOADS_IMPLEMENT, injected, said("m1", "Which library do you prefer?"))
    assert stop_guard.decide({"transcript_path": path}, judging(0.9, 0.1))["decision"] == "block"


def test_a_notification_after_the_answered_message_puts_the_run_back_on_its_own(transcript):
    path = transcript(LOADS_IMPLEMENT, user("Go on."), said("m1", "On it."), NOTIFIED, WAITS)
    assert stop_guard.decide({"transcript_path": path}, judging(0.9, 0.1))["decision"] == "block"


def test_a_message_typed_before_the_run_started_does_not_attend_it(transcript):
    path = transcript(user("Implement #78 please."), SLASH_IMPLEMENT, said("m1", "Which library do you prefer?"))
    assert stop_guard.decide({"transcript_path": path}, judging(0.9, 0.1))["decision"] == "block"


# A Claude Projects thread delivers the user's message as one entry wrapped whole in a <wake>, so no text survives
# INJECTED; Claude Code's own `origin` on the entry says who sent it (#206).
WOKEN = (
    '<wake reason="mention">\n  <message from="human" trust="principal">Is csi or syseng the better fit?</message>\n'
    "</wake>"
)


def test_a_wrapped_message_the_user_sent_attends_the_run(transcript):
    client = StubClient(lambda state, questions: {})
    path = transcript(LOADS_IMPLEMENT, said("m1", "PR #52 is up."), user(WOKEN, origin={"kind": "human"}), WAITS)
    assert stop_guard.decide({"transcript_path": path}, lambda: client) is None
    assert client.calls == []


@pytest.mark.parametrize(
    "origin",
    [{"kind": "task-notification"}, {"kind": "peer"}, {}, None, "human"],
    ids=["notification", "peer", "no kind", "null", "not a dict"],
)
def test_a_prompt_whose_origin_is_not_human_is_not_the_users_whatever_its_text(transcript, origin):
    path = transcript(LOADS_IMPLEMENT, user("Should the ledger live under scripts/?", origin=origin), WAITS)
    assert stop_guard.decide({"transcript_path": path}, judging(0.9, 0.1))["decision"] == "block"


def test_a_wrapped_message_with_no_origin_keeps_the_text_rule(transcript):
    path = transcript(LOADS_IMPLEMENT, user(WOKEN), WAITS)
    assert stop_guard.decide({"transcript_path": path}, judging(0.9, 0.1))["decision"] == "block"


@pytest.mark.parametrize(
    ("entries", "loads_jev"),
    [([said("m1", "Done for today.")], False), ([LOADS_IMPLEMENT, said("m1", "Which library?")], True)],
    ids=["no implement run", "implement run"],
)
def test_jev_and_the_sdk_load_only_when_there_is_a_message_to_judge(transcript, tmp_path, entries, loads_jev):
    # The hook runs on every turn of every session, and importing Jev and the SDK is most of its start.
    hook = json.dumps({"transcript_path": transcript(*entries), "stop_hook_active": False})
    probe = (
        "import io, pathlib, sys; import stop_guard; stop_guard.LOG = pathlib.Path(sys.argv[1]);"
        f" stop_guard.main(io.StringIO({hook!r}), client_factory=lambda: (_ for _ in ()).throw(RuntimeError('no live Jev in a unit test')));"
        " print(sorted(m for m in ('jev', 'jevtools', 'typesafe_sdk') if m in sys.modules))"
    )
    scripts = Path(stop_guard.__file__).parent
    loaded = subprocess.run(
        [sys.executable, "-c", probe, str(tmp_path / "stop-guard.log")],
        cwd=scripts,
        capture_output=True,
        text=True,
        check=True,
        env={"PYTHONPATH": str(scripts)},
    ).stdout.strip()
    assert (loaded != "[]") is loads_jev


@pytest.mark.parametrize(("spec", "imports_needs_uv"), [(None, True), (object(), False)], ids=["missing", "found"])
def test_ensure_sdk_hands_off_to_needs_uv_only_when_the_sdk_is_missing(monkeypatch, spec, imports_needs_uv):
    monkeypatch.delitem(sys.modules, "needs_uv", raising=False)
    stop_guard.ensure_sdk(lambda name: spec)
    assert ("needs_uv" in sys.modules) is imports_needs_uv


CONTRACT = "Run contract stops:\n- merging to the repository's default branch\n- picking the payment provider\n"


@pytest.mark.parametrize(
    ("entries", "stops"),
    [
        (
            [LOADS_IMPLEMENT, said("m1", f"Contract read.\n{CONTRACT}\nPrerequisites checked.")],
            [
                "merging to the repository's default branch",
                "picking the payment provider",
            ],
        ),
        (
            [LOADS_IMPLEMENT, said("m1", CONTRACT.rstrip())],
            [
                "merging to the repository's default branch",
                "picking the payment provider",
            ],
        ),
        (
            [LOADS_IMPLEMENT, said("m1", CONTRACT), said("m2", "Run contract stops:\n- picking the logo\n\nGoing on.")],
            [
                "merging to the repository's default branch",
                "picking the payment provider",
            ],
        ),
        ([LOADS_IMPLEMENT, said("m1", "Run contract stops:\n\nNone added.")], []),
        ([said("m1", CONTRACT), SLASH_IMPLEMENT, said("m2", "Reading the contract again.")], []),
        ([LOADS_IMPLEMENT, said("s1", CONTRACT, isSidechain=True)], []),
        ([LOADS_IMPLEMENT, user(CONTRACT), said("m1", "Run contract stops:\n- deleting data  \n")], ["deleting data"]),
        ([LOADS_IMPLEMENT, said("m1", f"**{CONTRACT}**")], []),
        ([said("m1", CONTRACT)], []),
    ],
    ids=[
        "block between other text",
        "block at the end with no blank line",
        "a later block can't widen the first",
        "block with no items",
        "block before the latest implement load",
        "subagent's block",
        "block in a user entry, then one with trailing spaces",
        "bold header",
        "no implement load",
    ],
)
def test_contract_stops_are_the_first_block_implement_printed_since_it_loaded(entries, stops):
    assert stop_guard.contract_stops(entries) == stops


def test_the_contract_stops_implement_printed_reach_jev_and_the_reason(transcript):
    client = StubClient(lambda state, questions: {"waits": noul(0.9), "allowed": noul(0.1)})
    path = transcript(LOADS_IMPLEMENT, said("m1", CONTRACT), said("m2", "Which library do you prefer?"))
    verdict = stop_guard.decide({"transcript_path": path}, lambda: client)
    allowed = client.calls[0][0]["allowed_stops"]
    assert allowed[-1] == "picking the payment provider"
    assert allowed.count("merging to the repository's default branch") == 1
    assert verdict == {"decision": "block", "reason": stop_guard.reason(["picking the payment provider"])}
    assert "picking the payment provider" in verdict["reason"]
