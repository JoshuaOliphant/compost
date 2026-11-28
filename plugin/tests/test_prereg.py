# ABOUTME: Tests prereg.py, compost:experiment's preregistration: check refuses incomplete, unpinned, or uncommitted files,
# ABOUTME: and score judges results by the bars as committed, so an amended bar, a stale ref, or a different n can't pass.
import io
import json

import prereg
import pytest
from conftest import commit, run_git

REF = "a" * 40

VALID = f"""
question = "Does 0.58.0's skeptic still refute the wrong claims it was tuned on?"
hypothesis = "The shipped replay numbers reproduce at main."
prediction = "Wrong claims refuted 7 of 10 in each run."
scorer = "python3 replay/bars.py results/x"
stop = "Two runs. An errored run is rerun once. No extra runs to rescue a miss."
budget = "$20"
n = 2
controls = ["the six clean control cases"]

[decision]
pass = "Keep 0.58.0's numbers as the baseline."
miss = "File an issue: the shipped numbers do not reproduce."

[subject]
repo = "JoshuaOliphant/compost"
ref = "{REF}"

[arms]
skeptic = "replay/run.py at subject.ref"

[sets]
wrong_claims = ["case-a S1", "case-b S2"]

[[bars]]
metric = "wrong_claims_refuted"
op = ">="
value = 7
aggregate = "each"
set = "wrong_claims"

[[bars]]
metric = "control_bm"
op = "<="
value = 2
aggregate = "max"
"""


def run(*argv) -> tuple[int, str]:
    out = io.StringIO()
    code = prereg.main([str(arg) for arg in argv], out)
    return code, out.getvalue()


@pytest.fixture
def registered(work_repo) -> tuple:
    """A committed, valid prereg.toml in work_repo and its registration commit."""
    sha = commit(work_repo, {"exp/prereg.toml": VALID}, "register")
    return work_repo / "exp" / "prereg.toml", sha


def results(tmp_path, **fields) -> str:
    body = {"ref": REF, "n": 2, "metrics": {"wrong_claims_refuted": [7, 8], "control_bm": [2, 1]}} | fields
    path = tmp_path / "results.json"
    path.write_text(json.dumps(body))
    return path


def test_a_committed_complete_prereg_checks_and_prints_its_registration(registered):
    path, sha = registered
    head = run_git(path.parent, "rev-parse", "HEAD~1")
    path.write_text(VALID.replace(REF, head))
    run_git(path.parent, "commit", "-qam", "pin a real commit")
    sha = run_git(path.parent, "rev-parse", "HEAD")
    assert run("check", path, "--subject-repo", path.parent) == (
        0,
        f"registered at {sha}; record it and pass it to score\n",
    )


@pytest.mark.parametrize(
    ("field", "named"),
    [
        ("hypothesis", "missing hypothesis"),
        ("scorer", "missing scorer"),
        ("controls", "missing controls"),
        ("n", "n must be"),
    ],
)
def test_check_refuses_a_committed_prereg_missing_a_field_and_names_it(work_repo, field, named):
    text = "\n".join(line for line in VALID.splitlines() if not line.startswith(f"{field} ="))
    commit(work_repo, {"p.toml": text}, "register without a field")
    code, said = run("check", work_repo / "p.toml", "--subject-repo", work_repo)
    assert code == 2 and named in said


@pytest.mark.parametrize(
    ("table", "named"),
    [
        ("sets", "missing sets"),
        ("decision", "missing decision.pass"),
        ("arms", "missing arms"),
        ("bars", "missing bars"),
    ],
)
def test_problems_names_a_missing_table(table, named):
    data = prereg.tomllib.loads(VALID)
    del data[table]
    assert any(named in line for line in prereg.problems(data))


@pytest.mark.parametrize(
    ("change", "named"),
    [
        ({"subject": {"repo": "x", "ref": "main"}}, "full 40-character SHA"),
        ({"subject": {"ref": REF}}, "missing subject.repo"),
        ({"decision": {"pass": "keep"}}, "decision.miss"),
        ({"controls": []}, "missing controls"),
        ({"n": 0}, "n must be"),
        ({"n": True}, "n must be"),
        ({"bars": ["x"]}, "bars[0]: must be a table"),
        ({"bars": [{"metric": "", "op": "~", "value": "7", "aggregate": "median"}]}, "bars[0]: missing metric"),
        ({"bars": [{"metric": "m", "op": "~", "value": 7}]}, "op must be one of"),
        ({"bars": [{"metric": "m", "op": ">=", "value": True}]}, "value must be a number"),
        ({"bars": [{"metric": "m", "op": ">=", "value": 7, "aggregate": "median"}]}, "aggregate must be one of"),
        ({"budget": "  "}, "missing budget"),
        ({"bars": [{"metric": "m", "op": ">=", "value": 7, "set": "nope"}]}, "set 'nope' is not a list in [sets]"),
        ({"question": "Does <change> help?"}, "question still holds the template placeholder <change>"),
    ],
)
def test_problems_names_each_way_a_field_falls_short(change, named):
    data = prereg.tomllib.loads(VALID) | change
    assert any(named in line for line in prereg.problems(data))
    assert prereg.problems(prereg.tomllib.loads(VALID)) == []


