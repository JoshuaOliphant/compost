"""
ABOUTME: Tests for count.py: turn ends, the Run contract stops, and permission denials read from stream-json transcripts.
ABOUTME: Transcripts are small hand-built event lists; Jev verdicts are given as dicts, so no test calls Jev.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import count  # noqa: E402

DENIED = "Permission for this tool use was denied. It requires approval, and this session has no approval surface."


def said(text, parent=None, message_id="m1"):
    return {
        "type": "assistant",
        "parent_tool_use_id": parent,
        "message": {"id": message_id, "content": [{"type": "text", "text": text}]},
    }


def tool_result(tool_use_id, content, parent=None):
    block = {
        "type": "tool_result",
        "tool_use_id": tool_use_id,
        "is_error": True,
        "content": content,
    }
    return {"type": "user", "parent_tool_use_id": parent, "message": {"content": [block]}}


def result(denials=(), text="", session="s1"):
    denied = [
        {"tool_name": "Bash", "tool_use_id": tool_use_id, "tool_input": {}}
        for tool_use_id in denials
    ]
    return {"type": "result", "session_id": session, "result": text, "permission_denials": denied}


def transcript(tmp_path, events, name="01-implement.jsonl"):
    path = tmp_path / name
    path.write_text("\n".join(json.dumps(event) for event in events) + "\nnot json\n")
    return path


def test_a_turn_with_no_result_text_ends_on_its_last_main_thread_message(tmp_path):
    first = transcript(
        tmp_path,
        [
            said("Working on it."),
            said("Two options."),
            said("subagent chatter", parent="toolu_task"),
            said("Which color?", message_id="m2"),
            said("Blue or red?", message_id="m2"),
            result(),
        ],
    )
    second = transcript(
        tmp_path, [said("Done; posted the PR body."), result()], name="02-implement.jsonl"
    )
    silent = transcript(tmp_path, [result()], name="03-implement.jsonl")

    assert count.turn_ends([first, second, silent]) == [
        "Which color?\nBlue or red?",
        "Done; posted the PR body.",
    ]


def test_a_turn_ends_on_the_result_text_when_there_is_one(tmp_path):
    path = transcript(tmp_path, [said("Starting."), result(text="Should I merge?")])

    assert count.turn_ends([path]) == ["Should I merge?"]


def test_contract_stops_are_the_latest_block_the_main_thread_printed(tmp_path):
    early = "Run contract stops:\n- merging\n\nnext"
    late = "Plan.\nRun contract stops:\n- merging to main\n- choosing the export format\n\nGo."
    subagent = "Run contract stops:\n- something a worker quoted\n"
    path = transcript(
        tmp_path, [said(early), said(late, message_id="m2"), said(subagent, parent="t"), result()]
    )

    assert count.contract_stops([path]) == ["merging to main", "choosing the export format"]


def test_no_contract_block_means_no_contract_stops(tmp_path):
    assert (
        count.contract_stops([transcript(tmp_path, [said("Run contract stops: none"), result()])])
        == []
    )


def test_payloads_pair_each_turn_end_with_the_contract_stops(tmp_path):
    path = transcript(
        tmp_path,
        [said("Run contract stops:\n- merging\n"), said("Merge?", message_id="m2"), result()],
    )

    assert count.payloads([path]) == [{"message": "Merge?", "contract_stops": ["merging"]}]


def test_denials_are_counted_once_per_tool_use_across_results_and_tool_results(tmp_path):
    first = transcript(
        tmp_path,
        [
            tool_result("a", DENIED),
            tool_result("b", [{"type": "text", "text": DENIED}], parent="t"),
            tool_result("c", "Exit code 1"),
            result(denials=["a"]),
        ],
    )
    second = transcript(tmp_path, [result(denials=["a", "d"])], name="02-implement.jsonl")

    assert count.permission_denials([first, second]) == 3


def test_report_counts_waits_and_the_waits_jev_allowed(tmp_path):
    path = transcript(
        tmp_path,
        [
            said("Merge?"),
            result(),
            said("Which format?", message_id="m2"),
            result(),
            said("All done.", message_id="m3"),
            result(denials=["x"]),
        ],
    )
    verdicts = [
        {"waits": 0.9, "allowed": 0.5},
        {"waits": 0.5, "allowed": 0.1},
        {"waits": 0.2, "allowed": 0.0},
    ]

    assert count.report([path], verdicts) == {
        "turn_ends": 3,
        "waits_on_user": 2,
        "waits_naming_a_stop": 1,
        "permission_denials": 1,
        "contract_stops": [],
        "waits": [
            {"message": "Merge?", "waits": 0.9, "allowed": 0.5},
            {"message": "Which format?", "waits": 0.5, "allowed": 0.1},
        ],
    }


def test_report_refuses_verdicts_that_do_not_match_the_turn_ends(tmp_path):
    path = transcript(tmp_path, [said("Merge?"), result()])

    with pytest.raises(ValueError, match="2 verdicts for 1 turn ends"):
        count.report([path], [{"waits": 0.9, "allowed": 0.8}, {"waits": 0.1, "allowed": 0.0}])


def test_main_prints_payloads_then_a_report_from_a_verdicts_file(tmp_path, capsys):
    path = transcript(tmp_path, [said("Merge?"), result()])
    verdicts = tmp_path / "verdicts.jsonl"
    verdicts.write_text(json.dumps({"tool": "stop-guard", "waits": 0.9, "allowed": 0.2}) + "\n\n")

    assert count.main(["payloads", str(path)]) == 0
    assert json.loads(capsys.readouterr().out) == {"message": "Merge?", "contract_stops": []}
    assert count.main(["report", "--verdicts", str(verdicts), str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["waits_on_user"] == 1
