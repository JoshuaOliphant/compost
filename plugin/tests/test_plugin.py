# ABOUTME: Checks the plugin as shipped: frontmatter, links, compost:<name> and ${CLAUDE_PLUGIN_ROOT} references,
# ABOUTME: pile.toml feeds and NOTICE, the tracker-doc fork-check fallback, the lane-routing table's values,
# ABOUTME: implement's stop list against the Stop hook's, that branching skills update the default branch first,
# ABOUTME: and that git tracks every shipped file. Runs on the real files.
import itertools
import os
import re
import subprocess

import pile
import pytest
import yaml
from conftest import PLUGIN_ROOT
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


def test_a_run_contract_keeps_every_irreversible_stop_and_the_prerequisite_stop_is_allowed():
    assert set(meta.IRREVERSIBLE_STOPS) < set(meta.ALLOWED_STOPS)
    assert meta.PREREQUISITE_STOP in meta.ALLOWED_STOPS
    template = (PLUGIN_ROOT / "skills" / "spec" / "references" / "parent-issue.md").read_text()
    contract = " ".join(template.split("## Run contract", 1)[1].split("\n## ", 1)[0].split())
    for heading in ("### Stops", "### Prerequisites", "### Departures"):
        assert heading in contract, f"the Run contract template lacks {heading!r}"
    for stop in meta.IRREVERSIBLE_STOPS:
        assert stop in contract, f"the Run contract template doesn't name the irreversible stop {stop!r}"


@pytest.mark.parametrize(
    ("step", "phrases"),
    [
        (
            "Check readiness and write the run contract.",
            [
                "(references/readiness.md)",
                "can add stops but never drop",
                "ask it as an open question before posting",
                "mark it unconfirmed",
                "readiness record",
            ],
        ),
        (
            "Post the parent issue",
            [
                "Bounded work hands off with no approval",
                "ask for approval once, naming the spec and its run contract",
            ],
        ),
    ],
)
def test_spec_ends_with_a_readiness_check_and_one_approval_for_architectural_work(step, phrases):
    text = " ".join((PLUGIN_ROOT / "skills" / "spec" / "SKILL.md").read_text().split())
    body = re.split(r" \d+\. \*\*| ## ", text.split(f"**{step}", 1)[1], maxsplit=1)[0]
    for phrase in phrases:
        assert phrase in body, f"spec's {step!r} step lacks {phrase!r}"


def test_the_readiness_check_is_short_for_bounded_work_and_full_for_architectural_work():
    text = " ".join((PLUGIN_ROOT / "skills" / "spec" / "references" / "readiness.md").read_text().split())
    short, full = text.split("The short check, for bounded work:", 1)[1].split("The full check, for architectural work")
    for item in ("names the kind of test and the seam", "every prerequisite's check has run", "no open question"):
        assert item in short, f"the short check lacks {item!r}"
    for item in ("rabbit holes", "no-gos", "pre-mortem"):
        assert item in full and item not in short, f"{item!r} belongs to the full check only"


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
