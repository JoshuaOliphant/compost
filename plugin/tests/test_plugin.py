# ABOUTME: Checks the plugin as shipped: frontmatter, links, compost:<name> and ${CLAUDE_PLUGIN_ROOT} references,
# ABOUTME: pile.toml feeds and NOTICE, the tracker-doc fork-check fallback, the lane-routing table's values,
# ABOUTME: implement's stop list against the Stop hook's, that branching skills update the default branch first,
# ABOUTME: and that git tracks every shipped file. Runs on the real files.
import io
import itertools
import json
import os
import re
import shlex
import subprocess

import pile
import pytest
import stamp
import yaml
from conftest import PLUGIN_ROOT, commit
from jevtools import meta

LOCAL_ONLY = {"tests", ".venv", ".pytest_cache", "__pycache__"}
SHIPPED = (
    ".claude-plugin",
    "agents",
    "canon",
    "hooks",
    "scripts",
    "skills",
    "workflows",
    "NOTICE",
    "pile.toml",
    "README.md",
)
SKILLS = sorted(path.parent for path in (PLUGIN_ROOT / "skills").glob("*/SKILL.md"))
MARKDOWN = sorted(
    path for path in PLUGIN_ROOT.rglob("*.md") if not LOCAL_ONLY & set(path.relative_to(PLUGIN_ROOT).parts)
)
LINK = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")
REFERENCE = re.compile(r"compost:([a-z][a-z0-9-]*)")
LOCAL_EVAL_CASES = re.compile(r"[\w./-]*\bevals/[\w-]+\.json")
PLUGIN_PATH = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([\w./-]+[\w/])")
WORKFLOW_NAME = re.compile(r"export const meta = \{\s*name: '([^']+)'")


def frontmatter(skill_dir):
    return file_frontmatter(skill_dir / "SKILL.md")


def file_frontmatter(path):
    text = path.read_text()
    assert text.startswith("---\n"), f"{path}: must open with frontmatter"
    return yaml.safe_load(text[4 : text.index("\n---", 4)])


def known_names():
    workflows = {WORKFLOW_NAME.search(path.read_text()).group(1) for path in (PLUGIN_ROOT / "workflows").glob("*.js")}
    agents = {path.stem for path in (PLUGIN_ROOT / "agents").glob("*.md")}
    return {path.name for path in SKILLS} | workflows | agents


@pytest.mark.parametrize("skill_dir", SKILLS, ids=lambda path: path.name)
def test_skill_frontmatter_names_its_directory_and_says_when_to_use_it(skill_dir):
    fields = frontmatter(skill_dir)
    assert fields["name"] == skill_dir.name
    assert re.search(r"\bUse (when|before|once|after)\b", fields["description"])
    assert len(fields["description"]) <= 1024


@pytest.mark.parametrize("agent", ["scope", "skeptic"])
def test_workflow_helper_agents_are_lean(agent):
    fields = file_frontmatter(PLUGIN_ROOT / "agents" / f"{agent}.md")
    assert fields["name"] == agent
    assert [tool.strip() for tool in fields["tools"].split(",")] == ["Read", "Grep", "Glob", "Bash"]


@pytest.mark.parametrize("document", MARKDOWN, ids=lambda path: str(path.relative_to(PLUGIN_ROOT)))
def test_relative_links_resolve(document):
    targets = [target for target in LINK.findall(document.read_text()) if "://" not in target]
    missing = [target for target in targets if not (document.parent / target).exists()]
    assert missing == []


def test_labeled_eval_cases_are_named_in_compost_evals_not_as_a_local_path():
    local = {
        (str(path.relative_to(PLUGIN_ROOT)), found)
        for path in MARKDOWN
        for found in LOCAL_EVAL_CASES.findall(path.read_text())
    }
    assert local == set()


def test_every_compost_reference_names_a_skill_workflow_or_agent():
    names = known_names()
    files = [*MARKDOWN, *(PLUGIN_ROOT / "workflows").glob("*.js")]
    unknown = {
        (str(path.relative_to(PLUGIN_ROOT)), name)
        for path in files
        for name in REFERENCE.findall(path.read_text())
        if name not in names
    }
    assert unknown == set()


# A mod is a file whose `register` the hooks module imports; helpers and the module itself are not.
MOD_IMPORT = re.compile(r"import \{[^}]*\bregister as \w+[^}]*\} from '\./([\w-]+)\.tsx?'")


def test_pile_feeds_only_existing_skills_the_canon_or_mechanisms_and_notice_is_current():
    sources = pile.load(PLUGIN_ROOT / "pile.toml").sources
    module = (PLUGIN_ROOT / "hooks" / "compost.ts").read_text()
    mods = {f"hooks/{name}" for name in MOD_IMPORT.findall(module)}
    assert mods, "no mods found; MOD_IMPORT no longer matches how hooks/compost.ts imports a mod's register"
    targets = {path.name for path in SKILLS} | {"canon", "hooks"} | mods
    fed = {skill for source in sources for skills in source.feeds.values() for skill in skills}
    assert fed - targets == set()
    assert (PLUGIN_ROOT / "NOTICE").read_text() == pile.render_notice(sources)


