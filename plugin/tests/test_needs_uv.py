# ABOUTME: Tests that compost's Jev scripts run under plain python3: they re-exec under uv when typesafe-sdk is
# ABOUTME: missing, and exit 3 with one line saying how to run them when uv can't help, never with a traceback.
import json
import os
import shutil
import subprocess
import sys
from types import SimpleNamespace

import needs_uv
import pytest
from conftest import PLUGIN_ROOT

SCRIPTS = PLUGIN_ROOT / "scripts"
MISSING = "compost_no_such_module"
JEV_SCRIPTS = sorted(
    str(path.relative_to(SCRIPTS))
    for path in SCRIPTS.rglob("*.py")
    if '# dependencies = ["typesafe-sdk' in path.read_text()
)


class Replaced(Exception):
    """Stands in for the process being replaced, which never returns."""


class Uv:
    """Stands in for a uv on PATH at /bin: records each call and answers `uv sync` with `sync_code`."""

    def __init__(self, sync_code=0):
        self.sync_code = sync_code
        self.calls = []

    def which(self, name, path=None):
        return "/bin/uv" if name == "uv" and path == "/bin" else None

    def run(self, args, env, check):
        self.calls.append(("run", args, env))
        if check and self.sync_code:
            raise subprocess.CalledProcessError(self.sync_code, args)
        return SimpleNamespace(returncode=self.sync_code)

    def execve(self, path, args, env):
        self.calls.append(("execve", path, args, env))
        raise Replaced


def test_an_importable_sdk_runs_in_process_and_drops_the_re_exec_marker():
    uv = Uv()
    environ = {"PATH": "/bin", "COMPOST_UV_REEXEC": "1"}
    needs_uv.ensure("json", ["jev.py", "list"], environ, uv.which, uv.run, uv.execve)
    assert uv.calls == []
    assert environ == {"PATH": "/bin"}


def test_a_missing_sdk_is_installed_by_uv_then_the_running_script_re_execs_with_its_arguments():
    uv = Uv()
    with pytest.raises(Replaced):
        needs_uv.ensure(
            MISSING, ["scripts/jev.py", "status", "--input", "x"], {"PATH": "/bin"}, uv.which, uv.run, uv.execve
        )
    env = {"PATH": "/bin", "COMPOST_UV_REEXEC": "1"}
    assert uv.calls == [
        ("run", ["/bin/uv", "sync", "--quiet", "--script", "scripts/jev.py"], env),
        (
            "execve",
            "/bin/uv",
            ["/bin/uv", "run", "--quiet", "--script", "scripts/jev.py", "status", "--input", "x"],
            env,
        ),
    ]


@pytest.mark.parametrize(
    "environ, sync_code, cause",
    [
        pytest.param({"PATH": "/usr/bin"}, 0, "uv is not on PATH to install it", id="no-uv"),
        pytest.param({"PATH": "/bin"}, 1, "uv could not install it", id="uv-install-fails"),
        pytest.param({"PATH": "/bin"}, -9, "uv could not install it", id="uv-install-killed"),
        pytest.param(
            {"PATH": "/bin", "COMPOST_UV_REEXEC": "1"},
            0,
            "uv ran it and it still did not import",
            id="already-re-execed",
        ),
    ],
)
def test_without_a_way_to_install_the_sdk_it_exits_3_in_one_line(environ, sync_code, cause, capsys):
    uv = Uv(sync_code)
    with pytest.raises(SystemExit) as stopped:
        needs_uv.ensure(MISSING, ["scripts/jev.py", "list"], environ, uv.which, uv.run, uv.execve)
    assert stopped.value.code == 3
    assert [call[0] for call in uv.calls] == (["run"] if sync_code else [])
    err = capsys.readouterr().err
    assert err.count("\n") == 1
    assert err.startswith(f"jev unavailable: {MISSING} is not installed for ")
    assert err.endswith(f" and {cause}. Run it as `uv run scripts/jev.py`, or make this call yourself.\n")


def bare_python(*args, path, stdin=None):
    """Runs a script with -S, so the dev environment's typesafe-sdk is out of sight, as for a plain python3."""
    env = {key: value for key, value in os.environ.items() if key != "COMPOST_UV_REEXEC"}
    env["PATH"] = path
    return subprocess.run(
        [sys.executable, "-S", *args], input=stdin, capture_output=True, text=True, env=env, timeout=120, check=False
    )


def waiting_stop(tmp_path) -> str:
    """A Stop hook's input whose transcript has an implement run waiting on the user, so stop_guard needs Jev."""
    transcript = tmp_path / "session.jsonl"
    loads = {
        "type": "assistant",
        "message": {
            "id": "m0",
            "content": [{"type": "tool_use", "name": "Skill", "input": {"skill": "compost:implement"}}],
        },
    }
    asks = {"type": "assistant", "message": {"id": "m1", "content": [{"type": "text", "text": "Which library?"}]}}
    transcript.write_text(f"{json.dumps(loads)}\n{json.dumps(asks)}\n")
    return json.dumps({"transcript_path": str(transcript), "stop_hook_active": False})


def test_the_scripts_that_need_typesafe_sdk_are_the_ones_found():
    """stop_guard.py gets the guard through its `import jev` (deferred until it has a message to judge); a new script with the header joins the next test."""
    assert JEV_SCRIPTS == ["jev.py", "lint/jev_lint.py", "lint/run_eval.py", "stop_guard.py"]


@pytest.mark.parametrize("script", JEV_SCRIPTS)
def test_each_jev_script_under_bare_python_without_uv_exits_3_without_a_traceback(script, tmp_path):
    # stop_guard.py imports Jev only once it has a message to judge, so it gets one.
    stdin = waiting_stop(tmp_path) if script == "stop_guard.py" else None
    ran = bare_python(str(SCRIPTS / script), path=str(tmp_path), stdin=stdin)
    assert ran.returncode == 3, ran.stderr
    assert "Traceback" not in ran.stderr
    assert f"Run it as `uv run {SCRIPTS / script}`" in ran.stderr


@pytest.mark.skipif(shutil.which("uv") is None, reason="needs uv on PATH")
def test_jev_py_under_bare_python_re_execs_under_uv_and_lists_the_tools():
    ran = bare_python(str(SCRIPTS / "jev.py"), "list", path=os.environ["PATH"])
    assert ran.returncode == 0, ran.stderr
    assert "review-risk" in ran.stdout
