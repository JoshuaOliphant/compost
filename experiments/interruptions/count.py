# ABOUTME: Counts how often a compost run waited on the user, read from its stream-json transcripts and Jev verdicts.
# ABOUTME: `payloads` prints one stop-guard input per turn end; `report` pairs them with Jev's verdicts and counts denials.
import argparse
import json
import re
import sys
from pathlib import Path

# The block implement prints from the parent's Run contract; plugin/scripts/stop_guard.py reads the same one.
CONTRACT_STOPS = re.compile(r"^Run contract stops:[ \t]*\n((?:- .*(?:\n|$))*)", re.MULTILINE)
# What Claude Code writes as the tool result when --permission-prompts none denies a call.
DENIED = "Permission for this tool use was denied"
# jev.py's stop-guard blocks at this score; a message waits, or names a stop, at the same line.
STOP_GUARD_THRESHOLD = 0.5


def events(paths: list[Path]) -> list[dict]:
    parsed = []
    for path in paths:
        for line in path.read_text().splitlines():
            try:
                parsed.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return parsed


def main_thread_texts(event: dict) -> list[str]:
    if event.get("type") != "assistant" or event.get("parent_tool_use_id"):
        return []
    content = event["message"].get("content") or []
    return [block["text"] for block in content if block.get("type") == "text" and block.get("text")]


def turn_ends(paths: list[Path]) -> list[str]:
    """What the user saw when each turn stopped: the result event's text, else the last main-thread message.

    stream-json splits one message over several assistant events that share its id. A turn that said nothing
    did not wait on anyone, so it has no turn end."""
    ends, last_id, last = [], None, []
    for event in events(paths):
        if texts := main_thread_texts(event):
            message_id = event["message"].get("id")
            if message_id != last_id:
                last_id, last = message_id, []
            last.extend(texts)
        elif event.get("type") == "result":
            if said := event.get("result") or "\n".join(last):
                ends.append(said)
            last_id, last = None, []
    return ends


def contract_stops(paths: list[Path]) -> list[str]:
    stops = []
    for event in events(paths):
        for text in main_thread_texts(event):
            for match in CONTRACT_STOPS.finditer(text):
                stops = [line.removeprefix("- ").strip() for line in match.group(1).splitlines()]
    return stops


def payloads(paths: list[Path]) -> list[dict]:
    stops = contract_stops(paths)
    return [{"message": message, "contract_stops": stops} for message in turn_ends(paths)]


def tool_result_text(block: dict) -> str:
    content = block.get("content")
    if isinstance(content, list):
        return "\n".join(part.get("text", "") for part in content)
    return str(content or "")


def permission_denials(paths: list[Path]) -> int:
    """Denied tool calls, once each: a result event lists its turn's denials, and every denial leaves a tool result."""
    denied = set()
    for event in events(paths):
        for denial in event.get("permission_denials") or []:
            denied.add(denial["tool_use_id"])
        content = (
            (event.get("message") or {}).get("content") if event.get("type") == "user" else None
        )
        for block in content if isinstance(content, list) else []:
            if block.get("type") == "tool_result" and DENIED in tool_result_text(block):
                denied.add(block["tool_use_id"])
    return len(denied)


def report(paths: list[Path], verdicts: list[dict]) -> dict:
    ends = turn_ends(paths)
    if len(verdicts) != len(ends):
        raise ValueError(f"{len(verdicts)} verdicts for {len(ends)} turn ends")
    waits = [
        {"message": message, "waits": verdict["waits"], "allowed": verdict["allowed"]}
        for message, verdict in zip(ends, verdicts)
        if verdict["waits"] >= STOP_GUARD_THRESHOLD
    ]
    return {
        "turn_ends": len(ends),
        "waits_on_user": len(waits),
        "waits_naming_a_stop": sum(wait["allowed"] >= STOP_GUARD_THRESHOLD for wait in waits),
        "permission_denials": permission_denials(paths),
        "contract_stops": contract_stops(paths),
        "waits": waits,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="count.py")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("payloads").add_argument("transcripts", nargs="+", type=Path)
    reporting = commands.add_parser("report")
    reporting.add_argument(
        "--verdicts", type=Path, required=True, help="JSON lines from jev.py stop-guard"
    )
    reporting.add_argument("transcripts", nargs="+", type=Path)
    args = parser.parse_args(argv)
    if args.command == "payloads":
        for payload in payloads(args.transcripts):
            print(json.dumps(payload))
        return 0
    verdicts = [json.loads(line) for line in args.verdicts.read_text().splitlines() if line.strip()]
    print(json.dumps(report(args.transcripts, verdicts), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
