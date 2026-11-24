"""
ABOUTME: Tests for smoke.py: the plugin-list and stream-json checks on recorded fixtures, and the whole run against a
ABOUTME: stand-in claude executable; the real run against the real CLI is the smoke itself.
"""

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import smoke  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
REPO = Path(__file__).resolve().parents[2]


def listing(name):
    return json.loads((FIXTURES / name).read_text())


def stream_events():
    return [json.loads(line) for line in (FIXTURES / "stream-pass.jsonl").read_text().splitlines()]


def as_stream(events):
    return "\n".join(json.dumps(event) for event in events) + "\n"


@pytest.mark.parametrize(
    ("entries", "problem"),
    [
        (listing("listing-pass.json"), None),
        (listing("listing-broken-hooks.json"), "Hook load failed: JSON Parse error"),
        ([], "compost@compost is not installed"),
        (
            [{**listing("listing-pass.json")[0], "enabled": False}],
            "compost@compost is installed but not enabled",
        ),
        (
            [{**listing("listing-pass.json")[0], "id": "compost@oliphant-plugins"}],
            "compost@compost is not installed",
        ),
    ],
    ids=["enabled-clean", "broken-hooks-json", "missing", "disabled", "other-marketplace-only"],
)
def test_plugin_list_must_show_compost_enabled_without_errors(entries, problem):
    problems = smoke.listing_problems(entries)
    if problem is None:
        assert problems == []
    else:
        assert any(problem in found for found in problems), problems


def break_skill_name(events):
    events[1]["message"]["content"][0]["input"]["skill"] = "other:verify"


def drop_compost_plugin(events):
    events[0]["plugins"] = [
        plugin for plugin in events[0]["plugins"] if plugin["name"] != "compost"
    ]


def fail_skill_load(events):
    events[2]["message"]["content"][0]["is_error"] = True


def subagent_loads_it(events):
    events[1]["parent_tool_use_id"] = "toolu_parent"


def crash_stop_hook(events):
    events[5].update(exit_code=1, outcome="error", stderr="Traceback: boom")


def run_out_of_turns(events):
    events[6].update(subtype="error_max_turns", is_error=True)


def cut_before_result(events):
    del events[6]


@pytest.mark.parametrize(
    ("edit", "problem"),
    [
        (None, None),
        (break_skill_name, "no compost skill was loaded"),
        (drop_compost_plugin, "compost did not load in the session"),
        (fail_skill_load, "the Skill call for compost:verify failed"),
        (subagent_loads_it, "no compost skill was loaded"),
        (crash_stop_hook, "Stop hook exited 1: Traceback: boom"),
        (run_out_of_turns, "the turn did not finish: error_max_turns"),
        (cut_before_result, "the turn did not finish: no result event"),
    ],
    ids=[
        "recorded-pass",
        "non-compost-skill",
        "plugin-not-loaded",
        "skill-load-error",
        "only-a-subagent-loads-it",
        "hook-crash",
        "max-turns",
        "no-result",
    ],
)
def test_stream_must_show_a_compost_skill_loaded_and_a_clean_finish(edit, problem):
    events = stream_events()
    if edit:
        edit(events)
    problems = smoke.stream_problems(as_stream(events) + "not json\n")
    if problem is None:
        assert problems == []
    else:
        assert problem in problems


def test_stop_commands_come_from_the_shipped_hooks_json():
    hooks = json.loads((REPO / "plugin" / "hooks" / "hooks.json").read_text())
    assert smoke.stop_commands(hooks) == [
        ('uv run --quiet "${CLAUDE_PLUGIN_ROOT}/scripts/stop_guard.py"', 30)
    ]
    assert smoke.stop_commands({"hooks": {"PreToolUse": []}}) == []
    prompt_only = {"hooks": {"Stop": [{"hooks": [{"type": "prompt", "prompt": "judge it"}]}]}}
    assert smoke.stop_commands(prompt_only) == []


@pytest.mark.parametrize(
    "stdout", ["", "compost stop-guard: nothing to judge\n", '{"continue": true}']
)
def test_a_stop_hook_that_exits_0_without_a_block_decision_allows_the_stop(stdout):
    done = subprocess.CompletedProcess("guard", 0, stdout=stdout, stderr="")
    assert smoke.guard_problems("guard", done) == []


def test_child_env_strips_what_a_nested_claude_must_not_inherit():
    parent = {
        "PATH": "/bin",
        "CLAUDE_MEMORY_STORES": "x",
        "CLAUDE_COWORK_MEMORY_PATH_OVERRIDE": "x",
        "CLAUDE_ADDITIONAL_DIRECTORIES": "x",
        "CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD": "x",
        "CLAUDE_CODE_SYNC_PLUGINS": "1",
        "CLAUDE_CODE_SYNC_SKILLS": "1",
        "CLAUDE_CONFIG_DIR": "/home/me/.claude",
    }
    assert smoke.child_env(parent, Path("/tmp/cfg")) == {
        "PATH": "/bin",
        "CLAUDE_CONFIG_DIR": "/tmp/cfg",
    }