def test_plugin_root_paths_exist_and_scripts_are_executable():
    referenced = {path for document in MARKDOWN for path in PLUGIN_PATH.findall(document.read_text())}
    assert referenced, "no ${CLAUDE_PLUGIN_ROOT} paths found; the pattern no longer matches the skills"
    assert sorted(path for path in referenced if not (PLUGIN_ROOT / path).exists()) == []
    scripts = sorted(PLUGIN_ROOT.glob("skills/*/scripts/*.sh"))
    assert [script.name for script in scripts if not os.access(script, os.X_OK)] == []


def test_git_ignores_no_shipped_file():
    ignored = subprocess.run(
        ["git", "-C", str(PLUGIN_ROOT), "ls-files", "--others", "--ignored", "--exclude-standard", *SHIPPED],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split("\n")
    assert [path for path in ignored if path and not LOCAL_ONLY & set(path.split("/"))] == []


# The Agent tool's `model` and `effort` enums, copied from Claude Code's Agent tool schema on 2026-10-20
# (AGENTS.md lists the same model aliases); a lane spawn with any other value is rejected.
AGENT_MODELS = {"haiku", "sonnet", "opus", "fable"}
AGENT_EFFORTS = {"low", "medium", "high", "xhigh", "max"}


def test_lane_routing_table_names_only_models_and_efforts_the_agent_tool_takes():
    table = (PLUGIN_ROOT / "skills" / "implement" / "references" / "lane-routing.md").read_text()
    cells = [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in table.splitlines()]
    start = next((i for i, row in enumerate(cells) if "Model" in row and "Effort" in row), None)
    assert start is not None, "lane-routing.md has no table with Model and Effort columns"
    model, effort = cells[start].index("Model"), cells[start].index("Effort")
    rows = list(itertools.takewhile(lambda row: len(row) > 1, cells[start + 2 :]))
    assert rows, "the routing table has no rows"
    short = [row for row in rows if len(row) <= max(model, effort)]
    assert short == [], "routing rows with fewer cells than the header"
    assert [row for row in rows if row[model] not in AGENT_MODELS or row[effort] not in AGENT_EFFORTS] == []


def test_implements_stop_list_opens_each_item_with_the_stop_hooks_allowed_stop_in_order():
    text = (PLUGIN_ROOT / "skills" / "implement" / "SKILL.md").read_text()
    block = text.split("Stop only for:\n", 1)[1].split("\n\n", 1)[0]
    items = [" ".join(item.split()) for item in re.split(r"^\s*- ", block, flags=re.MULTILINE) if item.strip()]
    assert len(items) == len(meta.ALLOWED_STOPS)
    for item, stop in zip(items, meta.ALLOWED_STOPS, strict=True):
        assert item.startswith(stop), f"{item!r} should open with {stop!r}"


@pytest.mark.parametrize(
    ("skill", "step", "keeps", "rules"),
    [
        ("implement", "Set up the feature branch.", "keep the local commits", "rule on it"),
        ("build", "Isolate the work.", "unpushed commits alone", "post a ruling"),
    ],
)
def test_branching_skills_fast_forward_the_default_branch_and_rule_when_it_cannot(skill, step, keeps, rules):
    text = " ".join((PLUGIN_ROOT / "skills" / skill / "SKILL.md").read_text().split())
    rule = re.split(r" \d+\. \*\*", text.split(f"**{step}**", 1)[1], maxsplit=1)[0]
    for phrase in (
        "git fetch origin",
        "git rev-list --count origin/<default>..",
        "git merge --ff-only origin/<default>",
        "branch from `origin/<default>`",
        "when uncommitted changes block",
        keeps,
        rules,
    ):
        assert phrase in rule, f"{skill}'s {step!r} step lacks {phrase!r}"


def step_text(skill, step):
    text = " ".join((PLUGIN_ROOT / "skills" / skill / "SKILL.md").read_text().split())
    return re.split(r" \d+\. \*\*", text.split(f"**{step}**", 1)[1], maxsplit=1)[0]


@pytest.mark.parametrize(
    ("skill", "step", "reports"),
    [
        ("verify", "Prove the one fact the change is safe because of.", "feature-map rows"),
        ("build", "See every new or changed test fail for the right reason.", None),
    ],
)
def test_live_checks_run_the_recorded_smoke_command_before_falling_back_to_run(skill, step, reports):
    rule = step_text(skill, step)
    smoke = rule.find("smoke command")
    assert smoke != -1 and "`## Run`" in rule, f"{skill}'s {step!r} step does not read the recorded smoke command"
    assert smoke < rule.find("`/run`"), f"{skill}'s {step!r} step reaches for /run before the smoke command"
    assert reports is None or reports in rule


@pytest.mark.parametrize(
    ("skill", "step", "phrases"),
    [
        pytest.param(
            "build",
            "Place each acceptance criterion.",
            ("property test", "round-trip", "invariant", "idempotent", "naive", "differential test", "oracle"),
            id="AC-1-build-names-property-and-differential-tests",
        ),
        pytest.param(
            "verify",
            "Run the verify command, and any gate it leaves out, fresh.",
            ("flaky test is never skipped, slept past, or retried", "delete", "ruling"),
            id="AC-2-verify-bans-flaky-shortcuts",
        ),
        pytest.param(
            "diagnose",
            "Build the feedback loop.",
            ("flaky test is never skipped, slept past, or retried", "delete", "ruling"),
            id="AC-2-diagnose-bans-flaky-shortcuts",
        ),
        pytest.param(
            "implement",
            "Review every issue.",
            ("failing gate", "three", "references/task-brief.md"),
            id="AC-3-implement-caps-gate-rounds",
        ),
    ],
)
def test_skills_carry_the_verification_rules_from_the_post(skill, step, phrases):
    rule = step_text(skill, step)
    for phrase in phrases:
        assert phrase in rule, f"{skill}'s {step!r} step lacks {phrase!r}"


def test_task_brief_caps_a_failing_gate_at_three_rounds_then_rules_and_moves_on():
    brief = " ".join((PLUGIN_ROOT / "skills" / "implement" / "references" / "task-brief.md").read_text().split())
    how = brief.split("## How to work", 1)[1].split("## Report", 1)[0]
    for phrase in ("failing gate", "third round", "ruling", "failing output", "DONE_WITH_CONCERNS"):
        assert phrase in how, f"the task brief's How to work lacks {phrase!r}"


def test_setup_records_a_smoke_command_and_feature_map_under_run():
    rule = step_text("setup", "Test convention, gates, and the run.")
    assert "`## Run`" in rule and "smoke command" in rule and "feature map" in rule
    reference = (PLUGIN_ROOT / "skills" / "setup" / "references" / "testing.md").read_text()
    template = reference.split("## Template for docs/agents/testing.md", 1)[1]
    run = template.split("\n## Run\n", 1)[1].split("\n## ", 1)[0]
    assert "| Feature | How to reach it | Expected result |" in run
    for status in ("passing", "broken: <first error>", "none: <why>"):
        assert status in run, f"the ## Run template has no {status!r} status"


def test_stop_guard_reference_keeps_the_rules_step_9_points_to():
    text = " ".join((PLUGIN_ROOT / "skills" / "implement" / "references" / "stop-guard.md").read_text().split())
    for phrase in (
        "stop only for the list",
        "resuming loads implement again, which starts a new run",
        "or the rest of the run is unguarded",
        "keeping to the list is still on you",
    ):
        assert phrase in text, f"stop-guard.md lost {phrase!r}"
    step9 = " ".join((PLUGIN_ROOT / "skills" / "implement" / "SKILL.md").read_text().split())
    assert "(references/stop-guard.md)" in step9.split("**Decide, log, proceed.**", 1)[1].split("**Close out.**")[0]


def test_every_skill_and_agent_reading_the_tracker_doc_falls_back_to_setups_fork_check():
    readers = [
        path
        for path in [*(skill / "SKILL.md" for skill in SKILLS), *sorted((PLUGIN_ROOT / "agents").glob("*.md"))]
        if path.parent.name != "setup" and "docs/agents/issue-tracker.md" in path.read_text()
    ]
    assert len(readers) >= 8
    for path in readers:
        text = " ".join(path.read_text().split())
        assert "fork check" in text and "setup/references/issue-tracker-github.md" in text, (
            f"{path.relative_to(PLUGIN_ROOT)} reads the tracker doc but has no fallback for one without the fork check"
        )


def step(skill: str, title: str) -> str:
    """The text of a skill's numbered step, from its bold title to the next step or section."""
    text = (PLUGIN_ROOT / "skills" / skill / "SKILL.md").read_text()
    return re.split(r"^(?:\d+\. \*\*|## )", text.split(f"**{title}**", 1)[1], maxsplit=1, flags=re.MULTILINE)[0]


def stamp_commands(text: str) -> list[list[str]]:
    """Each `scripts/stamp.py ...` invocation in skill text, as stamp.main's argv, line continuations joined."""
    return [shlex.split(call) for call in re.findall(r"scripts/stamp\.py ([^`\n]+)", text.replace("\\\n", " "))]


def test_verify_stamps_only_on_done_and_finish_sends_an_unstamped_head_back_to_verify(work_repo, monkeypatch):
    """Runs the stamp commands as the skills give them: finish's read prints none until verify's write runs."""
    verify = step("verify", "Report the evidence.")
    finish = " ".join(step("finish", "Confirm the branch is ready.").split())
    assert 'When you say "done", and never otherwise, stamp the commit' in " ".join(verify.split())
    assert "`none` means" in finish and "run `compost:verify` again first" in finish
    [write], [show] = stamp_commands(verify), stamp_commands(finish)
    assert write[0] == "write" and show == ["show", "HEAD"]
    monkeypatch.chdir(work_repo)

    def shown() -> str:
        out = io.StringIO()
        assert stamp.main(show, out) == 0
        return out.getvalue().strip()

    assert shown() == "none"
    assert stamp.main(write) == 0
    assert json.loads(shown())["ac"] == "7/7"
    commit(work_repo, {"file.txt": "after verify\n"}, "a commit after verify")
    assert shown() == "none"
