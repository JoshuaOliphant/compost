# ABOUTME: Tests gate_drift.py against real git repos: which changed files and added lines count as edits to the
# ABOUTME: checks that judge a branch, which removed tests it reports, its JSON and exit codes, and the merged-PR scan.
import json

import gate_drift
import pytest
from conftest import commit, run_git


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    run_git(root, "init", "-q", "-b", "main")
    run_git(root, "config", "user.email", "t@example.com")
    run_git(root, "config", "user.name", "Tester")
    run_git(root, "config", "commit.gpgsign", "false")
    commit(root, {"README.md": "hello\n"}, "root")
    return root


def changed(repo, files: dict[str, str]) -> list[tuple[str, str, str]]:
    """The hits for one commit on top of HEAD that writes `files`."""
    base = run_git(repo, "rev-parse", "HEAD")
    head = commit(repo, files, "change")
    return [(hit.kind, hit.path, hit.detail) for hit in gate_drift.drift(repo, base, head)]


@pytest.mark.parametrize(
    ("path", "kind"),
    [
        ("docs/agents/testing.md", "recorded gates"),
        ("REVIEW.md", "review guide"),
        ("scripts/verify", "verify command"),
        ("scripts/verify.sh", "verify command"),
        (".github/workflows/ci.yml", "CI workflow"),
        (".pre-commit-config.yaml", "pre-commit"),
        ("ruff.toml", "lint/test config"),
        (".ruff.toml", "lint/test config"),
        ("pytest.ini", "lint/test config"),
        ("tox.ini", "lint/test config"),
        ("setup.cfg", "lint/test config"),
        (".coveragerc", "lint/test config"),
        ("mypy.ini", "lint/test config"),
        ("plugin/tests/conftest.py", "test fixtures/collection"),
    ],
)
def test_a_changed_gate_file_is_a_hit(repo, path, kind):
    assert changed(repo, {path: "x\n"}) == [(kind, path, "file changed")]


def test_a_deleted_gate_file_is_a_hit(repo):
    commit(repo, {".github/workflows/ci.yml": "on: push\n"}, "ci")
    base = run_git(repo, "rev-parse", "HEAD")
    run_git(repo, "rm", "-q", ".github/workflows/ci.yml")
    run_git(repo, "commit", "-q", "-m", "drop ci")

    assert [hit.kind for hit in gate_drift.drift(repo, base, "HEAD")] == ["CI workflow"]


@pytest.mark.parametrize(
    ("path", "line", "kind"),
    [
        ("src/app.py", "x = 1  # pragma: no cover", "coverage exclusion"),
        ("src/app.py", "import os  # noqa: F401", "lint suppression"),
        ("src/app.py", "y = f()  # type: ignore[arg-type]", "type suppression"),
        ("tests/test_app.py", "@pytest.mark.skip(reason='later')", "skipped test"),
        ("tests/test_app.py", "@pytest.mark.xfail", "skipped test"),
        ("tests/test_app.py", "    pytest.skip('no key')", "skipped test"),
        ("web/app.test.js", "xit('renders', () => {})", "skipped test"),
        ("web/app.test.js", "it.skip('renders', () => {})", "skipped test"),
        ("pyproject.toml", "fail_under = 90", "coverage threshold"),
        ("Makefile", "\tpytest --cov-fail-under=80", "coverage threshold"),
        (".coveragerc", "exclude_also = ['def __repr__']", "coverage exclusion config"),
        (".coveragerc", "omit = src/legacy/*", "coverage exclusion config"),
        ("ruff.toml", 'per-file-ignores = {"x.py" = ["E501"]}', "lint ignore config"),
        ("ruff.toml", 'extend-ignore = ["E501"]', "lint ignore config"),
        ("tests/test_app.py", "    time.sleep(2)", "sleep/retry in a test"),
        ("tests/test_app.py", "@retry(times=3)", "sleep/retry in a test"),
        ("tests/test_app.py", "@pytest.mark.flaky(reruns=3)", "sleep/retry in a test"),
    ],
)
def test_an_added_weakener_is_a_hit(repo, path, line, kind):
    assert (kind, path, line.strip()) in changed(repo, {path: f"{line}\n"})


