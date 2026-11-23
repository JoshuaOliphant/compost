# ABOUTME: PreToolUse hook on Bash: a git push or PR create whose HEAD has no verify stamp is logged (observe), or
# ABOUTME: blocked twice per session and then let through as a bypass (enforce). Stdlib only: it runs on every Bash call.
import json
import os
import re
import shlex
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import stamp  # noqa: E402 - found through the path above when Claude Code runs this file directly

LOG = Path.home() / ".claude" / "verify-gate" / "log.jsonl"
MODE_VAR = "COMPOST_VERIFY_GATE"
BLOCKS_BEFORE_BYPASS = 2
SEPARATOR = re.compile(r"&&|\|\||[;|\n]")
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
BODY_FLAGS = {"-f", "-F", "--field", "--raw-field", "--input"}


def mode() -> str:
    chosen = os.environ.get(MODE_VAR, "observe").strip().lower()
    return chosen if chosen in {"off", "observe", "enforce"} else "observe"


def git_target(words: list[str], here: Path) -> Path | None:
    """The directory a `git ... push` runs in (after any -C), or None when the git command is not a push or only
    deletes remote branches, which ships no code."""
    index = 1
    while index < len(words) and words[index].startswith("-"):
        if words[index] == "-C" and index + 1 < len(words):
            here = here / Path(words[index + 1]).expanduser()
        index += 2 if words[index] in {"-C", "-c"} else 1
    if words[index : index + 1] != ["push"] or {"-d", "--delete"} & set(words[index:]):
        return None
    return here


def creates_pr(words: list[str]) -> bool:
    if words[1:3] == ["pr", "create"]:
        return True
    if words[1:2] != ["api"]:
        return False
    endpoint = any(word.rstrip("/").endswith("pulls") for word in words[2:])
    has_body = any(word.split("=", 1)[0] in BODY_FLAGS for word in words)
    method = next((words[i + 1] for i, word in enumerate(words[:-1]) if word in {"-X", "--method"}), None)
    return endpoint and (method.upper() == "POST" if method else has_body)


def gated(command: str, cwd: Path) -> tuple[str, Path] | None:
    """The first push or PR create in the command and the directory it runs in, following a `cd` before it."""
    here = cwd
    for segment in SEPARATOR.split(command):
        try:
            words = shlex.split(segment)
        except ValueError:
            continue
        while words and ASSIGNMENT.match(words[0]):
            words = words[1:]
        if words[:1] == ["cd"] and len(words) > 1:
            here = here / Path(words[1]).expanduser()
        elif words[:1] == ["git"] and (target := git_target(words, here)):
            return "push", target
        elif words[:1] == ["gh"] and creates_pr(words):
            return "pr-create", here
    return None


def head(repo: Path) -> tuple[str, str] | None:
    """The repo's top level and HEAD's SHA, or None outside a repo (git then fails the command on its own)."""
    try:
        top, sha = stamp.resolve(repo, "rev-parse", "--show-toplevel", "HEAD")
    except stamp.GitError:
        return None
    return top, sha


def record(entry: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as handle:
        handle.write(json.dumps({"time": datetime.now(UTC).isoformat(timespec="seconds"), **entry}) + "\n")


def blocks_so_far(session: str) -> int:
    if not LOG.exists():
        return 0
    entries = [json.loads(line) for line in LOG.read_text().splitlines() if line.strip()]
    return sum(entry.get("session_id") == session and entry.get("action") == "blocked" for entry in entries)


def deny(reason: str) -> dict:
    output = {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": reason}
    return {"hookSpecificOutput": output}


def decide(hook: dict) -> dict | None:
    chosen = mode()
    command = hook["tool_input"]["command"]
    if chosen == "off" or not isinstance(command, str) or not (found := gated(command, Path(hook["cwd"]))):
        return None
    kind, directory = found
    if not (located := head(directory)) or stamp.read(Path(located[0]), located[1]):
        return None
    repo, sha = located
    session = hook.get("session_id", "")
    entry = {"session_id": session, "repo": repo, "sha": sha, "kind": kind, "mode": chosen}
    if chosen == "observe":
        record(entry | {"action": "observed"})
        return None
    blocks = blocks_so_far(session)
    if blocks >= BLOCKS_BEFORE_BYPASS:
        record(entry | {"action": "bypass"})
        return None
    record(entry | {"action": "blocked"})
    return deny(
        f"compost verify-gate: HEAD {sha[:12]} in {repo} has no verify stamp, so nothing shows compost:verify ran "
        "on it. Run compost:verify on this commit; its step 9 writes the stamp when every gate is green and every "
        f"AC is met. This is block {blocks + 1} of {BLOCKS_BEFORE_BYPASS} in this session; the next attempt after "
        f"that goes through and is logged as a bypass. {MODE_VAR}=observe or off turns blocking off."
    )


def main(stdin=None, out=None) -> int:
    try:
        verdict = decide(json.load(stdin or sys.stdin))
    except Exception:  # noqa: BLE001 - a gate that crashes must never trap the Bash call; it lets it through.
        return 0
    if verdict:
        print(json.dumps(verdict), file=out or sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
