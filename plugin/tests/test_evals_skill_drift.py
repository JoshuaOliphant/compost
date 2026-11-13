# ABOUTME: Live evals for the skill-drift mod's Jev questions on labeled real skill-turns in compost-evals (COMPOST_EVALS).
# ABOUTME: Asks the questions hooks/skill-drift.ts asks for a stepped skill, prints a threshold sweep, and asserts the floors measured.
import asyncio
import json

import pytest
from conftest import TENTHS, evals_dir, rates, skill_drift_judgments, skill_drift_step_questions, sweep
from jevtools import core
from typesafe_sdk import Noul

pytestmark = pytest.mark.jev


def scored_build_turns() -> tuple[list[dict], list[dict[str, float]]]:
    """compost-evals' skill-drift-steps.json, each turn asked in one request as the hook asks it:
    `missing_guidance` plus one question per step of the build skill the turns are judged against."""
    root = evals_dir()
    cases = json.loads((root / "skill-drift-steps.json").read_text())

    async def judge(jev: core.Jev, case: dict) -> dict[str, float]:
        text = (root / case["skill"]["file"]).read_text()
        body = text.split("---", 2)[2].lstrip("\n") if text.startswith("---") else text
        skill = f"Base directory for this skill: /plugin/skills/build\n\n{body}"
        questions = {name: Noul(instructions=q) for name, q in skill_drift_step_questions(skill).items()}
        answer = await jev.ask(
            "skill-drift", {"skill": {"name": case["skill"]["name"], "text": skill}, "turn": case["turn"]}, questions
        )
        steps = [answer.noul(name) for name in questions if name.startswith("step ")]
        return {"deviated": max(steps), "missing_guidance": answer.noul("missing_guidance")}

    async def run() -> list[dict[str, float]]:
        async with core.open_client() as client:
            jev = core.Jev(client, core.Cache())
            return await asyncio.gather(*(judge(jev, case) for case in cases))

    return cases, asyncio.run(run())


def test_a_stepped_skill_flags_only_the_turns_labeled_for_each_question():
    """23 hand-labeled compost:build turns, 13 Nov 2026.

    deviated: 8 turns did every step and 15 skipped one or more. The whole-skill question scored all 23 between
    0.75 and 0.95. The likeliest skipped step keeps clean turns at 0.76 or under and puts 9 to 11 of the 15
    drifting ones at 0.8 or over (Jev varies run to run). 0.75 was first chosen on the 17 `calibration` turns,
    but over repeated runs one clean `held-out` turn crossed it, so the threshold is 0.8.

    missing_guidance: 5 turns hit something build gave no instruction for (Jev find-test exiting 2, or
    duplicate-test not seeing the doctest build preferred). The old question scored 16 of the other 18 over its
    0.6 threshold. Over three runs the one asked now kept the other 18 at 0.46 or under and the 5 at 0.48 to 0.81,
    so a labeled turn can dip under 0.5 and recall has a floor rather than 1.0. Both gaps are Jev-tool gaps; no
    other kind is labeled yet.
    """
    thresholds = skill_drift_judgments()["thresholds"]
    cases, scores = scored_build_turns()
    measured = {}
    for name in ("deviated", "missing_guidance"):
        rows = [(score[name], case["expected"][name]) for score, case in zip(scores, cases, strict=True)]
        held_out = [row for row, case in zip(rows, cases, strict=True) if case["split"] == "held-out"]
        print(f"\n{name}: {sum(label for _, label in rows)} positives of {len(rows)}")
        sweep(rows, TENTHS)
        measured[name] = rates(rows, thresholds[name])
        accuracy, precision, recall = measured[name]
        print(f"{name} at {thresholds[name]}: accuracy {accuracy:.2f} precision {precision:.2f} recall {recall:.2f}")
        right = sum((score >= thresholds[name]) == label for score, label in held_out)
        print(f"held out: {right} of {len(held_out)} right")
    assert measured["deviated"][1] == 1.0 and measured["deviated"][2] >= 0.5
    assert measured["missing_guidance"][1] == 1.0 and measured["missing_guidance"][2] >= 0.8
