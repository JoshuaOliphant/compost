# ABOUTME: Checks the plugin as shipped: frontmatter, links, compost:<name> and ${CLAUDE_PLUGIN_ROOT} references,
# ABOUTME: pile.toml feeds and NOTICE, the tracker-doc fork-check fallback, the lane-routing table's values,
# ABOUTME: implement's stop list against the Stop hook's, that branching skills update the default branch first,
# ABOUTME: the smoke, stamp, and verification rules the skills carry, and that git tracks every shipped file.
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


@pytest.mark.parametrize(
    "phrase",
    [
        "Judge the claim the reviewer made, not one you could make instead.",
        "the harm the claim predicts does not happen",
        "is not the claim: refute, and name it in your `reason`",
        "A baseline smell or a habit of the codebase is not a documented rule;",
        "A finding you uphold with `harm` set to `none` is refuted.",
        "the rule or AC-N it cites is missing or misquoted: give the `correction`",
        "the spec does not mention the defect: set `outsideSpec` (Spec findings)",
        "Grade the kind of harm that happens, not how often",
        "give in `limit` the file:line of the guard, caller, or flow that caps the harm",
        "Show where it stops, at a file:line;",
        "A claim that names several paths holds when any one of them reaches the harm, the headline one or not;",
        "Set `introduced` to false only when the claimed harm happens the same way at the base",
        "or adds a check that misses it; then `introduced` is true.",
        "the verdict is `unsure`; the finding survives as a minor",
    ],
)
def test_skeptic_refutes_a_harm_that_does_not_happen_and_grades_one_that_does(phrase):
    body = " ".join((PLUGIN_ROOT / "agents" / "skeptic.md").read_text().split())
    assert phrase in body
    assert "When you are uncertain, it is refuted" not in body
    assert "will bite" not in body


def test_skeptic_rubric_matches_the_reviewers():
    reviewer = (PLUGIN_ROOT / "agents" / "reviewer.md").read_text()
    workflow = (PLUGIN_ROOT / "workflows" / "review-changes.js").read_text()
    rubric = re.search(r"const SEVERITY_RUBRIC = `(.*?)`", workflow, re.S).group(1)
    for line in rubric.splitlines():
        level, text = line.removeprefix("- ").split(": ", 1)
        assert f"- `{level}`: {text}" in reviewer


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
    lead = r"Stop only for the run\s+contract's Stops \(step 1\), which always hold:\n"
    block = re.split(lead, text, maxsplit=1)[1].split("\n\n", 1)[0]
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


@pytest.mark.parametrize(
    ("reference", "step", "phrases"),
    [
        (
            "stop-guard.md",
            "Decide, log, proceed.",
            [
                "stop only for the list",
                "resuming loads implement again, which starts a new run",
                "or the rest of the run is unguarded",
                "keeping to the list is still on you",
                "plus any stop the parent's Run contract adds",
                "the first `Run contract stops:` block in your own messages since implement last loaded",
                "so a reload can narrow the stops, never widen them",
                "a second parent implemented in the same session",
            ],
        ),
        (
            "run-contract.md",
            "Orient.",
            [
                "Step 1 keeps to it before any worker branches",
                "On a parent without one, run the [readiness check](../../spec/references/readiness.md)",
                "whose **Ruling:** line ends `(assumed)`, then post the readiness record",
                "Stop before the first build only when a gap is on the Stops list",
                "a line `Run contract stops:`, then one `- <stop>` line per Stops item, word for word, then a blank line",
                "Print it again every time implement loads",
                "1. **Print the Stops.** Before anything that can stop the run",
                "Run each prerequisite's check before any worker branches",
                "marked unconfirmed, or one whose check fails now, stops the run there",
                "name the prerequisite and the check you ran",
                "stop only for an item on the contract's Stops, and post every other decision as a ruling comment",
            ],
        ),
    ],
    ids=["stop guard", "run contract"],
)
def test_implements_references_keep_the_rules_their_step_points_to(reference, step, phrases):
    text = " ".join((PLUGIN_ROOT / "skills" / "implement" / "references" / reference).read_text().split())
    for phrase in phrases:
        assert phrase in text, f"{reference} lost {phrase!r}"
    skill = " ".join((PLUGIN_ROOT / "skills" / "implement" / "SKILL.md").read_text().split())
    body = re.split(r" \d+\. \*\*", skill.split(f"**{step}**", 1)[1], maxsplit=1)[0]
    assert f"(references/{reference})" in body, f"implement's {step!r} step doesn't link {reference}"


def test_a_run_contract_keeps_every_irreversible_stop_and_the_prerequisite_stop_is_allowed():
    assert set(meta.IRREVERSIBLE_STOPS) < set(meta.ALLOWED_STOPS)
    assert meta.PREREQUISITE_STOP in meta.ALLOWED_STOPS
    template = (PLUGIN_ROOT / "skills" / "spec" / "references" / "parent-issue.md").read_text()
    contract = " ".join(template.split("## Run contract", 1)[1].split("\n## ", 1)[0].split())
    for heading in ("### Stops", "### Prerequisites", "### Departures"):
        assert heading in contract, f"the Run contract template lacks {heading!r}"
    stop_lines = template.split("### Stops", 1)[1].split("###", 1)[0].splitlines()
    for stop in meta.IRREVERSIBLE_STOPS:
        assert f"- {stop}" in stop_lines, f"the Run contract template doesn't give {stop!r} its own bullet"


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
                "(references/readiness.md#defaults-to-veto)",
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
    for item in (
        "names the kind of test and the seam",
        "whose Then is user-visible names an e2e test",
        "every prerequisite's check has run",
        "no open question",
    ):
        assert item in short, f"the short check lacks {item!r}"
    for item in ("rabbit holes", "no-gos", "pre-mortem"):
        assert item in full and item not in short, f"{item!r} belongs to the full check only"
    without_record = full.split("A parent without a record", 1)[1]
    for item in ("`compost:implement` runs the same check", "ruling marked `(assumed)`", "only when a gap is on"):
        assert item in without_record, f"readiness.md doesn't say implement {item!r}"


@pytest.mark.parametrize(
    ("path", "phrases"),
    [
        (
            "skills/spec/references/early-critique.md",
            [
                "Rerun and unpick may skip the critique: say the rung and why",
                "Migrate and can't undo always get it",
                "not a fork, not you, and without your reasoning",
                "a fact to re-check",
                "an area the interview must cover",
                "or a question",
            ],
        ),
        (
            "skills/spec/references/readiness.md",
            [
                "vetoes its number",
                "auth or credentials, untrusted input",
                "a destructive action, or overwriting the only copy",
            ],
        ),
        (
            "skills/verify/references/proof-ladder.md",
            [
                "Neither goes back to `compost:build`, and neither gets a fix loop",
                "delete it, or say what reaches it",
                "mark the check unverified",
                "is never `unreachable`",
                "one more attempt with a sharper brief",
                "never a third try",
                "stays unmet",
            ],
        ),
    ],
)
def test_early_critique_defaults_to_veto_and_checks_that_cannot_run_say_how(path, phrases):
    text = " ".join((PLUGIN_ROOT / path).read_text().split())
    for phrase in phrases:
        assert phrase in text, f"{path} lacks {phrase!r}"


def test_spec_and_verify_link_the_early_critique_and_the_outcomes_of_a_check_that_cannot_run():
    ask = step_text("spec", "Ask in rounds until no open decisions remain.")
    assert "rework ladder" in ask and "(references/early-critique.md)" in ask
    mapping = step_text("verify", "Map every acceptance criterion to a passing test.")
    assert "`unreachable` or `could_not_boot`" in mapping and "(references/proof-ladder.md)" in mapping
    assert "never sent to build" in mapping and "a skip written into the test stays unmet" in mapping
    report = step_text("verify", "Report the evidence.")
    assert "`unreachable` or `could_not_boot`" in report and "(references/stamp.md)" in report
    next_moves = " ".join((PLUGIN_ROOT / "skills" / "verify" / "SKILL.md").read_text().split()).split("## Next moves")[
        1
    ]
    assert (
        "`compost:build` when an AC is unmet (an `unreachable` or `could_not_boot` one goes to the user)" in next_moves
    )
    stamp = " ".join((PLUGIN_ROOT / "skills" / "verify" / "references" / "stamp.md").read_text().split())
    assert '"6/7, 1 unreachable"' in stamp and "never go back to `compost:build`" in stamp


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
def test_skills_carry_property_tests_the_flaky_test_ban_and_the_gate_round_cap(skill, step, phrases):
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