@pytest.mark.parametrize(
    ("path", "line"),
    [
        pytest.param("src/app.py", "    time.sleep(2)", id="sleep-outside-a-test"),
        pytest.param("tests/test_app.py", "    sys.exit(main())", id="exit-is-not-xit"),
        pytest.param("tests/test_app.py", "    os._exit(0)", id="underscore-exit-is-not-xit"),
        pytest.param("plugin/skills/verify/SKILL.md", "a `pragma: no cover` on that line", id="prose-in-a-doc"),
        pytest.param("src/app.py", "total = 1", id="plain-code"),
    ],
)
def test_a_line_that_weakens_nothing_is_no_hit(repo, path, line):
    assert changed(repo, {path: f"{line}\n"}) == []


def test_a_removed_weakener_is_no_hit(repo):
    commit(repo, {"src/app.py": "import os  # noqa: F401\n"}, "suppress")

    assert changed(repo, {"src/app.py": "import os\n"}) == []


def test_a_removed_test_is_a_hit_unless_the_same_file_defines_it_again(repo):
    commit(
        repo,
        {
            "tests/test_app.py": "def test_kept():\n    pass\n\n\nasync def test_dropped():\n    pass\n",
            "tests/test_moved.py": "class TestX:\n    def test_moved(self):\n        pass\n",
            "src/app.py": "def test_helper():\n    pass\n",
        },
        "tests",
    )

    hits = changed(
        repo,
        {
            "tests/test_app.py": "def test_kept(tmp_path):\n    pass\n",
            "tests/test_moved.py": "",
            "tests/test_other.py": "def test_moved():\n    pass\n",
            "src/app.py": "",
        },
    )

    assert hits == [
        ("test removed or renamed", "tests/test_app.py", "test_dropped"),
        ("test removed or renamed", "tests/test_moved.py", "test_moved"),
    ]


def test_a_deleted_test_file_reports_each_of_its_tests(repo):
    commit(repo, {"tests/test_gone.py": "def test_a():\n    pass\n\n\ndef test_b():\n    pass\n"}, "tests")
    base = run_git(repo, "rev-parse", "HEAD")
    run_git(repo, "rm", "-q", "tests/test_gone.py")
    run_git(repo, "commit", "-q", "-m", "drop")

    assert [(hit.path, hit.detail) for hit in gate_drift.drift(repo, base, "HEAD")] == [
        ("tests/test_gone.py", "test_a"),
        ("tests/test_gone.py", "test_b"),
    ]


PYPROJECT = """[project]
name = "app"
version = "1.0.0"

[tool.coverage.report]
fail_under = 100
show_missing = true

[[tool.mypy.overrides]]
module = "x"

[tool.ruff]
line-length = 120
"""


@pytest.mark.parametrize(
    ("old", "new", "sections"),
    [
        pytest.param('version = "1.0.0"', 'version = "1.1.0"', [], id="project-table-is-not-a-gate"),
        pytest.param("show_missing = true", "show_missing = false", ["tool.coverage.report"], id="coverage"),
        pytest.param("line-length = 120\n", "", ["tool.ruff"], id="removed-gate-line"),
        pytest.param('module = "x"', 'module = "y"', ["tool.mypy.overrides"], id="array-of-tables"),
        pytest.param(
            "[tool.ruff]\n",
            "[tool.pytest.ini_options]\naddopts = '-q'\n\n[tool.ruff]\n",
            ["tool.pytest.ini_options"],
            id="new-gate-section",
        ),
        pytest.param(
            "line-length = 120\n",
            "line-length = 120\n\n[project.scripts]\napp = 'app:main'\n",
            [],
            id="blank-line-before-a-new-table-is-not-the-gate-above",
        ),
    ],
)
def test_pyproject_is_a_hit_only_where_it_changes_a_gate_section(repo, old, new, sections):
    commit(repo, {"plugin/pyproject.toml": PYPROJECT}, "pyproject")

    hits = changed(repo, {"plugin/pyproject.toml": PYPROJECT.replace(old, new)})

    assert hits == [("lint/test config", "plugin/pyproject.toml", f"[{section}] changed") for section in sections]


def test_lowering_the_threshold_is_a_threshold_hit_and_a_gate_config_hit(repo):
    commit(repo, {"pyproject.toml": PYPROJECT}, "pyproject")

    assert changed(repo, {"pyproject.toml": PYPROJECT.replace("fail_under = 100", "fail_under = 90")}) == [
        ("coverage threshold", "pyproject.toml", "fail_under = 90"),
        ("lint/test config", "pyproject.toml", "[tool.coverage.report] changed"),
    ]


