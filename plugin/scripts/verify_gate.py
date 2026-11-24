# ABOUTME: PreToolUse hook on Bash: a git push or PR create whose commit has no verify stamp is logged (observe), or
# ABOUTME: blocked twice per session, then let through as bypasses (enforce). Stdlib only: it runs on every Bash call.
from __future__ import annotations

import json
import os
import re
import shlex
import sys
from datetime import datetime, timezone
from pathlib import Path

import stamp

LOG = Path.home() / ".claude" / "verify-gate" / "log.jsonl"
MODE_VAR = "COMPOST_VERIFY_GATE"
BLOCKS_BEFORE_BYPASS = 2
OPERATOR_CHARS = ";&|()<>\n"
HEREDOC = re.compile(r"<<(-?)\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\2")
WRAPPERS = {"env", "command", "nohup", "sudo", "exec", "time", "timeout"}
PUSH_VALUE_FLAGS = {"-o", "--push-option", "--repo", "--receive-pack", "--exec"}
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
BODY_FLAGS = {"-f", "-F", "--field", "--raw-field", "--input"}
API_VALUE_FLAGS = BODY_FLAGS | {
    "-X",
    "--method",
    "-H",
    "--header",
    "-q",
    "--jq",
    "-t",
    "--template",
    "--hostname",
    "--cache",
    "-p",
    "--preview",
}


def mode() -> str:
    chosen = os.environ.get(MODE_VAR, "observe").lower()
    return chosen if chosen in {"off", "observe", "enforce"} else "observe"


def git_target(words: list[str], here: Path) -> tuple[Path, str] | None:
    """The directory a `git ... push` runs in (after any -C) and the commit it sends: the source of its first refspec,
    else HEAD. None when the git command is not a push or only deletes remote branches, which ships no code."""
    index = 1
    while index < len(words) and words[index].startswith("-"):
        if words[index] == "-C" and index + 1 < len(words):
            here = here / Path(words[index + 1]).expanduser()
        index += 2 if words[index] in {"-C", "-c"} else 1
    if words[index : index + 1] != ["push"] or {"-d", "--delete"} & set(words[index:]):
        return None
    positional, rest = [], iter(words[index + 1 :])
    for word in rest:
        if word in PUSH_VALUE_FLAGS:
            next(rest, None)
        elif not word.startswith("-"):
            positional.append(word)
    if len(positional) < 2:
        return here, "HEAD"
    source = positional[1].lstrip("+").split(":")[0]
    return (here, source) if source and not source.startswith("refs/notes/") else None  # notes are no code


def creates_pr(words: list[str]) -> bool:
    if words[1:3] == ["pr", "create"]:
        return True
    if words[1:2] != ["api"]:
        return False
    endpoint = next(
        (
            word
            for previous, word in zip(words[1:], words[2:])
            if not word.startswith("-") and previous not in API_VALUE_FLAGS
        ),
        "",
    )
    has_body = any(word.split("=")[0] in BODY_FLAGS for word in words)
    method = next((words[i + 1] for i, word in enumerate(words[:-1]) if word in {"-X", "--method"}), None)
    method = method or next((word.split("=", 1)[1] for word in words if word.startswith("--method=")), None)
    method = method or next((word[2:] for word in words if word.startswith("-X") and len(word) > 2), None)
    return endpoint.rstrip("/").endswith("pulls") and (method.upper() == "POST" if method else has_body)


def without_heredoc_bodies(command: str) -> str:
    """The command with every heredoc's body dropped: its lines are data (a commit message, an issue body), not
    commands. A body runs to the line that is its delimiter alone (after leading tabs, for `<<-`)."""
    kept, closing = [], []
    for line in command.split("\n"):
        if closing:
            dash, delimiter = closing[0]
            if (line.lstrip("\t") if dash else line) == delimiter:
                closing.pop(0)
            continue
        kept.append(line)
        closing = [(match[1], match[3]) for match in HEREDOC.finditer(line)]
    return "\n".join(kept)


