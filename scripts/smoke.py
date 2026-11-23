#!/usr/bin/env python3
# ABOUTME: compost's smoke test: installs the plugin from the working tree into a throwaway CLAUDE_CONFIG_DIR, runs the
# ABOUTME: Stop hook on a no-run transcript, then one cheap claude -p turn that must load a compost skill.
"""Boot compost the way a user gets it and drive one real flow, exiting non-zero on the first failure.

Steps, each printed as `smoke: pass <step>` or `smoke: FAIL <step>: <why>`:

1. install: copy `.claude-plugin/` and `plugin/` (files only, no hard links: `claude plugin` refuses a
   tree with uv's hard-linked `.venv`), add that copy as a marketplace in a fresh CLAUDE_CONFIG_DIR, install
   compost@compost, and require `claude plugin list --json` to show it enabled with no load errors (a broken
   `hooks.json` shows up there).
2. stop-guard: run every Stop command in the installed `hooks/hooks.json` on a transcript that mentions
   compost:implement without loading it; each must exit 0 without blocking.
3. skill turn: one `claude -p` turn on a small model that must load a compost skill, checked in stream-json,
   along with a clean finish and every hook in the session exiting 0.

The scratch dir is removed after a pass (unless --keep) and kept after a failure, for its logs.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path

PLUGIN_ID = "compost@compost"
REPO = Path(__file__).resolve().parent.parent
COPIED = (".claude-plugin", "plugin")
LOCAL_ONLY = shutil.ignore_patterns(
    ".venv", "__pycache__", ".pytest_cache", ".ruff_cache", "node_modules", ".coverage"
)
PROMPT = "Load the compost:verify skill with the Skill tool. Use no other tool. Then reply with only the word done."
# A nested claude inherits the parent session's memory and extra directories, and a cloud session's synced
# plugins would load beside the one under test.
INHERITED = (
    "MEMORY",
    "ADDITIONAL_DIRECTORIES",
    "CLAUDE_CODE_SYNC_PLUGINS",
    "CLAUDE_CODE_SYNC_SKILLS",
)
TURN_TIMEOUT = 300
CLI_TIMEOUT = 120


class SmokeFailed(Exception):
    def __init__(self, step: str, why: str):
        super().__init__(f"{step}: {why}")
        self.step, self.why = step, why


def child_env(environ: Mapping[str, str], config_dir: Path) -> dict[str, str]:
    env = {
        key: value for key, value in environ.items() if not any(part in key for part in INHERITED)
    }
    return {**env, "CLAUDE_CONFIG_DIR": str(config_dir)}


def copy_login(environ: Mapping[str, str], config_dir: Path) -> None:
    """Carry the user's login into the throwaway config: on Linux an OAuth login is the config dir's
    .credentials.json (macOS keeps it in the keychain), and without it the skill turn runs logged out."""
    user_config = environ.get("CLAUDE_CONFIG_DIR") or str(
        Path(environ.get("HOME", "~")).expanduser() / ".claude"
    )
    login = Path(user_config) / ".credentials.json"
    if login.is_file():
        shutil.copy2(login, config_dir / login.name)


def stage(source: Path, dest: Path) -> Path:
    """Copy what the marketplace installs from; copytree writes new files, so no hard link survives."""
    for name in COPIED:
        shutil.copytree(source / name, dest / name, ignore=LOCAL_ONLY)
    return dest


def listing_problems(entries: list[dict]) -> list[str]:
    entry = next((entry for entry in entries if entry.get("id") == PLUGIN_ID), None)
    if entry is None:
        return [f"{PLUGIN_ID} is not installed"]
    problems = [] if entry.get("enabled") else [f"{PLUGIN_ID} is installed but not enabled"]
    if not entry.get("installPath"):
        problems.append(f"{PLUGIN_ID} has no installPath")
    return problems + [str(error) for error in entry.get("errors") or []]


def stop_commands(hooks: dict) -> list[tuple[str, int]]:
    return [
        (hook["command"], hook.get("timeout", 60))
        for group in hooks.get("hooks", {}).get("Stop", [])
        for hook in group.get("hooks", [])
        if hook.get("type") == "command"
    ]


def no_run_transcript() -> str:
    """A turn that talks about compost:implement but never loads it, so the guard parses it and must allow the stop."""
    entries = [
        {"type": "user", "message": {"role": "user", "content": "What does compost:implement do?"}},
        {
            "type": "assistant",
            "message": {
                "id": "msg_smoke",
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": "It drives filed issues to a branch. Shall I start one?",
                    }
                ],
            },
        },
    ]
    return "".join(json.dumps(entry) + "\n" for entry in entries)


def guard_problems(command: str, done: subprocess.CompletedProcess) -> list[str]:
    if done.returncode != 0:
        return [f"{command} exited {done.returncode}: {done.stderr.strip()}"]
    try:
        verdict = json.loads(done.stdout) if done.stdout.strip() else {}
    except json.JSONDecodeError:
        verdict = {}
    if isinstance(verdict, dict) and verdict.get("decision") == "block":
        return [f"{command} blocked a stop outside an implement run: {verdict.get('reason')}"]
    return []


def stream_problems(stream: str) -> list[str]:
    events = []
    for line in stream.splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    problems = []
    init = next((event for event in events if event.get("subtype") == "init"), {})
    if not any(plugin.get("name") == "compost" for plugin in init.get("plugins", [])):
        problems.append("compost did not load in the session")
    loads = {
        block["id"]: block["input"]["skill"]
        for event in events
        if event.get("type") == "assistant" and event.get("parent_tool_use_id") is None
        for block in event["message"]["content"]
        if block.get("type") == "tool_use"
        and block.get("name") == "Skill"
        and str(block.get("input", {}).get("skill", "")).startswith("compost:")
    }
    if not loads:
        problems.append("no compost skill was loaded")
    for event in events:
        content = event.get("message", {}).get("content") if event.get("type") == "user" else None
        for block in content if isinstance(content, list) else []:
            if block.get("tool_use_id") in loads and block.get("is_error"):
                problems.append(f"the Skill call for {loads[block['tool_use_id']]} failed")
        if event.get("subtype") == "hook_response" and event.get("exit_code") not in (0, None):
            problems.append(
                f"{event.get('hook_name')} hook exited {event['exit_code']}: {event.get('stderr', '').strip()}"
            )
    result = next((event for event in events if event.get("type") == "result"), None)
    if result is None:
        problems.append("the turn did not finish: no result event")
    elif result.get("subtype") != "success" or result.get("is_error"):
        problems.append(f"the turn did not finish: {result.get('subtype')}")
    return problems


def execute(
    command: str | list[str], step: str, timeout: int, **kwargs
) -> subprocess.CompletedProcess:
    """subprocess.run with text output captured, where running out of time is a failed step rather than a crash."""
    if "input" not in kwargs:
        kwargs["stdin"] = subprocess.DEVNULL
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=timeout, **kwargs)
    except subprocess.TimeoutExpired:
        name = command if isinstance(command, str) else " ".join(command[:3])
        raise SmokeFailed(step, f"{name} timed out after {timeout}s") from None
    except OSError as error:
        name = command if isinstance(command, str) else command[0]
        raise SmokeFailed(step, f"{name} could not run: {error}") from None


def cli(claude: str, args: list[str], env: dict[str, str], cwd: Path, step: str) -> str:
    done = execute([claude, *args], step, CLI_TIMEOUT, env=env, cwd=cwd)
    if done.returncode != 0:
        raise SmokeFailed(
            step, f"claude {' '.join(args[:3])} exited {done.returncode}: {done.stderr.strip()}"
        )
    return done.stdout


def install(claude: str, source: Path, root: Path, env: dict[str, str]) -> Path:
    staged = stage(source, root / "src")
    cli(claude, ["plugin", "marketplace", "add", str(staged)], env, root, "install")
    cli(claude, ["plugin", "install", PLUGIN_ID], env, root, "install")
    listed = cli(claude, ["plugin", "list", "--json"], env, root, "install")
    try:
        entries = json.loads(listed)
    except json.JSONDecodeError:
        raise SmokeFailed(
            "install", f"plugin list --json printed no JSON: {listed[:200]!r}"
        ) from None
    if not isinstance(entries, list) or not all(isinstance(entry, dict) for entry in entries):
        raise SmokeFailed(
            "install", f"plugin list --json printed no list of plugins: {listed[:200]!r}"
        )
    if problems := listing_problems(entries):
        raise SmokeFailed("install", "; ".join(problems))
    return Path(next(entry for entry in entries if entry.get("id") == PLUGIN_ID)["installPath"])


def guard(plugin_root: Path, root: Path, env: dict[str, str]) -> None:
    transcript = root / "no-run.jsonl"
    transcript.write_text(no_run_transcript())
    payload = {
        "session_id": "smoke",
        "transcript_path": str(transcript),
        "cwd": str(root),
        "hook_event_name": "Stop",
        "stop_hook_active": False,
    }
    hooks = json.loads((plugin_root / "hooks" / "hooks.json").read_text())
    for command, timeout in stop_commands(hooks):
        plugin_env = {**env, "CLAUDE_PLUGIN_ROOT": str(plugin_root)}
        done = execute(
            command,
            "stop-guard",
            timeout,
            shell=True,
            input=json.dumps(payload),
            env=plugin_env,
            cwd=root,
        )
        if problems := guard_problems(command, done):
            raise SmokeFailed("stop-guard", "; ".join(problems))


def turn(claude: str, model: str, root: Path, env: dict[str, str]) -> None:
    work = root / "work"
    work.mkdir()
    args = [
        "-p",
        PROMPT,
        "--model",
        model,
        "--output-format",
        "stream-json",
        "--verbose",
        "--max-turns",
        "4",
    ]
    done = execute([claude, *args], "skill turn", TURN_TIMEOUT, env=env, cwd=work)
    (root / "turn.jsonl").write_text(done.stdout)
    if done.returncode != 0:
        raise SmokeFailed(
            "skill turn", f"claude -p exited {done.returncode}: {done.stderr.strip()}"
        )
    if problems := stream_problems(done.stdout):
        raise SmokeFailed("skill turn", "; ".join(problems))


def main(argv: list[str] | None = None, environ: Mapping[str, str] = os.environ) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--source", type=Path, default=REPO, help="tree to install from (default: this checkout)"
    )
    parser.add_argument(
        "--model", default="haiku", help="model for the skill turn (default: haiku)"
    )
    parser.add_argument(
        "--claude", default="claude", help="claude executable (default: claude on PATH)"
    )
    parser.add_argument(
        "--scratch", type=Path, default=None, help="parent of the throwaway dir (default: $TMPDIR)"
    )
    parser.add_argument("--keep", action="store_true", help="keep the throwaway dir after a pass")
    args = parser.parse_args(argv)
    root = Path(tempfile.mkdtemp(prefix="compost-smoke-", dir=args.scratch))
    env = child_env(environ, root / "config")
    (root / "config").mkdir()
    copy_login(environ, root / "config")
    try:
        plugin_root = install(args.claude, args.source.resolve(), root, env)
        print(f"smoke: pass install ({plugin_root})")
        guard(plugin_root, root, env)
        print("smoke: pass stop-guard")
        turn(args.claude, args.model, root, env)
        print("smoke: pass skill turn")
    except SmokeFailed as failure:
        print(f"smoke: FAIL {failure.step}: {failure.why}")
        print(f"smoke: kept {root}")
        return 1
    print("smoke: passed")
    if args.keep:
        print(f"smoke: kept {root}")
    else:
        shutil.rmtree(root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