def test_drift_reads_from_the_merge_base_so_base_moving_on_adds_no_hits(repo):
    base = run_git(repo, "rev-parse", "HEAD")
    run_git(repo, "switch", "-q", "-c", "feature")
    commit(repo, {"src/app.py": "x = 1\n"}, "feature")
    run_git(repo, "switch", "-q", "main")
    commit(repo, {"tests/conftest.py": "x\n"}, "main moves on")

    assert gate_drift.drift(repo, "main", "feature") == []
    assert gate_drift.drift(repo, base, "main") != []


def test_main_prints_hits_as_json_and_exits_1(repo, capsys):
    base = run_git(repo, "rev-parse", "HEAD")
    commit(repo, {"tests/conftest.py": "x = 1  # pragma: no cover\n"}, "change")

    assert gate_drift.main([base, "HEAD", "--repo", str(repo)]) == 1

    assert json.loads(capsys.readouterr().out) == [
        {"kind": "test fixtures/collection", "path": "tests/conftest.py", "detail": "file changed"},
        {"kind": "coverage exclusion", "path": "tests/conftest.py", "detail": "x = 1  # pragma: no cover"},
    ]


def test_main_exits_0_with_no_hits(repo, capsys):
    base = run_git(repo, "rev-parse", "HEAD")
    commit(repo, {"src/app.py": "x = 1\n"}, "change")

    assert gate_drift.main([base, "HEAD", "--repo", str(repo)]) == 0
    assert json.loads(capsys.readouterr().out) == []


def test_main_exits_2_on_a_ref_git_cannot_resolve(repo, capsys):
    assert gate_drift.main(["no-such-ref", "HEAD", "--repo", str(repo)]) == 2
    assert "git merge-base failed" in capsys.readouterr().err


def test_main_needs_a_base_and_head_without_history(capsys):
    with pytest.raises(SystemExit) as raised:
        gate_drift.main(["main"])

    assert raised.value.code == 2
    assert "give <base> <head>, or --history" in capsys.readouterr().err


def merge_pr(repo, branch: str, files: dict[str, str], subject: str) -> str:
    run_git(repo, "switch", "-q", "-c", branch)
    commit(repo, files, branch)
    run_git(repo, "switch", "-q", "main")
    commit(repo, {f"{branch}.log": "main moved\n"}, f"main beside {branch}")
    run_git(repo, "merge", "-q", "--no-ff", "-m", subject, branch)
    return run_git(repo, "rev-parse", "HEAD")


def test_history_scans_every_merged_pr(repo, capsys):
    gated = merge_pr(
        repo, "one", {"tests/test_app.py": "import sys\nsys.exit(0)\n"}, "Merge pull request #1 from a/one"
    )
    clean = merge_pr(repo, "two", {"tests/conftest.py": "x\n"}, "Merge pull request #2 from a/two")
    merge_pr(repo, "three", {"tests/conftest.py": "y\n"}, "Merge branch 'three'")
    run_git(repo, "switch", "-q", "--orphan", "stray")
    commit(repo, {"stray.txt": "x\n"}, "stray")
    run_git(repo, "switch", "-q", "main")
    run_git(
        repo, "merge", "-q", "--no-ff", "--allow-unrelated-histories", "-m", "Merge pull request #4 from a/s", "stray"
    )
    unrelated = run_git(repo, "rev-parse", "HEAD")

    assert gate_drift.main(["--history", "--repo", str(repo)]) == 1

    report = json.loads(capsys.readouterr().out)
    assert [row["merge"] for row in report] == [unrelated, clean, gated]
    assert "git merge-base failed" in report[0]["error"]
    assert report[1] == {
        "merge": clean,
        "subject": "Merge pull request #2 from a/two",
        "hits": [{"kind": "test fixtures/collection", "path": "tests/conftest.py", "detail": "file changed"}],
    }
    assert report[2]["hits"] == []


def test_history_exits_0_when_no_merged_pr_has_hits(repo, capsys):
    merge_pr(repo, "one", {"src/app.py": "x\n"}, "Merge pull request #1 from a/one")

    assert gate_drift.main(["--history", "--repo", str(repo)]) == 0


def test_history_exits_2_outside_a_git_repo(tmp_path, capsys):
    assert gate_drift.main(["--history", "--repo", str(tmp_path)]) == 2
    assert "git log failed" in capsys.readouterr().err