def commands(command: str) -> list[list[str]]:
    """The simple commands in a Bash command line, as words: tokenized shell-aware, so a separator inside quotes is
    text, and split on control operators. A redirection (`>`, `2>&1`) and its target are dropped."""
    lexer = shlex.shlex(without_heredoc_bodies(command), posix=True, punctuation_chars=OPERATOR_CHARS)
    lexer.whitespace, lexer.whitespace_split = " \t\r", True
    found, words = [], []
    tokens = iter(lexer)
    for token in tokens:
        if token and set(token) <= set(OPERATOR_CHARS):
            if "<" in token or ">" in token:
                next(tokens, None)
            else:
                found, words = found + [words], []
        else:
            words.append(token)
    return [command for command in found + [words] if command]


def pr_head(words: list[str]) -> str:
    """The branch a PR create proposes: `gh pr create`'s --head or -H, or the `head` field of a `gh api` call (whose -H
    is a header); an `owner:branch` names the branch. HEAD when none is given."""
    api = words[1:2] == ["api"]
    for index, word in enumerate(words):
        flag, _, inline = word.partition("=")
        value = inline if inline else (words[index + 1] if index + 1 < len(words) else "")
        if api and flag in BODY_FLAGS - {"--input"} and value.startswith("head="):
            return value[len("head=") :].split(":")[-1]
        if not api and flag in {"--head", "-H"} and value:
            return value.split(":")[-1]
    return "HEAD"


def gated(command: str, cwd: Path) -> tuple[str, Path, str] | None:
    """The first push or PR create in the command, the directory it runs in (following a `cd` before it), and the
    revision it sends."""
    here = cwd
    try:
        parsed = commands(command)
    except ValueError:
        return None  # an unbalanced quote: bash rejects the line too
    for words in parsed:
        while words and (ASSIGNMENT.match(words[0]) or words[0] in WRAPPERS):
            words = words[2:] if words[0] == "timeout" else words[1:]
        if words[:1] == ["cd"] and len(words) > 1:
            here = here / Path(words[1]).expanduser()
        elif words[:1] == ["git"] and (target := git_target(words, here)):
            return "push", *target
        elif words[:1] == ["gh"] and creates_pr(words):
            return "pr-create", here, pr_head(words)
        elif words[:3] == ["glab", "mr", "create"]:
            return "pr-create", here, "HEAD"
    return None


def record(entry: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as handle:
        handle.write(json.dumps({"time": datetime.now(timezone.utc).isoformat(timespec="seconds"), **entry}) + "\n")


def blocks_so_far(session: str) -> int:
    if not LOG.exists():
        return 0
    blocks = 0
    for line in LOG.read_text().splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue  # a torn or hand-edited line from any session must not stop the count
        blocks += isinstance(entry, dict) and entry.get("session_id") == session and entry.get("action") == "blocked"
    return blocks


def deny(reason: str) -> dict:
    output = {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": reason}
    return {"hookSpecificOutput": output}


def decide(hook: dict) -> dict | None:
    """Raises outside a git repo (rev-parse fails), which main turns into letting the call through: git then fails
    the command on its own."""
    chosen = mode()
    if chosen == "off" or not (found := gated(hook["tool_input"]["command"], Path(hook["cwd"]))):
        return None
    kind, directory, revision = found
    repo, sha = stamp.git_lines(directory, "rev-parse", "--show-toplevel", f"{revision}^{{commit}}")
    if stamp.read(Path(repo), sha):
        return None
    session = hook["session_id"]
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
        f"compost verify-gate: commit {sha[:12]} ({revision}) in {repo} has no verify stamp, so nothing shows compost:verify ran "
        "on it. Run compost:verify on this commit; its step 9 writes the stamp when every gate is green and every "
        f"AC is met. This is block {blocks + 1} of {BLOCKS_BEFORE_BYPASS} in this session; after "
        f"that, attempts in this session go through and are logged as bypasses. {MODE_VAR}=observe or off turns blocking off."
    )


def main(stdin=sys.stdin, out=sys.stdout) -> int:
    try:
        verdict = decide(json.load(stdin))
    except Exception:  # noqa: BLE001 - a gate that crashes must never trap the Bash call; it lets it through.
        return 0
    if verdict is not None:
        print(json.dumps(verdict), file=out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