def test_spec_declares_frontend_work_and_names_an_e2e_test_for_each_user_visible_then():
    spec = " ".join((PLUGIN_ROOT / "skills" / "spec" / "SKILL.md").read_text().split())
    step7 = spec.split("**Write the spec**", 1)[1].split("**Add Gherkin feature files")[0]
    assert "rendered page or component" in step7 and "Frontend section" in step7, "spec's step 7 skips frontend work"
    template = (PLUGIN_ROOT / "skills" / "spec" / "references" / "parent-issue.md").read_text()
    assert "\n## Frontend\n" in template, "the parent template lacks a Frontend section"
    frontend = " ".join(template.split("\n## Frontend\n", 1)[1].split("\n## ", 1)[0].split())
    for phrase in ("only for frontend work", "one bullet per user-facing flow"):
        assert phrase in frontend, f"the Frontend section lacks {phrase!r}"
    record = template.split("## Readiness\n", 1)[1].split("```", 1)[0]
    assert "user-visible AC-N names an e2e test" in record, "the readiness record lacks the e2e item"
    criteria = " ".join((PLUGIN_ROOT / "skills" / "spec" / "references" / "acceptance-criteria.md").read_text().split())
    assert "A user-visible Then names its e2e test." in criteria


def test_setup_records_an_e2e_entry_naming_playwright_in_the_stacks_flavour():
    reference = (PLUGIN_ROOT / "skills" / "setup" / "references" / "testing.md").read_text()
    assert "\n## E2E\n" in reference, "testing.md's template lacks an E2E section"
    e2e = reference.split("\n## E2E\n", 1)[1].split("\n## ", 1)[0].split("````", 1)[0]
    entry = [line.split(":", 1)[0] for line in e2e.splitlines() if line.startswith("- ")]
    assert entry == ["- Tool", "- Tests", "- Start app", "- Baselines"]
    detection = " ".join(reference.split("## Template for docs/agents/testing.md", 1)[0].split())
    for flavour in ("`pytest-playwright`", "`@playwright/test`"):
        assert flavour in detection, f"setup's e2e detection doesn't recommend {flavour}"
    step6 = " ".join((PLUGIN_ROOT / "skills" / "setup" / "SKILL.md").read_text().split())
    assert "E2E entry" in step6.split("**Test convention, gates, and the run.**", 1)[1].split("**Observability.**")[0]


def test_the_first_frontend_slice_installs_a_missing_e2e_tool_and_gates_its_run():
    text = " ".join((PLUGIN_ROOT / "skills" / "slice" / "SKILL.md").read_text().split())
    step3 = text.split("**Cut tracer bullets.**", 1)[1].split("**Write each issue**")[0]
    for phrase in (
        "`## Frontend` section",
        "has no E2E entry",
        "not in the project's dependencies",
        "the first frontend issue adds it",
        "fills the E2E entry",
        "its run as a gate in `docs/agents/testing.md`",
    ):
        assert phrase in step3, f"slice's step 3 lacks {phrase!r}"


def verify_step(title):
    text = " ".join((PLUGIN_ROOT / "skills" / "verify" / "SKILL.md").read_text().split())
    assert f"**{title}**" in text, f"verify has no {title!r} step"
    return re.split(r" \d+\. \*\*| ## ", text.split(f"**{title}**", 1)[1], maxsplit=1)[0]


def verify_frontend_reference():
    reference = PLUGIN_ROOT / "skills" / "verify" / "references" / "frontend.md"
    assert reference.exists(), "verify has no frontend reference"
    return " ".join(reference.read_text().split())