def test_check_refuses_invalid_toml(work_repo):
    path = work_repo / "p.toml"
    path.write_text("question = ")
    code, said = run("check", path, "--subject-repo", work_repo)
    assert code == 2 and "not valid TOML" in said


def test_check_refuses_a_ref_the_subject_repo_does_not_hold(registered, work_repo):
    path, _ = registered
    code, said = run("check", path, "--subject-repo", work_repo)
    assert code == 2 and f"subject.ref {REF} is not a commit" in said
    head = run_git(work_repo, "rev-parse", "HEAD~1")
    path.write_text(VALID.replace(REF, head))
    run_git(work_repo, "commit", "-qam", "pin a real commit")
    assert run("check", path, "--subject-repo", work_repo)[0] == 0


def test_check_refuses_an_uncommitted_or_edited_prereg(registered, work_repo, tmp_path):
    path, _ = registered
    path.write_text(VALID + "\n# edited\n")
    code, said = run("check", path, "--subject-repo", work_repo)
    assert code == 2 and "uncommitted changes; commit it before running" in said

    fresh = work_repo / "fresh.toml"
    fresh.write_text(VALID)
    assert "uncommitted changes" in run("check", fresh, "--subject-repo", work_repo)[1]

    outside = tmp_path / "loose" / "p.toml"
    outside.parent.mkdir()
    outside.write_text(VALID)
    assert "not in a git repo" in run("check", outside, "--subject-repo", work_repo)[1]


def test_registration_refuses_a_file_git_has_never_committed(work_repo):
    path = work_repo / "p.toml"
    path.write_text(VALID)
    with pytest.raises(prereg.Refused, match="is not committed"):
        prereg.registration(path)


def test_score_prints_each_bar_and_passes(registered, tmp_path):
    path, sha = registered
    code, said = run("score", path, "--registered", sha, "--results", results(tmp_path))
    assert code == 0
    assert said.splitlines() == [
        "PASS  wrong_claims_refuted (each) 7 >= 7 of 2 in wrong_claims",
        "PASS  control_bm (max) 2 <= 2",
        "VERDICT: PASS",
    ]


def test_score_reports_a_miss_when_any_run_falls_short(registered, tmp_path):
    path, sha = registered
    metrics = {"wrong_claims_refuted": [8, 6], "control_bm": [0, 0]}
    code, said = run("score", path, "--registered", sha, "--results", results(tmp_path, metrics=metrics))
    assert code == 1
    assert "MISS  wrong_claims_refuted (each) 6 >= 7" in said and said.endswith("VERDICT: MISS\n")


def test_an_amended_bar_does_not_change_the_verdict(registered, tmp_path, work_repo):
    path, sha = registered
    path.write_text(VALID.replace("value = 7", "value = 6"))
    run_git(work_repo, "commit", "-qam", "loosen the bar after seeing a 6")
    metrics = {"wrong_claims_refuted": [6, 6], "control_bm": [0, 0]}
    code, said = run("score", path, "--registered", sha, "--results", results(tmp_path, metrics=metrics))
    assert code == 1
    assert f"amended after registration: judged by the bars at {sha[:12]}" in said


@pytest.mark.parametrize(
    ("fields", "named"),
    [
        ({"ref": "b" * 40}, "INVALID: the run used ref"),
        ({"n": 3}, "INVALID: the run has n=3"),
        ({"metrics": {"wrong_claims_refuted": [7, 7]}}, "INVALID: the results have no control_bm"),
        ({"metrics": {"wrong_claims_refuted": [7], "control_bm": [0, 0]}}, "has 1 values, but 2 runs"),
        ({"metrics": {"wrong_claims_refuted": 7, "control_bm": [0, 0]}}, "asks for the each of 2 runs"),
    ],
)
def test_score_refuses_results_that_do_not_match_the_registration(registered, tmp_path, fields, named):
    path, sha = registered
    code, said = run("score", path, "--registered", sha, "--results", results(tmp_path, **fields))
    assert code == 2 and named in said