def test_stage_copies_the_marketplace_and_plugin_without_hard_links_or_venvs(tmp_path):
    source = tmp_path / "repo"
    (source / ".claude-plugin").mkdir(parents=True)
    (source / ".claude-plugin" / "marketplace.json").write_text("{}")
    (source / "plugin" / ".venv").mkdir(parents=True)
    (source / "plugin" / ".venv" / "lib").write_text("x")
    (source / "plugin" / "a.md").write_text("a")
    os.link(source / "plugin" / "a.md", source / "plugin" / "b.md")
    (source / "experiments").mkdir()
    staged = smoke.stage(source, tmp_path / "src")
    assert sorted(str(path.relative_to(staged)) for path in staged.rglob("*")) == [
        ".claude-plugin",
        ".claude-plugin/marketplace.json",
        "plugin",
        "plugin/a.md",
        "plugin/b.md",
    ]
    assert (staged / "plugin" / "a.md").stat().st_nlink == 1


FAKE_CLAUDE = """\
#!{python}
import json, os, sys
from pathlib import Path
state = Path({state!r})
args = sys.argv[1:]
with (state / "calls.log").open("a") as log:
    log.write(json.dumps(args) + "\\n")
key = "-p" if args[0] == "-p" else " ".join(args[:2])
if (state / "fail").exists() and (state / "fail").read_text() == key:
    print(f"fake claude: {{key}} failed", file=sys.stderr)
    sys.exit(1)
if key == "-p":
    (state / "env.json").write_text(json.dumps(sorted(os.environ)))
    login = Path(os.environ["CLAUDE_CONFIG_DIR"]) / ".credentials.json"
    (state / "login.txt").write_text(login.read_text() if login.exists() else "")
    sys.stdout.write((state / "stream.jsonl").read_text())
elif key == "plugin list":
    sys.stdout.write((state / "listing.json").read_text())
"""