@pytest.mark.parametrize(
    ("step", "phrases"),
    [
        pytest.param(
            "Map every acceptance criterion to a passing test.",
            ["a user-visible AC-N needs a passing e2e test that drives the running app", "naming the AC-N"],
            id="ac-12-user-visible-ac-needs-an-e2e-test",
        ),
        pytest.param(
            "Prove frontend work in the running app.",
            ["(references/frontend.md)", "screenshot each changed screen", "what it shows against its AC-N"],
            id="ac-13-changed-screens-are-screenshotted-and-read",
        ),
        pytest.param(
            "Prove frontend work in the running app.",
            ["pixel comparison only against baselines that already exist", "never creating one"],
            id="ac-15-ac-16-pixel-comparison-only-against-existing-baselines",
        ),
        pytest.param(
            "Prove frontend work in the running app.",
            ["undeclared frontend change", "apply this step and step 5's e2e rule", "as a ruling when unattended"],
            id="ac-17-undeclared-ui-changes-are-flagged",
        ),
        pytest.param(
            "Prove frontend work in the running app.",
            ["rerun a failing e2e test once", "list it under Risk and file an issue", "fails verify, naming the test"],
            id="ac-20-ac-21-one-rerun-sorts-flaky-from-failing",
        ),
        pytest.param(
            "Run the verify command, and any gate it leaves out, fresh.",
            ["An e2e test is the exception: it gets one rerun"],
            id="first-failure-stop-spares-the-e2e-rerun",
        ),
        pytest.param(
            "Find the gates.",
            ["E2E entry", "`## Frontend` section"],
            id="reads-the-e2e-entry-and-the-frontend-section",
        ),
        pytest.param(
            "Report the evidence.",
            ["the Screenshots list (AC-N, raw URL on the screenshots branch", "the Flaky list"],
            id="report-lists-screenshots-and-flaky-tests",
        ),
    ],
)
def test_verify_proves_frontend_work_with_e2e_tests_and_screenshots(step, phrases):
    body = verify_step(step)
    for phrase in phrases:
        assert phrase in body, f"verify's {step!r} step lacks {phrase!r}"


@pytest.mark.parametrize(
    "phrases",
    [
        pytest.param(["`Tool: none`", "every user-visible AC-N is unmet"], id="ac-12-no-e2e-tool-fails-the-ac"),
        pytest.param(
            ["`screenshots/<feature branch>`", "`<issue id>/<AC-N>-<screen>.png`", "never merged"],
            id="ac-13-screenshots-branch",
        ),
        pytest.param(["--update-snapshots=none", "git status --porcelain"], id="ac-16-no-baseline-reaches-the-branch"),
        pytest.param(["What counts as UI files", ".tsx", "templates"], id="ac-17-ui-files-are-listed"),
        pytest.param(["--last-failed", "--lf", "Flaky e2e test:"], id="ac-20-ac-21-rerun-only-the-failures"),
        pytest.param(["--retries=0", "retries=0", "the one rerun above is the only one"], id="ac-21-no-tool-retries"),
    ],
)
def test_verify_frontend_reference_says_how(phrases):
    text = verify_frontend_reference()
    for phrase in phrases:
        assert phrase in text, f"verify's frontend reference lacks {phrase!r}"


@pytest.mark.parametrize(
    ("step", "phrase"),
    [
        ("Orient.", "Read [references/run-contract.md](references/run-contract.md) now"),
        ("Orient.", "before anything that can stop the run, print the contract's Stops block"),
        ("Close out.", "load `compost:finish` now"),
        ("Close out.", "posts the PR body (on the issue file for a local tracker)"),
        (
            "Set up the feature branch.",
            "Committing, pushing this branch, and the draft PR need no one's OK; merging the PR does",
        ),
    ],
    ids=[
        "reads-the-contract",
        "prints-before-stopping",
        "loads-finish",
        "finish-posts-the-body",
        "commit-and-push-need-no-ok",
    ],
)
def test_implement_reads_the_contract_first_and_ends_by_loading_finish(step, phrase):
    text = " ".join((PLUGIN_ROOT / "skills" / "implement" / "SKILL.md").read_text().split())
    body = re.split(r" \d+\. \*\*|For a run that outlives", text.split(f"**{step}**", 1)[1], maxsplit=1)[0]
    assert phrase in body, f"implement's {step!r} step lacks {phrase!r}"


def test_finish_puts_verifys_screenshots_under_validation_and_flaky_tests_under_risk():
    body = (PLUGIN_ROOT / "skills" / "finish" / "references" / "pr-body.md").read_text()
    validation = " ".join(body.split("## Validation", 1)[1].split("## Risk", 1)[0].split())
    risk = " ".join(body.split("## Risk", 1)[1].split("```", 1)[0].split())
    assert "Screenshots:" in validation and "raw URL" in validation and "AC-N" in validation
    assert "Flaky:" in risk and "filed issue" in risk
    step5 = " ".join((PLUGIN_ROOT / "skills" / "finish" / "SKILL.md").read_text().split())
    step5 = step5.split("**Open or update the pull request.**", 1)[1].split("Local green proves the branch")[0]
    assert "Screenshots list" in step5 and "Flaky list" in step5, "finish step 5 doesn't carry verify's lists"


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