def test_score_refuses_a_registration_commit_without_the_file(registered, work_repo, tmp_path):
    path, _ = registered
    first = run_git(work_repo, "rev-list", "--max-parents=0", "HEAD")
    code, said = run("score", path, "--registered", first, "--results", results(tmp_path))
    assert code == 2 and "is not in commit" in said


@pytest.mark.parametrize(
    ("bar", "values", "expected"),
    [
        ({"metric": "m", "op": ">=", "value": 7, "aggregate": "mean"}, [7, 8], (True, 7.5, "mean")),
        ({"metric": "m", "op": "<", "value": 3, "aggregate": "sum"}, [1, 1], (True, 2, "sum")),
        ({"metric": "m", "op": ">", "value": 4, "aggregate": "min"}, [5, 9], (True, 5, "min")),
        ({"metric": "m", "op": "==", "value": 1, "aggregate": "each"}, [1, 2], (False, 2, "each")),
        ({"metric": "m", "op": ">=", "value": 9}, 9, (True, 9, "value")),
        ({"metric": "m", "op": ">=", "value": 9, "aggregate": "mean"}, 9.5, (True, 9.5, "value")),
    ],
)
def test_judge_reduces_per_run_values_by_the_bars_aggregate(bar, values, expected):
    n = len(values) if isinstance(values, list) else 1
    assert prereg.judge(bar, values, n) == expected


def test_a_per_run_list_with_no_aggregate_is_refused():
    with pytest.raises(prereg.Refused, match="names no aggregate"):
        prereg.judge({"metric": "m", "op": ">=", "value": 7}, [7, 8], 2)


def test_the_skills_template_has_every_field_check_asks_for():
    template = prereg.Path(__file__).parent.parent / "skills" / "experiment" / "references" / "prereg-template.toml"
    found = prereg.problems(prereg.tomllib.loads(template.read_text()))
    assert "subject.ref must be the full 40-character SHA under test, not a branch or short SHA" in found
    assert "controls[0] still holds the template placeholder <control>" in found
    assert "bars[0].metric still holds the template placeholder <a metric the scorer prints>" in found
    assert all("placeholder" in line or "subject.ref" in line for line in found)


@pytest.mark.parametrize(
    ("body", "named"),
    [
        (None, "can't read results"),
        ("not json", "can't read results"),
        ("[1, 2]", 'must be an object with a "metrics" object'),
        (json.dumps({"ref": REF, "n": 2}), 'must be an object with a "metrics" object'),
        (
            json.dumps({"ref": REF, "n": 2, "metrics": {"wrong_claims_refuted": None}}),
            "metric wrong_claims_refuted must be",
        ),
        (
            json.dumps({"ref": REF, "n": 2, "metrics": {"wrong_claims_refuted": ["7", 8]}}),
            "must be a number or a non-empty list",
        ),
        (
            json.dumps({"ref": REF, "n": 2, "metrics": {"wrong_claims_refuted": []}}),
            "must be a number or a non-empty list",
        ),
        (
            json.dumps({"ref": REF, "n": 2, "metrics": {"wrong_claims_refuted": True}}),
            "must be a number or a non-empty list",
        ),
    ],
)
def test_score_refuses_a_broken_results_file_as_invalid_never_a_miss(registered, tmp_path, body, named):
    path, sha = registered
    results_file = tmp_path / "results.json"
    if body is not None:
        results_file.write_text(body)
    code, said = run("score", path, "--registered", sha, "--results", results_file)
    assert code == 2 and named in said


def test_check_needs_a_subject_repo_to_resolve_the_ref_in(registered):
    path, _ = registered
    with pytest.raises(SystemExit) as exited:
        run("check", path)
    assert exited.value.code == 2


def test_a_shell_redirect_in_the_scorer_is_not_a_template_placeholder():
    data = prereg.tomllib.loads(VALID) | {"scorer": "python3 bars.py < runs.txt > results.json"}
    assert prereg.problems(data) == []


def test_check_refuses_a_prereg_that_does_not_exist(work_repo):
    code, said = run("check", work_repo / "missing.toml", "--subject-repo", work_repo)
    assert code == 2 and "can't read" in said


def test_score_refuses_a_registered_value_that_is_not_a_full_sha(registered, tmp_path):
    path, sha = registered
    for bad in (sha[:12], "--output=/tmp/x"):
        code, said = run("score", path, f"--registered={bad}", "--results", results(tmp_path))
        assert code == 2 and "--registered must be the full 40-character commit" in said


def test_a_prereg_deleted_after_registration_is_still_judged_by_the_registered_bars(registered, tmp_path):
    path, sha = registered
    path.unlink()
    code, said = run("score", path, "--registered", sha, "--results", results(tmp_path))
    assert code == 0 and "amended after registration" in said