@pytest.fixture
def fake(tmp_path):
    """A stand-in claude that logs its calls and answers from files, and an install dir whose Stop hook tests set."""
    state = tmp_path / "state"
    state.mkdir()
    install = tmp_path / "install"
    (install / "hooks").mkdir(parents=True)
    entry = {**listing("listing-pass.json")[0], "installPath": str(install)}
    (state / "listing.json").write_text(json.dumps([entry]))
    (state / "stream.jsonl").write_text((FIXTURES / "stream-pass.jsonl").read_text())
    claude = tmp_path / "claude"
    claude.write_text(FAKE_CLAUDE.format(python=sys.executable, state=str(state)))
    claude.chmod(claude.stat().st_mode | stat.S_IXUSR)

    class Fake:
        def __init__(self):
            self.state, self.install, self.claude, self.scratch = (
                state,
                install,
                claude,
                tmp_path / "scratch",
            )
            self.scratch.mkdir()
            self.stop_hook('cat > "${CLAUDE_PLUGIN_ROOT}/payload.json"')

        def stop_hook(self, command):
            hooks = {
                "hooks": {
                    "Stop": [{"hooks": [{"type": "command", "command": command, "timeout": 30}]}]
                }
            }
            (install / "hooks" / "hooks.json").write_text(json.dumps(hooks))

        def run(self, *extra, environ=None):
            argv = [
                "--claude",
                str(claude),
                "--scratch",
                str(self.scratch),
                "--source",
                str(REPO),
                *extra,
            ]
            return smoke.main(argv, environ=environ or {**os.environ, "CLAUDE_MEMORY_STORES": "x"})

        def calls(self):
            log = state / "calls.log"
            return (
                [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
            )

    return Fake()


@pytest.mark.parametrize(
    ("extra", "model", "kept"),
    [([], "haiku", 0), (["--model", "claude-haiku-5-5", "--keep"], "claude-haiku-5-5", 1)],
    ids=["defaults-clean-up", "model-and-keep"],
)
def test_a_clean_run_installs_guards_and_loads_a_skill(fake, capsys, extra, model, kept):
    assert fake.run(*extra) == 0
    calls = fake.calls()
    assert calls[0][:3] == ["plugin", "marketplace", "add"]
    assert calls[1] == ["plugin", "install", "compost@compost"]
    assert calls[2] == ["plugin", "list", "--json"]
    turn = calls[3]
    assert turn[:2] == ["-p", smoke.PROMPT]
    assert turn[turn.index("--model") + 1] == model
    assert turn[turn.index("--output-format") + 1] == "stream-json"
    payload = json.loads((fake.install / "payload.json").read_text())
    assert payload["hook_event_name"] == "Stop" and payload["stop_hook_active"] is False
    assert Path(payload["transcript_path"]).exists() is bool(kept)
    assert "CLAUDE_MEMORY_STORES" not in json.loads((fake.state / "env.json").read_text())
    assert len(list(fake.scratch.iterdir())) == kept
    out = capsys.readouterr().out
    assert [line.split()[:2] for line in out.splitlines() if line.startswith("smoke:")][:4] == [
        ["smoke:", "pass"],
        ["smoke:", "pass"],
        ["smoke:", "pass"],
        ["smoke:", "passed"],
    ]


def test_the_no_run_transcript_mentions_implement_without_loading_it():
    lines = [json.loads(line) for line in smoke.no_run_transcript().splitlines()]
    text = json.dumps(lines)
    assert "compost:implement" in text
    assert not any(
        block.get("type") == "tool_use" and block.get("name") == "Skill"
        for line in lines
        for block in line["message"]["content"]
        if isinstance(block, dict)
    )


def fail_marketplace_add(fake):
    (fake.state / "fail").write_text("plugin marketplace")


def break_listing(fake):
    (fake.state / "listing.json").write_text((FIXTURES / "listing-broken-hooks.json").read_text())


def garble_listing(fake):
    (fake.state / "listing.json").write_text("Loading plugins...")


def list_a_mapping(fake):
    (fake.state / "listing.json").write_text(json.dumps({"plugins": listing("listing-pass.json")}))


def remove_claude(fake):
    fake.claude.unlink()


def drop_install_path(fake):
    entries = listing("listing-pass.json")
    del entries[0]["installPath"]
    (fake.state / "listing.json").write_text(json.dumps(entries))


def block_the_stop(fake):
    fake.stop_hook("""echo '{"decision": "block", "reason": "waits on the user"}'""")


def crash_the_guard(fake):
    fake.stop_hook("echo 'no module named jev' >&2; exit 2")


def hang_the_guard(fake):
    hooks = {
        "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "sleep 5", "timeout": 1}]}]}
    }
    (fake.install / "hooks" / "hooks.json").write_text(json.dumps(hooks))


def load_no_skill(fake):
    events = stream_events()
    break_skill_name(events)
    (fake.state / "stream.jsonl").write_text(as_stream(events))


def fail_the_turn(fake):
    (fake.state / "fail").write_text("-p")


@pytest.mark.parametrize(
    ("plant", "step", "message", "turn_ran"),
    [
        (fail_marketplace_add, "install", "fake claude: plugin marketplace failed", False),
        (break_listing, "install", "Hook load failed", False),
        (garble_listing, "install", "plugin list --json printed no JSON", False),
        (drop_install_path, "install", "compost@compost has no installPath", False),
        (list_a_mapping, "install", "plugin list --json printed no list of plugins", False),
        (remove_claude, "install", "could not run", False),
        (
            block_the_stop,
            "stop-guard",
            "blocked a stop outside an implement run: waits on the user",
            False,
        ),
        (crash_the_guard, "stop-guard", "exited 2: no module named jev", False),
        (hang_the_guard, "stop-guard", "sleep 5 timed out after 1s", False),
        (load_no_skill, "skill turn", "no compost skill was loaded", True),
        (fail_the_turn, "skill turn", "claude -p exited 1: fake claude: -p failed", True),
    ],
    ids=[
        "marketplace-add-fails",
        "broken-hooks-json",
        "listing-not-json",
        "listing-without-install-path",
        "listing-not-a-list",
        "no-claude",
        "guard-blocks",
        "guard-crashes",
        "guard-hangs",
        "no-skill",
        "turn-fails",
    ],
)
def test_any_failing_step_exits_non_zero_names_it_and_keeps_the_scratch_dir(
    fake, capsys, plant, step, message, turn_ran
):
    plant(fake)
    assert fake.run() == 1
    out = capsys.readouterr().out
    assert f"smoke: FAIL {step}" in out and message in out
    assert any(call[0] == "-p" for call in fake.calls()) is turn_ran
    assert len(list(fake.scratch.iterdir())) == 1


@pytest.mark.parametrize(
    "where, failing", [("CLAUDE_CONFIG_DIR", False), ("HOME", False), ("HOME", True)]
)
def test_the_turn_runs_logged_in_and_no_kept_dir_holds_the_login(fake, tmp_path, where, failing):
    """On Linux an OAuth login lives in the config dir's .credentials.json; without it the turn runs logged out. A
    dir kept for its logs (after --keep or a failure) must not keep a copy of it."""
    config = tmp_path / "user-config"
    login = (
        config / ".credentials.json"
        if where == "CLAUDE_CONFIG_DIR"
        else tmp_path / ".claude" / ".credentials.json"
    )
    login.parent.mkdir(parents=True)
    login.write_text('{"token": "t"}')
    environ = {"PATH": os.environ["PATH"], "HOME": str(tmp_path)}
    if where == "CLAUDE_CONFIG_DIR":
        environ["CLAUDE_CONFIG_DIR"] = str(config)
    if failing:
        (fake.state / "stream.jsonl").write_text("")
    assert fake.run("--keep", environ=environ) == int(failing)
    assert (fake.state / "login.txt").read_text() == '{"token": "t"}'
    [kept] = fake.scratch.iterdir()
    assert not (kept / "config" / ".credentials.json").exists()


def test_wrapper_runs_the_python_script():
    done = subprocess.run(
        [REPO / "scripts" / "smoke", "--help"], capture_output=True, text=True, check=False
    )
    assert done.returncode == 0 and "--source" in done.stdout
