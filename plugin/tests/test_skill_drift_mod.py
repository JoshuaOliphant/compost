# ABOUTME: Runs compost's hooks module engine tests (skill-drift, architecture-review) and validation from pytest, so CI's one test command covers them.
# ABOUTME: Also checks the judgments file stays plain JSON, every skill fits the hook's SKILL_CHARS, and its server, model and key constants match jevtools.core.
import os
import re
import shutil
import subprocess

import pytest
from conftest import PLUGIN_ROOT, skill_drift_judgments
from jevtools import core

needs_claude = pytest.mark.skipif(
    shutil.which("claude") is None and not os.environ.get("CI"),
    reason="the claude CLI runs the hooks module's tests; CI installs it, so there a missing CLI fails instead",
)


def test_judgments_are_plain_json_with_a_threshold_per_question():
    judgments = skill_drift_judgments()
    asked = {**judgments["turn"], **judgments["next_message"]}
    assert set(asked) == set(judgments["thresholds"]) == {"deviated", "missing_guidance", "corrected"}


def test_the_hook_targets_the_same_server_model_and_placeholder_key_as_core():
    """The hook cannot import core.py, so its copy of the Ollaya rules is held equal here."""
    source = (PLUGIN_ROOT / "hooks" / "skill-drift.ts").read_text()
    constants = dict(re.findall(r"^const (\w+) = '([^']*)'$", source, re.MULTILINE))
    assert constants["TYPESAFE_URL"] == core.TYPESAFE_URL
    assert constants["DEFAULT_MODEL"] == core.DEFAULT_MODEL
    assert constants["LOCAL_KEY"] == core.LOCAL_KEY
    for variable in (core.BASE_URL_VAR, core.MODEL_VAR, core.ENV_VAR):
        assert f"$.env.get('{variable}')" in source


def test_every_compost_skill_reaches_jev_whole():
    """A skill cut short is judged on part of its steps: a skipped step 11 is missing, not a deviation."""
    source = (PLUGIN_ROOT / "hooks" / "skill-drift.ts").read_text()
    limit = int(re.search(r"^const SKILL_CHARS = (\d+)$", source, re.MULTILINE).group(1))
    # What skill.prompt hands the hook: a "Base directory for this skill: <path>" line, then the body.
    header = (
        len("Base directory for this skill: ")
        + len("/Users/someone/.claude/plugins/cache/compost/compost/9.99.0/skills/")
        + 40
    )
    longest = max(
        (len(path.read_text()) + header, path.parent.name) for path in (PLUGIN_ROOT / "skills").glob("*/SKILL.md")
    )
    assert longest[0] <= limit, f"{longest[1]} is {longest[0]} chars with its header; SKILL_CHARS is {limit}"


@needs_claude
@pytest.mark.parametrize("command", ["validate", "test"])
def test_the_hooks_module_validates_and_passes_its_engine_tests(command):
    result = subprocess.run(
        ["claude", "plugin", command, str(PLUGIN_ROOT)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr
